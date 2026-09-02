"""API router for Recovery Cases and Operational Metrics."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.db.session import get_db_session, get_sessionmaker
from paymentflow.services.recovery_orchestrator import RecoveryOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["Recovery Cases"])


class CaseSummaryResponse(BaseModel):
    """Schema for individual recovery case details."""

    model_config = ConfigDict(from_attributes=True)

    case_id: str
    failed_payment_id: str
    order_id: str | None = None
    customer_id: str | None = None
    amount: int
    currency: str
    payment_method: str | None = None
    failure_category: str | None = None
    failure_code: str | None = None
    failure_description: str | None = None
    eligibility_status: str | None = None
    eligibility_reason: str | None = None
    ai_policy_id: str | None = None
    validated_policy_id: str | None = None
    action_status: str | None = None
    payment_link_id: str | None = None
    payment_link_short_url: str | None = None
    payment_link_status: str | None = None
    recovered_payment_id: str | None = None
    recovered_amount: int | None = None
    state: str
    scheduled_at: str | None = None
    created_at: str
    updated_at: str


class CaseDetailResponse(BaseModel):
    """Detailed recovery case schema with complete audit trail."""

    case: dict[str, Any]
    audit_trail: list[dict[str, Any]]


class MetricsSummaryResponse(BaseModel):
    """Aggregated recovery metrics summary."""

    total_cases: int
    recovered_cases: int
    total_recovered_amount_inr: float
    recovery_rate_pct: float
    active_recovery_links: int
    escalated_cases: int
    terminal_no_action_cases: int
    category_breakdown: dict[str, int]
    policy_breakdown: dict[str, int]


@router.get(
    "",
    response_model=list[dict[str, Any]],
    summary="List Recovery Cases",
)
async def list_cases(
    state: str | None = Query(default=None, description="Filter by case state"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List recovery cases with optional state filtering."""
    query = select(RecoveryCaseModel).order_by(RecoveryCaseModel.created_at.desc())
    if state:
        query = query.where(RecoveryCaseModel.state == state)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    cases = result.scalars().all()

    return [
        {
            "case_id": c.case_id,
            "failed_payment_id": c.failed_payment_id,
            "order_id": c.order_id,
            "customer_id": c.customer_id,
            "amount_paise": c.amount,
            "amount_inr": c.amount / 100.0,
            "currency": c.currency,
            "payment_method": c.payment_method,
            "failure_category": c.failure_category,
            "state": c.state,
            "validated_policy_id": c.validated_policy_id,
            "payment_link_id": c.payment_link_id,
            "payment_link_short_url": c.payment_link_short_url,
            "recovered_amount_paise": c.recovered_amount,
            "recovered_amount_inr": (c.recovered_amount / 100.0) if c.recovered_amount else 0.0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        }
        for c in cases
    ]


