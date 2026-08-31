import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  RefreshCw,
  Clock,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Zap,
} from 'lucide-react';
import type { CaseSummaryItem, CaseState } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { TableRowSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';

interface CasesPageProps {
  cases: CaseSummaryItem[];
  loading: boolean;
  onSelectCase: (caseId: string) => void;
  onProcessDelayed: () => void;
  delayedProcessing: boolean;
  onRefresh: () => void;
  onTriggerTriage: (caseId: string) => void;
  triageLoadingCaseId: string | null;
}

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
  const [searchQuery, setSearchQuery] = useState('');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const stateFilters: Array<{ label: string; value: string }> = [
    { label: 'All Cases', value: 'ALL' },
    { label: 'Recovered', value: 'RECOVERED' },
    { label: 'Link Executed', value: 'ACTION_EXECUTED' },
    { label: 'Action Approved', value: 'ACTION_APPROVED' },
    { label: 'Escalated', value: 'ESCALATED' },
    { label: 'No Action', value: 'TERMINAL_NO_ACTION' },
    { label: 'Ingested', value: 'FAILED_INGESTED' },
  ];

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      // 1. State filter
      if (stateFilter !== 'ALL' && c.state !== stateFilter) {
        return false;
      }
      // 2. Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesId = c.case_id.toLowerCase().includes(q);
        const matchesPayId = c.failed_payment_id.toLowerCase().includes(q);
        const matchesCust = c.customer_id?.toLowerCase().includes(q) ?? false;
        const matchesOrder = c.order_id?.toLowerCase().includes(q) ?? false;
        return matchesId || matchesPayId || matchesCust || matchesOrder;
      }
      return true;
    });
  }, [cases, stateFilter, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredCases.length / pageSize));
  const paginatedCases = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredCases.slice(start, start + pageSize);
  }, [filteredCases, page, pageSize]);

  const formatInr = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(amount);
  };

  return (
    <div className="space-y-5">
      {/* Action and Filter Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-background-surface border border-border-subtle">
        {/* Left: Search input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by Case ID, Payment ID, Customer ID..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full bg-background-subtle border border-border rounded-lg pl-9 pr-4 py-2 text-xs text-gray-200 placeholder:text-zinc-500 focus:outline-none focus:border-brand-500/50 transition-colors font-mono"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500 hover:text-zinc-300"
            >
              Clear
            </button>
          )}
        </div>

        {/* Right: Operational Actions */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onProcessDelayed}
            disabled={delayedProcessing}
            title="Batch process all due delayed recovery cases"
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-500/10 text-blue-300 border border-blue-500/30 hover:bg-blue-500/20 transition-colors disabled:opacity-50"
          >
            <Clock className={`w-3.5 h-3.5 ${delayedProcessing ? 'animate-spin' : ''}`} />
            <span>{delayedProcessing ? 'Processing Due...' : 'Process Due Delayed Cases'}</span>
          </button>

          <button
            onClick={onRefresh}
            title="Refresh case collection"
            className="p-2 rounded-lg bg-background-elevated border border-border text-zinc-400 hover:text-zinc-200 hover:bg-background-hover transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* State Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <Filter className="w-3.5 h-3.5 text-zinc-500 shrink-0 mr-1" />
        {stateFilters.map((sf) => {
          const isSelected = stateFilter === sf.value;
          return (
            <button
              key={sf.value}
              onClick={() => {
                setStateFilter(sf.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 font-mono ${
                isSelected
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 shadow-sm'
                  : 'bg-background-surface/80 text-zinc-400 border border-border hover:bg-background-elevated hover:text-zinc-200'
              }`}
            >
              {sf.label}
            </button>
          );
        })}
      </div>

      {/* Table Container */}
      <div className="rounded-xl bg-background-surface border border-border-subtle overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-border bg-background-subtle/50 text-zinc-400 font-mono text-[11px]">
                <th className="py-3.5 pl-4 font-medium">Case Identifier</th>
                <th className="py-3.5 font-medium">Original Amount</th>
                <th className="py-3.5 font-medium">Failure Category</th>
                <th className="py-3.5 font-medium">Lifecycle State</th>
                <th className="py-3.5 font-medium">Authorized Policy</th>
                <th className="py-3.5 font-medium">Payment Link</th>
                <th className="py-3.5 font-medium">Recovered Amount</th>
                <th className="py-3.5 pr-4 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle font-mono">
              {loading ? (
                <>
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                  <TableRowSkeleton columns={8} />
                </>
              ) : paginatedCases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-0">
                    <EmptyState
                      title="No Recovery Cases Found"
                      description={
                        searchQuery || stateFilter !== 'ALL'
                          ? 'No cases match your active search or state filters.'
                          : 'No failed payment cases are currently registered in the database.'
                      }
                      actionText={searchQuery || stateFilter !== 'ALL' ? 'Reset Filters' : undefined}
                      onAction={() => {
                        setSearchQuery('');
                        setStateFilter('ALL');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                paginatedCases.map((c) => {
                  const isTriagePending = triageLoadingCaseId === c.case_id;
                  return (
                    <tr
                      key={c.case_id}
                      onClick={() => onSelectCase(c.case_id)}
                      className="hover:bg-background-elevated/50 transition-colors cursor-pointer group"
                    >
                      {/* Case ID */}
                      <td className="py-3.5 pl-4 font-medium text-brand-300 group-hover:underline">
                        <div>{c.case_id}</div>
                        <div className="text-[10px] text-zinc-500 font-normal">
                          {c.failed_payment_id}
                        </div>
                      </td>

                      {/* Original Amount */}
                      <td className="py-3.5 font-semibold text-gray-200">
                        <div>{formatInr(c.amount_inr)}</div>
                        <div className="text-[10px] text-zinc-500 font-normal">
                          {c.amount_paise} paise
                        </div>
                      </td>

                      {/* Category */}
                      <td className="py-3.5">
                        <CategoryBadge category={c.failure_category} />
                      </td>

                      {/* State */}
                      <td className="py-3.5 font-sans">
                        <StatusBadge state={c.state as CaseState} size="sm" />
                      </td>

                      {/* Validated Policy */}
                      <td className="py-3.5">
                        <PolicyBadge policy={c.validated_policy_id} />
                      </td>

                      {/* Payment Link */}
                      <td className="py-3.5 text-zinc-400 text-[11px]">
                        {c.payment_link_id ? (
                          <div className="flex items-center gap-1.5">
                            <span className="text-emerald-400 font-medium">
                              {c.payment_link_id}
                            </span>
                            {c.payment_link_short_url && (
                              <a
                                href={c.payment_link_short_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-zinc-500 hover:text-brand-300"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>

                      {/* Recovered Amount */}
                      <td className="py-3.5 font-semibold">
                        {c.recovered_amount_paise && c.recovered_amount_paise > 0 ? (
                          <span className="text-emerald-400">
                            {formatInr(c.recovered_amount_inr)}
                          </span>
                        ) : (
                          <span className="text-zinc-600">₹0.00</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 pr-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2 font-sans">
                          {c.state === 'FAILED_INGESTED' && (
                            <button
                              onClick={() => onTriggerTriage(c.case_id)}
                              disabled={isTriagePending}
                              title="Trigger AI Triage Orchestration"
                              className="px-2 py-1 text-[11px] font-semibold rounded bg-brand-500/10 text-brand-400 border border-brand-500/30 hover:bg-brand-500/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                            >
                              <Zap className={`w-3 h-3 ${isTriagePending ? 'animate-spin' : ''}`} />
                              <span>{isTriagePending ? '...' : 'Triage'}</span>
                            </button>
                          )}
                          <button
                            onClick={() => onSelectCase(c.case_id)}
                            className="px-2.5 py-1 text-[11px] font-medium rounded text-zinc-300 hover:text-gray-100 hover:bg-background-elevated transition-colors border border-border"
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

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-background-subtle/30 text-xs text-zinc-400">
          <div className="font-mono">
            Showing{' '}
            <span className="text-zinc-200 font-semibold">
              {filteredCases.length === 0 ? 0 : (page - 1) * pageSize + 1}
            </span>{' '}
            to{' '}
            <span className="text-zinc-200 font-semibold">
              {Math.min(page * pageSize, filteredCases.length)}
            </span>{' '}
            of <span className="text-zinc-200 font-semibold">{filteredCases.length}</span> cases
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg border border-border bg-background-surface text-zinc-400 hover:text-zinc-200 hover:bg-background-elevated disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-mono px-2 text-zinc-300">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded-lg border border-border bg-background-surface text-zinc-400 hover:text-zinc-200 hover:bg-background-elevated disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
