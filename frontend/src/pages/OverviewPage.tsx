import React from 'react';
import {
  TrendingUp,
  IndianRupee,
  Link as LinkIcon,
  ArrowRight,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import type { CaseSummaryItem, MetricsSummary } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { KpiCardSkeleton, TableRowSkeleton } from '../components/common/Skeleton';
import { CATEGORY_INFO, type FailureCategory } from '../types';

interface OverviewPageProps {
  metrics: MetricsSummary | null;
  metricsLoading: boolean;
  recentCases: CaseSummaryItem[];
  casesLoading: boolean;
  onSelectCase: (caseId: string) => void;
  onNavigateToCases: () => void;
  onNavigateToMcp: () => void;
  onTriggerTriage: (caseId: string) => void;
  triageLoadingCaseId: string | null;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  metrics,
  metricsLoading,
  recentCases,
  casesLoading,
  onSelectCase,
  onNavigateToCases,
  onNavigateToMcp,
  onTriggerTriage,
  triageLoadingCaseId,
}) => {
  // Format monetary numbers
  const formatInr = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* 1. Hero KPI Grid */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase font-mono tracking-wider">
            Operational Recovery Performance
          </h3>
          <span className="text-[11px] text-zinc-500 font-mono">
            Deterministic Captured Attribution
          </span>
        </div>

        {metricsLoading || !metrics ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCardSkeleton />
            <KpiCardSkeleton />
            <KpiCardSkeleton />
            <KpiCardSkeleton />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* KPI 1: Recovered Revenue */}
            <div className="p-5 rounded-xl bg-background-surface border border-emerald-500/20 shadow-glow-success relative overflow-hidden flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-emerald-400">Total Revenue Recovered</span>
                <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <IndianRupee className="w-4 h-4" />
                </span>
              </div>
              <div className="my-2">
                <div className="text-2xl font-extrabold text-gray-100 tracking-tight font-mono">
                  {formatInr(metrics.total_recovered_amount_inr)}
                </div>
                <div className="text-[11px] text-emerald-400/80 font-mono mt-1">
                  100% Captured & Settled Verification
                </div>
              </div>
              <div className="text-[10px] text-zinc-400 flex items-center gap-1 border-t border-border-subtle pt-2">
                <span>{metrics.recovered_cases} successful recovery cases</span>
              </div>
            </div>

            {/* KPI 2: Recovery Conversion Rate */}
            <div className="p-5 rounded-xl bg-background-surface border border-brand-500/20 shadow-glow-brand flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-brand-400">Recovery Conversion Rate</span>
                <span className="p-2 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  <TrendingUp className="w-4 h-4" />
                </span>
              </div>
              <div className="my-2">
                <div className="text-2xl font-extrabold text-gray-100 tracking-tight font-mono">
                  {metrics.recovery_rate_pct.toFixed(1)}%
                </div>
                <div className="text-[11px] text-brand-400/80 font-mono mt-1">
                  {metrics.recovered_cases} of {metrics.total_cases} failed payments
                </div>
              </div>
              <div className="text-[10px] text-zinc-400 flex items-center gap-1 border-t border-border-subtle pt-2">
                <span>{metrics.active_recovery_links} active links awaiting customer</span>
              </div>
            </div>

            {/* KPI 3: Active Links & In-Flight */}
            <div className="p-5 rounded-xl bg-background-surface border border-border-subtle flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-400">Active Recovery Links</span>
                <span className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <LinkIcon className="w-4 h-4" />
                </span>
              </div>
              <div className="my-2">
                <div className="text-2xl font-extrabold text-gray-100 tracking-tight font-mono">
                  {metrics.active_recovery_links}
                </div>
                <div className="text-[11px] text-zinc-400 font-mono mt-1">
                  Single-link limit strictly enforced
                </div>
              </div>
              <div className="text-[10px] text-zinc-500 flex items-center gap-1 border-t border-border-subtle pt-2">
                <span>Total processed cases: {metrics.total_cases}</span>
              </div>
            </div>

            {/* KPI 4: Guardrail Protected / Escalated */}
            <div className="p-5 rounded-xl bg-background-surface border border-border-subtle flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-400">Guardrail Enforced</span>
                <span className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  <ShieldCheck className="w-4 h-4" />
                </span>
              </div>
              <div className="my-2">
                <div className="text-2xl font-extrabold text-gray-100 tracking-tight font-mono">
                  {metrics.escalated_cases + metrics.terminal_no_action_cases}
                </div>
                <div className="text-[11px] text-zinc-400 font-mono mt-1">
                  {metrics.escalated_cases} Risk Escalated · {metrics.terminal_no_action_cases} Halted Safe
                </div>
              </div>
              <div className="text-[10px] text-zinc-500 flex items-center gap-1 border-t border-border-subtle pt-2">
                <span>Zero unauthorized payment writes</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 2. Recovery Pipeline State Funnel */}
      <section className="p-5 rounded-xl bg-background-surface border border-border-subtle">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-gray-100">Recovery Lifecycle Funnel</h3>
            <p className="text-xs text-zinc-400">
              State transitions verified by deterministic state machine & guardrails
            </p>
          </div>
          <button
            onClick={onNavigateToMcp}
            className="flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 font-medium transition-colors"
          >
            <span>View Guardrail Rules</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {[
            {
              step: '01',
              title: 'FAILED_INGESTED',
              desc: 'Webhook signature verified & deduplicated',
              count: metrics?.total_cases ?? 0,
              badgeClass: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
            },
            {
              step: '02',
              title: 'CONTEXT_RETRIEVED',
              desc: 'Gateway details enriched & C1–C5 classified',
              count: metrics?.total_cases ?? 0,
              badgeClass: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
            },
            {
              step: '03',
              title: 'ELIGIBILITY_CHECKED',
              desc: '8 deterministic rules & cooldown checks',
              count: (metrics?.total_cases ?? 0) - (metrics?.terminal_no_action_cases ?? 0),
              badgeClass: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
            },
            {
              step: '04',
              title: 'ACTION_APPROVED',
              desc: 'AI proposed & GuardrailEngine authorized',
              count: (metrics?.active_recovery_links ?? 0) + (metrics?.recovered_cases ?? 0),
              badgeClass: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
            },
            {
              step: '05',
              title: 'ACTION_EXECUTED',
              desc: 'Razorpay Payment Link generated & sent',
              count: (metrics?.active_recovery_links ?? 0) + (metrics?.recovered_cases ?? 0),
              badgeClass: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
            },
            {
              step: '06',
              title: 'RECOVERED',
              desc: 'Captured payment verified & attributed',
              count: metrics?.recovered_cases ?? 0,
              badgeClass: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
            },
          ].map((s, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-background-elevated/40 border border-border flex flex-col justify-between"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono text-zinc-500">{s.step}</span>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${s.badgeClass}`}>
                  {s.count} Cases
                </span>
              </div>
              <div className="text-xs font-semibold text-gray-200 font-mono tracking-tight">
                {s.title}
              </div>
              <p className="text-[10px] text-zinc-400 mt-1 leading-snug">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 3. Failure Intelligence (C1–C5 Breakdown) */}
      <section className="p-5 rounded-xl bg-background-surface border border-border-subtle">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-gray-100">Failure Taxonomy & Intelligence (C1–C5)</h3>
            <p className="text-xs text-zinc-400">
              Deterministic rule-based categorization connected to effective recovery policies
            </p>
          </div>
          <div className="text-xs text-zinc-500 font-mono">
            5 Formal Classes
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {(['C1', 'C2', 'C3', 'C4', 'C5'] as FailureCategory[]).map((cat) => {
            const meta = CATEGORY_INFO[cat];
            const caseCount = metrics?.category_breakdown?.[cat] ?? 0;
            return (
              <div
                key={cat}
                className="p-4 rounded-xl bg-background-elevated/30 border border-border hover:border-zinc-500/40 transition-colors flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <CategoryBadge category={cat} />
                    <span className="text-xs font-mono font-bold text-gray-200">
                      {caseCount} {caseCount === 1 ? 'case' : 'cases'}
                    </span>
                  </div>
                  <h4 className="text-xs font-semibold text-zinc-200">{meta.name}</h4>
                  <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                    {meta.description}
                  </p>
                </div>

                <div className="mt-4 pt-2 border-t border-border-subtle/60 text-[10px] space-y-1">
                  <div className="flex items-center justify-between text-zinc-400">
                    <span>Default:</span>
                    <PolicyBadge policy={meta.defaultPolicy} showIcon={false} />
                  </div>
                  <div className="flex items-center justify-between text-zinc-400">
                    <span>Likelihood:</span>
                    <span className="font-mono text-zinc-300">{meta.recoveryLikelihood.split(' ')[0]}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Live Operational Cases Feed */}
      <section className="p-5 rounded-xl bg-background-surface border border-border-subtle">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-gray-100">Live Recovery Pipeline Stream</h3>
            <p className="text-xs text-zinc-400">
              Recent failed payment cases and real-time execution status
            </p>
          </div>
          <button
            onClick={onNavigateToCases}
            className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 font-medium transition-colors"
          >
            <span>View All Cases</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-border text-zinc-400 font-mono text-[11px]">
                <th className="pb-3 pl-2 font-medium">Case ID</th>
                <th className="pb-3 font-medium">Amount</th>
                <th className="pb-3 font-medium">Category</th>
                <th className="pb-3 font-medium">State</th>
                <th className="pb-3 font-medium">Authorized Policy</th>
                <th className="pb-3 font-medium">Payment Link</th>
                <th className="pb-3 pr-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {casesLoading ? (
                <>
                  <TableRowSkeleton columns={7} />
                  <TableRowSkeleton columns={7} />
                  <TableRowSkeleton columns={7} />
                  <TableRowSkeleton columns={7} />
                  <TableRowSkeleton columns={7} />
                </>
              ) : recentCases.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-zinc-500 font-mono">
                    No failed payment cases recorded yet.
                  </td>
                </tr>
              ) : (
                recentCases.slice(0, 8).map((c) => {
                  const isTriagePending = triageLoadingCaseId === c.case_id;
                  return (
                    <tr
                      key={c.case_id}
                      onClick={() => onSelectCase(c.case_id)}
                      className="hover:bg-background-elevated/50 transition-colors cursor-pointer group"
                    >
                      <td className="py-3 pl-2 font-mono font-medium text-brand-300 group-hover:underline">
                        {c.case_id}
                      </td>
                      <td className="py-3 font-mono font-semibold text-gray-200">
                        {formatInr(c.amount_inr)}
                      </td>
                      <td className="py-3">
                        <CategoryBadge category={c.failure_category} />
                      </td>
                      <td className="py-3">
                        <StatusBadge state={c.state} size="sm" />
                      </td>
                      <td className="py-3">
                        <PolicyBadge policy={c.validated_policy_id} />
                      </td>
                      <td className="py-3 font-mono text-zinc-400 text-[11px]">
                        {c.payment_link_id ? (
                          <span className="text-emerald-400 font-medium">
                            {c.payment_link_id}
                          </span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="py-3 pr-2 text-right">
                        <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                          {c.state === 'FAILED_INGESTED' && (
                            <button
                              onClick={() => onTriggerTriage(c.case_id)}
                              disabled={isTriagePending}
                              title="Run AI Triage"
                              className="px-2.5 py-1 text-[11px] font-semibold rounded bg-brand-500/10 text-brand-400 border border-brand-500/30 hover:bg-brand-500/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                            >
                              <Zap className={`w-3 h-3 ${isTriagePending ? 'animate-spin' : ''}`} />
                              <span>{isTriagePending ? 'Triaging...' : 'Triage'}</span>
                            </button>
                          )}
                          <button
                            onClick={() => onSelectCase(c.case_id)}
                            className="px-2 py-1 text-[11px] font-medium rounded text-zinc-400 hover:text-zinc-200 hover:bg-background-elevated transition-colors"
                          >
                            Inspect
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
