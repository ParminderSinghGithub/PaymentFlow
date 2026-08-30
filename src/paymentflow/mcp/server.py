"""Model Context Protocol (MCP) server for PaymentFlow Recovery Agent."""

import logging
from datetime import timedelta
from typing import Any

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import (
    ActorType,
    CaseState,
    FailureCategory,
    PolicyDecision,
    RecoveryPolicy,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails
from paymentflow.domain.policy_engine import PolicyGuardrailEngine
from paymentflow.domain.state_machine import RecoveryStateMachine

logger = logging.getLogger(__name__)

# Initialize MCP Server (MCP 2.x standard)
mcp_server = MCPServer(
    name="paymentflow-recovery",
    instructions="Model Context Protocol interface for Razorpay PaymentFlow recovery triage.",
)


@mcp_server.tool()
async def get_allowed_recovery_policies() -> list[dict[str, str]]:
    """Return the four frozen allowed recovery policies and their operational constraints."""
    return [
        {
            "policy_id": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
            "description": "Create and deliver an immediate Razorpay Payment Link to customer.",
            "applicable_to": "Eligible transient customer failures (C1) and standard recoveries.",
        },
        {
            "policy_id": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
            "description": "Schedule a delayed Payment Link to allow gateway/bank recovery.",
            "applicable_to": "Soft infrastructure / network timeout failures (C2).",
        },
        {
            "policy_id": RecoveryPolicy.P_ESCALATE_ONLY.value,
            "description": "Escalate case to merchant operations without customer notification.",
            "applicable_to": "High-value payments (>₹50k), business/risk failures (C4).",
        },
        {
            "policy_id": RecoveryPolicy.P_NO_ACTION.value,
            "description": "Take no recovery action; close workflow.",
            "applicable_to": "Technical errors (C5), customer cooldown limit, duplicate cases.",
        },
    ]


@mcp_server.tool()
async def get_payment_context(payment_id: str) -> dict[str, Any]:
    """Retrieve sanitized payment details and failure diagnostics for a given payment ID."""
    if not payment_id:
        return {"error": "payment_id must not be empty."}

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        res = await session.execute(
            select(RecoveryCaseModel).where(RecoveryCaseModel.failed_payment_id == payment_id)
        )
        case = res.scalars().first()
        if not case:
            return {"error": f"Payment '{payment_id}' not found in recovery records."}

        return {
            "payment_id": case.failed_payment_id,
            "amount_paise": case.amount,
            "amount_inr": f"₹{case.amount / 100:.2f}",
            "currency": case.currency,
            "payment_method": case.payment_method,
            "failure_category": case.failure_category,
            "failure_code": case.failure_code,
            "failure_description": case.failure_description,
            "failure_context": case.failure_context or {},
            "order_id": case.order_id,
            "customer_id": case.customer_id,
        }


@mcp_server.tool()
async def get_recovery_case(case_id: str) -> dict[str, Any]:
    """Retrieve structured recovery case information for agent reasoning."""
    if not case_id:
        return {"error": "case_id must not be empty."}

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, case_id)
        if not case:
            return {"error": f"Recovery case '{case_id}' not found."}

        return {
            "case_id": case.case_id,
            "failed_payment_id": case.failed_payment_id,
            "amount": case.amount,
            "currency": case.currency,
            "state": case.state,
            "failure_category": case.failure_category,
            "eligibility_status": case.eligibility_status,
            "eligibility_reason": case.eligibility_reason,
            "classification_evidence": case.classification_evidence or {},
            "created_at": case.created_at.isoformat() if case.created_at else None,
        }


@mcp_server.tool()
async def get_recovery_status(case_id: str) -> dict[str, Any]:
    """Retrieve the current state machine status and workflow flags for a case."""
    if not case_id:
        return {"error": "case_id must not be empty."}

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, case_id)
        if not case:
            return {"error": f"Recovery case '{case_id}' not found."}

        state_enum = CaseState(case.state)
        is_terminal = RecoveryStateMachine.is_terminal(state_enum)

        return {
            "case_id": case.case_id,
            "state": case.state,
            "is_terminal": is_terminal,
            "is_eligible": case.eligibility_status == "ELIGIBLE",
            "has_recovery_link": bool(case.payment_link_id),
            "validated_policy_id": case.validated_policy_id,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        }


