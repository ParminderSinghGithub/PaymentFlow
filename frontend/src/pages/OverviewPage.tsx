import React, { useMemo } from 'react';
import {
  IndianRupee,
  TrendingUp,
  Link2,
  ShieldCheck,
  Database,
  ArrowRight,
  Shield,
  Bot,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Zap,
  Store,
} from 'lucide-react';
import type { CaseSummaryItem, MetricsSummary, FailureCategory } from '../types';
import { CATEGORY_INFO } from '../types';
import { KpiCard, KpiCardSkeleton } from '../components/common/KpiCard';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { MoneyValue } from '../components/common/MoneyValue';
import { ActionButton } from '../components/common/ActionButton';
import { PageHeader } from '../components/common/PageHeader';
import { SectionHeader } from '../components/common/SectionHeader';
import { ZoneCard } from '../components/common/ZoneCard';
import { TableRowSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { getMerchantStorefrontUrl } from '../api/client';

interface OverviewPageProps {
  metrics: MetricsSummary | null;
  metricsLoading: boolean;
  recentCases: CaseSummaryItem[];
  casesLoading: boolean;
  onSelectCase: (id: string) => void;
  onNavigateToCases: () => void;
  onNavigateToArchitecture: () => void;
  onTriggerTriage: (id: string) => void;
  triageLoadingCaseId: string | null;
  onSeedDemoBatch?: () => void;
  seedingBatch?: boolean;
  hasEvaluationRun?: boolean;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  metrics,
  metricsLoading,
  recentCases,
  casesLoading,
  onSelectCase,
  onNavigateToCases,
  onNavigateToArchitecture,
  onTriggerTriage,
  triageLoadingCaseId,
  onSeedDemoBatch,
  seedingBatch = false,
  hasEvaluationRun = false,
}) => {

  // When no evaluation has been run in the current session, exclude past evaluation batch cases
  // so the overview defaults to the clean initial state until an evaluation or live case occurs.
  const activeCases = useMemo(() => {
    if (hasEvaluationRun) return recentCases;
    return recentCases.filter((c) => c.case_source === 'MERCHANT_CHECKOUT');
  }, [recentCases, hasEvaluationRun]);

  // Derive genuine pipeline totals from active cases
  const totalRevenueAtRiskInr = useMemo(() => {
    return activeCases.reduce((sum, c) => sum + (c.amount_inr || 0), 0);
  }, [activeCases]);

  const unrecoveredRevenueAtRiskInr = useMemo(() => {
    return activeCases
      .filter((c) => c.state !== 'RECOVERED')
      .reduce((sum, c) => sum + (c.amount_inr || 0), 0);
  }, [activeCases]);

  const revenueRecoveryRatePct = useMemo(() => {
    if (!metrics || totalRevenueAtRiskInr <= 0) return 0;
    return (metrics.total_recovered_amount_inr / totalRevenueAtRiskInr) * 100;
  }, [metrics, totalRevenueAtRiskInr]);

  // Derive category revenue breakdown dynamically from active cases
  const categoryRevenueMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of activeCases) {
      const cat = c.failure_category || 'UNKNOWN';
      map[cat] = (map[cat] || 0) + (c.amount_inr || 0);
    }
    return map;
  }, [activeCases]);

  // Operational Attention Queue: Top prioritized actionable cases
  // Ranked: ESCALATED first -> in-flight/ingested -> RECOVERED -> TERMINAL_NO_ACTION
  const attentionCases = useMemo(() => {
    const getStateRank = (state: string): number => {
      if (state === 'ESCALATED') return 1;
      if (state === 'FAILED_INGESTED') return 2;
      if (state === 'ACTION_EXECUTED') return 3;
      if (state === 'RECOVERED') return 4;
      if (state === 'TERMINAL_NO_ACTION') return 5;
      return 6;
    };

    return [...activeCases].sort((a, b) => {
      const rankA = getStateRank(a.state);
      const rankB = getStateRank(b.state);
      if (rankA !== rankB) return rankA - rankB;
      // Within same state tier, prioritize higher money value
      return (b.amount_inr || 0) - (a.amount_inr || 0);
    });
  }, [activeCases]);

  const m = hasEvaluationRun ? metrics : (metrics?.case_source !== 'CANONICAL_EVALUATION' ? metrics : null);
  const isBenchmark = m?.case_source === 'CANONICAL_EVALUATION';

  return (
    <div className="space-y-8 animate-fade-in">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <PageHeader
        title="Payment Recovery Command Center"
        description="Detect revenue leakage across payment dropoffs, enforce bounded recovery policies, and attribute verified gateway cash."
        actions={
          <div className="flex items-center gap-2.5">
            {onSeedDemoBatch && (
              <ActionButton
                label={seedingBatch ? 'Running Evaluation…' : 'Run Controlled Evaluation'}
                variant="secondary"
                size="sm"
                icon={Database}
                loading={seedingBatch}
                onClick={onSeedDemoBatch}
                aria-label="Run controlled canonical recovery evaluation"
              />
            )}
            <a
              href={getMerchantStorefrontUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded text-xs font-semibold text-white bg-primary-600 hover:bg-primary-500 transition-colors shadow-sm"
              aria-label="Open external merchant storefront demonstration in a new tab"
            >
              <Store className="w-3.5 h-3.5" />
              <span>Open Merchant Storefront</span>
              <ExternalLink className="w-3 h-3 text-white/70" />
            </a>
          </div>
        }
      />

      {/* ── Core Operating Principle Banner ─────────────────────────────── */}
      <div className="bg-surface-base border border-white/[0.06] rounded-lg p-3.5 px-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="font-mono text-guard-text font-semibold uppercase tracking-wider">
            Architecture Boundary:
          </span>
          <span className="text-[#9CA3AF]">
            LLM recommends. Deterministic guardrails authorize. Gateway verifies.
          </span>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-mono shrink-0">
          <span className="flex items-center gap-1.5 text-ai-text">
            <Bot className="w-3.5 h-3.5" />
            Violet = AI Advisory
          </span>
          <span className="flex items-center gap-1.5 text-guard-text">
            <Shield className="w-3.5 h-3.5" />
            Teal = Guardrail Gate
          </span>
          <span className="flex items-center gap-1.5 text-recover-text">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Emerald = Captured Cash
          </span>
        </div>
      </div>

      {/* ── Initial Empty State (When no evaluation or cases exist yet) ──── */}
      {!metricsLoading && !casesLoading && (!hasEvaluationRun && activeCases.length === 0) ? (
        <div className="bg-surface-base border border-white/[0.06] rounded-xl p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center mx-auto text-guard-text">
            <Database className="w-6 h-6" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="text-base font-semibold text-[#F0F2F5]">
              No evaluation run yet
            </h3>
            <p className="text-xs text-[#9CA3AF] leading-relaxed">
              Run the controlled evaluation to populate recovery metrics and observe pipeline state machine decisions, or receive live merchant checkout failures.
            </p>
          </div>
          {onSeedDemoBatch && (
            <div className="pt-2">
              <ActionButton
                label={seedingBatch ? 'Running Evaluation…' : 'Run Controlled Evaluation'}
                variant="primary"
                size="md"
                icon={Database}
                loading={seedingBatch}
                onClick={onSeedDemoBatch}
              />
            </div>
          )}
        </div>
      ) : (
        <>
          {/* ── Primary KPI Ribbon (5 Metrics, Strong Financial Hierarchy) ──── */}
          <section aria-label="Key Performance Indicators">
            {metricsLoading || !m ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <KpiCardSkeleton key={i} />
                ))}
              </div>
            ) : isBenchmark ? (
              /* ── Canonical Benchmark Evaluator Metrics (Truthful Semantics) ── */
              <div className="space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  {/* 1. Evaluation Revenue at Risk */}
                  <KpiCard
                    label="Revenue at Risk"
                    value={
                      <MoneyValue
                        amountInr={m.total_at_risk_amount_inr ?? totalRevenueAtRiskInr}
                        variant="at-risk"
                        size="xl"
                      />
                    }
                    subValue={`${m.total_cases} evaluation cases`}
                    footer={
                      <span>
                        Eligible: <strong className="text-[#9CA3AF] font-mono font-medium">₹{(m.eligible_opportunity_amount_inr || 0).toLocaleString('en-IN')}</strong> ({m.eligible_cases || 0} cases)
                      </span>
                    }
                    accent="risk"
                    icon={<IndianRupee className="w-4 h-4 text-risk-text" />}
                  />

                  {/* 2. Recovered Eligible Revenue - Explicitly marked Evaluation Recovered */}
                  <KpiCard
                    label="Evaluation Recovered"
                    value={
                      <MoneyValue
                        amountInr={m.total_recovered_amount_inr}
                        variant="recovered"
                        size="xl"
                      />
                    }
                    subValue="Controlled Evaluation Evidence"
                    footer={`${m.evaluation_recovered_cases ?? m.recovered_cases ?? 0} of ${m.eligible_cases || 0} eligible cases recovered`}
                    accent="recover"
                    icon={<TrendingUp className="w-4 h-4 text-recover-text" />}
                  />

                  {/* 3. Primary Evaluation Metric: Eligible Opportunity Recovery */}
                  <KpiCard
                    label="Eligible Opportunity Recovery"
                    value={
                      <span className="font-mono text-guard-text font-bold text-[24px]">
                        {(m.eligible_opportunity_recovery_rate_pct ?? m.recovery_rate_pct ?? 0).toFixed(2)}%
                      </span>
                    }
                    subValue="Primary Evaluation Metric"
                    footer={`₹${m.total_recovered_amount_inr.toLocaleString('en-IN')} / ₹${(m.eligible_opportunity_amount_inr || 0).toLocaleString('en-IN')}`}
                    accent="guard"
                    icon={<PercentBadge className="w-4 h-4 text-guard-text" />}
                  />

                  {/* 4. Overall Case Conversion */}
                  <KpiCard
                    label="Overall Case Recovery"
                    value={
                      <span className="font-mono text-[#F0F2F5] font-bold text-[24px]">
                        {(m.overall_case_recovery_rate_pct || 0).toFixed(1)}%
                      </span>
                    }
                    subValue={`${m.recovered_cases} of ${m.total_cases} total cases`}
                    footer={`Eligible case rate: ${(m.eligible_case_recovery_rate_pct || 0).toFixed(1)}%`}
                    accent="none"
                    icon={<Shield className="w-4 h-4 text-[#9CA3AF]" />}
                  />

                  {/* 5. Gated / Safeguarded Compliance Operations */}
                  <KpiCard
                    label="Operations Gated"
                    value={
                      <span className="font-mono text-halt-text font-bold text-[24px]">
                        {(m.escalated_cases || 0) + (m.terminal_no_action_cases || 0)} Gated
                      </span>
                    }
                    subValue={`${m.escalated_cases || 0} escalated · ${m.terminal_no_action_cases || 0} safe halts`}
                    footer={`Protected Volume: ₹${((m.escalated_amount_inr || 0) + (m.terminal_amount_inr || 0)).toLocaleString('en-IN')}`}
                    accent="halt"
                    icon={<ShieldCheck className="w-4 h-4 text-halt-text" />}
                  />
                </div>

                {/* Supporting Counts Strip */}
                <div className="bg-surface-raised border border-white/[0.06] rounded-md px-3.5 py-2 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
                  <span className="text-[#9CA3AF]">
                    Cohort Breakdown: <strong className="text-white">{m.total_cases} Total</strong>
                  </span>
                  <div className="flex flex-wrap items-center gap-3 text-[10px]">
                    <span className="text-guard-text">Eligible: <strong>{m.eligible_cases || 0}</strong></span>
                    <span className="text-recover-text">Recovered: <strong>{m.recovered_cases || 0}</strong></span>
                    <span className="text-amber-300">Escalated: <strong>{m.escalated_cases || 0}</strong></span>
                    <span className="text-rose-400">Terminal Halts: <strong>{m.terminal_no_action_cases || 0}</strong></span>
                  </div>
                </div>
              </div>
            ) : (
              /* ── Live / Operational Recovery Metrics ── */
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {/* 1. Revenue at Risk */}
                <KpiCard
                  label="Revenue at Risk"
                  value={
                    <MoneyValue
                      amountInr={totalRevenueAtRiskInr}
                      variant="at-risk"
                      size="xl"
                    />
                  }
                  subValue={`${m.total_cases} failed transactions detected`}
                  footer={
                    <span>
                      Pending: <strong className="text-risk-text font-mono font-medium">₹{unrecoveredRevenueAtRiskInr.toLocaleString('en-IN')}</strong>
                    </span>
                  }
                  accent="risk"
                  icon={<IndianRupee className="w-4 h-4 text-risk-text" />}
                />

                {/* 2. Recovered Revenue */}
                <KpiCard
                  label="Live Captured Revenue"
                  value={
                    <MoneyValue
                      amountInr={m.total_recovered_amount_inr}
                      variant="recovered"
                      size="xl"
                    />
                  }
                  subValue="100% gateway captured & verified"
                  footer={`${m.recovered_cases} of ${m.total_cases} cases recovered`}
                  accent="recover"
                  icon={<TrendingUp className="w-4 h-4 text-recover-text" />}
                />

                {/* 3. Operational Case Recovery Rate */}
                <KpiCard
                  label="Operational Case Recovery Rate"
                  value={
                    <span className="font-mono text-guard-text font-bold text-[24px]">
                      {revenueRecoveryRatePct.toFixed(1)}%
                    </span>
                  }
                  subValue={`Case conversion: ${m.recovery_rate_pct.toFixed(1)}%`}
                  footer={`${m.recovered_cases} of ${m.total_cases} operational cases`}
                  accent="guard"
                  icon={<PercentBadge className="w-4 h-4 text-guard-text" />}
                />

                {/* 4. Active Recovery Interventions */}
                <KpiCard
                  label="Active Links"
                  value={
                    <span className="font-mono text-[#F0F2F5] font-bold text-[24px]">
                      {m.active_recovery_links}
                    </span>
                  }
                  subValue="In-flight customer links"
                  footer="Single-link limit enforced"
                  accent="none"
                  icon={<Link2 className="w-4 h-4 text-[#9CA3AF]" />}
                />

                {/* 5. Human Attention / Escalated */}
                <KpiCard
                  label="Operations Gated"
                  value={
                    <span className="font-mono text-halt-text font-bold text-[24px]">
                      {m.escalated_cases}
                    </span>
                  }
                  subValue={`${m.terminal_no_action_cases} compliance halts`}
                  footer="High-value / AML risk protected"
                  accent="halt"
                  icon={<ShieldCheck className="w-4 h-4 text-halt-text" />}
                />
              </div>
            )}
          </section>

      {/* ── Canonical Evaluation Recovery Rate & Measurement Breakdown ──── */}
      {isBenchmark && m && (
        <section
          aria-label="Evaluation Recovery Rate Breakdown"
          className="bg-surface-base border border-white/[0.08] rounded-lg p-5 space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-white/[0.06]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-guard-text" />
                <h3 className="text-[13px] font-semibold text-[#F0F2F5]">
                  Controlled Evaluation Recovery Rate &amp; Measurement Semantics
                </h3>
              </div>
              <p className="text-[11px] text-[#9CA3AF] mt-0.5">
                Primary Eligible Metric vs Gross Portfolio Metrics
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Metric 1: Primary - Eligible Opportunity Recovery */}
            <div className="bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.30)] rounded-lg p-4 flex flex-col justify-between space-y-2">
              <div>
                <div className="flex items-center justify-between text-[10px] font-mono text-guard-text font-semibold uppercase">
                  <span>Primary Metric</span>
                  <span className="px-1.5 py-0.2 rounded bg-guard-muted text-guard-text border border-guard-border">
                    Eligible
                  </span>
                </div>
                <div className="text-[12px] font-medium text-[#F0F2F5] mt-1">
                  Eligible Opportunity Recovery
                </div>
                <div className="font-mono text-[26px] font-bold text-guard-text mt-2">
                  {(m.eligible_opportunity_recovery_rate_pct ?? m.recovery_rate_pct ?? 0).toFixed(2)}%
                </div>
                <div className="text-[11px] font-mono text-[#5EEAD4] mt-1">
                  ₹{(m.total_recovered_amount_inr || 0).toLocaleString('en-IN')} / ₹{(m.eligible_opportunity_amount_inr ?? m.total_at_risk_amount_inr ?? 0).toLocaleString('en-IN')}
                </div>
              </div>
              <p className="text-[10px] text-[#9CA3AF] leading-relaxed pt-2 border-t border-white/[0.06]">
                Evaluates recovery strictly where recovery is safe and compliant. Excludes policy halts and terminal conditions.
              </p>
            </div>

            {/* Metric 2: Eligible Case Recovery */}
            <div className="bg-surface-raised border border-white/[0.06] rounded-lg p-4 flex flex-col justify-between space-y-2">
              <div>
                <div className="text-[10px] font-mono text-[#9CA3AF] uppercase font-semibold">
                  Eligible Conversion
                </div>
                <div className="text-[12px] font-medium text-[#F0F2F5] mt-1">
                  Eligible Case Recovery Rate
                </div>
                <div className="font-mono text-[26px] font-bold text-[#F0F2F5] mt-2">
                  {(m.eligible_case_recovery_rate_pct ?? 0).toFixed(1)}%
                </div>
                <div className="text-[11px] font-mono text-[#9CA3AF] mt-1">
                  {m.evaluation_recovered_cases ?? m.recovered_cases ?? 0} of {m.eligible_cases ?? 0} eligible cases
                </div>
              </div>
              <p className="text-[10px] text-[#6B7280] leading-relaxed pt-2 border-t border-white/[0.06]">
                Proportion of policy-eligible cases converted to successful recovery.
              </p>
            </div>

            {/* Metric 3: Overall Case Recovery */}
            <div className="bg-surface-raised border border-white/[0.06] rounded-lg p-4 flex flex-col justify-between space-y-2">
              <div>
                <div className="text-[10px] font-mono text-[#9CA3AF] uppercase font-semibold">
                  Batch Conversion
                </div>
                <div className="text-[12px] font-medium text-[#F0F2F5] mt-1">
                  Overall Case Recovery Rate
                </div>
                <div className="font-mono text-[26px] font-bold text-[#D1D5DB] mt-2">
                  {(m.overall_case_recovery_rate_pct ?? m.recovery_rate_pct ?? 0).toFixed(1)}%
                </div>
                <div className="text-[11px] font-mono text-[#9CA3AF] mt-1">
                  {m.recovered_cases ?? 0} of {m.total_cases ?? 0} total cases
                </div>
              </div>
              <p className="text-[10px] text-[#6B7280] leading-relaxed pt-2 border-t border-white/[0.06]">
                Overall conversion across all evaluation cases including policy-halted and terminal cases.
              </p>
            </div>

            {/* Metric 4: Portfolio Revenue Recovery */}
            <div className="bg-surface-raised border border-white/[0.06] rounded-lg p-4 flex flex-col justify-between space-y-2">
              <div>
                <div className="text-[10px] font-mono text-[#9CA3AF] uppercase font-semibold">
                  Portfolio Revenue
                </div>
                <div className="text-[12px] font-medium text-[#F0F2F5] mt-1">
                  Gross Portfolio Recovery Rate
                </div>
                <div className="font-mono text-[26px] font-bold text-[#D1D5DB] mt-2">
                  {(m.portfolio_revenue_recovery_rate_pct ?? revenueRecoveryRatePct ?? 0).toFixed(1)}%
                </div>
                <div className="text-[11px] font-mono text-[#9CA3AF] mt-1">
                  ₹{(m.total_recovered_amount_inr || 0).toLocaleString('en-IN')} / ₹{(m.total_at_risk_amount_inr ?? totalRevenueAtRiskInr ?? 0).toLocaleString('en-IN')}
                </div>
              </div>
              <p className="text-[10px] text-[#6B7280] leading-relaxed pt-2 border-t border-white/[0.06]">
                Gross revenue recovered versus total volume at risk, reflecting protective guardrails on high-value transactions.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Recovery Pipeline Story & Funnel ────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <SectionHeader
          title="Revenue Recovery Pipeline Story"
          subtitle="From gateway failure detection to verified captured cash"
          action={
            <button
              onClick={onNavigateToArchitecture}
              className="flex items-center gap-1 text-[11px] font-mono text-[#6B7280] hover:text-[#9CA3AF] transition-colors"
            >
              Inspect Invariants <ChevronRight className="w-3.5 h-3.5" />
            </button>
          }
        />

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
          {/* Stage 1: Detect Revenue at Risk */}
          <div className="bg-surface-raised border border-white/[0.08] rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-[10px] font-mono text-[#4B5563] mb-1">
                <span>STAGE 01</span>
                <span className="text-risk-text font-bold">100% INGESTED</span>
              </div>
              <div className="text-[13px] font-semibold text-[#F0F2F5]">
                1. Detect Leakage
              </div>
              <p className="text-[11px] text-[#6B7280] mt-1 leading-snug">
                Signature verified HMAC webhooks & idempotency check.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-baseline justify-between">
              <span className="text-[11px] text-[#4B5563]">Detected At Risk:</span>
              <span className="font-mono text-[12px] font-bold text-risk-text">
                {m ? `${m.total_cases} cases (₹${(m.total_at_risk_amount_inr ?? totalRevenueAtRiskInr).toLocaleString('en-IN')})` : '—'}
              </span>
            </div>
          </div>

          {/* Stage 2: AI Triage & Diagnosis */}
          <div className="bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.22)] rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-[10px] font-mono text-ai-text mb-1">
                <span>STAGE 02 · ADVISORY</span>
                <span className="font-bold">MCP READ-ONLY</span>
              </div>
              <div className="text-[13px] font-semibold text-ai-text">
                2. AI Diagnosis
              </div>
              <p className="text-[11px] text-[#6B7280] mt-1 leading-snug">
                C1–C5 failure taxonomy mapping & LLM policy proposal.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(124,58,237,0.12)] flex items-baseline justify-between">
              <span className="text-[11px] text-[#4B5563]">Triaged Cases:</span>
              <span className="font-mono text-[12px] font-bold text-ai-text">
                {m ? `${m.eligible_cases ?? Math.max(0, m.total_cases - m.terminal_no_action_cases)} eligible` : '—'}
              </span>
            </div>
          </div>

          {/* Stage 3: Deterministic Guardrail Authorization */}
          <div className="bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.22)] rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-[10px] font-mono text-guard-text mb-1">
                <span>STAGE 03 · GUARDRAIL GATE</span>
                <span className="font-bold">GUARDRAIL CHECKS</span>
              </div>
              <div className="text-[13px] font-semibold text-guard-text">
                3. Bounded Action
              </div>
              <p className="text-[11px] text-[#6B7280] mt-1 leading-snug">
                Single-link limits, cooldown checks, and Razorpay API dispatch.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(13,148,136,0.12)] flex items-baseline justify-between">
              <span className="text-[11px] text-[#4B5563]">Authorized Links:</span>
              <span className="font-mono text-[12px] font-bold text-guard-text">
                {m ? `${m.active_recovery_links} executed` : '—'}
              </span>
            </div>
          </div>

          {/* Stage 4: Verified Captured Revenue */}
          <div className="bg-[rgba(5,150,105,0.06)] border border-[rgba(5,150,105,0.22)] rounded-lg p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-[10px] font-mono text-recover-text mb-1">
                <span>STAGE 04 · CAPTURED</span>
                <span className="font-bold">ATTRIBUTED</span>
              </div>
              <div className="text-[13px] font-semibold text-recover-text">
                4. Verified Cash
              </div>
              <p className="text-[11px] text-[#6B7280] mt-1 leading-snug">
                Razorpay payment.captured webhook confirms verified recovered revenue.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[rgba(5,150,105,0.12)] flex items-baseline justify-between">
              <span className="text-[11px] text-[#4B5563]">Recovered Cash:</span>
              <span className="font-mono text-[12px] font-bold text-recover-text">
                {m
                  ? isBenchmark
                    ? `₹${m.total_recovered_amount_inr.toLocaleString('en-IN')} (${(m.eligible_opportunity_recovery_rate_pct ?? m.recovery_rate_pct ?? 0).toFixed(1)}% eligible)`
                    : `₹${m.total_recovered_amount_inr.toLocaleString('en-IN')}`
                  : '—'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Operations Queue & Live Merchant Recovery Showcase (2-Column Grid) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left 2 Cols: Operations Attention Queue */}
        <section className="lg:col-span-2 bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
            <div>
              <h3 className="text-[13px] font-semibold text-[#F0F2F5]">
                Operations Attention Queue
              </h3>
              <p className="text-[11px] text-[#4B5563] mt-0.5">
                Prioritized failure cases requiring operational review or tracking
              </p>
            </div>
            <span className="text-[10px] font-mono text-[#9CA3AF] bg-surface-raised px-2.5 py-1 rounded border border-white/[0.06]">
              Top 5 Priority Cases
            </span>
          </div>

          {/* Cases Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse" aria-label="Operations attention cases">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10px] font-mono uppercase tracking-wider text-[#4B5563]">
                  <th className="py-2.5 px-2">Case ID</th>
                  <th className="py-2.5 px-2">Amount</th>
                  <th className="py-2.5 px-2">Taxonomy</th>
                  <th className="py-2.5 px-2">State</th>
                  <th className="py-2.5 px-2">Authorized Policy</th>
                  <th className="py-2.5 px-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {casesLoading ? (
                  [1, 2, 3, 4, 5].map((i) => <TableRowSkeleton key={i} columns={6} />)
                ) : attentionCases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8">
                      <EmptyState
                        compact
                        title="No priority cases in this queue"
                        description="All active cases in this filter have completed or are normal."
                      />
                    </td>
                  </tr>
                ) : (
                  attentionCases.slice(0, 5).map((c) => {
                    const isTriaging = triageLoadingCaseId === c.case_id;

                    return (
                      <tr
                        key={c.case_id}
                        onClick={() => onSelectCase(c.case_id)}
                        className="hover:bg-white/[0.02] cursor-pointer transition-colors group"
                      >
                        <td className="py-3 px-2 font-mono text-[11px] text-ai-text group-hover:underline">
                          {c.case_id}
                        </td>
                        <td className="py-3 px-2">
                          <MoneyValue
                            amountInr={c.amount_inr}
                            variant={c.state === 'RECOVERED' ? 'recovered' : c.amount_inr >= 50000 ? 'at-risk' : 'neutral'}
                            size="sm"
                          />
                        </td>
                        <td className="py-3 px-2">
                          <CategoryBadge category={c.failure_category} />
                        </td>
                        <td className="py-3 px-2">
                          <StateBadge state={c.state} size="sm" />
                        </td>
                        <td className="py-3 px-2">
                          <PolicyBadge policy={c.validated_policy_id} context="guard" showIcon={false} />
                        </td>
                        <td className="py-3 px-2 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-2">
                            {c.state === 'FAILED_INGESTED' && (
                              <button
                                onClick={() => onTriggerTriage(c.case_id)}
                                disabled={isTriaging}
                                className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold text-ai-text bg-ai-muted hover:bg-ai-base/20 border border-ai-border rounded transition-colors disabled:opacity-50"
                              >
                                <Zap className={`w-3 h-3 ${isTriaging ? 'animate-spin' : ''}`} />
                                {isTriaging ? '…' : 'Triage'}
                              </button>
                            )}
                            <button
                              onClick={() => onSelectCase(c.case_id)}
                              className="text-[11px] font-mono text-[#6B7280] group-hover:text-guard-text flex items-center gap-0.5 transition-colors"
                            >
                              Inspect <ArrowRight className="w-3 h-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between text-[11px]">
            <span className="text-[#4B5563] font-mono">
              Showing top {Math.min(5, attentionCases.length)} of {activeCases.length} pipeline cases
            </span>
            <button
              onClick={onNavigateToCases}
              className="text-guard-text hover:underline flex items-center gap-1 font-mono font-medium"
            >
              View Full Pipeline ({activeCases.length} Cases) <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </section>

        {/* Right 1 Col: Live Merchant Recovery Showcase */}
        <div className="space-y-4">
          <ZoneCard
            zone="recover"
            label="Live Merchant Recovery"
            icon={Store}
            description="External Merchant Checkout Integration"
          >
            <div className="space-y-3 text-[12px]">
              <div className="font-semibold text-[#F0F2F5] text-[13px] leading-tight flex items-center justify-between">
                <span>Real Merchant Storefront</span>
                <span className="px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-300 font-mono text-[10px] font-semibold border border-teal-500/30">
                  Razorpay Test Mode
                </span>
              </div>
              <p className="text-[#9CA3AF] text-[11px] leading-relaxed">
                Experience real-world recovery flow from the customer perspective on the external merchant store:
              </p>

              <ul className="space-y-1.5 text-[11px] text-[#9CA3AF] font-mono pl-1">
                <li className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-risk-text" />
                  <span>Real merchant checkout failure</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-guard-text" />
                  <span>PaymentFlow recovery decision</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-guard-text" />
                  <span>Razorpay Payment Link</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400" />
                  <span>Native notification handoff</span>
                </li>
                <li className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-recover-text" />
                  <span>Authoritative gateway verification</span>
                </li>
              </ul>

              <div className="pt-2">
                <a
                  href={getMerchantStorefrontUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 w-full px-4 py-2 rounded text-xs font-semibold text-white bg-primary-600 hover:bg-primary-500 transition-colors shadow-md shadow-primary-900/20"
                  aria-label="Open Merchant Storefront in a new tab"
                >
                  <Store className="w-3.5 h-3.5" />
                  <span>Open Merchant Storefront</span>
                  <ExternalLink className="w-3.5 h-3.5 text-white/70" />
                </a>
              </div>
            </div>
          </ZoneCard>

          {/* Quick Architecture Anchor */}
          <div className="bg-surface-base border border-white/[0.06] rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-[#6B7280] uppercase tracking-wider">
                Safety Invariants
              </span>
              <span className="text-[10px] font-mono text-guard-text font-bold">ACTIVE & ENFORCED</span>
            </div>
            <p className="text-[11px] text-[#4B5563] leading-snug">
              Strictly enforces ₹50k escalation threshold, 1-link limit, and constant-time HMAC webhook verification.
            </p>
            <button
              onClick={onNavigateToArchitecture}
              className="text-[11px] font-mono text-[#9CA3AF] hover:text-[#F0F2F5] flex items-center gap-1 transition-colors pt-1"
            >
              Review Guardrail Contracts <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Failure / Revenue Loss Breakdown (C1–C5) ───────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4">
        <SectionHeader
          title="Revenue Leakage Taxonomy Breakdown"
          subtitle="Normalized root causes across payment failures and associated recovery likelihoods"
          badge={m ? `${Object.values(m.category_breakdown).reduce((a, b) => a + b, 0)} Classified` : undefined}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {(['C1', 'C2', 'C3', 'C4', 'C5'] as FailureCategory[]).map((cat) => {
            const meta = CATEGORY_INFO[cat];
            const count = m?.category_breakdown[cat] ?? 0;
            const categoryRevenue = categoryRevenueMap[cat] || 0;
            const pct = m && m.total_cases > 0 ? ((count / m.total_cases) * 100).toFixed(0) : '0';

            return (
              <div
                key={cat}
                className="bg-surface-raised border border-white/[0.06] rounded-lg p-4 flex flex-col justify-between hover:border-white/[0.12] transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <CategoryBadge category={cat} />
                    <span className="font-mono text-[14px] font-bold text-[#F0F2F5]">
                      {count} <span className="text-[10px] font-normal text-[#4B5563]">({pct}%)</span>
                    </span>
                  </div>
                  <h4 className="text-[12px] font-semibold text-[#9CA3AF] mb-1">{meta.name}</h4>
                  <p className="text-[11px] text-[#6B7280] leading-relaxed">
                    {meta.description}
                  </p>
                </div>

                <div className="mt-3 pt-3 border-t border-white/[0.04] space-y-1.5 text-[10px] font-mono">
                  <div className="flex items-center justify-between text-[#4B5563]">
                    <span>At Risk:</span>
                    <span className="text-[#D1D5DB] font-semibold">
                      ₹{categoryRevenue.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#4B5563]">
                    <span>Likelihood:</span>
                    <span className="text-[#9CA3AF]">
                      {meta.recoveryLikelihood}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#4B5563]">
                    <span>Policy:</span>
                    <span className="text-guard-text font-semibold">
                      {meta.defaultPolicy === 'P_CREATE_LINK_IMMEDIATE'
                        ? 'Immediate Link'
                        : meta.defaultPolicy === 'P_CREATE_LINK_DELAYED'
                        ? 'Delayed Link'
                        : meta.defaultPolicy === 'P_ESCALATE_ONLY'
                        ? 'Escalate Only'
                        : meta.defaultPolicy === 'P_NO_ACTION'
                        ? 'No Action'
                        : meta.defaultPolicy}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
        </>
      )}
    </div>
  );
};

/** Minimal Percent Icon Helper */
const PercentBadge: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <line x1="19" y1="5" x2="5" y2="19" />
    <circle cx="6.5" cy="6.5" r="2.5" />
    <circle cx="17.5" cy="17.5" r="2.5" />
  </svg>
);
