"""End-to-end production recovery orchestrator for PaymentFlow Recovery Agent.

Coordinates: Ingestion -> Context Enrichment -> Classification & Eligibility ->
MCP Tool Discovery & Query -> Real LLM Reasoning -> MCP Action Guardrails ->
Deterministic Execution (Immediate / Delayed) -> Outcome Attribution.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.config import Settings, get_settings
from paymentflow.db.models import AuditEventModel, RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import (
    CaseState,
    EligibilityStatus,
    RecoveryPolicy,
)
from paymentflow.domain.models import RecoveryExecutionResult
from paymentflow.mcp.client import RecoveryAgentClient
from paymentflow.services.recovery_executor import RecoveryExecutor
from paymentflow.services.recovery_service import RecoveryTriageService

logger = logging.getLogger(__name__)


class RecoveryOrchestrator:
    """Production orchestrator executing the end-to-end recovery pipeline."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession] | None = None,
        razorpay_adapter: RazorpayAdapter | None = None,
        agent_client: RecoveryAgentClient | None = None,
        executor: RecoveryExecutor | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.sessionmaker = sessionmaker or get_sessionmaker()
        self.settings = settings or get_settings()
        self.adapter = razorpay_adapter or RazorpayAdapter(settings=self.settings)
        self.agent_client = agent_client or RecoveryAgentClient(settings=self.settings)
        self.executor = executor or RecoveryExecutor(
            sessionmaker=self.sessionmaker,
            razorpay_adapter=self.adapter,
            settings=self.settings,
        )

    async def orchestrate_recovery(
        self,
        case_id: str,
        fetch_from_gateway: bool = True,
    ) -> dict[str, Any]:
        """Execute complete end-to-end recovery pipeline for a given recovery case."""
        logger.info(f"RecoveryOrchestrator: Starting recovery pipeline for case {case_id}...")

        # -----------------------------------------------------------------
        # STEP 0: Check if case is already resolved/terminal
        # -----------------------------------------------------------------
        async with self.sessionmaker() as session:
            existing = await session.get(RecoveryCaseModel, case_id)
            if not existing:
                return {
                    "success": False,
                    "case_id": case_id,
                    "stage": "NOT_FOUND",
                    "error": f"Case '{case_id}' not found.",
                }
            if existing.state in (
                CaseState.RECOVERED.value,
                CaseState.ACTION_EXECUTED.value,
                CaseState.ESCALATED.value,
                CaseState.TERMINAL_NO_ACTION.value,
            ):
                logger.info(
                    f"RecoveryOrchestrator: Case {case_id} already at terminal/executed state "
                    f"'{existing.state}'. Skipping pipeline."
                )
                return {
                    "success": True,
                    "case_id": case_id,
                    "stage": "TERMINAL_PRESERVED",
                    "state": existing.state,
                    "action_executed": bool(existing.payment_link_id),
                    "payment_link_id": existing.payment_link_id,
                    "policy": existing.validated_policy_id,
                }

        # -----------------------------------------------------------------
        # STEP 1 & 2: Context Enrichment, Classification & Eligibility (L2)
        # -----------------------------------------------------------------
        async with self.sessionmaker() as session:
            triage_service = RecoveryTriageService(
                db_session=session,
                razorpay_adapter=self.adapter,
            )
            case, eligibility_decision = await triage_service.process_triage_pipeline(
                case_id=case_id,
                fetch_from_gateway=fetch_from_gateway,
            )

        if eligibility_decision.status != EligibilityStatus.ELIGIBLE:
            logger.info(
                f"RecoveryOrchestrator: Case {case_id} not eligible for AI triage: "
                f"status={eligibility_decision.status.value}, state={case.state}."
            )
            return {
                "success": True,
                "case_id": case_id,
                "stage": "ELIGIBILITY_EVALUATION",
                "state": case.state,
                "eligibility_status": eligibility_decision.status.value,
                "eligibility_reason": eligibility_decision.reason_code.value,
                "action_executed": False,
            }

        # -----------------------------------------------------------------
        # STEP 3: MCP Protocol Traversal, LLM Proposal & Guardrail Gate (L3)
        # -----------------------------------------------------------------
        agent_result = await self.agent_client.run_recovery_triage(case_id=case_id)
        if not agent_result.get("success"):
            err_msg = agent_result.get("error", "Agent triage failed.")
            logger.error(f"RecoveryOrchestrator: Agent triage failed for {case_id}: {err_msg}")
            return {
                "success": False,
                "case_id": case_id,
                "stage": "AGENT_TRIAGE",
                "error": err_msg,
            }

        mcp_action = agent_result.get("mcp_action_result", {})
        is_authorized = mcp_action.get("authorized", False)
        effective_policy = mcp_action.get("effective_policy")
        case_state = mcp_action.get("case_state")

        # -----------------------------------------------------------------
        # STEP 4: Execution Routing (L4A)
        # -----------------------------------------------------------------
        if is_authorized and effective_policy == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value:
            logger.info(
                f"RecoveryOrchestrator: Immediate Payment Link authorized for {case_id}. "
                "Executing write path..."
            )
            exec_result = await self.executor.execute(case_id=case_id, is_delayed=False)
            return {
                "success": exec_result.success,
                "case_id": case_id,
                "stage": "EXECUTION",
                "state": exec_result.state.value,
                "policy": effective_policy,
                "payment_link_id": exec_result.payment_link_id,
                "payment_link_url": exec_result.payment_link_short_url,
                "execution_result": exec_result.model_dump(),
                "agent_decision": agent_result.get("llm_proposal"),
            }

        if is_authorized and effective_policy == RecoveryPolicy.P_CREATE_LINK_DELAYED.value:
            logger.info(
                f"RecoveryOrchestrator: Delayed Payment Link authorized for {case_id}. "
                "Scheduled for restart-safe background execution."
            )
            return {
                "success": True,
                "case_id": case_id,
                "stage": "SCHEDULED_DELAYED",
                "state": case_state,
                "policy": effective_policy,
                "action_executed": False,
                "scheduled": True,
                "agent_decision": agent_result.get("llm_proposal"),
            }

        # Terminal non-financial outcomes (P_ESCALATE_ONLY / P_NO_ACTION)
        logger.info(
            f"RecoveryOrchestrator: Non-financial policy {effective_policy} enforced "
            f"for {case_id}. Final state: {case_state}."
        )
        return {
            "success": True,
            "case_id": case_id,
            "stage": "GUARDRAIL_TERMINAL",
            "state": case_state,
            "policy": effective_policy,
            "action_executed": False,
            "agent_decision": agent_result.get("llm_proposal"),
            "mcp_action": mcp_action,
        }

    async def process_due_delayed_cases(
        self,
        now: datetime | None = None,
    ) -> list[RecoveryExecutionResult]:
        """Query and execute all due delayed recovery cases restart-safely with re-validation."""
        current_time = now or utc_now()
        due_case_ids: list[str] = []

        async with self.sessionmaker() as session:
            stmt = select(RecoveryCaseModel.case_id).where(
                RecoveryCaseModel.state == CaseState.ACTION_APPROVED.value,
                RecoveryCaseModel.validated_policy_id == RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
                RecoveryCaseModel.payment_link_id.is_(None),
                RecoveryCaseModel.scheduled_at <= current_time,
            )
            res = await session.execute(stmt)
            due_case_ids = list(res.scalars().all())

        if not due_case_ids:
            logger.debug("RecoveryOrchestrator: No delayed recovery cases currently due.")
            return []

        logger.info(
            f"RecoveryOrchestrator: Found {len(due_case_ids)} due delayed cases. "
            "Executing restart-safe recovery..."
        )

        results: list[RecoveryExecutionResult] = []
        for case_id in due_case_ids:
            try:
                exec_res = await self.executor.execute(case_id=case_id, is_delayed=True)
                results.append(exec_res)
            except Exception as exc:
                logger.error(f"Error executing due delayed case {case_id}: {exc}")

        return results

    async def get_case_audit_trail(self, case_id: str) -> list[dict[str, Any]]:
        """Retrieve complete chronological audit events for a recovery case."""
        async with self.sessionmaker() as session:
            stmt = (
                select(AuditEventModel)
                .where(AuditEventModel.case_id == case_id)
                .order_by(AuditEventModel.timestamp.asc())
            )
            res = await session.execute(stmt)
            events = res.scalars().all()
            return [
                {
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "decision": e.decision,
                    "policy": e.policy,
                    "action": e.action,
                    "outcome": e.outcome,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "details": e.details,
                    "guardrail_result": e.guardrail_result,
                }
                for e in events
            ]
