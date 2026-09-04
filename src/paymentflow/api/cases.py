"""API router for Recovery Cases and Operational Metrics."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.db.models import AuditEventModel, EvaluationRunModel, RecoveryCaseModel
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
    """Aggregated recovery metrics summary with explicit semantic rates."""

    total_cases: int
    recovered_cases: int
    total_recovered_amount_inr: float
    recovery_rate_pct: float
    active_recovery_links: int
    escalated_cases: int
    terminal_no_action_cases: int
    category_breakdown: dict[str, int]
    policy_breakdown: dict[str, int]
    eval_run_id: str | None = None
    case_source: str | None = None
    total_at_risk_amount_inr: float | None = None
    eligible_cases: int | None = None
    eligible_opportunity_amount_inr: float | None = None
    evaluation_recovered_cases: int | None = None
    evaluation_recovered_amount_inr: float | None = None
    escalated_amount_inr: float | None = None
    terminal_amount_inr: float | None = None
    overall_case_recovery_rate_pct: float | None = None
    eligible_case_recovery_rate_pct: float | None = None
    portfolio_revenue_recovery_rate_pct: float | None = None
    eligible_opportunity_recovery_rate_pct: float | None = None


class BenchmarkRunResponse(BaseModel):
    """Schema for benchmark batch execution response."""

    eval_run_id: str
    case_source: str
    status: str
    total_cases: int
    total_at_risk_amount_inr: float
    eligible_cases: int
    eligible_opportunity_amount_inr: float
    recovery_actions_executed: int
    recovery_actions_blocked: int
    evaluation_recovered_cases: int
    evaluation_recovered_amount_inr: float
    escalated_cases: int
    escalated_amount_inr: float
    terminal_cases: int
    terminal_amount_inr: float
    overall_case_recovery_rate_pct: float
    eligible_case_recovery_rate_pct: float
    portfolio_revenue_recovery_rate_pct: float
    eligible_opportunity_recovery_rate_pct: float
    cases: list[dict[str, Any]]


class BenchmarkLatestResponse(BaseModel):
    """Schema for latest benchmark evaluation metrics."""

    eval_run_id: str
    case_source: str
    status: str
    total_cases: int
    total_at_risk_amount_inr: float
    eligible_cases: int
    eligible_opportunity_amount_inr: float
    recovery_actions_executed: int
    recovery_actions_blocked: int
    evaluation_recovered_cases: int
    evaluation_recovered_amount_inr: float
    recovered_cases: int = 0
    total_recovered_amount_inr: float = 0.0
    escalated_cases: int
    escalated_amount_inr: float
    terminal_cases: int
    terminal_amount_inr: float
    overall_case_recovery_rate_pct: float
    eligible_case_recovery_rate_pct: float
    portfolio_revenue_recovery_rate_pct: float
    eligible_opportunity_recovery_rate_pct: float
    category_breakdown: dict[str, int]
    policy_breakdown: dict[str, int]
    created_at: str | None = None


@router.get(
    "",
    response_model=list[dict[str, Any]],
    summary="List Recovery Cases",
)
async def list_cases(
    state: str | None = Query(default=None, description="Filter by case state"),
    case_source: str | None = Query(default=None, description="Filter by case provenance"),
    eval_run_id: str | None = Query(default=None, description="Filter by evaluation run ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List recovery cases with optional state, provenance, and run filtering."""
    query = select(RecoveryCaseModel).order_by(RecoveryCaseModel.created_at.desc())
    if state:
        query = query.where(RecoveryCaseModel.state == state)
    if eval_run_id:
        query = query.where(RecoveryCaseModel.eval_run_id == eval_run_id)
    elif case_source:
        query = query.where(RecoveryCaseModel.case_source == case_source)
    else:
        # If no provenance or run specified, scope canonical evaluation data to the latest run
        from sqlalchemy import and_, or_

        latest_eval_q = (
            select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()).limit(1)
        )
        latest_eval = (await db.execute(latest_eval_q)).scalar_one_or_none()
        if latest_eval:
            query = query.where(
                or_(
                    and_(
                        RecoveryCaseModel.case_source == "CANONICAL_EVALUATION",
                        RecoveryCaseModel.eval_run_id == latest_eval.eval_run_id,
                        RecoveryCaseModel.case_id.like(f"eval_case_{latest_eval.eval_run_id}_%"),
                    ),
                    RecoveryCaseModel.case_source != "CANONICAL_EVALUATION",
                )
            )
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
            "state": c.state,
            "failure_code": c.failure_code,
            "failure_category": c.failure_category,
            "case_source": c.case_source,
            "eval_run_id": c.eval_run_id,
            "eligibility_status": c.eligibility_status,
            "eligibility_reason": c.eligibility_reason,
            "ai_policy_id": c.ai_policy_id,
            "ai_explanation": c.ai_explanation,
            "validated_policy_id": c.validated_policy_id,
            "action_status": c.action_status,
            "payment_link_id": c.payment_link_id,
            "payment_link_short_url": c.payment_link_short_url,
            "payment_link_status": c.payment_link_status,
            "recovered_payment_id": c.recovered_payment_id,
            "recovered_amount_inr": (c.recovered_amount / 100.0) if c.recovered_amount else 0.0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in cases
    ]


