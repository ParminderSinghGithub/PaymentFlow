"""Integrated agent client orchestrating LLM reasoning and MCP boundary tools."""

import json
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult

from paymentflow.adapters.llm_adapter import LLMClient
from paymentflow.config import Settings, get_settings
from paymentflow.domain.models import PaymentContext, PaymentFailureDetails
from paymentflow.mcp.server import mcp_server as default_mcp_server

logger = logging.getLogger(__name__)


class RecoveryAgentClient:
    """Agent orchestrator discovering MCP tools and invoking them via MCP protocol APIs."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: LLMClient | None = None,
        server: MCPServer | None = None,
    ):
        self.settings = settings or get_settings()
        self.llm_client = llm_client or LLMClient(settings=self.settings)
        self.server = server or default_mcp_server

    async def discover_tools(self) -> list[dict[str, Any]]:
        """Query MCP Server to discover available tools and their schemas."""
        try:
            tools = await self.server.list_tools()
        except Exception as exc:
            logger.error(f"MCP tool discovery failed: {exc}")
            return []

        discovered = []
        for t in tools:
            schema = t.inputSchema if hasattr(t, "inputSchema") else getattr(t, "input_schema", {})
            discovered.append({
                "name": t.name,
                "description": t.description,
                "input_schema": schema,
            })
        return discovered

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Invoke an MCP tool through the MCP protocol boundary and decode output."""
        args = arguments or {}
        try:
            result: CallToolResult = await self.server.call_tool(tool_name, args)
        except Exception as exc:
            logger.error(f"MCP tool call '{tool_name}' failed with exception: {exc}")
            return {"error": str(exc)}

        if not result or not result.content:
            return None

        # Parse text content blocks from CallToolResult
        parsed_blocks = []
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    parsed_blocks.append(json.loads(block.text))
                except (json.JSONDecodeError, TypeError):
                    parsed_blocks.append(block.text)

        if len(parsed_blocks) == 1:
            return parsed_blocks[0]
        return parsed_blocks

    async def run_recovery_triage(
        self,
        case_id: str,
    ) -> dict[str, Any]:
        """Execute end-to-end Layer 3 triage: MCP Protocol -> LLM -> MCP Action Request."""
        # 1. Query MCP Read Tools over MCP protocol
        case_info = await self.call_tool("get_recovery_case", {"case_id": case_id})
        if not case_info or "error" in case_info:
            err = case_info.get("error") if case_info else "Failed to retrieve case."
            return {"success": False, "error": err}

        status_info = await self.call_tool("get_recovery_status", {"case_id": case_id})
        if status_info and status_info.get("is_terminal"):
            err_msg = f"Case '{case_id}' in terminal state '{status_info.get('state')}'."
            return {"success": False, "error": err_msg}

        payment_info = await self.call_tool(
            "get_payment_context", {"payment_id": case_info["failed_payment_id"]}
        )
        if not payment_info or "error" in payment_info:
            err = (
                payment_info.get("error")
                if payment_info
                else "Failed to retrieve payment context."
            )
            return {"success": False, "error": err}

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

        # 4. Submit through MCP Bounded Action Request Tool over MCP Protocol
        mcp_result = await self.call_tool(
            "request_recovery_action",
            {
                "case_id": case_id,
                "proposed_policy": proposal.policy_id.value,
                "proposed_amount": context.amount,
                "proposed_currency": context.currency,
                "explanation": proposal.explanation,
            },
        )

        return {
            "success": True,
            "case_id": case_id,
            "llm_proposal": proposal.model_dump(),
            "llm_metadata": llm_metadata,
            "mcp_action_result": mcp_result,
        }
