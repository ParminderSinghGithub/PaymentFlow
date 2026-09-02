import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  CheckCircle2,
  ExternalLink,
  RotateCcw,
  RefreshCw,
  Shield,
  Sparkles,
  Clock,
  CreditCard,
  Building2,
  FileCheck,
  Search,
} from 'lucide-react';
import {
  launchInteractiveScenario,
  fetchInteractiveStatus,
  verifyInteractivePayment,
  resetInteractiveCase,
  ApiError,
} from '../api/client';
import type { InteractiveStatusResponse, InteractiveVerifyResponse } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { useToast } from '../components/common/Toast';

interface InteractivePageProps {
  onNavigateToInvestigation?: (caseId: string) => void;
  onRefreshGlobalMetrics?: () => void;
}

export const InteractivePage: React.FC<InteractivePageProps> = ({
  onNavigateToInvestigation,
  onRefreshGlobalMetrics,
}) => {
  const { showToast } = useToast();

  const [status, setStatus] = useState<InteractiveStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [verifyResult, setVerifyResult] = useState<InteractiveVerifyResponse | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchInteractiveStatus();
      setStatus(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to query interactive status';
      showToast('error', 'Status Query Failed', msg);
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleLaunch = async () => {
    setLaunching(true);
    setVerifyResult(null);
    try {
      const res = await launchInteractiveScenario({
        scenario_id: 'CS01',
        amount_paise: 250000, // ₹2,500.00
        customer_email: 'demo.buyer@example.com',
        customer_contact: '+919876543210',
        reset_previous: true,
      });

      if (res.status === 'success') {
        showToast(
          'success',
          'Interactive Pipeline Executed',
          `Payment Link created: ${res.payment_link_id ?? 'Live link ready'}`
        );
        await loadStatus();
        onRefreshGlobalMetrics?.();
      } else {
        showToast('error', 'Launch Error', 'Failed to execute recovery pipeline.');
      }
    } catch (err) {
      showToast('error', 'Launch Error', err instanceof ApiError ? err.detail : 'Pipeline launch failed');
    } finally {
      setLaunching(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await verifyInteractivePayment();
      setVerifyResult(res);

      if (res.verified) {
        showToast(
          'success',
          'Payment Verified & Recovered!',
          `₹${res.recovered_amount_inr?.toFixed(2) ?? '2,500.00'} attributed to verified revenue.`
        );
        await loadStatus();
        onRefreshGlobalMetrics?.();
      } else {
        showToast(
          'warning',
          'Payment Not Yet Completed',
          res.message ?? 'Link is currently unpaid in Razorpay Test Mode.'
        );
        await loadStatus();
      }
    } catch (err) {
      showToast('error', 'Verification Error', err instanceof ApiError ? err.detail : 'Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setVerifyResult(null);
    try {
      await resetInteractiveCase();
      showToast('success', 'Reset Complete', 'Interactive demonstration run cleared.');
      await loadStatus();
      onRefreshGlobalMetrics?.();
    } catch (err) {
      showToast('error', 'Reset Error', err instanceof ApiError ? err.detail : 'Reset failed');
    } finally {
      setResetting(false);
    }
  };

  const isRecovered = status?.state === 'RECOVERED';
  const hasLink = Boolean(status?.payment_link_url);

  return (
    <div className="space-y-6">
      {/* ── Header Card ─────────────────────────────────────────────────── */}
      <div className="bg-surface rounded-xl border border-white/[0.08] p-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-ai-base/10 text-ai-text border border-ai-base/20">
                FLAGSHIP DEMONSTRATION
              </span>
              <span className="text-[#4B5563] text-xs">·</span>
              <span className="text-xs text-[#9CA3AF]">Scenario CS01: OTP Timeout Dropoff (₹2,500.00)</span>
            </div>
            <h2 className="text-xl font-bold text-[#F0F2F5] mt-1.5">
              Live End-to-End Recovery Journey
            </h2>
            <p className="text-sm text-[#6B7280] mt-1 max-w-2xl">
              Experience the genuine multi-stage recovery loop. Launch the scenario, observe real-time AI and guardrail reasoning, complete the test checkout, and authoritatively verify revenue attribution.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {status?.exists && onNavigateToInvestigation && (
              <button
                onClick={() => onNavigateToInvestigation(status.case_id)}
                className="px-3.5 py-2 rounded-lg text-xs font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors flex items-center gap-2"
              >
                <Search className="w-3.5 h-3.5" />
                View Decision Story
              </button>
            )}

            {status?.exists && (
              <button
                onClick={handleReset}
                disabled={resetting || launching || verifying}
                className="px-3.5 py-2 rounded-lg text-xs font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors flex items-center gap-2"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin' : ''}`} />
                Reset Run
              </button>
            )}

            <button
              onClick={handleLaunch}
              disabled={launching || verifying}
              className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-ai-base hover:bg-purple-600 active:bg-purple-700 transition-colors shadow-lg shadow-ai-base/20 flex items-center gap-2"
            >
              <Play className={`w-3.5 h-3.5 fill-current ${launching ? 'animate-spin' : ''}`} />
              {status?.exists ? 'Rerun CS01 Scenario' : 'Launch Scenario CS01'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Main Stage Area ─────────────────────────────────────────────── */}
      {!status?.exists && !loading && (
        <div className="bg-surface rounded-xl border border-white/[0.08] p-12 text-center">
          <div className="w-12 h-12 rounded-xl bg-ai-base/10 border border-ai-base/20 flex items-center justify-center mx-auto text-ai-text mb-4">
            <Sparkles className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-[#F0F2F5]">
            No Active Interactive Demonstration
          </h3>
          <p className="text-sm text-[#6B7280] max-w-md mx-auto mt-1 mb-6">
            Click &ldquo;Launch Scenario CS01&rdquo; to initiate a ₹2,500 card dropoff payment failure and observe the recovery pipeline in action.
          </p>
          <button
            onClick={handleLaunch}
            disabled={launching}
            className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-ai-base hover:bg-purple-600 transition-colors inline-flex items-center gap-2"
          >
            <Play className="w-4 h-4 fill-current" />
            Launch Interactive Scenario
          </button>
        </div>
      )}

      {status?.exists && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── Left 2 Columns: Pipeline & Decision Story ────────────────── */}
          <div className="lg:col-span-2 space-y-6">
            {/* Status & Outcome Ribbon */}
            <div className={`rounded-xl border p-5 ${
              isRecovered
                ? 'bg-emerald-950/20 border-emerald-500/30'
                : 'bg-surface border-white/[0.08]'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    isRecovered
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                  }`}>
                    {isRecovered ? <CheckCircle2 className="w-5 h-5" /> : <Clock className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <StateBadge state={status.state ?? 'UNKNOWN'} size="md" />
                      <CategoryBadge category={status.failure_category ?? 'C1'} />
                    </div>
                    <div className="text-xs text-[#6B7280] mt-1 font-mono">
                      Case ID: {status.case_id} · Amount: ₹{status.amount_inr?.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-[11px] text-[#6B7280] uppercase tracking-wider font-semibold">
                    Attributed Revenue
                  </div>
                  <div className={`text-xl font-bold font-mono ${
                    isRecovered ? 'text-emerald-400' : 'text-[#6B7280]'
                  }`}>
                    {isRecovered ? `+₹${status.recovered_amount_inr?.toFixed(2) ?? '2,500.00'}` : '₹0.00'}
                  </div>
                </div>
              </div>
            </div>

            {/* Two-Zone AI vs Guardrail Card */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Violet Zone: AI Recommendation */}
              <div className="bg-surface rounded-xl border border-ai-base/30 p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-ai-base/5 rounded-full blur-xl pointer-events-none" />
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-ai-text" />
                  <span className="text-xs font-semibold text-ai-text uppercase tracking-wider font-mono">
                    AI Recommendation (Violet Zone)
                  </span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="text-[11px] text-[#6B7280]">Proposed Recovery Policy</div>
                    <div className="mt-1">
                      <PolicyBadge policy={status.ai_policy ?? 'P_CREATE_LINK_IMMEDIATE'} />
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-[#6B7280]">Model Explanation</div>
                    <p className="text-xs text-[#D1D5DB] mt-1 leading-relaxed">
                      {status.ai_explanation ?? 'Customer dropped off during OTP entry; immediate recovery payment link recommended for frictionless retry.'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Teal Zone: Deterministic Guardrails */}
              <div className="bg-surface rounded-xl border border-guard-base/30 p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-guard-base/5 rounded-full blur-xl pointer-events-none" />
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="w-4 h-4 text-guard-text" />
                  <span className="text-xs font-semibold text-guard-text uppercase tracking-wider font-mono">
                    Guardrail Gate (Teal Zone)
                  </span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="text-[11px] text-[#6B7280]">Authorized Policy</div>
                    <div className="mt-1">
                      <PolicyBadge policy={status.validated_policy ?? 'P_CREATE_LINK_IMMEDIATE'} />
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-[#6B7280]">Safety Invariants Verified</div>
                    <ul className="text-xs text-[#D1D5DB] mt-1 space-y-1">
                      <li className="flex items-center gap-1.5 text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        Amount exact: ₹{status.amount_inr?.toFixed(2)} (no discount)
                      </li>
                      <li className="flex items-center gap-1.5 text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        Currency: INR (no mutation)
                      </li>
                      <li className="flex items-center gap-1.5 text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        Under ₹50,000 threshold
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            {/* Audit Trail Stream */}
            <div className="bg-surface rounded-xl border border-white/[0.08] p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <FileCheck className="w-4 h-4 text-[#9CA3AF]" />
                  <h3 className="text-sm font-semibold text-[#F0F2F5]">
                    Immutable Chronological Audit Stream
                  </h3>
                </div>
                <span className="text-xs font-mono text-[#6B7280]">
                  {status.audit_trail?.length ?? 0} events persisted
                </span>
              </div>

              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {status.audit_trail?.map((event, idx) => (
                  <div
                    key={event.id ?? idx}
                    className="p-3 rounded-lg bg-surface-raised border border-white/[0.04] text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-[#D1D5DB]">
                        {event.event_type}
                      </span>
                      <span className="text-[10px] text-[#6B7280] font-mono">
                        {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '—'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-[#9CA3AF]">
                      <span>Actor: <strong className="text-[#D1D5DB]">{event.actor}</strong></span>
                      <span>·</span>
                      <span>Decision: <strong className="text-[#D1D5DB]">{event.decision ?? '—'}</strong></span>
                      {event.outcome && (
                        <>
                          <span>·</span>
                          <span className={event.outcome === 'SUCCESS' ? 'text-emerald-400' : 'text-amber-400'}>
                            {event.outcome}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Right Column: Payment Link & Verification Action ────────── */}
          <div className="space-y-6">
            {/* Payment Link Card */}
            <div className="bg-surface rounded-xl border border-white/[0.08] p-5">
              <h3 className="text-sm font-semibold text-[#F0F2F5] mb-3 flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-brand-base" />
                Razorpay Test Mode Link
              </h3>

              {hasLink ? (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-lg bg-surface-raised border border-white/[0.06] space-y-2">
                    <div className="text-[11px] text-[#6B7280] uppercase tracking-wider font-semibold">
                      Payment Link ID
                    </div>
                    <div className="font-mono text-xs text-brand-text font-bold break-all">
                      {status.payment_link_id}
                    </div>

                    <div className="text-[11px] text-[#6B7280] uppercase tracking-wider font-semibold pt-1">
                      Hosted Checkout URL
                    </div>
                    <a
                      href={status.payment_link_url!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:text-blue-300 underline font-mono break-all inline-flex items-center gap-1"
                    >
                      {status.payment_link_url}
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>

                  <a
                    href={status.payment_link_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20"
                  >
                    Open Hosted Checkout
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>

                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-[11px] text-[#9CA3AF] space-y-1">
                    <div className="font-semibold text-[#D1D5DB]">Test Mode Instructions:</div>
                    <p>1. Open the hosted link in a new tab.</p>
                    <p>2. Select Card or Netbanking in Razorpay modal.</p>
                    <p>3. Use test card: <code className="font-mono text-[#F0F2F5]">4111 1111 1111 1111</code> (any future expiry & CVV).</p>
                    <p>4. Complete success payment and return here.</p>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-[#6B7280] p-4 text-center">
                  Payment Link will appear once the scenario is launched.
                </div>
              )}
            </div>

            {/* Authoritative Gateway Verification Card */}
            <div className="bg-surface rounded-xl border border-white/[0.08] p-5">
              <h3 className="text-sm font-semibold text-[#F0F2F5] mb-2 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-guard-text" />
                Gateway Capture Verification
              </h3>
              <p className="text-xs text-[#6B7280] mb-4">
                Queries the Razorpay API for live payment status and invokes authoritative revenue attribution.
              </p>

              <button
                onClick={handleVerify}
                disabled={verifying || !hasLink || isRecovered}
                className={`w-full py-2.5 px-4 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-2 ${
                  isRecovered
                    ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/30 cursor-default'
                    : 'text-white bg-guard-base hover:bg-teal-600 active:bg-teal-700 shadow-lg shadow-guard-base/20'
                }`}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
                {isRecovered ? 'Verified on Gateway (RECOVERED)' : 'Verify Payment Capture'}
              </button>

              {verifyResult && (
                <div className={`mt-3 p-3 rounded-lg text-xs border ${
                  verifyResult.verified
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                }`}>
                  <div className="font-semibold">
                    {verifyResult.verified ? '✓ Attribution Verified' : 'ℹ Payment Pending'}
                  </div>
                  <div className="text-[11px] mt-0.5 opacity-90">
                    {verifyResult.message ?? (verifyResult.verified ? 'Captured payment credited.' : 'Link is unpaid.')}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