@router.get(
    "/metrics/summary",
    response_model=MetricsSummaryResponse,
    summary="Get Recovery Metrics Summary",
)
async def get_metrics_summary(
    case_source: str | None = Query(default=None, description="Scope by case provenance"),
    eval_run_id: str | None = Query(default=None, description="Scope by benchmark run ID"),
    db: AsyncSession = Depends(get_db_session),
) -> MetricsSummaryResponse:
    """Compute aggregate recovery revenue and conversion performance with run isolation."""
    from paymentflow.db.models import EvaluationRunModel

    clean_eval_run_id = eval_run_id if isinstance(eval_run_id, str) and eval_run_id else None
    clean_case_source = case_source if isinstance(case_source, str) and case_source else None

    # Case A: Scoped by eval_run_id or canonical benchmark
    target_eval_run: EvaluationRunModel | None = None
    if clean_eval_run_id:
        target_eval_run = await db.get(EvaluationRunModel, clean_eval_run_id)
    elif clean_case_source == "CANONICAL_EVALUATION":
        latest_eval_q = (
            select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()).limit(1)
        )
        target_eval_run = (await db.execute(latest_eval_q)).scalar_one_or_none()
    elif clean_case_source is None:
        # Check if any non-canonical (live/interactive) operational cases exist
        non_canon_count_q = select(func.count(RecoveryCaseModel.case_id)).where(
            RecoveryCaseModel.case_source != "CANONICAL_EVALUATION"
        )
        non_canon_count = (await db.execute(non_canon_count_q)).scalar_one()
        if non_canon_count == 0:
            latest_eval_q = (
                select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()).limit(1)
            )
            target_eval_run = (await db.execute(latest_eval_q)).scalar_one_or_none()
            if not target_eval_run:
                canon_count_q = select(func.count(RecoveryCaseModel.case_id)).where(
                    RecoveryCaseModel.case_source == "CANONICAL_EVALUATION"
                )
                canon_count = (await db.execute(canon_count_q)).scalar_one()
                if canon_count > 0:
                    clean_case_source = "CANONICAL_EVALUATION"

    if target_eval_run:
        # Category breakdown for this run
        cat_q = (
            select(RecoveryCaseModel.failure_category, func.count(RecoveryCaseModel.case_id))
            .where(
                RecoveryCaseModel.eval_run_id == target_eval_run.eval_run_id,
                RecoveryCaseModel.case_id.like(f"eval_case_{target_eval_run.eval_run_id}_%"),
            )
            .group_by(RecoveryCaseModel.failure_category)
        )
        cat_res = await db.execute(cat_q)
        cat_breakdown = {str(row[0] or "UNKNOWN"): int(row[1]) for row in cat_res.fetchall()}

        # Policy breakdown for this run
        pol_q = (
            select(RecoveryCaseModel.validated_policy_id, func.count(RecoveryCaseModel.case_id))
            .where(
                RecoveryCaseModel.eval_run_id == target_eval_run.eval_run_id,
                RecoveryCaseModel.case_id.like(f"eval_case_{target_eval_run.eval_run_id}_%"),
            )
            .group_by(RecoveryCaseModel.validated_policy_id)
        )
        pol_res = await db.execute(pol_q)
        pol_breakdown = {str(row[0] or "NONE"): int(row[1]) for row in pol_res.fetchall()}

        return MetricsSummaryResponse(
            total_cases=target_eval_run.total_cases,
            recovered_cases=target_eval_run.evaluation_recovered_cases,
            total_recovered_amount_inr=round(
                float(target_eval_run.evaluation_recovered_amount) / 100.0, 2
            ),
            recovery_rate_pct=target_eval_run.eligible_opportunity_recovery_rate_pct,
            active_recovery_links=target_eval_run.recovery_actions_executed,
            escalated_cases=target_eval_run.escalated_cases,
            terminal_no_action_cases=target_eval_run.terminal_cases,
            category_breakdown=cat_breakdown,
            policy_breakdown=pol_breakdown,
            eval_run_id=target_eval_run.eval_run_id,
            case_source="CANONICAL_EVALUATION",
            total_at_risk_amount_inr=round(float(target_eval_run.total_at_risk_amount) / 100.0, 2),
            eligible_cases=target_eval_run.eligible_cases,
            eligible_opportunity_amount_inr=round(
                float(target_eval_run.eligible_opportunity_amount) / 100.0, 2
            ),
            evaluation_recovered_cases=target_eval_run.evaluation_recovered_cases,
            evaluation_recovered_amount_inr=round(
                float(target_eval_run.evaluation_recovered_amount) / 100.0, 2
            ),
            escalated_amount_inr=round(float(target_eval_run.escalated_amount) / 100.0, 2),
            terminal_amount_inr=round(float(target_eval_run.terminal_amount) / 100.0, 2),
            overall_case_recovery_rate_pct=target_eval_run.overall_case_recovery_rate_pct,
            eligible_case_recovery_rate_pct=target_eval_run.eligible_case_recovery_rate_pct,
            portfolio_revenue_recovery_rate_pct=target_eval_run.portfolio_revenue_recovery_rate_pct,
            eligible_opportunity_recovery_rate_pct=target_eval_run.eligible_opportunity_recovery_rate_pct,
        )

    # Case B: Live/Interactive operational metrics query
    base_filter = []
    if clean_case_source:
        base_filter.append(RecoveryCaseModel.case_source == clean_case_source)
    else:
        # Live operational metrics strictly exclude all benchmark evaluation data
        base_filter.append(RecoveryCaseModel.case_source != "CANONICAL_EVALUATION")

    total_q = select(func.count(RecoveryCaseModel.case_id))
    at_risk_q = select(func.sum(RecoveryCaseModel.amount))
    rec_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "RECOVERED"
    )
    rev_q = select(func.sum(RecoveryCaseModel.recovered_amount)).where(
        RecoveryCaseModel.state == "RECOVERED"
    )
    links_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.payment_link_id.isnot(None),
        RecoveryCaseModel.state.in_(["ACTION_EXECUTED", "RECOVERED"]),
    )
    esc_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "ESCALATED"
    )
    no_act_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.state == "TERMINAL_NO_ACTION"
    )
    elig_q = select(func.count(RecoveryCaseModel.case_id)).where(
        RecoveryCaseModel.eligibility_status == "ELIGIBLE"
    )
    elig_amt_q = select(func.sum(RecoveryCaseModel.amount)).where(
        RecoveryCaseModel.eligibility_status == "ELIGIBLE"
    )

    for cond in base_filter:
        total_q = total_q.where(cond)
        at_risk_q = at_risk_q.where(cond)
        rec_q = rec_q.where(cond)
        rev_q = rev_q.where(cond)
        links_q = links_q.where(cond)
        esc_q = esc_q.where(cond)
        no_act_q = no_act_q.where(cond)
        elig_q = elig_q.where(cond)
        elig_amt_q = elig_amt_q.where(cond)

    total_cases = (await db.scalar(total_q)) or 0
    at_risk_paise = (await db.scalar(at_risk_q)) or 0
    total_at_risk_inr = float(at_risk_paise) / 100.0
    recovered_cases = (await db.scalar(rec_q)) or 0
    recovered_paise = (await db.scalar(rev_q)) or 0
    recovered_inr = float(recovered_paise) / 100.0
    active_links = (await db.scalar(links_q)) or 0
    escalated_cases = (await db.scalar(esc_q)) or 0
    terminal_no_act = (await db.scalar(no_act_q)) or 0
    eligible_cases = (await db.scalar(elig_q)) or 0
    elig_amt_paise = (await db.scalar(elig_amt_q)) or 0
    eligible_amt_inr = float(elig_amt_paise) / 100.0

    case_recovery_rate = (
        (float(recovered_cases) / float(total_cases) * 100.0) if total_cases > 0 else 0.0
    )
    rev_recovery_rate = (
        (float(recovered_paise) / float(at_risk_paise) * 100.0) if at_risk_paise > 0 else 0.0
    )
    elig_case_rate = (
        (float(recovered_cases) / float(eligible_cases) * 100.0) if eligible_cases > 0 else 0.0
    )
    elig_opportunity_rate = (
        (float(recovered_paise) / float(elig_amt_paise) * 100.0) if elig_amt_paise > 0 else 0.0
    )

    cat_q = select(
        RecoveryCaseModel.failure_category, func.count(RecoveryCaseModel.case_id)
    ).group_by(RecoveryCaseModel.failure_category)
    pol_q = select(
        RecoveryCaseModel.validated_policy_id, func.count(RecoveryCaseModel.case_id)
    ).group_by(RecoveryCaseModel.validated_policy_id)

    for cond in base_filter:
        cat_q = cat_q.where(cond)
        pol_q = pol_q.where(cond)

    cat_res = await db.execute(cat_q)
    cat_breakdown = {str(row[0] or "UNKNOWN"): int(row[1]) for row in cat_res.fetchall()}
    pol_res = await db.execute(pol_q)
    pol_breakdown = {str(row[0] or "NONE"): int(row[1]) for row in pol_res.fetchall()}

    return MetricsSummaryResponse(
        total_cases=total_cases,
        recovered_cases=recovered_cases,
        total_recovered_amount_inr=round(recovered_inr, 2),
        recovery_rate_pct=round(case_recovery_rate, 2),
        active_recovery_links=active_links,
        escalated_cases=escalated_cases,
        terminal_no_action_cases=terminal_no_act,
        category_breakdown=cat_breakdown,
        policy_breakdown=pol_breakdown,
        case_source=clean_case_source or "LIVE_OPERATIONAL",
        total_at_risk_amount_inr=round(total_at_risk_inr, 2),
        eligible_cases=eligible_cases,
        eligible_opportunity_amount_inr=round(eligible_amt_inr, 2),
        overall_case_recovery_rate_pct=round(case_recovery_rate, 2),
        eligible_case_recovery_rate_pct=round(elig_case_rate, 2),
        portfolio_revenue_recovery_rate_pct=round(rev_recovery_rate, 2),
        eligible_opportunity_recovery_rate_pct=round(elig_opportunity_rate, 2),
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
        "case_source": case.case_source,
        "eval_run_id": case.eval_run_id,
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
            "eval_run_id": a.eval_run_id,
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
    "/benchmark/run",
    response_model=BenchmarkRunResponse,
    summary="Run Canonical Recovery Workflow Benchmark Execution",
)
async def run_benchmark_batch(
    db: AsyncSession = Depends(get_db_session),
) -> BenchmarkRunResponse:
    """Execute the canonical 15-scenario recovery workflow benchmark dynamically.

    Runs each scenario through PaymentFlow diagnosis, C1-C5 classification, deterministic
    eligibility, deterministic evaluation advisory, policy guardrails, and safe evaluation
    recovery execution. Computes and persists run-scoped metrics.
    """
    from paymentflow.eval.benchmark_runner import BenchmarkRunner

    result = await BenchmarkRunner.run_benchmark(session=db)
    return BenchmarkRunResponse(**result)


