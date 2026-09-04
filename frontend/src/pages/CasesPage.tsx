import React, { useState, useMemo } from 'react';
import {
  RefreshCw,
  Clock,
  Zap,
  ArrowRight,
  Timer,
  ListChecks,
} from 'lucide-react';
import type { CaseSummaryItem, CaseState } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { MoneyValue } from '../components/common/MoneyValue';
import { ActionButton } from '../components/common/ActionButton';
import { PageHeader } from '../components/common/PageHeader';
import { TableRowSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';

interface CasesPageProps {
  cases: CaseSummaryItem[];
  loading: boolean;
  onSelectCase: (id: string) => void;
  onProcessDelayed: () => void;
  delayedProcessing: boolean;
  onRefresh: () => void;
  onTriggerTriage: (id: string) => void;
  triageLoadingCaseId: string | null;
}

type StateFilter =
  | 'ALL'
  | 'FAILED_INGESTED'
  | 'ACTION_EXECUTED'
  | 'RECOVERED'
  | 'ESCALATED'
  | 'TERMINAL_NO_ACTION';

const STATE_FILTERS: { id: StateFilter; label: string }[] = [
  { id: 'ALL',                label: 'All Cases' },
  { id: 'FAILED_INGESTED',    label: 'Ingested' },
  { id: 'ACTION_EXECUTED',    label: 'Action Executed' },
  { id: 'RECOVERED',          label: 'Recovered' },
  { id: 'ESCALATED',          label: 'Escalated' },
  { id: 'TERMINAL_NO_ACTION', label: 'Terminal / No Action' },
];

const FILTER_ACTIVE_CLASSES: Record<StateFilter, string> = {
  ALL:                'bg-white/[0.08] border-white/[0.20] text-[#F0F2F5]',
  FAILED_INGESTED:    'bg-[rgba(217,119,6,0.12)] border-[rgba(217,119,6,0.30)] text-[#FCD34D]',
  ACTION_EXECUTED:    'bg-[rgba(13,148,136,0.12)] border-[rgba(13,148,136,0.30)] text-guard-text',
  RECOVERED:          'bg-[rgba(5,150,105,0.12)] border-[rgba(5,150,105,0.30)] text-recover-text',
  ESCALATED:          'bg-[rgba(217,119,6,0.12)] border-[rgba(217,119,6,0.30)] text-risk-text',
  TERMINAL_NO_ACTION: 'bg-[rgba(225,29,72,0.08)] border-[rgba(225,29,72,0.25)] text-halt-text',
};

const formatRelative = (ts: string | null | undefined) => {
  if (!ts) return '—';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

export const CasesPage: React.FC<CasesPageProps> = ({
  cases,
  loading,
  onSelectCase,
  onProcessDelayed,
  delayedProcessing,
  onRefresh,
  onTriggerTriage,
  triageLoadingCaseId,
}) => {
  const [activeFilter, setActiveFilter] = useState<StateFilter>('ALL');

  const filteredCases = useMemo(() => {
    if (activeFilter === 'ALL') return cases;
    return cases.filter((c) => c.state === activeFilter);
  }, [cases, activeFilter]);

  const hasDelayed = cases.some((c) => c.scheduled_at !== null && c.state === 'FAILED_INGESTED');

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <PageHeader
        title="Recovery Cases Explorer"
        description="Explore the authoritative failure lifecycle: from webhook ingestion and taxonomy classification to policy authorization and verified gateway attribution."
        icon={ListChecks}
        actions={
          <div className="flex items-center gap-2">
            {hasDelayed && (
              <ActionButton
                label={delayedProcessing ? 'Processing…' : 'Process Due Delayed'}
                variant="secondary"
                size="sm"
                icon={Timer}
                loading={delayedProcessing}
                onClick={onProcessDelayed}
              />
            )}
            <ActionButton
              label="Refresh Cases"
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={onRefresh}
            />
          </div>
        }
      />

      {/* ── Toolbar & State Filters ───────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 bg-surface-base border border-white/[0.06] rounded-lg">
        {/* State filter buttons */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {STATE_FILTERS.map((f) => {
            const isActive = activeFilter === f.id;
            const count = f.id === 'ALL' ? cases.length : cases.filter((c) => c.state === f.id).length;
            const activeClass = FILTER_ACTIVE_CLASSES[f.id];

            return (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono border rounded transition-colors ${
                  isActive
                    ? `${activeClass} font-semibold`
                    : 'bg-surface-raised border-white/[0.06] text-[#6B7280] hover:text-[#9CA3AF] hover:border-white/[0.12]'
                }`}
              >
                <span>{f.label}</span>
                <span className="text-[10px] opacity-75 font-bold">({count})</span>
              </button>
            );
          })}
        </div>

        <span className="text-[11px] font-mono text-[#4B5563] shrink-0 self-end sm:self-auto">
          Showing {filteredCases.length} of {cases.length} cases
        </span>
      </div>

      {/* ── Cases Table ────────────────────────────────────────────────── */}
      <div className="bg-surface-base border border-white/[0.06] rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" aria-label="Recovery Cases Registry">
            <thead>
              <tr className="border-b border-white/[0.06] bg-surface-raised/40">
                {[
                  { label: 'Case ID',    cls: 'pl-5' },
                  { label: 'Payment ID', cls: '' },
                  { label: 'Amount',     cls: 'text-right' },
                  { label: 'Category',   cls: '' },
                  { label: 'State',      cls: '' },
                  { label: 'Authorized Policy', cls: '' },
                  { label: 'Ingested',    cls: '' },
                  { label: 'Actions',    cls: 'pr-5 text-right' },
                ].map(({ label, cls }) => (
                  <th
                    key={label}
                    className={`py-3 px-3 text-[10px] font-mono text-[#6B7280] uppercase tracking-wider font-semibold ${cls}`}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {loading ? (
                [1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                  <TableRowSkeleton key={i} columns={8} />
                ))
              ) : filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12">
                    <EmptyState
                      title={activeFilter === 'ALL' ? 'No cases in pipeline' : `No ${activeFilter.toLowerCase().replace(/_/g, ' ')} cases`}
                      description={
                        activeFilter === 'ALL'
                          ? 'Cases will appear here once payment.failed webhooks are ingested or the canonical batch is seeded.'
                          : 'Try selecting another state filter above to inspect other cases.'
                      }
                    />
                  </td>
                </tr>
              ) : (
                filteredCases.map((c) => {
                  const isTriaging = triageLoadingCaseId === c.case_id;

                  return (
                    <tr
                      key={c.case_id}
                      onClick={() => onSelectCase(c.case_id)}
                      className="hover:bg-white/[0.02] cursor-pointer transition-colors group"
                    >
                      {/* Case ID */}
                      <td className="py-3 pl-5 px-3">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-[11px] text-ai-text group-hover:underline font-medium">
                            {c.case_id}
                          </span>
                          {c.case_source === 'CANONICAL_EVALUATION' && (
                            <span className="px-1 py-0.2 rounded text-[9px] font-mono font-medium tracking-wide uppercase bg-amber-500/10 text-amber-300 border border-amber-500/20">
                              BENCHMARK
                            </span>
                          )}
                          {c.case_source === 'MERCHANT_CHECKOUT' && (
                            <span className="px-1 py-0.2 rounded text-[9px] font-mono font-medium tracking-wide uppercase bg-teal-500/10 text-teal-300 border border-teal-500/20">
                              MERCHANT
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Payment ID (Complete, No Arbitrary Slicing) */}
                      <td className="py-3 px-3">
                        <span className="font-mono text-[11px] text-[#9CA3AF]">
                          {c.failed_payment_id || '—'}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="py-3 px-3 text-right">
                        <MoneyValue
                          amountInr={c.amount_inr}
                          variant={c.state === 'RECOVERED' ? 'recovered' : c.amount_inr >= 50000 ? 'at-risk' : 'neutral'}
                          size="sm"
                        />
                      </td>

                      {/* Category */}
                      <td className="py-3 px-3">
                        <CategoryBadge category={c.failure_category} />
                      </td>

                      {/* State */}
                      <td className="py-3 px-3">
                        <StateBadge state={c.state as CaseState} size="sm" />
                      </td>

                      {/* Policy */}
                      <td className="py-3 px-3">
                        <PolicyBadge policy={c.validated_policy_id} context="guard" showIcon={false} />
                      </td>

                      {/* Ingested Timestamp */}
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1 text-[10px] font-mono text-[#6B7280]">
                          <Clock className="w-3 h-3 shrink-0" />
                          {formatRelative(c.created_at)}
                        </div>
                        {c.scheduled_at && (
                          <div className="flex items-center gap-1 text-[9px] font-mono text-risk-text mt-0.5">
                            <Timer className="w-2.5 h-2.5 shrink-0" />
                            Scheduled
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td
                        className="py-3 pr-5 px-3 text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
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
                            aria-label={`Investigate case ${c.case_id}`}
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
      </div>
    </div>
  );
};
