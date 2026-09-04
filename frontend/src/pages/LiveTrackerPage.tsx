import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Radio,
  IndianRupee,
  Link2,
  CheckCircle2,
  Layers,
  ExternalLink,
  Search,
  ArrowRight,
  Store,
  RefreshCw,
  Clock,
} from 'lucide-react';
import type { CaseSummaryItem } from '../types';
import { fetchCases, getMerchantStorefrontUrl } from '../api/client';
import { KpiCard } from '../components/common/KpiCard';
import { StateBadge } from '../components/common/StateBadge';
import { MoneyValue } from '../components/common/MoneyValue';
import { PageHeader } from '../components/common/PageHeader';

interface LiveTrackerPageProps {
  onSelectCase: (caseId: string) => void;
  onNavigateToMerchantStore?: () => void;
}

// Retention duration for RECOVERED cases in the active live queue (10 seconds)
const RECOVERED_RETENTION_MS = 10000;

export const LiveTrackerPage: React.FC<LiveTrackerPageProps> = ({
  onSelectCase,
}) => {
  const [liveCases, setLiveCases] = useState<CaseSummaryItem[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());

  // Track the timestamp when each case was first observed in RECOVERED state
  // This enables keeping it visible for 10 seconds before removing it from the active queue
  const [recoveredTimestamps, setRecoveredTimestamps] = useState<Record<string, number>>({});
  const recoveredTimestampsRef = useRef<Record<string, number>>({});
  recoveredTimestampsRef.current = recoveredTimestamps;

  // Poll active merchant cases every 5 seconds
  const pollActiveCases = async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    try {
      // Query operational merchant cases (strictly excludes canonical benchmark eval cases)
      const data = await fetchCases({ case_source: 'MERCHANT_CHECKOUT', limit: 50 });
      setLastSyncTime(new Date());

      // Update timestamps for cases reaching RECOVERED
      const now = Date.now();
      const updatedTimestamps = { ...recoveredTimestampsRef.current };
      let timestampsChanged = false;

      for (const c of data) {
        if (c.state === 'RECOVERED' && !updatedTimestamps[c.case_id]) {
          updatedTimestamps[c.case_id] = now;
          timestampsChanged = true;
        }
      }

      if (timestampsChanged) {
        setRecoveredTimestamps(updatedTimestamps);
      }

      setLiveCases(data);
    } catch (err) {
      console.warn('Live tracker sync warning:', err);
    } finally {
      if (isManualRefresh) setIsRefreshing(false);
    }
  };

  useEffect(() => {
    pollActiveCases();
    const interval = setInterval(() => {
      pollActiveCases();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Filter active cases for the live operational queue:
  // - Unresolved cases (not RECOVERED and not TERMINAL_NO_ACTION)
  // - RECOVERED cases that are still within the 10-second display retention window
  const activeQueue = useMemo(() => {
    const now = Date.now();
    return liveCases.filter((c) => {
      if (c.state === 'TERMINAL_NO_ACTION' || c.state === 'ESCALATED') {
        return false;
      }
      if (c.state === 'RECOVERED') {
        const recoveredAt = recoveredTimestamps[c.case_id];
        // If just observed as RECOVERED or within the 10s retention window, keep visible
        if (!recoveredAt) return true;
        return now - recoveredAt <= RECOVERED_RETENTION_MS;
      }
      // All other in-flight states are active
      return true;
    });
  }, [liveCases, recoveredTimestamps]);

  // Derived minimal operational metrics
  const amountAtRisk = useMemo(() => {
    // Sum of unresolved amounts in the active queue
    return activeQueue
      .filter((c) => c.state !== 'RECOVERED')
      .reduce((sum, c) => sum + (c.amount_inr || 0), 0);
  }, [activeQueue]);

  const recoveryLinkSentCount = useMemo(() => {
    // Count of active cases where recovery produced a Payment Link
    return activeQueue.filter(
      (c) =>
        Boolean(c.payment_link_id) ||
        Boolean(c.payment_link_short_url) ||
        c.state === 'ACTION_EXECUTED' ||
        c.state === 'RECOVERED'
    ).length;
  }, [activeQueue]);

  const amountRecovered = useMemo(() => {
    // Authoritative recovered amount for cases in the current active tracking window
    return activeQueue
      .filter((c) => c.state === 'RECOVERED')
      .reduce((sum, c) => sum + (c.recovered_amount_inr || 0), 0);
  }, [activeQueue]);

  const activeRecoveriesCount = useMemo(() => {
    // Active unresolved recoveries
    return activeQueue.filter((c) => c.state !== 'RECOVERED').length;
  }, [activeQueue]);

  // Relative time helper
  const getRelativeTime = (isoString?: string | null) => {
    if (!isoString) return 'Just now';
    const elapsedSec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (elapsedSec < 5) return 'Just now';
    if (elapsedSec < 60) return `${elapsedSec}s ago`;
    const elapsedMin = Math.floor(elapsedSec / 60);
    if (elapsedMin < 60) return `${elapsedMin}m ago`;
    return `${Math.floor(elapsedMin / 60)}h ago`;
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-void overflow-y-auto">
      {/* Page Header */}
      <PageHeader
        title="Live Recovery Tracker"
        description="Real-time operational recovery queue across connected merchants."
        icon={Radio}
        actions={
          <div className="flex items-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-mono font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE SYNC &bull; 5s
            </div>

            <a
              href={getMerchantStorefrontUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-surface-base border border-white/[0.08] hover:border-white/[0.18] transition-colors"
            >
              <Store className="w-3.5 h-3.5 text-guard-text" />
              <span>Open Merchant Store Demo</span>
              <ExternalLink className="w-3 h-3 text-[#4B5563]" />
            </a>

            <button
              onClick={() => pollActiveCases(true)}
              disabled={isRefreshing}
              className="p-1.5 rounded text-[#9CA3AF] hover:text-[#F0F2F5] bg-surface-base border border-white/[0.08] hover:border-white/[0.18] transition-colors disabled:opacity-50"
              title="Refresh Queue"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        }
      />

      <div className="p-6 space-y-6">
        {/* Minimal Live Metrics Bar */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Amount at Risk"
            value={<MoneyValue amountInr={amountAtRisk} />}
            subValue={
              activeRecoveriesCount > 0
                ? `${activeRecoveriesCount} active case${activeRecoveriesCount > 1 ? 's' : ''}`
                : 'No active risk'
            }
            accent={amountAtRisk > 0 ? 'risk' : 'none'}
            icon={<IndianRupee className="w-4 h-4 text-risk-base" />}
          />

          <KpiCard
            label="Recovery Link Sent"
            value={recoveryLinkSentCount}
            subValue={
              recoveryLinkSentCount > 0
                ? `${recoveryLinkSentCount} active link${recoveryLinkSentCount > 1 ? 's' : ''} dispatched`
                : 'Awaiting failures'
            }
            accent={recoveryLinkSentCount > 0 ? 'guard' : 'none'}
            icon={<Link2 className="w-4 h-4 text-guard-text" />}
          />

          <KpiCard
            label="Amount Recovered"
            value={<MoneyValue amountInr={amountRecovered} />}
            subValue={
              amountRecovered > 0
                ? 'Captured & attributed'
                : 'Active tracking window'
            }
            accent={amountRecovered > 0 ? 'recover' : 'none'}
            icon={<CheckCircle2 className="w-4 h-4 text-recover-text" />}
          />

          <KpiCard
            label="Active Recoveries"
            value={activeRecoveriesCount}
            subValue={
              activeRecoveriesCount > 0
                ? 'Unresolved operational cases'
                : 'Queue clear'
            }
            accent={activeRecoveriesCount > 0 ? 'ai' : 'none'}
            icon={<Layers className="w-4 h-4 text-ai-text" />}
          />
        </div>

        {/* Live Recovery Queue Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="text-[14px] font-semibold text-[#F0F2F5] tracking-tight">
                Active Operational Queue
              </h2>
              <span className="text-[11px] font-mono text-[#6B7280]">
                ({activeQueue.length} in queue)
              </span>
            </div>

            <div className="text-[11px] text-[#6B7280]">
              Last synchronized: {lastSyncTime.toLocaleTimeString()}
            </div>
          </div>

          {/* Queue Content */}
          {activeQueue.length === 0 ? (
            /* Clean Empty State */
            <div className="bg-surface-base border border-white/[0.06] rounded-lg p-10 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-white/[0.03] border border-white/[0.08] flex items-center justify-center">
                <Radio className="w-6 h-6 text-[#6B7280]" />
              </div>
              <h3 className="text-[15px] font-medium text-[#F0F2F5] mb-1">
                Awaiting Live Merchant Recovery
              </h3>
              <p className="text-[12px] text-[#6B7280] max-w-md mx-auto mb-6 leading-relaxed">
                The live tracker continuously listens for incoming merchant checkout failures,
                autonomous policy validation, and gateway-confirmed recovery attribution.
              </p>

              {/* Lifecycle explanation flow */}
              <div className="inline-flex items-center gap-2 p-3 rounded-lg bg-surface-raised border border-white/[0.04] text-[11px] text-[#9CA3AF] mb-6">
                <span>Payment Failure</span>
                <ArrowRight className="w-3 h-3 text-[#4B5563]" />
                <span>Detection & Triage</span>
                <ArrowRight className="w-3 h-3 text-[#4B5563]" />
                <span>Payment Link Sent</span>
                <ArrowRight className="w-3 h-3 text-[#4B5563]" />
                <span>Awaiting Payment</span>
                <ArrowRight className="w-3 h-3 text-[#4B5563]" />
                <span className="text-recover-text font-medium">Recovery Captured</span>
              </div>

              <div>
                <a
                  href={getMerchantStorefrontUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-guard-base/15 border border-guard-base/30 text-guard-text text-[12px] font-semibold hover:bg-guard-base/25 transition-colors"
                >
                  <Store className="w-3.5 h-3.5" />
                  <span>Launch Merchant Store Demo to Simulate Failure</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          ) : (
            /* Active Recovery Items Table */
            <div className="bg-surface-base border border-white/[0.06] rounded-lg overflow-hidden">
              <table className="w-full text-left text-[12px]">
                <thead className="bg-surface-raised border-b border-white/[0.06] text-[#6B7280] font-mono text-[11px] uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Case / Order</th>
                    <th className="py-3 px-4">Amount at Risk</th>
                    <th className="py-3 px-4">Recovery Stage</th>
                    <th className="py-3 px-4">Payment Link</th>
                    <th className="py-3 px-4">Recovered Amount</th>
                    <th className="py-3 px-4">Elapsed</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {activeQueue.map((c) => {
                    const isRecovered = c.state === 'RECOVERED';
                    const hasLink = Boolean(c.payment_link_id || c.payment_link_short_url);

                    return (
                      <tr
                        key={c.case_id}
                        className={`transition-colors duration-150 ${
                          isRecovered
                            ? 'bg-emerald-500/[0.04] hover:bg-emerald-500/[0.07]'
                            : 'hover:bg-white/[0.02]'
                        }`}
                      >
                        {/* Case & Order Info */}
                        <td className="py-3.5 px-4 font-mono">
                          <div className="flex items-center gap-2">
                            {isRecovered ? (
                              <span className="w-2 h-2 rounded-full bg-emerald-400" title="Recovery captured" />
                            ) : (
                              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" title="Recovery active" />
                            )}
                            <span className="font-semibold text-[#F0F2F5]">
                              {c.case_id}
                            </span>
                          </div>
                          {c.order_id && (
                            <div className="text-[10px] text-[#6B7280] mt-0.5 ml-4">
                              Order: {c.order_id}
                            </div>
                          )}
                        </td>

                        {/* Amount at Risk */}
                        <td className="py-3.5 px-4">
                          <span className="font-mono font-medium text-[#F0F2F5]">
                            <MoneyValue amountInr={c.amount_inr} />
                          </span>
                        </td>

                        {/* Truthful Stage Badge */}
                        <td className="py-3.5 px-4">
                          <div className="flex flex-col gap-1 items-start">
                            <StateBadge state={c.state} size="sm" />
                            <span className="text-[10px] text-[#6B7280]">
                              {c.state === 'FAILED_INGESTED' && 'Failure detected; awaiting triage'}
                              {c.state === 'CONTEXT_RETRIEVED' && 'Context resolved'}
                              {c.state === 'ELIGIBILITY_CHECKED' && 'Eligibility evaluated'}
                              {c.state === 'AI_TRIAGED' && 'Recommendation produced'}
                              {c.state === 'POLICY_VALIDATED' && 'Guardrails validated'}
                              {c.state === 'ACTION_APPROVED' && 'Action authorized'}
                              {c.state === 'ACTION_EXECUTED' && 'Payment link dispatched; awaiting customer payment'}
                              {c.state === 'RECOVERED' && 'Gateway-confirmed captured payment attributed'}
                            </span>
                          </div>
                        </td>

                        {/* Payment Link State */}
                        <td className="py-3.5 px-4 font-mono text-[11px]">
                          {hasLink ? (
                            <div className="flex items-center gap-1.5">
                              {c.payment_link_short_url ? (
                                <a
                                  href={c.payment_link_short_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1"
                                >
                                  <span>{c.payment_link_short_url.replace(/^https?:\/\//, '')}</span>
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              ) : (
                                <span className="text-guard-text">
                                  {c.payment_link_id}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-[#4B5563]">—</span>
                          )}
                        </td>

                        {/* Recovered Amount */}
                        <td className="py-3.5 px-4">
                          {isRecovered ? (
                            <span className="font-mono font-semibold text-emerald-400">
                              <MoneyValue amountInr={c.recovered_amount_inr || c.amount_inr} />
                            </span>
                          ) : (
                            <span className="font-mono text-[#4B5563]">—</span>
                          )}
                        </td>

                        {/* Elapsed Time */}
                        <td className="py-3.5 px-4 text-[11px] text-[#9CA3AF]">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-[#4B5563]" />
                            <span>{getRelativeTime(c.created_at)}</span>
                          </div>
                        </td>

                        {/* Action Drill-Down */}
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => onSelectCase(c.case_id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium text-guard-text bg-guard-base/10 border border-guard-base/20 hover:bg-guard-base/20 transition-colors"
                          >
                            <Search className="w-3 h-3" />
                            <span>Investigate</span>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default LiveTrackerPage;