@router.get(
    "/benchmark/latest",
    response_model=BenchmarkLatestResponse,
    summary="Get Latest Canonical Benchmark Run Metrics",
)
async def get_latest_benchmark_metrics(
    db: AsyncSession = Depends(get_db_session),
) -> BenchmarkLatestResponse:
    """Retrieve run-scoped metrics for the most recent benchmark evaluation run."""
    from paymentflow.db.models import EvaluationRunModel

    latest_eval_q = (
        select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()).limit(1)
    )
    latest_eval = (await db.execute(latest_eval_q)).scalar_one_or_none()
    if not latest_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No canonical benchmark evaluation runs exist.",
        )

    # Category breakdown for this run
    cat_q = (
        select(RecoveryCaseModel.failure_category, func.count(RecoveryCaseModel.case_id))
        .where(
            RecoveryCaseModel.eval_run_id == latest_eval.eval_run_id,
            RecoveryCaseModel.case_id.like(f"eval_case_{latest_eval.eval_run_id}_%"),
        )
        .group_by(RecoveryCaseModel.failure_category)
    )
    cat_res = await db.execute(cat_q)
    cat_breakdown = {str(row[0] or "UNKNOWN"): int(row[1]) for row in cat_res.fetchall()}

    # Policy breakdown for this run
    pol_q = (
        select(RecoveryCaseModel.validated_policy_id, func.count(RecoveryCaseModel.case_id))
        .where(
            RecoveryCaseModel.eval_run_id == latest_eval.eval_run_id,
            RecoveryCaseModel.case_id.like(f"eval_case_{latest_eval.eval_run_id}_%"),
        )
        .group_by(RecoveryCaseModel.validated_policy_id)
    )
    pol_res = await db.execute(pol_q)
    pol_breakdown = {str(row[0] or "NONE"): int(row[1]) for row in pol_res.fetchall()}

    return BenchmarkLatestResponse(
        eval_run_id=latest_eval.eval_run_id,
        case_source="CANONICAL_EVALUATION",
        status="COMPLETED",
        total_cases=latest_eval.total_cases,
        total_at_risk_amount_inr=round(float(latest_eval.total_at_risk_amount) / 100.0, 2),
        eligible_cases=latest_eval.eligible_cases,
        eligible_opportunity_amount_inr=round(
            float(latest_eval.eligible_opportunity_amount) / 100.0, 2
        ),
        recovery_actions_executed=latest_eval.recovery_actions_executed,
        recovery_actions_blocked=latest_eval.recovery_actions_blocked,
        evaluation_recovered_cases=latest_eval.evaluation_recovered_cases,
        evaluation_recovered_amount_inr=round(
            float(latest_eval.evaluation_recovered_amount) / 100.0, 2
        ),
        recovered_cases=latest_eval.evaluation_recovered_cases,
        total_recovered_amount_inr=round(float(latest_eval.evaluation_recovered_amount) / 100.0, 2),
        escalated_cases=latest_eval.escalated_cases,
        escalated_amount_inr=round(float(latest_eval.escalated_amount) / 100.0, 2),
        terminal_cases=latest_eval.terminal_cases,
        terminal_amount_inr=round(float(latest_eval.terminal_amount) / 100.0, 2),
        overall_case_recovery_rate_pct=latest_eval.overall_case_recovery_rate_pct,
        eligible_case_recovery_rate_pct=latest_eval.eligible_case_recovery_rate_pct,
        portfolio_revenue_recovery_rate_pct=latest_eval.portfolio_revenue_recovery_rate_pct,
        eligible_opportunity_recovery_rate_pct=latest_eval.eligible_opportunity_recovery_rate_pct,
        category_breakdown=cat_breakdown,
        policy_breakdown=pol_breakdown,
        created_at=latest_eval.created_at.isoformat() if latest_eval.created_at else None,
    )


@router.post(
    "/{case_id}/triage",
    summary="Execute Recovery Orchestration",
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
    summary="Seed Canonical Demonstration Batch",
    deprecated=True,
    include_in_schema=False,
)
async def seed_demo_batch(
    reset_first: bool = Query(default=True, description="Reset previous demo cases before seeding"),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """DEPRECATED: Use POST /cases/benchmark/run instead.

    Maintained for legacy compatibility with prior static test fixtures.
    """
    from paymentflow.eval.canonical_batch import seed_canonical_demonstration_batch

    result = await seed_canonical_demonstration_batch(session=db, reset_first=reset_first)
    return result
