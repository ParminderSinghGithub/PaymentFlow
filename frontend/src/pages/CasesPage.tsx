import React, { useState, useMemo } from 'react';
import {
  Filter,
  RefreshCw,
  Clock,
  Zap,
  ArrowRight,
  Timer,
} from 'lucide-react';
import type { CaseSummaryItem, CaseState } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
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
  | 'RECOVERED'
  | 'ESCALATED'
  | 'TERMINAL_NO_ACTION'
  | 'ACTION_EXECUTED';

const STATE_FILTERS: { id: StateFilter; label: string }[] = [
  { id: 'ALL',               label: 'All' },
  { id: 'FAILED_INGESTED',   label: 'Ingested' },
  { id: 'ACTION_EXECUTED',   label: 'In Flight' },
  { id: 'RECOVERED',         label: 'Recovered' },
  { id: 'ESCALATED',         label: 'Escalated' },
  { id: 'TERMINAL_NO_ACTION',label: 'No Action' },
];

const FILTER_ACTIVE_CLASSES: Partial<Record<StateFilter, string>> = {
  FAILED_INGESTED:   'bg-[rgba(217,119,6,0.12)] border-[rgba(217,119,6,0.30)] text-[#FCD34D]',
  ACTION_EXECUTED:   'bg-[rgba(13,148,136,0.12)] border-[rgba(13,148,136,0.30)] text-guard-text',
  RECOVERED:         'bg-[rgba(5,150,105,0.12)] border-[rgba(5,150,105,0.30)] text-recover-text',
  ESCALATED:         'bg-[rgba(217,119,6,0.12)] border-[rgba(217,119,6,0.30)] text-risk-text',
  TERMINAL_NO_ACTION:'bg-[rgba(225,29,72,0.08)] border-[rgba(225,29,72,0.25)] text-halt-text',
  ALL:               'bg-[rgba(124,58,237,0.10)] border-[rgba(124,58,237,0.30)] text-ai-text',
};

const formatInr = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(v);

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
    <div className="space-y-4 animate-fade-in">

      {/* ── Toolbar ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {/* State filter pills */}
        <div className="flex items-center gap-1 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-[#4B5563] shrink-0 mr-1" />
          {STATE_FILTERS.map((f) => {
            const isActive = activeFilter === f.id;
            const count = f.id === 'ALL' ? cases.length : cases.filter((c) => c.state === f.id).length;
            const activeClass = FILTER_ACTIVE_CLASSES[f.id] ?? 'bg-surface-raised border-white/[0.12] text-[#9CA3AF]';

            return (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium border rounded transition-colors ${
                  isActive
                    ? activeClass
                    : 'bg-transparent border-white/[0.08] text-[#4B5563] hover:border-white/[0.14] hover:text-[#6B7280]'
                }`}
              >
                {f.label}
                <span className="font-mono text-[10px] opacity-70">{count}</span>
              </button>
            );
          })}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          {hasDelayed && (
            <button
              onClick={onProcessDelayed}
              disabled={delayedProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-guard-text bg-[rgba(13,148,136,0.10)] hover:bg-[rgba(13,148,136,0.18)] border border-[rgba(13,148,136,0.25)] rounded-md transition-colors disabled:opacity-50"
            >
              <Timer className={`w-3.5 h-3.5 ${delayedProcessing ? 'animate-spin-slow' : ''}`} />
              {delayedProcessing ? 'Processing…' : 'Process Delayed'}
            </button>
          )}
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#6B7280] hover:text-[#9CA3AF] bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.08] rounded-md transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <span className="text-[10px] font-mono text-[#4B5563]">
            {filteredCases.length} cases
          </span>
        </div>
      </div>

      {/* ── Cases Table ──────────────────────────────────────────────── */}
      <div className="bg-surface-base border border-white/[0.06] rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {[
                  { label: 'Case ID',    cls: 'pl-5' },
                  { label: 'Payment ID', cls: '' },
                  { label: 'Amount',     cls: 'text-right' },
                  { label: 'Category',   cls: '' },
                  { label: 'State',      cls: '' },
                  { label: 'Policy',     cls: '' },
                  { label: 'Created',    cls: '' },
                  { label: 'Actions',    cls: 'pr-5 text-right' },
                ].map(({ label, cls }) => (
                  <th
                    key={label}
                    className={`py-3 px-3 text-[10px] font-mono text-[#4B5563] uppercase tracking-wider font-medium ${cls}`}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <>
                  {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                    <TableRowSkeleton key={i} columns={8} />
                  ))}
                </>
              ) : filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <EmptyState
                      title={activeFilter === 'ALL' ? 'No cases yet' : `No ${activeFilter.toLowerCase().replace('_', ' ')} cases`}
                      description={
                        activeFilter === 'ALL'
                          ? 'Cases will appear here once payment.failed webhooks are received from Razorpay.'
                          : 'Try a different state filter to see other cases.'
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
                      className="border-b border-white/[0.04] hover:bg-surface-raised cursor-pointer transition-colors group"
                    >
                      {/* Case ID */}
                      <td className="py-3 pl-5 px-3">
                        <span className="font-mono text-[11px] text-ai-text group-hover:underline">
                          {c.case_id}
                        </span>
                      </td>

                      {/* Payment ID */}
                      <td className="py-3 px-3">
                        <span className="font-mono text-[10px] text-[#4B5563]">
                          {c.failed_payment_id ? `${c.failed_payment_id.slice(0, 18)}…` : '—'}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="py-3 px-3 text-right">
                        <span className="font-mono text-[12px] font-semibold text-[#F0F2F5]">
                          {formatInr(c.amount_inr)}
                        </span>
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

                      {/* Created */}
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1 text-[10px] font-mono text-[#4B5563]">
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
                              className="flex items-center gap-1 px-2 py-1 text-[10px] font-semibold text-ai-text bg-[rgba(124,58,237,0.10)] hover:bg-[rgba(124,58,237,0.18)] border border-[rgba(124,58,237,0.25)] rounded transition-colors disabled:opacity-50"
                            >
                              <Zap className={`w-3 h-3 ${isTriaging ? 'animate-spin-slow' : ''}`} />
                              {isTriaging ? '…' : 'Triage'}
                            </button>
                          )}
                          <button
                            onClick={() => onSelectCase(c.case_id)}
                            className="flex items-center gap-1 text-[10px] text-[#4B5563] hover:text-[#9CA3AF] transition-colors"
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
