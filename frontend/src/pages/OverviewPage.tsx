import React from 'react';
import {
  IndianRupee,
  TrendingUp,
  Link2,
  ShieldCheck,
  ArrowRight,
  BrainCircuit,
  Zap,
  Sparkles,
  Database,
} from 'lucide-react';
import type { CaseSummaryItem, MetricsSummary } from '../types';
import { KpiCard, KpiCardSkeleton } from '../components/common/KpiCard';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { TableRowSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { CATEGORY_INFO, type FailureCategory } from '../types';

interface OverviewPageProps {
  metrics: MetricsSummary | null;
  metricsLoading: boolean;
  recentCases: CaseSummaryItem[];
  casesLoading: boolean;
  onSelectCase: (id: string) => void;
  onNavigateToCases: () => void;
  onNavigateToArchitecture: () => void;
  onNavigateToInteractive?: () => void;
  onTriggerTriage: (id: string) => void;
  triageLoadingCaseId: string | null;
  onSeedDemoBatch?: () => void;
  seedingBatch?: boolean;
}

const formatInr = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v);

// ─── Pipeline Funnel Stage ────────────────────────────────────────────

interface FunnelStage {
  num: string;
  label: string;
  desc: string;
  zone: 'teal' | 'violet' | 'neutral' | 'emerald';
  count: number;
}

