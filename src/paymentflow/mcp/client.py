"""Integrated agent client orchestrating LLM reasoning and MCP boundary tools."""

import logging
from typing import Any

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.config import Settings, get_settings
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails
from paymentflow.mcp.server import (
    get_payment_context,
    get_recovery_case,
    get_recovery_status,
    request_recovery_action,
)

logger = logging.getLogger(__name__)


class RecoveryAgentClient:
    """Agent orchestrator querying MCP tools and submitting bounded action proposals."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: LLMClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.llm_client = llm_client or LLMClient(settings=self.settings)

    async def run_recovery_triage(
        self,
        case_id: str,
    ) -> dict[str, Any]:
        """Execute end-to-end Layer 3 triage: MCP Read -> LLM -> Guardrail Action Request."""
        # 1. Query MCP Read Tools
        case_info = await get_recovery_case(case_id)
        if "error" in case_info:
            return {"success": False, "error": case_info["error"]}

        status_info = await get_recovery_status(case_id)
        if status_info.get("is_terminal"):
            err_msg = f"Case '{case_id}' in terminal state '{status_info.get('state')}'."
            return {"success": False, "error": err_msg}

        payment_info = await get_payment_context(case_info["failed_payment_id"])
        if "error" in payment_info:
            return {"success": False, "error": payment_info["error"]}

        # 2. Build PaymentContext for LLM
        failure_ctx = payment_info.get("failure_context") or {}
        context = PaymentContext(
            payment_id=payment_info["payment_id"],
            amount=payment_info["amount_paise"],
            currency=payment_info["currency"],
            status="failed",
            method=payment_info.get("payment_method"),
            customer_id=payment_info.get("customer_id"),
            order_id=payment_info.get("order_id"),
            failure=PaymentFailureDetails(
                code=payment_info.get("failure_code"),
                description=payment_info.get("failure_description"),
                source=failure_ctx.get("error_source"),
                step=failure_ctx.get("error_step"),
                reason=failure_ctx.get("error_reason"),
            ),
        )

        # 3. Request LLM Advisory Proposal
        proposal, llm_metadata = await self.llm_client.generate_proposal(context)

        logger.info(
            f"Agent received LLM proposal for case {case_id}: "
            f"category={proposal.failure_category.value}, policy={proposal.policy_id.value} "
            f"(fallback={llm_metadata['is_fallback']})."
        )

        # 4. Submit through MCP Bounded Action Request Tool
        mcp_result = await request_recovery_action(
            case_id=case_id,
            proposed_policy=proposal.policy_id.value,
            proposed_amount=context.amount,
            proposed_currency=context.currency,
            explanation=proposal.explanation,
        )

        return {
            "success": True,
            "case_id": case_id,
            "llm_proposal": proposal.model_dump(),
            "llm_metadata": llm_metadata,
            "mcp_action_result": mcp_result,
        }
