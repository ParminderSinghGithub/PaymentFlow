"""Layer 4A Recovery Executor: Deterministic pre-write validation
and idempotent Payment Link execution.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings, get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import (
    CaseState,
    PolicyDecision,
    RecoveryPolicy,
)
from paymentflow.domain.exceptions import (
    RazorpayAdapterError,
    RazorpayAPIError,
    RazorpayAuthError,
    RazorpayRateLimitError,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails, RecoveryExecutionResult
from paymentflow.domain.policy_engine import PolicyGuardrailEngine

logger = logging.getLogger(__name__)


class RecoveryExecutor:
    """Executes approved recovery actions by creating Razorpay Payment Links with strict safety."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession] | None = None,
        razorpay_adapter: RazorpayAdapter | None = None,
        settings: Settings | None = None,
    ):
        self.sessionmaker = sessionmaker or get_sessionmaker()
        self.settings = settings or get_settings()
        self.razorpay_adapter = razorpay_adapter or RazorpayAdapter(settings=self.settings)

    async def execute(self, case_id: str) -> RecoveryExecutionResult:
        """Execute approved recovery action for the given case ID with safety."""
        async with self.sessionmaker() as session:
            # 1. Pessimistic Row Lock (Concurrency protection)
            stmt = (
                select(RecoveryCaseModel)
                .where(RecoveryCaseModel.case_id == case_id)
                .with_for_update()
            )
            res = await session.execute(stmt)
            case = res.scalar_one_or_none()

            if not case:
                logger.warning(f"RecoveryExecutor: Case '{case_id}' not found.")
                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision="NOT_FOUND",
                    state=CaseState.ERROR_TERMINAL,
                    message=f"Case '{case_id}' not found.",
                )

            # 2. Idempotency Check: Already has a created Payment Link
            if case.payment_link_id:
                logger.info(
                    f"RecoveryExecutor: Case '{case_id}' already has Payment Link "
                    f"'{case.payment_link_id}'. Returning existing result."
                )
                return RecoveryExecutionResult(
                    success=True,
                    case_id=case_id,
                    decision="ALREADY_EXECUTED",
                    state=CaseState(case.state),
                    payment_link_id=case.payment_link_id,
                    payment_link_short_url=case.payment_link_short_url,
                    message="Payment Link already created.",
                )

            # 3. State Check: Must be in ACTION_APPROVED
            if case.state != CaseState.ACTION_APPROVED.value:
                logger.warning(
                    f"RecoveryExecutor: Case '{case_id}' is in state '{case.state}', "
                    "expected ACTION_APPROVED."
                )
                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision="INVALID_STATE",
                    state=CaseState(case.state),
                    message=f"Case state is '{case.state}', expected ACTION_APPROVED.",
                )

            # 4. Policy Check: Must be P_CREATE_LINK_IMMEDIATE
            if case.validated_policy_id != RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value:
                logger.info(
                    f"RecoveryExecutor: Case '{case_id}' policy is '{case.validated_policy_id}', "
                    "not eligible for immediate link execution."
                )
                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision="NON_EXECUTABLE_POLICY",
                    state=CaseState(case.state),
                    message=(
                        f"Policy '{case.validated_policy_id}' is not executable for "
                        "immediate link creation."
                    ),
                )

            # 5. Final Pre-Write Defense-in-Depth Validation via PolicyGuardrailEngine
            failure_ctx = case.failure_context or {}
            payment_context = PaymentContext(
                payment_id=case.failed_payment_id,
                order_id=case.order_id,
                customer_id=case.customer_id,
                amount=case.amount,
                currency=case.currency,
                status="failed",
                method=case.payment_method,
                failure=PaymentFailureDetails(
                    code=case.failure_code,
                    description=case.failure_description,
                    source=failure_ctx.get("error_source"),
                    step=failure_ctx.get("error_step"),
                    reason=failure_ctx.get("error_reason"),
                ),
            )

            validation = PolicyGuardrailEngine.validate(
                context=payment_context,
                requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
                proposed_amount=case.amount,
                proposed_currency=case.currency,
            )

            if validation.decision != PolicyDecision.APPROVE:
                logger.warning(
                    f"RecoveryExecutor: Pre-write validation failed for '{case_id}': "
                    f"decision={validation.decision.value}, reason={validation.reason_code}"
                )
                if validation.decision == PolicyDecision.ESCALATE:
                    case.state = CaseState.ESCALATED.value
                else:
                    case.state = CaseState.TERMINAL_NO_ACTION.value

                audit = AuditEventModel(
                    case_id=case_id,
                    event_type="PRE_WRITE_VALIDATION_REJECTED",
                    actor="policy_guardrail_engine",
                    decision=validation.decision.value,
                    policy=validation.effective_policy.value,
                    guardrail_result=validation.model_dump(),
                    timestamp=utc_now(),
                )
                session.add(audit)
                await session.commit()

                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision=validation.decision.value,
                    state=CaseState(case.state),
                    reason_code=validation.reason_code,
                    message="Pre-write guardrail validation rejected execution.",
                    details=validation.model_dump(),
                )

            # 6. Audit Pre-Write Execution Request
            session.add(
                AuditEventModel(
                    case_id=case_id,
                    event_type="ACTION_EXECUTION_REQUESTED",
                    actor="recovery_executor",
                    decision="EXECUTE",
                    policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
                    action="create_payment_link",
                    timestamp=utc_now(),
                    details={
                        "amount_paise": case.amount,
                        "currency": case.currency,
                        "reference_id": case.case_id,
                    },
                )
            )

            # 7. Call Razorpay API to Create Payment Link
            try:
                link_response = await self.razorpay_adapter.create_payment_link(
                    amount=case.amount,
                    currency=case.currency,
                    description=f"Recovery link for failed payment {case.failed_payment_id}",
                    reference_id=case.case_id,
                    notes={
                        "case_id": case.case_id,
                        "failed_payment_id": case.failed_payment_id,
                    },
                )

                link_id = link_response.get("id")
                short_url = link_response.get("short_url")
                status = link_response.get("status", "created")

                if not link_id or not short_url:
                    raise RazorpayAPIError(
                        status_code=502,
                        message="Razorpay returned malformed link creation response.",
                    )

                # 8. Persist Payment Link Identity & Transition State
                case.payment_link_id = link_id
                case.payment_link_reference_id = case.case_id
                case.payment_link_short_url = short_url
                case.payment_link_status = status
                case.state = CaseState.ACTION_EXECUTED.value
                case.action_status = "LINK_CREATED"
                case.updated_at = utc_now()

                session.add(
                    AuditEventModel(
                        case_id=case_id,
                        event_type="RAZORPAY_PAYMENT_LINK_CREATED",
                        actor="razorpay_adapter",
                        decision="SUCCESS",
                        policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
                        action="create_payment_link",
                        outcome="LINK_CREATED",
                        timestamp=utc_now(),
                        details={
                            "payment_link_id": link_id,
                            "short_url": short_url,
                            "amount_paise": case.amount,
                            "currency": case.currency,
                        },
                    )
                )
                await session.commit()

                logger.info(
                    f"RecoveryExecutor: Payment Link created successfully for case '{case_id}': "
                    f"link_id={link_id}, url={short_url}"
                )

                return RecoveryExecutionResult(
                    success=True,
                    case_id=case_id,
                    decision="EXECUTED",
                    state=CaseState.ACTION_EXECUTED,
                    payment_link_id=link_id,
                    payment_link_short_url=short_url,
                    message="Payment Link created and persisted successfully.",
                    details={"raw_response": link_response},
                )

            except (RazorpayAPIError, RazorpayAuthError, RazorpayRateLimitError) as exc:
                # 9. Razorpay API Rejection / Auth / Rate Limit
                logger.error(
                    f"RecoveryExecutor: Razorpay API rejected link creation for '{case_id}': {exc}"
                )

                case.state = CaseState.ERROR_TERMINAL.value
                case.updated_at = utc_now()

                session.add(
                    AuditEventModel(
                        case_id=case_id,
                        event_type="RAZORPAY_PAYMENT_LINK_FAILED",
                        actor="razorpay_adapter",
                        decision="FAILED",
                        outcome="API_REJECTED",
                        timestamp=utc_now(),
                        details={"error": str(exc)},
                    )
                )
                await session.commit()

                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision="API_ERROR",
                    state=CaseState.ERROR_TERMINAL,
                    reason_code="RAZORPAY_API_ERROR",
                    message=str(exc),
                )

            except RazorpayAdapterError as exc:
                # 10. Critical Failure Scenario: Timeout / Unknown External Outcome
                err_msg = f"Timeout or network failure during Razorpay Payment Link creation: {exc}"
                logger.error(
                    f"RecoveryExecutor: Critical failure for case '{case_id}': {err_msg}. "
                    "Halting execution without blind retry."
                )

                case.state = CaseState.ERROR_TERMINAL.value
                case.updated_at = utc_now()

                session.add(
                    AuditEventModel(
                        case_id=case_id,
                        event_type="RAZORPAY_PAYMENT_LINK_UNKNOWN_OUTCOME",
                        actor="razorpay_adapter",
                        decision="HALT",
                        outcome="UNKNOWN_EXTERNAL_OUTCOME",
                        timestamp=utc_now(),
                        details={"error": err_msg, "requires_reconciliation": True},
                    )
                )
                await session.commit()

                return RecoveryExecutionResult(
                    success=False,
                    case_id=case_id,
                    decision="UNKNOWN_EXTERNAL_OUTCOME",
                    state=CaseState.ERROR_TERMINAL,
                    reason_code="EXTERNAL_TIMEOUT_RECONCILIATION_REQUIRED",
                    message=err_msg,
                )
