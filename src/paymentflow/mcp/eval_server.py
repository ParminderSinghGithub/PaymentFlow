"""In-memory Model Context Protocol (MCP) server for offline evaluation and testing."""

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from paymentflow.domain.enums import (
    RecoveryPolicy,
)
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails
from paymentflow.domain.policy_engine import PolicyGuardrailEngine
from paymentflow.eval.models import DecisionContext

logger = logging.getLogger(__name__)

eval_mcp_server = MCPServer(
    name="paymentflow-eval-mcp",
    instructions="Offline MCP server interface for PaymentFlow recovery evaluation.",
)

# In-memory evaluation context registry
_eval_context_registry: dict[str, DecisionContext] = {}


def register_eval_context(context: DecisionContext) -> None:
    """Register a DecisionContext for in-memory MCP tool querying."""
    _eval_context_registry[context.case_id] = context
    _eval_context_registry[context.failed_payment_id] = context


def clear_eval_contexts() -> None:
    """Clear all registered contexts."""
    _eval_context_registry.clear()


@eval_mcp_server.tool()
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


@eval_mcp_server.tool()
async def get_payment_context(payment_id: str) -> dict[str, Any]:
    """Retrieve sanitized payment details and failure diagnostics for a given payment ID."""
    if not payment_id:
        return {"error": "payment_id must not be empty."}

    ctx = _eval_context_registry.get(payment_id)
    if not ctx:
        return {"error": f"Payment '{payment_id}' not found in evaluation registry."}

    return {
        "payment_id": ctx.failed_payment_id,
        "amount_paise": ctx.amount,
        "amount_inr": f"₹{ctx.amount / 100:.2f}",
        "currency": ctx.currency,
        "payment_method": ctx.payment_method,
        "failure_category": ctx.failure_category.value,
        "failure_code": ctx.failure_code,
        "failure_description": ctx.failure_description,
        "failure_context": {
            "error_source": ctx.failure_source,
            "error_step": ctx.failure_step,
            "error_reason": ctx.failure_reason,
        },
        "order_id": ctx.order_id,
        "customer_id": ctx.customer_id,
    }


@eval_mcp_server.tool()
async def get_recovery_case(case_id: str) -> dict[str, Any]:
    """Retrieve structured recovery case information for agent reasoning."""
    if not case_id:
        return {"error": "case_id must not be empty."}

    ctx = _eval_context_registry.get(case_id)
    if not ctx:
        return {"error": f"Recovery case '{case_id}' not found in evaluation registry."}

    return {
        "case_id": ctx.case_id,
        "failed_payment_id": ctx.failed_payment_id,
        "amount": ctx.amount,
        "currency": ctx.currency,
        "state": "ELIGIBILITY_CHECKED",
        "failure_category": ctx.failure_category.value,
        "eligibility_status": "ELIGIBLE",
        "prior_failed_count_24h": ctx.prior_failed_count_24h,
        "has_prior_recovery_attempt": ctx.last_attempt_at is not None,
    }


@eval_mcp_server.tool()
async def get_recovery_status(case_id: str) -> dict[str, Any]:
    """Retrieve the current state machine status and workflow flags for a case."""
    if not case_id:
        return {"error": "case_id must not be empty."}

    ctx = _eval_context_registry.get(case_id)
    if not ctx:
        return {"error": f"Recovery case '{case_id}' not found in evaluation registry."}

    return {
        "case_id": ctx.case_id,
        "state": "ELIGIBILITY_CHECKED",
        "is_terminal": False,
        "is_eligible": True,
        "has_recovery_link": ctx.last_attempt_at is not None,
    }


@eval_mcp_server.tool()
async def request_recovery_action(
    case_id: str,
    proposed_policy: str,
    proposed_amount: int | None = None,
    proposed_currency: str | None = None,
    explanation: str = "",
) -> dict[str, Any]:
    """Submit agent proposal to PolicyGuardrailEngine without financial side effects."""
    if not case_id:
        return {"authorized": False, "error": "case_id is required."}

    ctx = _eval_context_registry.get(case_id)
    if not ctx:
        return {"authorized": False, "error": f"Case '{case_id}' not found in evaluation registry."}

    payment_context = PaymentContext(
        payment_id=ctx.failed_payment_id,
        order_id=ctx.order_id,
        customer_id=ctx.customer_id,
        amount=ctx.amount,
        currency=ctx.currency,
        status="failed",
        method=ctx.payment_method,
        failure=PaymentFailureDetails(
            code=ctx.failure_code,
            description=ctx.failure_description,
            source=ctx.failure_source,
            step=ctx.failure_step,
            reason=ctx.failure_reason,
        ),
        created_at=int(ctx.created_at.timestamp()) if ctx.created_at else None,
    )

    validation_res = PolicyGuardrailEngine.validate(
        context=payment_context,
        requested_policy=proposed_policy,
        failure_category=ctx.failure_category,
        has_existing_recovery_link=ctx.last_attempt_at is not None,
        customer_attempts_today=ctx.prior_failed_count_24h,
        proposed_amount=proposed_amount,
        proposed_currency=proposed_currency,
    )

    return {
        "authorized": validation_res.is_approved,
        "decision": validation_res.decision.value,
        "requested_policy": proposed_policy,
        "effective_policy": validation_res.effective_policy.value,
        "reason_code": validation_res.reason_code,
        "reasons": validation_res.reasons,
        "guardrails_checked": validation_res.guardrails_checked,
    }