const FunnelStageCard: React.FC<{ stage: FunnelStage }> = ({ stage }) => {
  const zoneColors = {
    teal:    'border-[rgba(13,148,136,0.25)] text-guard-text bg-[rgba(13,148,136,0.06)]',
    violet:  'border-[rgba(124,58,237,0.30)] text-ai-text bg-[rgba(124,58,237,0.08)]',
    emerald: 'border-[rgba(5,150,105,0.25)] text-recover-text bg-[rgba(5,150,105,0.06)]',
    neutral: 'border-white/[0.08] text-[#6B7280] bg-surface-raised',
  };

  return (
    <div className={`border rounded-lg p-3 flex flex-col gap-1 ${zoneColors[stage.zone]}`}>
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono text-[#4B5563]">{stage.num}</span>
        <span className="text-[11px] font-mono font-bold">{stage.count}</span>
      </div>
      <div className="text-[11px] font-mono font-semibold uppercase tracking-tight">
        {stage.label}
      </div>
      <p className="text-[10px] text-[#4B5563] leading-snug">{stage.desc}</p>
    </div>
  );
};

// ─── Category Card ─────────────────────────────────────────────────────

const CategoryCard: React.FC<{
  cat: FailureCategory;
  count: number;
}> = ({ cat, count }) => {
  const meta = CATEGORY_INFO[cat];

  const catColors: Record<FailureCategory, { border: string; bg: string; num: string }> = {
    C1: { border: 'border-[rgba(217,119,6,0.20)]',  bg: 'bg-[rgba(217,119,6,0.04)]',  num: 'text-[#FCD34D]' },
    C2: { border: 'border-[rgba(37,99,235,0.20)]',  bg: 'bg-[rgba(37,99,235,0.04)]',  num: 'text-[#93C5FD]' },
    C3: { border: 'border-[rgba(234,88,12,0.20)]',  bg: 'bg-[rgba(234,88,12,0.04)]',  num: 'text-[#FDBA74]' },
    C4: { border: 'border-[rgba(225,29,72,0.20)]',  bg: 'bg-[rgba(225,29,72,0.04)]',  num: 'text-[#FDA4AF]' },
    C5: { border: 'border-[rgba(82,82,91,0.20)]',   bg: 'bg-[rgba(82,82,91,0.04)]',   num: 'text-[#A1A1AA]' },
    UNKNOWN: { border: 'border-white/[0.06]', bg: 'bg-surface-raised', num: 'text-[#6B7280]' },
  };

  const colors = catColors[cat];

  return (
    <div className={`border rounded-lg p-4 flex flex-col gap-2 ${colors.border} ${colors.bg} hover:border-white/[0.14] transition-colors`}>
      <div className="flex items-center justify-between">
        <CategoryBadge category={cat} />
        <span className={`text-[15px] font-mono font-bold ${colors.num}`}>{count}</span>
      </div>
      <h4 className="text-[12px] font-semibold text-[#9CA3AF]">{meta.name}</h4>
      <p className="text-[11px] text-[#4B5563] leading-relaxed">{meta.description}</p>
      <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
        <span className="text-[10px] text-[#4B5563]">Default</span>
        <PolicyBadge policy={meta.defaultPolicy} context="guard" showIcon={false} />
      </div>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────

export const OverviewPage: React.FC<OverviewPageProps> = ({
  metrics,
  metricsLoading,
  recentCases,
  casesLoading,
  onSelectCase,
  onNavigateToCases,
  onNavigateToArchitecture,
  onNavigateToInteractive,
  onTriggerTriage,
  triageLoadingCaseId,
  onSeedDemoBatch,
  seedingBatch = false,
}) => {
  const m = metrics;

  const funnelStages: FunnelStage[] = [
    {
      num: '01', label: 'INGESTED',  zone: 'neutral',
      desc: 'Webhook verified + deduplicated',
      count: m?.total_cases ?? 0,
    },
    {
      num: '02', label: 'CLASSIFIED', zone: 'teal',
      desc: 'C1–C5 taxonomy mapped',
      count: m?.total_cases ?? 0,
    },
    {
      num: '03', label: 'ELIGIBLE',   zone: 'teal',
      desc: '8 deterministic rules checked',
      count: (m?.total_cases ?? 0) - (m?.terminal_no_action_cases ?? 0),
    },
    {
      num: '04', label: 'AI TRIAGE',  zone: 'violet',
      desc: 'LLM proposes policy via MCP',
      count: (m?.active_recovery_links ?? 0) + (m?.recovered_cases ?? 0),
    },
    {
      num: '05', label: 'GUARDRAIL',  zone: 'teal',
      desc: 'PolicyGuardrailEngine authorizes',
      count: (m?.active_recovery_links ?? 0) + (m?.recovered_cases ?? 0),
    },
    {
      num: '06', label: 'RECOVERED',  zone: 'emerald',
      desc: 'Captured · attributed',
      count: m?.recovered_cases ?? 0,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Section Header with Quick Actions ─────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-1 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono uppercase tracking-widest text-[#6B7280]">
            Autonomous Recovery Command Center
          </span>
          <span className="text-[#4B5563] text-xs hidden sm:inline">·</span>
          <span className="text-[11px] font-mono text-guard-text hidden sm:inline">
            Captured-only attribution
          </span>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          {onSeedDemoBatch && (
            <button
              onClick={onSeedDemoBatch}
              disabled={seedingBatch}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#D1D5DB] bg-surface-raised hover:bg-white/[0.06] border border-white/[0.08] rounded-md transition-colors disabled:opacity-50"
            >
              <Database className={`w-3.5 h-3.5 text-guard-text ${seedingBatch ? 'animate-spin' : ''}`} />
              {seedingBatch ? 'Seeding...' : 'Seed 15-Case Batch'}
            </button>
          )}

          {onNavigateToInteractive && (
            <button
              onClick={onNavigateToInteractive}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-[11px] font-semibold text-white bg-ai-base hover:bg-purple-600 rounded-md transition-colors shadow-sm shadow-ai-base/20"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Launch Live Demo
            </button>
          )}
        </div>
      </div>

      {/* ── KPI Cards ────────────────────────────────────────────────── */}
      {metricsLoading || !m ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <KpiCardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Revenue Recovered"
            value={formatInr(m.total_recovered_amount_inr)}
            subValue="100% captured · verified"
            footer={`${m.recovered_cases} successful cases`}
            accent="recover"
            icon={<IndianRupee className="w-4 h-4" />}
          />
          <KpiCard
            label="Recovery Rate"
            value={`${m.recovery_rate_pct.toFixed(1)}%`}
            subValue={`${m.recovered_cases} of ${m.total_cases} cases`}
            footer={`${m.active_recovery_links} links awaiting customer`}
            accent="guard"
            icon={<TrendingUp className="w-4 h-4" />}
          />
          <KpiCard
            label="Active Links"
            value={String(m.active_recovery_links)}
            subValue="Single-link limit enforced"
            footer={`${m.total_cases} total cases processed`}
            accent="none"
            icon={<Link2 className="w-4 h-4" />}
          />
          <KpiCard
            label="Guardrail Protected"
            value={String(m.escalated_cases + m.terminal_no_action_cases)}
            subValue={`${m.escalated_cases} escalated · ${m.terminal_no_action_cases} halted`}
            footer="Zero unauthorized writes"
            accent="halt"
            icon={<ShieldCheck className="w-4 h-4" />}
          />
        </div>
      )}

      {/* ── Recovery Pipeline Funnel ──────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-[13px] font-semibold text-[#F0F2F5]">Recovery Pipeline</h3>
            <p className="text-[11px] text-[#4B5563] mt-0.5">
              Deterministic state machine · AI advisory at stage 4
            </p>
          </div>
          <button
            onClick={onNavigateToArchitecture}
            className="flex items-center gap-1 text-[11px] text-[#6B7280] hover:text-[#9CA3AF] transition-colors"
          >
            Architecture <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Funnel grid */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
          {funnelStages.map((stage, idx) => (
            <React.Fragment key={stage.num}>
              <FunnelStageCard stage={stage} />
              {idx < funnelStages.length - 1 && (
                <div className="hidden md:flex items-center justify-center -mx-1 z-10">
                  <ArrowRight className={`w-3 h-3 ${
                    idx === 2 ? 'text-ai-base' : 'text-[#4B5563]'
                  }`} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Zone legend */}
        <div className="flex items-center gap-5 mt-4 pt-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-2">
            <div className="w-3 h-px bg-guard-base" />
            <span className="text-[10px] text-[#4B5563] font-mono">Deterministic stages</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-px bg-ai-base" />
            <BrainCircuit className="w-3 h-3 text-ai-text" />
            <span className="text-[10px] text-ai-text font-mono">AI advisory (Stage 04)</span>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <ShieldCheck className="w-3.5 h-3.5 text-guard-text" />
            <span className="text-[10px] text-guard-text font-mono">10 Safety Invariants Active</span>
          </div>
        </div>
      </section>

      {/* ── Category Matrix ───────────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-semibold text-[#F0F2F5]">
            Failure Taxonomy (C1–C5)
          </h3>
          <span className="text-[11px] text-[#4B5563]">
            {m ? `${Object.values(m.category_breakdown).reduce((a, b) => a + b, 0)} classified events` : 'Loading…'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {(['C1', 'C2', 'C3', 'C4', 'C5'] as FailureCategory[]).map((cat) => (
            <CategoryCard
              key={cat}
              cat={cat}
              count={m?.category_breakdown[cat] ?? 0}
            />
          ))}
        </div>
      </section>

      {/* ── Recent Cases ──────────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-[13px] font-semibold text-[#F0F2F5]">Recent Recovery Cases</h3>
            <p className="text-[11px] text-[#4B5563] mt-0.5">
              Live cases across all states
            </p>
          </div>
          <button
            onClick={onNavigateToCases}
            className="flex items-center gap-1 text-[11px] text-[#6B7280] hover:text-[#9CA3AF] transition-colors"
          >
            All cases ({recentCases.length}) <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" aria-label="Recent recovery cases">
            <thead>
              <tr className="border-b border-white/[0.06] text-[10px] font-mono uppercase tracking-wider text-[#4B5563]">
                <th className="py-2 px-2">Case ID</th>
                <th className="py-2 px-2">Amount</th>
                <th className="py-2 px-2">Category</th>
                <th className="py-2 px-2">State</th>
                <th className="py-2 px-2">Validated Policy</th>
                <th className="py-2 px-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {casesLoading ? (
                [1, 2, 3, 4, 5].map((i) => <TableRowSkeleton key={i} />)
              ) : recentCases.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8">
                    <EmptyState
                      title="No cases in pipeline"
                      description="Ingest a payment.failed webhook or seed the demo batch to begin."
                    />
                  </td>
                </tr>
              ) : (
                recentCases.slice(0, 8).map((c) => {
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
                      <td className="py-3 px-2 font-mono text-[12px] font-semibold text-[#F0F2F5]">
                        ₹{c.amount_inr.toFixed(2)}
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
                              className="flex items-center gap-1 px-2 py-1 text-[10px] font-semibold text-ai-text bg-[rgba(124,58,237,0.10)] hover:bg-[rgba(124,58,237,0.18)] border border-[rgba(124,58,237,0.25)] rounded transition-colors disabled:opacity-50"
                            >
                              <Zap className={`w-3 h-3 ${isTriaging ? 'animate-spin-slow' : ''}`} />
                              {isTriaging ? '…' : 'Triage'}
                            </button>
                          )}
                          <button
                            onClick={() => onSelectCase(c.case_id)}
                            className="text-[10px] text-[#4B5563] hover:text-[#9CA3AF] transition-colors"
                          >
                            Inspect →
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
      </section>
    </div>
  );
};