@mcp_server.tool()
async def request_recovery_action(
    case_id: str,
    proposed_policy: str,
    proposed_amount: int | None = None,
    proposed_currency: str | None = None,
    explanation: str = "",
) -> dict[str, Any]:
    """Request authorization for a recovery action through deterministic guardrails."""
    if not case_id:
        return {"authorized": False, "error": "case_id is required."}

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, case_id)
        if not case:
            return {"authorized": False, "error": f"Case '{case_id}' not found."}

        current_state = CaseState(case.state)
        if RecoveryStateMachine.is_terminal(current_state):
            return {
                "authorized": False,
                "error": f"Case '{case_id}' is in terminal state '{current_state.value}'.",
            }

        # Build verified context
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
                source=(case.failure_context or {}).get("error_source"),
                step=(case.failure_context or {}).get("error_step"),
                reason=(case.failure_context or {}).get("error_reason"),
            ),
            created_at=int(case.created_at.timestamp()) if case.created_at else None,
        )

        category_enum = FailureCategory(case.failure_category) if case.failure_category else None

        # Execute deterministic policy & guardrail validation
        validation_res = PolicyGuardrailEngine.validate(
            context=payment_context,
            requested_policy=proposed_policy,
            failure_category=category_enum,
            has_existing_recovery_link=bool(case.payment_link_id),
            proposed_amount=proposed_amount,
            proposed_currency=proposed_currency,
            current_time_utc=utc_now(),
        )

        # Update case attributes
        case.ai_policy_id = (
            RecoveryPolicy(proposed_policy)
            if proposed_policy in RecoveryPolicy._value2member_map_
            else None
        )
        case.ai_explanation = explanation[:1000] if explanation else None
        case.validated_policy_id = validation_res.effective_policy.value
        case.updated_at = utc_now()

        # Transition state deterministically
        if validation_res.decision == PolicyDecision.APPROVE:
            if validation_res.effective_policy == RecoveryPolicy.P_NO_ACTION:
                case.state = CaseState.TERMINAL_NO_ACTION.value
                case.action_status = "NO_ACTION"
            elif validation_res.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY:
                case.state = CaseState.ESCALATED.value
                case.action_status = "ESCALATED"
            else:
                if current_state in (CaseState.ELIGIBILITY_CHECKED, CaseState.CONTEXT_RETRIEVED):
                    case.state = CaseState.ACTION_APPROVED.value
                if validation_res.effective_policy == RecoveryPolicy.P_CREATE_LINK_DELAYED:
                    case.action_status = "SCHEDULED_DELAYED"
                    case.scheduled_at = utc_now() + timedelta(minutes=15)
                elif validation_res.effective_policy == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE:
                    case.action_status = "APPROVED_IMMEDIATE"
        elif validation_res.decision == PolicyDecision.ESCALATE:
            case.state = CaseState.ESCALATED.value
            case.action_status = "ESCALATED"
        else:
            # DOWNGRADE or REJECT to no action
            if validation_res.effective_policy == RecoveryPolicy.P_NO_ACTION:
                case.state = CaseState.TERMINAL_NO_ACTION.value
                case.action_status = "NO_ACTION"
            elif validation_res.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY:
                case.state = CaseState.ESCALATED.value
                case.action_status = "ESCALATED"

        # Record immutable audit trail
        audit_event = AuditEventModel(
            case_id=case_id,
            event_type="POLICY_GUARDRAIL_VALIDATED",
            actor=ActorType.POLICY_ENGINE.value,
            decision=validation_res.decision.value,
            policy=validation_res.effective_policy.value,
            action="VALIDATE_RECOVERY_PROPOSAL",
            outcome="SUCCESS" if validation_res.is_approved else "REJECTED_OR_OVERRIDDEN",
            guardrail_result=validation_res.model_dump(),
            correlation_id=case.failed_payment_id,
            timestamp=utc_now(),
            details={
                "requested_policy": proposed_policy,
                "effective_policy": validation_res.effective_policy.value,
                "reason_code": validation_res.reason_code,
                "explanation": explanation,
            },
        )
        session.add(audit_event)
        await session.commit()

        logger.info(
            f"MCP action for {case_id}: decision={validation_res.decision.value}, "
            f"effective={validation_res.effective_policy.value}, state={case.state}."
        )

        return {
            "authorized": validation_res.is_approved,
            "decision": validation_res.decision.value,
            "requested_policy": proposed_policy,
            "effective_policy": validation_res.effective_policy.value,
            "reason_code": validation_res.reason_code,
            "case_state": case.state,
        }