@router.get(
    "/metrics/summary",
    response_model=MetricsSummaryResponse,
    summary="Get Recovery Performance Metrics",
)
async def get_metrics_summary(
    db: AsyncSession = Depends(get_db_session),
) -> MetricsSummaryResponse:
    """Compute aggregate recovery revenue and conversion performance."""
    # 1. Basic counts
    total_q = select(func.count(RecoveryCaseModel.case_id))
    total_cases = (await db.scalar(total_q)) or 0

    rec_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "RECOVERED"
    )
    recovered_cases = (await db.scalar(rec_q)) or 0

    rev_q = select(func.sum(RecoveryCaseModel.recovered_amount)).where(
        RecoveryCaseModel.state == "RECOVERED"
    )
    recovered_paise = (await db.scalar(rev_q)) or 0
    recovered_inr = float(recovered_paise) / 100.0

    links_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.payment_link_id.isnot(None),
        RecoveryCaseModel.state.in_(["ACTION_EXECUTED", "RECOVERED"]),
    )
    active_links = (await db.scalar(links_q)) or 0

    esc_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "ESCALATED"
    )
    escalated_cases = (await db.scalar(esc_q)) or 0

    no_act_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "TERMINAL_NO_ACTION"
    )
    terminal_no_act = (await db.scalar(no_act_q)) or 0

    recovery_rate = (recovered_cases / total_cases * 100.0) if total_cases > 0 else 0.0

    # 2. Category Breakdown
    cat_q = select(
        RecoveryCaseModel.failure_category, func.count(RecoveryCaseModel.case_id)
    ).group_by(RecoveryCaseModel.failure_category)
    cat_res = await db.execute(cat_q)
    cat_breakdown = {str(row[0] or "UNKNOWN"): int(row[1]) for row in cat_res.fetchall()}

    # 3. Policy Breakdown
    pol_q = select(
        RecoveryCaseModel.validated_policy_id, func.count(RecoveryCaseModel.case_id)
    ).group_by(RecoveryCaseModel.validated_policy_id)
    pol_res = await db.execute(pol_q)
    pol_breakdown = {str(row[0] or "NONE"): int(row[1]) for row in pol_res.fetchall()}

    return MetricsSummaryResponse(
        total_cases=total_cases,
        recovered_cases=recovered_cases,
        total_recovered_amount_inr=round(recovered_inr, 2),
        recovery_rate_pct=round(recovery_rate, 2),
        active_recovery_links=active_links,
        escalated_cases=escalated_cases,
        terminal_no_action_cases=terminal_no_act,
        category_breakdown=cat_breakdown,
        policy_breakdown=pol_breakdown,
    )


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    summary="Get Recovery Case Detail & Audit Trail",
)
async def get_case_detail(
    case_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CaseDetailResponse:
    """Retrieve complete case details and immutable audit log."""
    case_q = select(RecoveryCaseModel).where(RecoveryCaseModel.case_id == case_id)
    case_res = await db.execute(case_q)
    case = case_res.scalar_one_or_none()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery case '{case_id}' not found.",
        )

    audit_q = (
        select(AuditEventModel)
        .where(AuditEventModel.case_id == case_id)
        .order_by(AuditEventModel.timestamp.asc())
    )
    audit_res = await db.execute(audit_q)
    audit_events = audit_res.scalars().all()

    case_dict = {
        "case_id": case.case_id,
        "failed_payment_id": case.failed_payment_id,
        "order_id": case.order_id,
        "customer_id": case.customer_id,
        "amount_paise": case.amount,
        "amount_inr": case.amount / 100.0,
        "currency": case.currency,
        "payment_method": case.payment_method,
        "failure_category": case.failure_category,
        "failure_code": case.failure_code,
        "failure_description": case.failure_description,
        "failure_context": case.failure_context,
        "eligibility_status": case.eligibility_status,
        "eligibility_reason": case.eligibility_reason,
        "classification_evidence": case.classification_evidence,
        "ai_policy_id": case.ai_policy_id,
        "ai_explanation": case.ai_explanation,
        "validated_policy_id": case.validated_policy_id,
        "action_status": case.action_status,
        "payment_link_id": case.payment_link_id,
        "payment_link_reference_id": case.payment_link_reference_id,
        "payment_link_short_url": case.payment_link_short_url,
        "payment_link_status": case.payment_link_status,
        "recovered_payment_id": case.recovered_payment_id,
        "recovered_amount_paise": case.recovered_amount,
        "recovered_amount_inr": (case.recovered_amount / 100.0) if case.recovered_amount else 0.0,
        "state": case.state,
        "scheduled_at": case.scheduled_at.isoformat() if case.scheduled_at else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }

    audit_list = [
        {
            "id": a.id,
            "event_type": a.event_type,
            "actor": a.actor,
            "decision": a.decision,
            "policy": a.policy,
            "action": a.action,
            "outcome": a.outcome,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "details": a.details,
            "guardrail_result": a.guardrail_result,
        }
        for a in audit_events
    ]

    return CaseDetailResponse(case=case_dict, audit_trail=audit_list)


@router.post(
    "/{case_id}/triage",
    summary="Execute Production Recovery Orchestration",
)
async def trigger_case_triage(
    case_id: str,
) -> dict[str, Any]:
    """Manually trigger end-to-end recovery pipeline for a case."""
    orchestrator = RecoveryOrchestrator(sessionmaker=get_sessionmaker())
    result = await orchestrator.orchestrate_recovery(case_id=case_id)
    if not result.get("success") and result.get("stage") == "NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", f"Recovery case '{case_id}' not found."),
        )
    return result


@router.post(
    "/delayed/process",
    summary="Process Due Delayed Recovery Cases",
)
async def process_due_delayed_cases() -> dict[str, Any]:
    """Execute all due delayed recovery cases restart-safely."""
    orchestrator = RecoveryOrchestrator(sessionmaker=get_sessionmaker())
    results = await orchestrator.process_due_delayed_cases()
    return {
        "processed_count": len(results),
        "results": [r.model_dump() for r in results],
    }


@router.post(
    "/demo/seed",
    summary="Seed Canonical 15-Case Demonstration Batch",
)
async def seed_demo_batch(
    reset_first: bool = Query(default=True, description="Reset previous demo cases before seeding"),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Seed the canonical 15-case demonstration batch into PostgreSQL."""
    from paymentflow.eval.canonical_batch import seed_canonical_demonstration_batch

    result = await seed_canonical_demonstration_batch(session=db, reset_first=reset_first)
    return result
