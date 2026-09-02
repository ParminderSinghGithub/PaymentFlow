"""Interactive recovery service coordinating the live CS01 demonstration.

Reuses existing RecoveryOrchestrator, RecoveryTriageService, PolicyGuardrailEngine,
LLMAgentDecisionProvider, RazorpayAdapter, and WebhookService attribution logic.
"""

import logging
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings, get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import ActorType, CaseState
from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator
from paymentflow.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

INTERACTIVE_CASE_ID = "case_interactive_cs01"
INTERACTIVE_FAILED_PAYMENT_ID = "pay_interactive_cs01_failed"
INTERACTIVE_ORDER_ID = "order_interactive_cs01"
INTERACTIVE_CUSTOMER_ID = "cust_interactive_cs01"
DEFAULT_AMOUNT_PAISE = 250000  # ₹2,500.00


class InteractiveRecoveryService:
    """Service managing the live interactive demonstration without modifying canonical cases."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession] | None = None,
        razorpay_adapter: RazorpayAdapter | None = None,
        orchestrator: RecoveryOrchestrator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.sessionmaker = sessionmaker or get_sessionmaker()
        self.settings = settings or get_settings()
        self.adapter = razorpay_adapter or RazorpayAdapter(settings=self.settings)
        self.orchestrator = orchestrator or RecoveryOrchestrator(
            sessionmaker=self.sessionmaker,
            razorpay_adapter=self.adapter,
            settings=self.settings,
        )

    async def launch_scenario(
        self,
        scenario_id: str = "CS01",
        amount_paise: int = DEFAULT_AMOUNT_PAISE,
        customer_email: str = "demo.buyer@example.com",
        customer_contact: str = "+919876543210",
        reset_previous: bool = True,
    ) -> dict[str, Any]:
        """Initialize the interactive scenario and execute the existing recovery pipeline."""
        if amount_paise <= 0:
            raise ValueError("amount_paise must be a positive integer in paise.")

        logger.info(
            f"InteractiveRecoveryService: Launching scenario {scenario_id} "
            f"(amount={amount_paise} paise)..."
        )

        async with self.sessionmaker() as session:
            # 1. Isolated reset of previous interactive run if requested
            if reset_previous:
                await session.execute(
                    delete(AuditEventModel).where(AuditEventModel.case_id == INTERACTIVE_CASE_ID)
                )
                await session.execute(
                    delete(RecoveryCaseModel).where(
                        RecoveryCaseModel.case_id == INTERACTIVE_CASE_ID
                    )
                )
                await session.flush()

            # 2. Persist initial failure event in recovery_cases
            now = utc_now()
            failed_pay_id = f"pay_interactive_cs01_{int(now.timestamp())}"
            case = RecoveryCaseModel(
                case_id=INTERACTIVE_CASE_ID,
                failed_payment_id=failed_pay_id,
                order_id=INTERACTIVE_ORDER_ID,
                customer_id=INTERACTIVE_CUSTOMER_ID,
                amount=amount_paise,
                currency="INR",
                payment_method="card",
                failure_category="C1",
                failure_code="BAD_REQUEST_ERROR",
                failure_description="Customer dropped off during OTP entry.",
                failure_context={
                    "scenario": "OTP Timeout / Dropoff on Checkout (Interactive Live)",
                    "email": customer_email,
                    "contact": customer_contact,
                },
                eligibility_status="PENDING",
                payment_link_reference_id=f"FP-{failed_pay_id}",
                state=CaseState.FAILED_INGESTED.value,
                created_at=now,
                updated_at=now,
            )
            session.add(case)

            # Audit event for ingestion
            session.add(
                AuditEventModel(
                    case_id=INTERACTIVE_CASE_ID,
                    event_type="WEBHOOK_INGESTED",
                    actor=ActorType.SYSTEM.value,
                    decision="CASE_CREATED",
                    action="INGEST",
                    outcome="SUCCESS",
                    timestamp=now,
                    details={
                        "payment_id": failed_pay_id,
                        "amount_paise": amount_paise,
                        "currency": "INR",
                        "interactive": True,
                    },
                )
            )
            await session.commit()

        # 3. Execute existing recovery pipeline through RecoveryOrchestrator
        orch_res = await self.orchestrator.orchestrate_recovery(
            case_id=INTERACTIVE_CASE_ID,
            fetch_from_gateway=False,
        )

        # 4. Retrieve updated case details
        async with self.sessionmaker() as session:
            updated_case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
            audit_events = await self.orchestrator.get_case_audit_trail(INTERACTIVE_CASE_ID)

        if not updated_case:
            raise RuntimeError(f"Failed to retrieve case {INTERACTIVE_CASE_ID} after launch.")

        return {
            "status": "success" if orch_res.get("success") else "error",
            "case_id": INTERACTIVE_CASE_ID,
            "scenario_id": scenario_id,
            "state": updated_case.state,
            "failure_category": updated_case.failure_category,
            "amount_paise": updated_case.amount,
            "amount_inr": updated_case.amount / 100.0,
            "ai_policy": updated_case.ai_policy_id,
            "validated_policy": updated_case.validated_policy_id,
            "action_status": updated_case.action_status,
            "payment_link_id": updated_case.payment_link_id,
            "payment_link_url": updated_case.payment_link_short_url,
            "audit_trail_count": len(audit_events),
            "orchestrator_result": orch_res,
        }

    async def get_status(self) -> dict[str, Any]:
        """Retrieve persisted state, payment link status, and audit trail of interactive case."""
        async with self.sessionmaker() as session:
            case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
            if not case:
                return {
                    "case_id": INTERACTIVE_CASE_ID,
                    "exists": False,
                    "state": None,
                    "message": "Interactive case not found. Launch a scenario first.",
                }

            audit_events = await self.orchestrator.get_case_audit_trail(INTERACTIVE_CASE_ID)

            return {
                "case_id": case.case_id,
                "exists": True,
                "state": case.state,
                "failure_category": case.failure_category,
                "failure_code": case.failure_code,
                "failure_description": case.failure_description,
                "amount_paise": case.amount,
                "amount_inr": case.amount / 100.0,
                "currency": case.currency,
                "payment_link_id": case.payment_link_id,
                "payment_link_url": case.payment_link_short_url,
                "payment_link_status": case.payment_link_status,
                "recovered_payment_id": case.recovered_payment_id,
                "recovered_amount_paise": case.recovered_amount,
                "recovered_amount_inr": (
                    (case.recovered_amount / 100.0) if case.recovered_amount else 0.0
                ),
                "ai_policy": case.ai_policy_id,
                "ai_explanation": case.ai_explanation,
                "validated_policy": case.validated_policy_id,
                "scheduled_at": case.scheduled_at.isoformat() if case.scheduled_at else None,
                "audit_trail": audit_events,
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            }

    async def verify_payment(self) -> dict[str, Any]:
        """Verify payment against Razorpay API and reuse WebhookService attribution."""
        async with self.sessionmaker() as session:
            case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
            if not case:
                return {
                    "case_id": INTERACTIVE_CASE_ID,
                    "verified": False,
                    "error": "Interactive case not found.",
                }

            # If already recovered, return idempotent success
            if case.state == CaseState.RECOVERED.value:
                return {
                    "case_id": INTERACTIVE_CASE_ID,
                    "verified": True,
                    "already_recovered": True,
                    "state": case.state,
                    "payment_status": "captured",
                    "recovered_payment_id": case.recovered_payment_id,
                    "recovered_amount_inr": (
                        (case.recovered_amount / 100.0) if case.recovered_amount else 0.0
                    ),
                    "message": "Recovery case already verified and attributed.",
                }

            if not case.payment_link_id:
                return {
                    "case_id": INTERACTIVE_CASE_ID,
                    "verified": False,
                    "state": case.state,
                    "error": "No payment link generated for this case.",
                }

            plink_id = case.payment_link_id

        # Query Razorpay API for live payment link details
        try:
            plink_data = await self.adapter.get_payment_link(plink_id)
        except Exception as exc:
            logger.error(f"Failed to fetch payment link {plink_id} from Razorpay: {exc}")
            return {
                "case_id": INTERACTIVE_CASE_ID,
                "verified": False,
                "state": case.state,
                "error": f"Razorpay API error: {exc}",
            }

        plink_status = plink_data.get("status")
        payments_list = plink_data.get("payments") or []

        # If payment link is not yet paid
        if plink_status != "paid" or not payments_list:
            return {
                "case_id": INTERACTIVE_CASE_ID,
                "verified": False,
                "state": case.state,
                "payment_link_id": plink_id,
                "payment_link_status": plink_status,
                "message": (
                    "Payment link is currently unpaid. Complete the payment in Razorpay checkout."
                ),
            }

        # Extract latest payment entity from link
        latest_payment = payments_list[0] if isinstance(payments_list[0], dict) else {}
        payment_id = latest_payment.get("payment_id") or latest_payment.get("id")

        if not payment_id:
            return {
                "case_id": INTERACTIVE_CASE_ID,
                "verified": False,
                "state": case.state,
                "error": "Payment link marked paid but payment ID is missing in Razorpay response.",
            }

        # Construct authoritative outcome payload and invoke existing WebhookService attribution
        payload = {
            "entity": "event",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": plink_data,
                },
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "payment_link_id": plink_id,
                        "amount": case.amount,
                        "currency": case.currency,
                        "status": "captured",
                        "notes": {
                            "case_id": INTERACTIVE_CASE_ID,
                            "failed_payment_id": case.failed_payment_id,
                        },
                    },
                },
            },
        }

        async with self.sessionmaker() as session:
            webhook_service = WebhookService(
                db_session=session,
                razorpay_adapter=self.adapter,
            )
            raw_body = b'{"event":"payment_link.paid","interactive":true}'
            proc_res = await webhook_service.process_webhook(
                raw_body=raw_body,
                payload=payload,
                signature_verified=True,
            )

        # Query final case state
        async with self.sessionmaker() as session:
            final_case = await session.get(RecoveryCaseModel, INTERACTIVE_CASE_ID)
            audit_events = await self.orchestrator.get_case_audit_trail(INTERACTIVE_CASE_ID)

        if not final_case:
            raise RuntimeError(f"Case {INTERACTIVE_CASE_ID} not found after verification.")

        is_recovered = final_case.state == CaseState.RECOVERED.value
        rec_amt = final_case.recovered_amount or 0
        return {
            "case_id": INTERACTIVE_CASE_ID,
            "verified": is_recovered,
            "state": final_case.state,
            "payment_status": "captured" if is_recovered else "unresolved",
            "recovered_payment_id": final_case.recovered_payment_id,
            "recovered_amount_inr": rec_amt / 100.0,
            "payment_link_id": plink_id,
            "audit_trail_count": len(audit_events),
            "webhook_result": proc_res.model_dump(),
            "message": (
                f"Payment verified as captured. ₹{rec_amt / 100.0:.2f} successfully attributed."
                if is_recovered
                else proc_res.message
            ),
        }

    async def reset(self) -> dict[str, Any]:
        """Safely clean up only the interactive demonstration case and its audit events."""
        async with self.sessionmaker() as session:
            await session.execute(
                delete(AuditEventModel).where(AuditEventModel.case_id == INTERACTIVE_CASE_ID)
            )
            await session.execute(
                delete(RecoveryCaseModel).where(RecoveryCaseModel.case_id == INTERACTIVE_CASE_ID)
            )
            await session.commit()

        logger.info("InteractiveRecoveryService: Interactive demonstration case reset.")
        return {
            "status": "success",
            "message": "Interactive demonstration case cleaned up cleanly.",
        }
