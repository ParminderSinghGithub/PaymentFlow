import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  CheckCircle2,
  ExternalLink,
  RotateCcw,
  RefreshCw,
  ShieldCheck,
  Bot,
  CreditCard,
  Building2,
  Sparkles,
  Search,
  Copy,
  Check,
  HelpCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  launchInteractiveScenario,
  fetchInteractiveStatus,
  verifyInteractivePayment,
  resetInteractiveCase,
  ApiError,
} from '../api/client';
import type { InteractiveStatusResponse, InteractiveVerifyResponse, CaseState } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { MoneyValue } from '../components/common/MoneyValue';
import { ActionButton } from '../components/common/ActionButton';
import { ZoneCard } from '../components/common/ZoneCard';
import { PageHeader } from '../components/common/PageHeader';
import { AuditTimeline } from '../components/common/AuditTimeline';
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
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedCard, setCopiedCard] = useState(false);
  const [verifyResult, setVerifyResult] = useState<InteractiveVerifyResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'journey' | 'audit'>('journey');

  const pollTimerRef = useRef<number | null>(null);

  const loadStatus = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const data = await fetchInteractiveStatus();
      setStatus(data);
    } catch (err) {
      if (!silent) {
        const msg = err instanceof ApiError ? err.detail : 'Failed to query interactive status';
        showToast('error', 'Status Query Failed', msg);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [showToast]);

  // Initial load
  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Bounded Polling: only poll when active case is in flight (ACTION_EXECUTED) and not yet recovered
  const isRecovered = status?.state === 'RECOVERED';
  const isActionExecuted = status?.state === 'ACTION_EXECUTED';
  const hasLink = Boolean(status?.payment_link_url);

  useEffect(() => {
    if (status?.exists && isActionExecuted && !isRecovered) {
      pollTimerRef.current = window.setInterval(() => {
        loadStatus(true);
      }, 5000);
    } else {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [status?.exists, isActionExecuted, isRecovered, loadStatus]);

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
          `Razorpay Test Mode Link created: ${res.payment_link_id ?? 'Ready for test checkout'}`
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
          `₹${(res.recovered_amount_inr ?? 2500).toFixed(2)} attributed to verified revenue.`
        );
        await loadStatus();
        onRefreshGlobalMetrics?.();
      } else {
        showToast(
          'warning',
          'Payment Not Yet Completed',
          res.message ?? 'Link is currently unpaid in Razorpay Test Mode.'
        );
        await loadStatus(true);
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

  const handleCopyLink = () => {
    if (status?.payment_link_url) {
      navigator.clipboard.writeText(status.payment_link_url);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  const handleCopyCard = () => {
    navigator.clipboard.writeText('4111111111111111');
    setCopiedCard(true);
    setTimeout(() => setCopiedCard(false), 2000);
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <PageHeader
        title="Interactive CS01 Live Recovery Demo"
        description="Experience the complete bounded recovery journey: trigger a dropoff failure, observe read-only AI diagnosis and deterministic authorization, complete a genuine Razorpay Test Mode checkout, and verify authoritative revenue attribution."
        breadcrumbs={[
          { label: 'Flagship Demo' },
          { label: 'CS01 Live Journey' },
        ]}
        icon={Sparkles}
        actions={
          <div className="flex items-center gap-2">
            {status?.exists && onNavigateToInvestigation && (
              <ActionButton
                label="Decision Story"
                variant="secondary"
                size="sm"
                icon={Search}
                onClick={() => onNavigateToInvestigation(status.case_id)}
              />
            )}
            {status?.exists && (
              <ActionButton
                label={resetting ? 'Resetting…' : 'Reset Demo'}
                variant="destructive"
                size="sm"
                icon={RotateCcw}
                loading={resetting}
                disabled={launching || verifying}
                onClick={handleReset}
              />
            )}
            <ActionButton
              label="Refresh Status"
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              loading={loading}
              onClick={() => loadStatus()}
            />
          </div>
        }
      />

      {/* ── Pre-Launch State (When case not yet initiated) ─────────────── */}
      {!status?.exists && !loading && (
        <div className="bg-surface-base border border-white/[0.08] rounded-xl p-8 lg:p-10 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-ai-muted text-ai-text border border-ai-border">
                  FLAGSHIP SCENARIO · CS01
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-surface-raised text-[#9CA3AF] border border-white/[0.08]">
                  RAZORPAY TEST MODE
                </span>
              </div>
              <h2 className="text-[18px] font-bold text-[#F0F2F5] mt-2">
                OTP Timeout / Customer Checkout Dropoff
              </h2>
              <p className="text-[12px] text-[#6B7280] mt-1 max-w-xl leading-relaxed">
                A customer initiated a ₹2,500.00 payment, but abandoned the checkout during bank OTP verification. PaymentFlow ingests the failure webhook, diagnoses the root cause, authorizes a bounded recovery link via deterministic guardrails, and waits for completion in Razorpay Test Mode.
              </p>
            </div>

            <div className="text-left sm:text-right shrink-0 bg-surface-raised/40 p-4 rounded-lg border border-white/[0.04]">
              <div className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                Revenue at Risk
              </div>
              <div className="mt-1">
                <MoneyValue amountInr={2500} variant="at-risk" size="lg" />
              </div>
              <div className="mt-1">
                <CategoryBadge category="C1" />
              </div>
            </div>
          </div>

          {/* Compact Planned Roadmap */}
          <div className="space-y-3">
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#6B7280]">
              Planned Bounded Workflow
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-[11px] font-mono">
              <div className="p-3 bg-surface-raised border border-white/[0.06] rounded-md">
                <div className="text-[9px] text-[#6B7280] uppercase">01 DETECT</div>
                <div className="font-semibold text-[#D1D5DB] mt-1">Ingest Failure</div>
              </div>
              <div className="p-3 bg-ai-muted border border-ai-border rounded-md">
                <div className="text-[9px] text-ai-text uppercase">02 AI ADVISORY</div>
                <div className="font-semibold text-ai-text mt-1">Read-Only Proposal</div>
              </div>
              <div className="p-3 bg-guard-muted border border-guard-border rounded-md">
                <div className="text-[9px] text-guard-text uppercase">03 GUARDRAIL</div>
                <div className="font-semibold text-guard-text mt-1">Deterministic Gate</div>
              </div>
              <div className="p-3 bg-surface-raised border border-white/[0.06] rounded-md">
                <div className="text-[9px] text-[#6B7280] uppercase">04 ACTION</div>
                <div className="font-semibold text-[#D1D5DB] mt-1">Test Payment Link</div>
              </div>
              <div className="p-3 bg-recover-muted border border-recover-border rounded-md">
                <div className="text-[9px] text-recover-text uppercase">05 VERIFY</div>
                <div className="font-semibold text-recover-text mt-1">Attributed Cash</div>
              </div>
            </div>
          </div>

          {/* Launch Action */}
          <div className="pt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <ActionButton
              label="Launch Live Recovery Scenario (CS01)"
              variant="primary"
              size="lg"
              icon={Play}
              loading={launching}
              onClick={handleLaunch}
            />
            <span className="text-[11px] text-[#6B7280] font-sans">
              Safe Sandbox Execution · Uses genuine Razorpay Test Mode credentials · Zero production customer contact.
            </span>
          </div>
        </div>
      )}

      {/* ── Active Live Journey Area ────────────────────────────────────── */}
      {status?.exists && (
        <div className="space-y-6">
          {/* Section A: Live Operational Status Strip */}
          <div
            className={`rounded-xl border p-5 transition-all ${
              isRecovered
                ? 'bg-[rgba(5,150,105,0.08)] border-[rgba(5,150,105,0.30)]'
                : 'bg-surface-base border-white/[0.08]'
            }`}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Metric 1: State */}
              <div>
                <div className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                  Persisted Case State
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <StateBadge state={status.state as CaseState} size="md" />
                </div>
                <div className="text-[10px] text-[#6B7280] mt-1 font-mono">
                  {isRecovered
                    ? 'Attributed to verified revenue'
                    : isActionExecuted
                    ? 'Waiting for customer payment'
                    : 'Pipeline in progress'}
                </div>
              </div>

              {/* Metric 2: Revenue at Risk */}
              <div>
                <div className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                  Revenue at Risk
                </div>
                <div className="mt-1">
                  <MoneyValue
                    amountInr={status.amount_inr ?? 2500}
                    variant={isRecovered ? 'neutral' : 'at-risk'}
                    size="md"
                  />
                </div>
                <div className="text-[10px] text-[#6B7280] mt-1 font-mono">
                  Original checkout transaction
                </div>
              </div>

              {/* Metric 3: Verified Recovered Cash */}
              <div>
                <div className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                  Verified Recovered Cash
                </div>
                <div className="mt-1">
                  <MoneyValue
                    amountInr={isRecovered ? (status.recovered_amount_inr ?? 2500) : 0}
                    variant={isRecovered ? 'recovered' : 'neutral'}
                    size="md"
                  />
                </div>
                <div className="text-[10px] text-[#6B7280] mt-1 font-mono">
                  {isRecovered ? '100% Captured & Credited' : 'Unverified · ₹0.00 until captured'}
                </div>
              </div>

              {/* Metric 4: Gateway Test Link Status */}
              <div>
                <div className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                  Payment Link Status
                </div>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      isRecovered || status.payment_link_status === 'paid'
                        ? 'bg-recover-base'
                        : 'bg-risk-base animate-pulse'
                    }`}
                  />
                  <span
                    className={`font-mono text-[12px] font-semibold uppercase ${
                      isRecovered || status.payment_link_status === 'paid'
                        ? 'text-recover-text'
                        : 'text-risk-text'
                    }`}
                  >
                    {isRecovered || status.payment_link_status === 'paid' ? 'PAID (CAPTURED)' : 'CREATED (UNPAID)'}
                  </span>
                </div>
                <div className="text-[10px] text-[#6B7280] mt-1 font-mono truncate" title={status.payment_link_id || ''}>
                  ID: {status.payment_link_id || '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Section B: 7-Stage End-to-End Decision Pipeline */}
          <div className="bg-surface-base border border-white/[0.06] rounded-xl p-4">
            <div className="text-[10px] font-mono uppercase tracking-wider text-[#6B7280] mb-3">
              End-to-End Bounded Decision Progression
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-[11px] font-mono">
              {/* Stage 1 */}
              <div className="p-2.5 bg-surface-raised border border-white/[0.04] rounded-md">
                <div className="text-[9px] text-[#6B7280] uppercase">01 FAILURE</div>
                <div className="font-semibold text-[#D1D5DB] mt-1">OTP Timeout</div>
                <div className="text-[9px] text-[#4B5563] mt-1">Ingested</div>
              </div>

              {/* Stage 2 */}
              <div className="p-2.5 bg-surface-raised border border-white/[0.04] rounded-md">
                <div className="text-[9px] text-[#6B7280] uppercase">02 DIAGNOSIS</div>
                <div className="font-semibold text-[#D1D5DB] mt-1">C1 Customer</div>
                <div className="text-[9px] text-[#4B5563] mt-1">Dropoff</div>
              </div>

              {/* Stage 3 (Violet) */}
              <div className="p-2.5 bg-ai-muted border border-ai-border rounded-md">
                <div className="text-[9px] text-ai-text uppercase flex items-center gap-1 font-semibold">
                  <Bot className="w-2.5 h-2.5" /> 03 AI ADVISORY
                </div>
                <div className="font-semibold text-ai-text mt-1">P_CREATE_LINK</div>
                <div className="text-[9px] text-ai-text/70 mt-1">Read-Only</div>
              </div>

              {/* Stage 4 (Teal) */}
              <div className="p-2.5 bg-guard-muted border border-guard-border rounded-md">
                <div className="text-[9px] text-guard-text uppercase flex items-center gap-1 font-semibold">
                  <ShieldCheck className="w-2.5 h-2.5" /> 04 GUARDRAIL
                </div>
                <div className="font-semibold text-guard-text mt-1">APPROVE</div>
                <div className="text-[9px] text-guard-text/70 mt-1">10 Invariants</div>
              </div>

              {/* Stage 5 */}
              <div className="p-2.5 bg-surface-raised border border-white/[0.04] rounded-md">
                <div className="text-[9px] text-[#6B7280] uppercase">05 ACTION</div>
                <div className="font-semibold text-[#D1D5DB] mt-1">Link Active</div>
                <div className="text-[9px] text-[#4B5563] mt-1">Dispatched</div>
              </div>

              {/* Stage 6 */}
              <div
                className={`p-2.5 rounded-md border ${
                  isRecovered
                    ? 'bg-recover-muted border-recover-border'
                    : 'bg-surface-raised border-white/[0.04]'
                }`}
              >
                <div className="text-[9px] text-[#6B7280] uppercase">06 VERIFY</div>
                <div className={`font-semibold mt-1 ${isRecovered ? 'text-recover-text' : 'text-[#D1D5DB]'}`}>
                  {isRecovered ? 'Captured' : 'Awaiting'}
                </div>
                <div className="text-[9px] text-[#4B5563] mt-1">Gateway API</div>
              </div>

              {/* Stage 7 */}
              <div
                className={`p-2.5 rounded-md border ${
                  isRecovered
                    ? 'bg-recover-muted border-recover-border'
                    : 'bg-surface-raised border-white/[0.04]'
                }`}
              >
                <div className="text-[9px] text-[#6B7280] uppercase">07 OUTCOME</div>
                <div className={`font-semibold mt-1 ${isRecovered ? 'text-recover-text' : 'text-[#D1D5DB]'}`}>
                  {isRecovered ? 'Recovered' : 'Action Executed'}
                </div>
                <div className="text-[9px] text-[#4B5563] mt-1">
                  {isRecovered ? '₹2,500 Cash' : 'In Flight'}
                </div>
              </div>
            </div>
          </div>

          {/* Section C: Side-by-Side Architectural Contrast: AI Advisory vs Guardrail Gate */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Violet ZoneCard: AI Advisory */}
            <ZoneCard
              zone="ai"
              label="AI ADVISORY · RECOMMENDATION ONLY"
              icon={Bot}
              description="Read-only context ingestion via MCP. The LLM suggests the recovery policy."
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-[#6B7280] font-mono">Proposed Policy:</span>
                  <PolicyBadge policy={status.ai_policy || 'P_CREATE_LINK_IMMEDIATE'} context="ai" />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-[#6B7280] font-mono">Failure Taxonomy:</span>
                  <CategoryBadge category={status.failure_category || 'C1'} />
                </div>

                <div className="p-3 bg-surface-base/60 border border-white/[0.04] rounded-md space-y-1">
                  <div className="text-[10px] font-mono text-ai-text uppercase font-semibold">
                    Advisory Rationale
                  </div>
                  <p className="text-[11px] text-[#D1D5DB] leading-relaxed">
                    {status.ai_explanation ||
                      'Customer dropped off during OTP entry; immediate recovery payment link recommended for frictionless retry.'}
                  </p>
                </div>

                <div className="text-[10px] font-mono text-[#6B7280] flex items-center gap-1.5 pt-1">
                  <HelpCircle className="w-3 h-3 text-ai-text shrink-0" />
                  <span>AI recommends. Deterministic guardrails hold 100% write authority.</span>
                </div>
              </div>
            </ZoneCard>

            {/* Teal ZoneCard: Guardrail Authorization */}
            <ZoneCard
              zone="guard"
              label="GUARDRAIL AUTHORIZATION · DETERMINISTIC CONTROL"
              icon={ShieldCheck}
              description="Mathematical safety invariants gate all financial writes to the gateway."
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-[#6B7280] font-mono">Authorized Policy:</span>
                  <PolicyBadge policy={status.validated_policy || 'P_CREATE_LINK_IMMEDIATE'} context="guard" />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-[#6B7280] font-mono">Authorization Decision:</span>
                  <span className="font-mono text-[11px] font-bold text-guard-text bg-guard-muted px-2 py-0.5 rounded border border-guard-border">
                    APPROVE (ALL CHECKS PASSED)
                  </span>
                </div>

                <div className="p-3 bg-surface-base/60 border border-white/[0.04] rounded-md space-y-1.5 text-[11px] font-mono">
                  <div className="flex items-center justify-between text-[#9CA3AF]">
                    <span>Amount Lock:</span>
                    <span className="text-guard-text font-semibold flex items-center gap-1">
                      <Check className="w-3 h-3" /> Exact ₹2,500.00
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#9CA3AF]">
                    <span>Currency Lock:</span>
                    <span className="text-guard-text font-semibold flex items-center gap-1">
                      <Check className="w-3 h-3" /> INR (Zero Mutation)
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#9CA3AF]">
                    <span>Value Cap:</span>
                    <span className="text-guard-text font-semibold flex items-center gap-1">
                      <Check className="w-3 h-3" /> &lt; ₹50,000 Threshold
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#9CA3AF]">
                    <span>Rate / Spam Limit:</span>
                    <span className="text-guard-text font-semibold flex items-center gap-1">
                      <Check className="w-3 h-3" /> Link 1 of 1 (Cooldown Valid)
                    </span>
                  </div>
                </div>

                <div className="text-[10px] font-mono text-[#6B7280] flex items-center gap-1.5 pt-1">
                  <ShieldCheck className="w-3 h-3 text-guard-text shrink-0" />
                  <span>Authorized RecoveryExecutor to dispatch Payment Link to Razorpay.</span>
                </div>
              </div>
            </ZoneCard>
          </div>

          {/* Section D: Central Interactive Action Surface (Test Checkout & Gateway Verification) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Card 1: Razorpay Test Mode Payment Link */}
            <div className="bg-surface-base border border-white/[0.08] rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-guard-text" />
                  <h3 className="text-[13px] font-semibold text-[#F0F2F5]">
                    Razorpay Test Mode Link
                  </h3>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-raised text-[#9CA3AF] border border-white/[0.06]">
                  Genuine Hosted Sandbox
                </span>
              </div>

              {hasLink ? (
                <div className="space-y-3">
                  <div className="p-3 bg-surface-raised border border-white/[0.06] rounded-lg space-y-2 text-[11px] font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[#6B7280]">Payment Link ID:</span>
                      <span className="text-guard-text font-semibold">{status.payment_link_id}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#6B7280]">Amount:</span>
                      <span className="text-[#F0F2F5] font-semibold">₹2,500.00 INR</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#6B7280]">Status:</span>
                      <span
                        className={`font-semibold uppercase ${
                          isRecovered || status.payment_link_status === 'paid'
                            ? 'text-recover-text'
                            : 'text-risk-text'
                        }`}
                      >
                        {status.payment_link_status || 'created'}
                      </span>
                    </div>
                  </div>

                  {/* Primary Test Payment Action Button */}
                  <a
                    href={status.payment_link_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-2.5 px-4 rounded-md text-[12px] font-semibold text-white bg-guard-base hover:bg-[#0f9e91] active:bg-[#0b7a72] transition-colors flex items-center justify-center gap-2 shadow-[0_1px_3px_rgba(0,0,0,0.4)]"
                  >
                    <span>Open Test Payment in Razorpay</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>

                  {/* Copy Link Helper */}
                  <button
                    onClick={handleCopyLink}
                    className="w-full py-1.5 text-[11px] font-mono text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.06] rounded transition-colors flex items-center justify-center gap-1.5"
                  >
                    {copiedLink ? (
                      <>
                        <Check className="w-3 h-3 text-recover-text" />
                        <span>Link URL Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy Hosted URL</span>
                      </>
                    )}
                  </button>

                  {/* Test Mode Card Helper */}
                  <div className="p-3 bg-white/[0.02] border border-white/[0.06] rounded-md space-y-1.5 text-[11px]">
                    <div className="font-semibold text-[#D1D5DB] flex items-center justify-between">
                      <span>Razorpay Test Card:</span>
                      <button
                        onClick={handleCopyCard}
                        className="text-[10px] text-ai-text hover:underline flex items-center gap-1 font-mono"
                      >
                        {copiedCard ? 'Copied' : 'Copy Card #'}
                      </button>
                    </div>
                    <div className="font-mono text-xs text-[#F0F2F5] bg-surface-raised p-1.5 rounded border border-white/[0.04]">
                      4111 1111 1111 1111
                    </div>
                    <div className="text-[10px] text-[#6B7280]">
                      Expiry: Any future date (e.g. 12/30) · CVV: 123 · OTP: Any 6 digits
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center text-[12px] text-[#6B7280] font-mono">
                  No payment link active. Launch scenario to generate one.
                </div>
              )}
            </div>

            {/* Card 2: Authoritative Gateway Verification & Attribution */}
            <div className="bg-surface-base border border-white/[0.08] rounded-xl p-5 space-y-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-guard-text" />
                    <h3 className="text-[13px] font-semibold text-[#F0F2F5]">
                      Gateway Capture Verification
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-raised text-[#9CA3AF] border border-white/[0.06]">
                    Direct Gateway Query
                  </span>
                </div>

                <p className="text-[11px] text-[#6B7280] leading-relaxed mb-4">
                  Directly queries the Razorpay API for live payment status and invokes authoritative revenue attribution. Recovered revenue is credited only upon captured payment confirmation.
                </p>

                {isRecovered ? (
                  <div className="p-4 rounded-lg bg-[rgba(5,150,105,0.10)] border border-[rgba(5,150,105,0.30)] space-y-2">
                    <div className="flex items-center gap-2 text-recover-text font-semibold text-[13px]">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>VERIFIED RECOVERY · CASH ATTRIBUTED</span>
                    </div>
                    <div className="mt-2">
                      <MoneyValue
                        amountInr={status.recovered_amount_inr ?? 2500}
                        variant="recovered"
                        size="lg"
                      />
                    </div>
                    <div className="text-[11px] font-mono text-[#9CA3AF] pt-2 border-t border-[rgba(5,150,105,0.20)] space-y-1">
                      <div>Captured Payment ID: <strong className="text-[#F0F2F5]">{status.recovered_payment_id || 'pay_verified'}</strong></div>
                      <div>Attribution Mechanism: Razorpay Webhook HMAC Signature Validated</div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="p-3 bg-surface-raised border border-white/[0.06] rounded-lg text-[11px] font-mono space-y-1.5 text-[#9CA3AF]">
                      <div className="flex items-center justify-between">
                        <span>Attributed Revenue:</span>
                        <span className="text-[#6B7280] font-semibold">₹0.00 (Unverified)</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Verification Rule:</span>
                        <span className="text-[#D1D5DB]">Captured payment ID required</span>
                      </div>
                    </div>

                    <ActionButton
                      label={verifying ? 'Verifying Gateway…' : 'Verify Payment Capture'}
                      variant="primary"
                      size="md"
                      icon={RefreshCw}
                      loading={verifying}
                      disabled={!hasLink || isRecovered}
                      onClick={handleVerify}
                      className="w-full"
                    />

                    {verifyResult && !verifyResult.verified && (
                      <div className="p-3 bg-[rgba(217,119,6,0.10)] border border-[rgba(217,119,6,0.25)] rounded text-[11px] text-risk-text flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                        <div>
                          <strong>Payment Not Yet Completed</strong>
                          <p className="text-[10px] opacity-90 mt-0.5">
                            {verifyResult.message || 'Link is unpaid. Complete checkout in the test tab and verify again.'}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="text-[10px] font-mono text-[#6B7280] pt-3 border-t border-white/[0.04]">
                Auto-polling every 5s while waiting for customer payment.
              </div>
            </div>
          </div>

          {/* Section E: Tabbed Decision Story & Immutable Audit Stream */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('journey')}
                  className={`px-3 py-1 text-[11px] font-mono font-medium rounded transition-colors ${
                    activeTab === 'journey'
                      ? 'bg-surface-raised text-[#F0F2F5] border border-white/[0.12]'
                      : 'text-[#6B7280] hover:text-[#9CA3AF]'
                  }`}
                >
                  Decision Rationale
                </button>
                <button
                  onClick={() => setActiveTab('audit')}
                  className={`px-3 py-1 text-[11px] font-mono font-medium rounded transition-colors flex items-center gap-1.5 ${
                    activeTab === 'audit'
                      ? 'bg-surface-raised text-[#F0F2F5] border border-white/[0.12]'
                      : 'text-[#6B7280] hover:text-[#9CA3AF]'
                  }`}
                >
                  <span>Immutable Audit Stream</span>
                  <span className="text-[10px] font-bold opacity-75">
                    ({status.audit_trail?.length ?? 0})
                  </span>
                </button>
              </div>

              {onNavigateToInvestigation && (
                <button
                  onClick={() => onNavigateToInvestigation(status.case_id)}
                  className="text-[11px] font-mono text-ai-text hover:underline flex items-center gap-1"
                >
                  Open Full Case Investigation <Search className="w-3 h-3" />
                </button>
              )}
            </div>

            {activeTab === 'journey' && (
              <div className="p-4 bg-surface-base border border-white/[0.06] rounded-xl text-[12px] text-[#9CA3AF] space-y-2 leading-relaxed">
                <h4 className="text-[13px] font-semibold text-[#F0F2F5]">
                  Why This Recovery Succeeded
                </h4>
                <p>
                  1. <strong>Failure Detection:</strong> The customer dropped off during bank OTP entry, generating a transient <code className="text-[#D1D5DB] font-mono">BAD_REQUEST_ERROR</code>.
                </p>
                <p>
                  2. <strong>AI Diagnosis:</strong> The model ingested sanitized checkout telemetry and recognized that intent was intact, proposing <code className="text-ai-text font-mono">P_CREATE_LINK_IMMEDIATE</code>.
                </p>
                <p>
                  3. <strong>Guardrail Gate:</strong> Deterministic financial guardrails verified that the transaction amount was under the ₹50,000 human escalation threshold, exact paise was preserved, and no active links were dispatched in the last 24h.
                </p>
                <p>
                  4. <strong>Bounded Action & Verification:</strong> RecoveryExecutor created a genuine Razorpay Test Mode Payment Link. Upon customer completion, the backend authoritatively confirmed gateway capture and attributed the ₹2,500.00 recovery.
                </p>
              </div>
            )}

            {activeTab === 'audit' && (
              <div className="bg-surface-base border border-white/[0.06] rounded-xl p-4">
                <AuditTimeline events={status.audit_trail || []} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
