import React, { useState, useMemo } from 'react';
import {
  ArrowLeft,
  Zap,
  RefreshCw,
  BrainCircuit,
  ShieldCheck,
  Copy,
  ExternalLink,
  Bot,
  Lock,
  ListChecks,
  GitMerge,
  Clock,
  Sparkles,
} from 'lucide-react';
import type { CaseDetailResponse, CaseState } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { MoneyValue } from '../components/common/MoneyValue';
import { ActionButton } from '../components/common/ActionButton';
import { PageHeader } from '../components/common/PageHeader';
import { SectionHeader } from '../components/common/SectionHeader';
import { ZoneCard } from '../components/common/ZoneCard';
import { AuditTimeline } from '../components/common/AuditTimeline';
import { DataRow } from '../components/common/DataRow';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../components/common/Toast';

interface CaseInvestigationPageProps {
  caseId: string | null;
  detail: CaseDetailResponse | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onTriggerTriage: (caseId: string) => void;
  triageLoading: boolean;
  onRefresh: () => void;
}

type Tab = 'story' | 'audit' | 'telemetry';

export const CaseInvestigationPage: React.FC<CaseInvestigationPageProps> = ({
  caseId,
  detail,
  loading,
  error,
  onBack,
  onTriggerTriage,
  triageLoading,
  onRefresh,
}) => {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<Tab>('story');

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    showToast('info', 'Copied to Clipboard', `${label}: ${text.slice(0, 36)}…`);
  };

  const c = detail?.case;
  const audits = detail?.audit_trail || [];

  // Determine Guardrail vs AI Relationship
  const guardrailAnalysis = useMemo(() => {
    if (!c) return null;
    const aiProposed = c.ai_policy_id;
    const guardrailAuth = c.validated_policy_id;

    const isOverridden = Boolean(aiProposed && guardrailAuth && aiProposed !== guardrailAuth);
    const isApproved = Boolean(aiProposed && guardrailAuth && aiProposed === guardrailAuth);
    const isEscalated = c.state === 'ESCALATED' || guardrailAuth === 'P_ESCALATE_ONLY';
    const isHalted = c.state === 'TERMINAL_NO_ACTION' || guardrailAuth === 'P_NO_ACTION';

    // Find guardrail validation audit event
    const validationEvent = audits.find(
      (a) => a.event_type === 'POLICY_GUARDRAIL_VALIDATED' || a.actor === 'policy_engine'
    );
    const reasons = (validationEvent?.details?.reasons as string[]) || [];

    const defaultDecision = isHalted
      ? (c.eligibility_status === 'INELIGIBLE' || isOverridden ? 'REJECT' : 'APPROVE')
      : isOverridden
      ? 'DOWNGRADE'
      : isApproved
      ? 'APPROVE'
      : 'EVALUATE';

    return {
      aiProposed,
      guardrailAuth,
      isOverridden,
      isApproved,
      isEscalated,
      isHalted,
      reasons,
      decision: validationEvent?.decision || defaultDecision,
    };
  }, [c, audits]);

  // Specific invariant statuses derived from case attributes & audit reasons
  const invariantChecks = useMemo(() => {
    if (!c) {
      return {
        amount: { label: 'Lock Enforced', violated: false },
        currency: { label: 'Constant Enforced', violated: false },
        idempotency: { label: 'Max 1 Link Enforced', violated: false },
        amlGate: { label: 'Passed (<₹50k)', violated: false },
      };
    }

    const reasonsJoined = (guardrailAnalysis?.reasons || []).join(' ') + ' ' + (c.eligibility_reason || '');

    // Amount check
    const amountViolated = /amount.*not match|amount.*mutation|invalid_amount/i.test(reasonsJoined);
    const amountLabel = amountViolated
      ? 'REJECTED: Amount Modified'
      : `₹${c.amount_inr.toFixed(2)} Lock Verified`;

    // Currency check
    const currencyViolated = /currency.*not match|currency.*mutation/i.test(reasonsJoined);
    const currencyLabel = currencyViolated
      ? 'REJECTED: Currency Mismatch'
      : `${c.currency || 'INR'} Constant Verified`;

    // Single link idempotency check
    let idempotencyLabel = 'Max 1 Link Enforced';
    let idempotencyViolated = false;
    if (/duplicate/i.test(reasonsJoined)) {
      idempotencyLabel = 'BLOCKED: Duplicate Event';
      idempotencyViolated = true;
    } else if (/max_attempts|cooldown/i.test(reasonsJoined)) {
      idempotencyLabel = 'BLOCKED: Cooldown Limit';
      idempotencyViolated = true;
    } else if (/already_paid|already paid/i.test(reasonsJoined)) {
      idempotencyLabel = 'BLOCKED: Order Already Paid';
      idempotencyViolated = true;
    }

    // High value & AML
    let amlLabel = 'Passed (<₹50k)';
    let amlViolated = false;
    if (c.amount_inr > 50000) {
      amlLabel = 'Gated: Exceeds ₹50k Limit';
      amlViolated = true;
    } else if (c.failure_category === 'C4') {
      amlLabel = 'Gated: AML / Risk Flag';
      amlViolated = true;
    } else if (c.failure_category === 'C5') {
      amlLabel = 'Halted: C5 Gateway Fatal';
      amlViolated = true;
    }

    return {
      amount: { label: amountLabel, violated: amountViolated },
      currency: { label: currencyLabel, violated: currencyViolated },
      idempotency: { label: idempotencyLabel, violated: idempotencyViolated },
      amlGate: { label: amlLabel, violated: amlViolated },
    };
  }, [c, guardrailAnalysis]);

  // Dynamic "Why this happened" narrative derivation
  const causalNarrative = useMemo(() => {
    if (!c) return '';
    const cat = c.failure_category || 'Unclassified';
    const desc = c.failure_description || 'Payment failure detected at checkout.';

    if (c.state === 'RECOVERED') {
      const policyType = c.validated_policy_id === 'P_CREATE_LINK_DELAYED' ? 'delayed link' : 'immediate link';
      if (c.case_source === 'CANONICAL_EVALUATION') {
        return `Transaction failed due to ${cat} (${desc}). Evaluated under controlled recovery evaluation: AI proposed ${policyType}, deterministic guardrails validated all policy invariants, and verified recovery credit of ₹${c.recovered_amount_inr.toLocaleString('en-IN')} was attributed to pipeline revenue.`;
      }
      return `Transaction failed due to ${cat} (${desc}). The AI advisory proposed ${policyType}. Deterministic guardrails verified all safety checks (amount & currency lock, cooldown, single-link limit) and authorized link creation. The customer completed checkout, and Razorpay captured webhook verified authentic revenue of ₹${c.recovered_amount_inr.toLocaleString('en-IN')}.`;
    }
    if (c.state === 'ESCALATED') {
      return `Transaction failed with code ${c.failure_code || 'RISK_CHECK_FAILED'} (${cat}: ${desc}). Although the AI proposed recovery, the deterministic policy engine enforced compliance invariants (${c.eligibility_reason || 'Safety / Compliance Gate'}), downgraded the action to manual escalation, and safely halted automated writes to protect merchant risk.`;
    }
    if (c.state === 'TERMINAL_NO_ACTION') {
      return `Transaction failed with ${cat} (${desc}). The eligibility engine determined this case is non-recoverable (${c.eligibility_reason || 'Terminal defect'}). Guardrails enforced P_NO_ACTION, preventing wasteful customer messaging or duplicate payment links.`;
    }
    if (c.state === 'ACTION_EXECUTED') {
      const policyType = c.validated_policy_id === 'P_CREATE_LINK_DELAYED' ? 'delayed link' : 'immediate link';
      if (c.case_source === 'CANONICAL_EVALUATION') {
        return `Transaction failed with ${cat} (${desc}). Evaluated under controlled recovery evaluation: AI proposed ${policyType}, and deterministic guardrails validated the recovery action. Dispatched recovery link is currently active and in-flight awaiting customer checkout.`;
      }
      return `Transaction failed with ${cat} (${desc}). The AI proposed ${policyType}, which was verified and authorized by deterministic guardrails. A genuine Razorpay Hosted Payment Link was generated and dispatched. Currently in-flight awaiting customer checkout.`;
    }
    return `Transaction failed with ${cat} (${desc}). Ingested and awaiting automated or manual triage evaluation.`;
  }, [c]);

  // Loading State
  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in" aria-busy="true">
        <div className="h-10 w-48 skeleton-shimmer rounded" />
        <div className="h-28 w-full skeleton-shimmer rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 skeleton-shimmer rounded-lg" />
          ))}
        </div>
        <div className="h-72 w-full skeleton-shimmer rounded-lg" />
      </div>
    );
  }

  // Error State
  if (error || !c) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Case Investigation"
          description="Trace the recovery decision from failure to verified outcome."
          actions={
            <ActionButton
              label="Back to Cases"
              variant="secondary"
              icon={ArrowLeft}
              onClick={onBack}
            />
          }
        />
        <ErrorBanner
          title={error ? `Failed to load case ${caseId}` : 'Case Not Found'}
          message={error || `Case ID "${caseId}" was not found in the recovery pipeline.`}
          onRetry={onRefresh}
        />
        <EmptyState
          icon={GitMerge}
          title="No case details available"
          description="Return to the Cases Explorer to choose an active recovery case."
          actionText="Return to Cases"
          onAction={onBack}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── A. Page Header ─────────────────────────────────────────────────── */}
      <PageHeader
        title={`Case Investigation · ${c.case_id}`}
        description="Trace the complete decision story: failure detection, AI proposal, guardrail authorization, and verified gateway cash."
        breadcrumbs={[
          { label: 'Cases', onClick: onBack },
          { label: c.case_id },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <ActionButton
              label="Back to Cases"
              variant="secondary"
              size="sm"
              icon={ArrowLeft}
              onClick={onBack}
            />
            {c.state === 'FAILED_INGESTED' && (
              <ActionButton
                label={triageLoading ? 'Triaging…' : 'Execute Triage'}
                variant="primary"
                size="sm"
                icon={Zap}
                loading={triageLoading}
                onClick={() => onTriggerTriage(c.case_id)}
              />
            )}
            <ActionButton
              label="Refresh"
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={onRefresh}
            />
          </div>
        }
      />

      {/* ── State-Aware Provenance Banner for Live Merchant Recovery ─────── */}
      {c.case_source === 'MERCHANT_CHECKOUT' && (
        <div className="bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.25)] rounded-lg p-3.5 px-4 space-y-2 text-[11px]">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 font-mono text-[10px] font-bold uppercase tracking-wider">
                Live Merchant Recovery
              </span>
              <span className="px-1.5 py-0.5 rounded bg-white/[0.08] text-[#9CA3AF] font-mono text-[10px]">
                Razorpay Test Mode
              </span>
            </div>
            {c.order_id && (
              <span className="text-[10px] font-mono text-teal-200">
                Merchant Order: {c.order_id}
              </span>
            )}
          </div>

          {/* State-Aware Content */}
          {c.state === 'FAILED_INGESTED' && (
            <p className="text-[#D1D5DB] leading-relaxed">
              Real merchant checkout failure received and ingested. Recovery triage and guardrail verification have not yet executed. No recovered amount attributed.
            </p>
          )}

          {c.state === 'ACTION_EXECUTED' && (
            <div className="space-y-1 text-[#D1D5DB] leading-relaxed">
              <p>
                Deterministic recovery action authorized and executed. Razorpay Payment Link generated and dispatched to customer via native notification.
              </p>
              <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono text-[#9CA3AF] pt-1 border-t border-teal-500/20">
                <span>Status: <strong className="text-amber-300">Awaiting Customer Payment</strong></span>
                {c.payment_link_id && <span>Payment Link: <strong className="text-white">{c.payment_link_id}</strong></span>}
                <span>Recovered Amount: <strong className="text-white">₹0.00</strong> (pending customer action)</span>
              </div>
            </div>
          )}

          {c.state === 'RECOVERED' && (
            <div className="space-y-1 text-[#D1D5DB] leading-relaxed">
              <p>
                Customer opened recovery Payment Link and completed checkout. Authoritative Razorpay REST verification confirmed gateway capture. Single attribution recorded.
              </p>
              <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono text-[#9CA3AF] pt-1 border-t border-teal-500/20">
                <span>Outcome: <strong className="text-recover-text">Authoritative Gateway Verified Capture</strong></span>
                <span>Recovered Cash: <strong className="text-recover-text font-bold">₹{c.recovered_amount_inr.toLocaleString('en-IN')}</strong></span>
                {c.payment_link_id && <span>Payment Link: <strong className="text-white">{c.payment_link_id}</strong></span>}
                {c.failed_payment_id && <span>Original Payment: <strong className="text-white">{c.failed_payment_id}</strong></span>}
              </div>
            </div>
          )}

          {c.state === 'ESCALATED' && (
            <p className="text-[#D1D5DB] leading-relaxed">
              Real merchant checkout transaction escalated to operations review under compliance guardrails. Automated recovery link withheld. State: <strong className="text-risk-text font-mono">ESCALATED</strong>.
            </p>
          )}

          {c.state === 'TERMINAL_NO_ACTION' && (
            <p className="text-[#D1D5DB] leading-relaxed">
              Real merchant checkout transaction halted under deterministic safety invariants (P_NO_ACTION). Automated recovery withheld to prevent duplicate links or futile messaging.
            </p>
          )}

          {c.state !== 'FAILED_INGESTED' && c.state !== 'ACTION_EXECUTED' && c.state !== 'RECOVERED' && c.state !== 'ESCALATED' && c.state !== 'TERMINAL_NO_ACTION' && (
            <p className="text-[#D1D5DB] leading-relaxed">
              Real merchant checkout transaction halted or escalated under deterministic compliance guardrails. State: <strong className="text-white font-mono">{c.state}</strong>.
            </p>
          )}
        </div>
      )}

      {/* ── B. Case Identity & Outcome Strip ───────────────────────────────── */}
      <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-[14px] font-bold text-[#F0F2F5]">
              {c.case_id}
            </span>
            <button
              onClick={() => handleCopy(c.case_id, 'Case ID')}
              className="text-[#4B5563] hover:text-[#9CA3AF] transition-colors p-0.5"
              aria-label="Copy case ID"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <StateBadge state={c.state as CaseState} />
            <CategoryBadge category={c.failure_category} />
            {c.customer_id && (
              <span className="text-[11px] font-mono text-[#6B7280]">
                Customer: <strong className="text-[#9CA3AF]">{c.customer_id}</strong>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] text-[#4B5563]">
            <Clock className="w-3.5 h-3.5" />
            <span>Ingested: {new Date(c.created_at || Date.now()).toUTCString()}</span>
          </div>
        </div>

        {/* 4 Core Financial & Decision Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {/* Metric 1: Revenue at Risk */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3.5 flex flex-col justify-between">
            <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
              Revenue at Risk
            </span>
            <div className="mt-1">
              <MoneyValue
                amountInr={c.amount_inr}
                variant={c.state === 'RECOVERED' ? 'neutral' : 'at-risk'}
                size="lg"
              />
              <div className="text-[10px] font-mono text-[#4B5563] mt-0.5">
                {c.currency} · Base units: {c.amount_paise.toLocaleString('en-IN')}
              </div>
            </div>
          </div>

          {/* Metric 2: AI Proposal */}
          <div className="bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.20)] rounded-md p-3.5 flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-ai-text uppercase tracking-wider flex items-center gap-1">
                <Bot className="w-3 h-3" /> AI Advisory
              </span>
              <span className="text-[9px] font-mono text-ai-text/60">MCP Read-Only</span>
            </div>
            <div className="mt-1">
              <PolicyBadge policy={c.ai_policy_id} context="ai" />
              <div className="text-[10px] font-mono text-[#6B7280] mt-1">
                {c.ai_explanation
                  ? 'Rationale logged'
                  : c.state === 'TERMINAL_NO_ACTION' && !c.ai_policy_id
                  ? 'Bypassed (Duplicate / Ineligible)'
                  : 'Pending triage'}
              </div>
            </div>
          </div>

          {/* Metric 3: Guardrail Authorized */}
          <div className="bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.20)] rounded-md p-3.5 flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-guard-text uppercase tracking-wider flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Guardrail Gate
              </span>
              <span className="text-[9px] font-mono text-guard-text/60">
                {guardrailAnalysis?.decision || 'DETERMINISTIC'}
              </span>
            </div>
            <div className="mt-1">
              <PolicyBadge policy={c.validated_policy_id} context="guard" />
              <div className="text-[10px] font-mono text-[#6B7280] mt-1">
                {guardrailAnalysis?.decision === 'REJECT'
                  ? 'Proposal Rejected'
                  : guardrailAnalysis?.isOverridden
                  ? 'Proposal Downgraded'
                  : c.state === 'TERMINAL_NO_ACTION'
                  ? 'Terminal Non-Recoverable'
                  : c.state === 'ESCALATED'
                  ? 'Threshold Escalated'
                  : c.state === 'FAILED_INGESTED'
                  ? 'Pending Evaluation'
                  : 'Safety Verified'}
              </div>
            </div>
          </div>

          {/* Metric 4: Verified Recovery Outcome */}
          <div
            className={`rounded-md p-3.5 flex flex-col justify-between border ${
              c.state === 'RECOVERED'
                ? 'bg-[rgba(5,150,105,0.08)] border-[rgba(5,150,105,0.25)]'
                : c.state === 'ESCALATED'
                ? 'bg-[rgba(217,119,6,0.08)] border-[rgba(217,119,6,0.25)]'
                : c.state === 'ACTION_EXECUTED'
                ? 'bg-[rgba(13,148,136,0.08)] border-[rgba(13,148,136,0.25)]'
                : 'bg-surface-raised border-white/[0.06]'
            }`}
          >
            <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
              {c.state === 'RECOVERED' ? 'Verified Recovered Cash' : 'Recovery Outcome'}
            </span>
            <div className="mt-1">
              {c.state === 'RECOVERED' ? (
                <>
                  <MoneyValue
                    amountInr={c.recovered_amount_inr}
                    variant="recovered"
                    size="lg"
                  />
                  <div className="text-[10px] font-mono text-recover-text mt-0.5 font-medium">
                    100% Captured & Attributed
                  </div>
                </>
              ) : c.state === 'ESCALATED' ? (
                <>
                  <span className="text-[15px] font-mono font-bold text-risk-text">
                    ESCALATED
                  </span>
                  <div className="text-[10px] font-mono text-risk-text mt-0.5">
                    Gated: Manual Review
                  </div>
                </>
              ) : c.state === 'ACTION_EXECUTED' ? (
                <>
                  <span className="text-[15px] font-mono font-bold text-guard-text">
                    ACTION EXECUTED
                  </span>
                  <div className="text-[10px] font-mono text-guard-text/80 mt-0.5">
                    In-Flight: Awaiting Payment
                  </div>
                </>
              ) : c.state === 'TERMINAL_NO_ACTION' ? (
                <>
                  <span className="text-[15px] font-mono font-bold text-[#9CA3AF]">
                    TERMINAL NO ACTION
                  </span>
                  <div className="text-[10px] font-mono text-[#6B7280] mt-0.5">
                    Withheld: Non-Recoverable
                  </div>
                </>
              ) : (
                <>
                  <span className="text-[15px] font-mono font-bold text-[#9CA3AF]">
                    {c.state.replace(/_/g, ' ')}
                  </span>
                  <div className="text-[10px] font-mono text-[#4B5563] mt-0.5">
                    Pending Triage
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── C. Decision Pipeline (Centerpiece 7-Stage Workflow) ─────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <SectionHeader
          title="End-to-End Decision Pipeline"
          subtitle="Chronological progression through the bounded recovery workflow"
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2 mt-4">
          {/* Stage 1: Detect */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">01 DETECTED</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Failure Ingest</div>
              <p className="text-[10px] text-[#6B7280] mt-1 leading-snug">
                Failure Event Captured
              </p>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.payment_method?.toUpperCase() || 'PAYMENT'}
            </div>
          </div>

          {/* Stage 2: Diagnose */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">02 DIAGNOSED</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Taxonomy C1–C5</div>
              <div className="mt-1">
                <CategoryBadge category={c.failure_category} />
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.failure_code ? c.failure_code.replace(/_/g, ' ') : 'Taxonomy Mapped'}
            </div>
          </div>

          {/* Stage 3: AI Recommendation (Violet Zone) */}
          <div className="bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.25)] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-ai-text uppercase flex items-center gap-1 font-semibold">
                <Bot className="w-2.5 h-2.5" /> 03 AI ADVISORY
              </div>
              <div className="text-[12px] font-semibold text-ai-text mt-0.5">Policy Proposal</div>
              <div className="mt-1">
                <PolicyBadge policy={c.ai_policy_id} context="ai" showIcon={false} />
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-[rgba(124,58,237,0.12)] text-[10px] font-mono text-ai-text/70">
              {c.ai_policy_id ? 'Read-Only Proposal' : 'Bypassed (Duplicate)'}
            </div>
          </div>

          {/* Stage 4: Guardrail Authorization (Teal Zone) */}
          <div className="bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.25)] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-guard-text uppercase flex items-center gap-1 font-semibold">
                <ShieldCheck className="w-2.5 h-2.5" /> 04 GUARDRAIL
              </div>
              <div className="text-[12px] font-semibold text-guard-text mt-0.5">Deterministic Gate</div>
              <div className="mt-1">
                <PolicyBadge policy={c.validated_policy_id} context="guard" showIcon={false} />
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-[rgba(13,148,136,0.12)] text-[10px] font-mono text-guard-text/70">
              {guardrailAnalysis?.decision}
            </div>
          </div>

          {/* Stage 5: Action */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">05 ACTION</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Execution</div>
              <p className="text-[10px] text-[#6B7280] mt-1 leading-snug">
                {c.state === 'RECOVERED'
                  ? 'Link Dispatched'
                  : c.state === 'ACTION_EXECUTED'
                  ? 'Link Dispatched'
                  : c.state === 'ESCALATED'
                  ? 'Gated Escalation'
                  : c.state === 'TERMINAL_NO_ACTION'
                  ? 'Action Withheld'
                  : 'Pending Triage'}
              </p>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.state === 'RECOVERED'
                ? 'Checkout Completed'
                : c.state === 'ACTION_EXECUTED'
                ? 'Link Active'
                : c.state === 'ESCALATED'
                ? 'Safeguarded'
                : c.state === 'TERMINAL_NO_ACTION'
                ? 'Safely Halted'
                : 'Awaiting Evaluation'}
            </div>
          </div>

          {/* Stage 6: Verification */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">06 VERIFY</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Gateway Capture</div>
              <p className="text-[10px] text-[#6B7280] mt-1 leading-snug">
                {c.state === 'RECOVERED'
                  ? 'Captured Webhook'
                  : c.state === 'ACTION_EXECUTED'
                  ? 'Awaiting Webhook'
                  : c.state === 'ESCALATED'
                  ? 'Escalation Logged'
                  : c.state === 'TERMINAL_NO_ACTION'
                  ? 'Not Applicable'
                  : 'Pending'}
              </p>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.state === 'RECOVERED'
                ? 'Capture Confirmed'
                : c.state === 'ACTION_EXECUTED'
                ? 'Awaiting Payment'
                : c.state === 'ESCALATED'
                ? 'Zero Attribution'
                : c.state === 'TERMINAL_NO_ACTION'
                ? 'Zero Attribution'
                : 'Pending Assessment'}
            </div>
          </div>

          {/* Stage 7: Outcome */}
          <div
            className={`rounded-md p-3 flex flex-col justify-between border ${
              c.state === 'RECOVERED'
                ? 'bg-[rgba(5,150,105,0.06)] border-[rgba(5,150,105,0.25)]'
                : c.state === 'ACTION_EXECUTED'
                ? 'bg-[rgba(13,148,136,0.06)] border-[rgba(13,148,136,0.25)]'
                : c.state === 'ESCALATED'
                ? 'bg-[rgba(217,119,6,0.06)] border-[rgba(217,119,6,0.25)]'
                : 'bg-surface-raised border-white/[0.06]'
            }`}
          >
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">07 OUTCOME</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Persisted State</div>
              <div className="mt-1">
                <StateBadge state={c.state as CaseState} size="sm" />
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono font-semibold">
              {c.state === 'RECOVERED' ? (
                <span className="text-recover-text">Attributed</span>
              ) : c.state === 'ACTION_EXECUTED' ? (
                <span className="text-guard-text">In-Flight</span>
              ) : c.state === 'ESCALATED' ? (
                <span className="text-risk-text">Gated Escalation</span>
              ) : c.state === 'TERMINAL_NO_ACTION' ? (
                <span className="text-[#9CA3AF]">Closed Terminal</span>
              ) : (
                <span className="text-blue-300">Pending Triage</span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── Sub-navigation Tab Bar ────────────────────────────────────────── */}
      <div className="flex items-center gap-1 border-b border-white/[0.06] overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => setActiveTab('story')}
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all shrink-0 ${
            activeTab === 'story'
              ? 'border-b-ai-base text-[#F0F2F5]'
              : 'border-b-transparent text-[#6B7280] hover:text-[#9CA3AF]'
          }`}
        >
          <BrainCircuit className="w-3.5 h-3.5" />
          Decision Story & Rationale
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all shrink-0 ${
            activeTab === 'audit'
              ? 'border-b-ai-base text-[#F0F2F5]'
              : 'border-b-transparent text-[#6B7280] hover:text-[#9CA3AF]'
          }`}
        >
          <ListChecks className="w-3.5 h-3.5" />
          Immutable Audit Stream ({audits.length})
        </button>

        <button
          onClick={() => setActiveTab('telemetry')}
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all shrink-0 ${
            activeTab === 'telemetry'
              ? 'border-b-ai-base text-[#F0F2F5]'
              : 'border-b-transparent text-[#6B7280] hover:text-[#9CA3AF]'
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          Raw JSON Telemetry
        </button>
      </div>

      {/* ── Tab Content: Decision Story ───────────────────────────────────── */}
      {activeTab === 'story' && (
        <div className="space-y-6 animate-fade-in">
          {/* Causal Narrative Box ("Why This Happened") */}
          <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
            <div className="flex items-center gap-2 text-[11px] font-mono text-[#9CA3AF] uppercase tracking-wider mb-2 font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-guard-text" />
              Decision Transparency Rationale
            </div>
            <p className="text-[12px] text-[#D1D5DB] leading-relaxed">
              {causalNarrative}
            </p>
          </div>

          {/* D & E: AI Advisory vs Guardrail Authorization (2-Column High-Contrast Grid) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Violet Zone: AI Advisory */}
            <ZoneCard
              zone="ai"
              label="AI ADVISORY · RECOMMENDATION ONLY"
              icon={Bot}
              description="Read-only diagnostic proposal generated via sanitized MCP context"
            >
              <div className="space-y-3.5">
                <div className="p-3 bg-white/[0.02] border border-[rgba(124,58,237,0.15)] rounded-md space-y-2">
                  <div className="text-[10px] font-mono text-ai-text uppercase font-semibold">
                    Advisory Policy Proposal
                  </div>
                  <div className="flex items-center justify-between">
                    <PolicyBadge policy={c.ai_policy_id} context="ai" />
                    <span className="text-[10px] font-mono text-[#6B7280]">
                      Category: {c.failure_category || 'C1'}
                    </span>
                  </div>
                </div>

                {c.ai_explanation ? (
                  <div className="p-3 bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.18)] rounded-md">
                    <div className="text-[10px] font-mono text-ai-text uppercase font-semibold mb-1">
                      LLM Reasoning Explanation
                    </div>
                    <p className="text-[11px] text-[#C4B5FD] italic leading-relaxed">
                      &ldquo;{c.ai_explanation}&rdquo;
                    </p>
                  </div>
                ) : (c.eligibility_reason === 'DUPLICATE_EVENT' || !c.ai_policy_id) ? (
                  <div className="p-3 bg-white/[0.02] border border-white/[0.06] rounded-md">
                    <div className="text-[10px] font-mono text-[#9CA3AF] uppercase font-semibold mb-1">
                      Advisory Layer Note
                    </div>
                    <p className="text-[11px] text-[#6B7280] leading-relaxed">
                      AI diagnostic invocation bypassed: duplicate or ineligible failure event suppressed prior to LLM reasoning.
                    </p>
                  </div>
                ) : null}

                <div className="space-y-1.5 text-[11px] pt-1">
                  <DataRow label="Diagnosed Category" value={c.failure_category || 'C1'} mono />
                  <DataRow label="Diagnosis Rule" value={c.failure_code || 'BAD_REQUEST_ERROR'} mono />
                  <DataRow label="Advisory Provider" value="gemini-2.5-flash via MCP" mono />
                </div>

                {/* Explicit Responsibility Boundary Notice */}
                <div className="p-2.5 rounded bg-black/30 border border-white/[0.04] text-[10px] font-mono text-[#6B7280] leading-snug">
                  🛡️ <strong>Safety Invariant:</strong> The AI advisory layer operates strictly in read-only mode and has zero write authority to payment gateways.
                </div>
              </div>
            </ZoneCard>

            {/* Teal Zone: Guardrail Authorization */}
            <ZoneCard
              zone="guard"
              label="GUARDRAIL GATE · DETERMINISTIC AUTHORIZATION"
              icon={ShieldCheck}
              description="Deterministic mathematical invariants enforce merchant risk & compliance rules"
            >
              <div className="space-y-3.5">
                <div className="p-3 bg-white/[0.02] border border-[rgba(13,148,136,0.15)] rounded-md space-y-2">
                  <div className="text-[10px] font-mono text-guard-text uppercase font-semibold flex items-center justify-between">
                    <span>Authorized Policy Execution</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-guard-muted text-guard-text border border-guard-border">
                      {guardrailAnalysis?.decision}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <PolicyBadge policy={c.validated_policy_id} context="guard" />
                    <span className="text-[10px] font-mono text-guard-text">
                      {guardrailAnalysis?.decision === 'REJECT'
                        ? 'AI Proposal Rejected'
                        : guardrailAnalysis?.isOverridden
                        ? 'AI Proposal Overridden'
                        : 'Authorized as Proposed'}
                    </span>
                  </div>
                </div>

                {/* Specific Rule / Reason */}
                <div className="p-3 bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.18)] rounded-md">
                  <div className="text-[10px] font-mono text-guard-text uppercase font-semibold mb-1">
                    Authorization Enforcement Rationale
                  </div>
                  <p className="text-[11px] text-[#5EEAD4] leading-relaxed">
                    {guardrailAnalysis?.reasons.length
                      ? guardrailAnalysis.reasons.join(' · ')
                      : c.eligibility_reason
                      ? `Enforced rule: ${c.eligibility_reason}`
                      : 'Deterministic guardrail checks satisfied without policy downgrade.'}
                  </p>
                </div>

                {/* Supported Invariants Checklist */}
                <div className="space-y-1 text-[11px] pt-1">
                  <div className="flex items-center justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-[#6B7280]">Amount Immutability:</span>
                    <span className={`font-mono text-[11px] ${invariantChecks.amount.violated ? 'text-halt-text font-bold' : 'text-guard-text'}`}>
                      {invariantChecks.amount.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-[#6B7280]">Currency Lock:</span>
                    <span className={`font-mono text-[11px] ${invariantChecks.currency.violated ? 'text-halt-text font-bold' : 'text-guard-text'}`}>
                      {invariantChecks.currency.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-[#6B7280]">Single-Link Idempotency:</span>
                    <span className={`font-mono text-[11px] ${invariantChecks.idempotency.violated ? 'text-halt-text font-bold' : 'text-guard-text'}`}>
                      {invariantChecks.idempotency.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <span className="text-[#6B7280]">High-Value & AML Gate:</span>
                    <span className={`font-mono text-[11px] ${invariantChecks.amlGate.violated ? 'text-risk-text font-bold' : 'text-guard-text'}`}>
                      {invariantChecks.amlGate.label}
                    </span>
                  </div>
                </div>
              </div>
            </ZoneCard>
          </div>

          {/* F & G: Action Execution & Gateway Verification (2-Column Grid) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Panel F: Action / Razorpay Execution */}
            <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4">
              <SectionHeader
                title="Action Execution"
                subtitle={
                  c.state === 'TERMINAL_NO_ACTION'
                    ? 'Automated recovery withheld under deterministic safety policy'
                    : c.state === 'ESCALATED'
                    ? 'Automated gateway write halted; routed to operations review'
                    : c.state === 'FAILED_INGESTED'
                    ? 'Awaiting triage evaluation; no gateway action executed'
                    : c.case_source === 'CANONICAL_EVALUATION'
                    ? 'Safe evaluation execution under deterministic policy'
                    : 'Gateway write dispatched under deterministic policy'
                }
                badge={
                  c.payment_link_id
                    ? 'Executed'
                    : c.state === 'ESCALATED'
                    ? 'Escalated'
                    : c.state === 'TERMINAL_NO_ACTION'
                    ? 'Withheld'
                    : 'Pending'
                }
              />

              <div className="space-y-2 text-[11px]">
                <DataRow
                  label="Action Status"
                  value={
                    c.state === 'TERMINAL_NO_ACTION'
                      ? 'WITHHELD (P_NO_ACTION)'
                      : c.state === 'ESCALATED'
                      ? 'GATED_ESCALATION'
                      : c.state === 'FAILED_INGESTED'
                      ? 'PENDING_TRIAGE'
                      : (c.action_status || (c.payment_link_id ? 'EXECUTED' : 'SKIPPED'))
                  }
                  mono
                />
                <DataRow
                  label="Payment Link ID"
                  value={
                    c.payment_link_id ||
                    (c.state === 'TERMINAL_NO_ACTION'
                      ? 'None created (policy invariant)'
                      : c.state === 'ESCALATED'
                      ? 'None created (safeguarded)'
                      : 'None created (un-triaged)')
                  }
                  mono
                />
                <DataRow label="Reference ID" value={c.payment_link_reference_id || '—'} mono />
                <DataRow
                  label="Link State"
                  value={
                    c.state === 'TERMINAL_NO_ACTION' || c.state === 'ESCALATED' || c.state === 'FAILED_INGESTED'
                      ? 'NOT APPLICABLE'
                      : (c.payment_link_status?.toUpperCase() || '—')
                  }
                  mono
                />
                {c.payment_link_short_url && (
                  <div className="data-row flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
                    <span className="data-row__label">
                      {c.case_source === 'CANONICAL_EVALUATION' ? 'Evaluation Link Reference' : 'Payment Link URL'}
                    </span>
                    <div className="data-row__value flex-1 min-w-0">
                      {c.case_source === 'CANONICAL_EVALUATION' ? (
                        <div className="space-y-0.5">
                          <div className="text-[#9CA3AF] text-[11px] font-mono break-all select-all leading-relaxed">
                            {c.payment_link_short_url}
                          </div>
                          <div className="text-[10px] text-[#6B7280]">
                            (Evaluation synthetic route)
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start gap-2 min-w-0">
                          <a
                            href={c.payment_link_short_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-ai-text hover:underline break-all text-[11px] font-mono leading-relaxed"
                          >
                            {c.payment_link_short_url}
                          </a>
                          <a
                            href={c.payment_link_short_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[#6B7280] hover:text-[#F0F2F5] shrink-0 mt-0.5"
                            aria-label="Open payment link"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {c.payment_link_short_url && c.case_source !== 'CANONICAL_EVALUATION' && (
                <div className="pt-2">
                  <a
                    href={c.payment_link_short_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded bg-surface-raised hover:bg-white/[0.06] border border-white/[0.08] text-[11px] font-mono text-[#D1D5DB] transition-colors w-full"
                  >
                    Open Hosted Checkout Link <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>

            {/* Panel G: Verification & Revenue Outcome */}
            <div
              className={`border rounded-lg p-5 space-y-4 ${
                c.state === 'RECOVERED'
                  ? 'bg-[rgba(5,150,105,0.04)] border-[rgba(5,150,105,0.22)]'
                  : c.state === 'ACTION_EXECUTED'
                  ? 'bg-[rgba(13,148,136,0.04)] border-[rgba(13,148,136,0.22)]'
                  : c.state === 'ESCALATED'
                  ? 'bg-[rgba(217,119,6,0.04)] border-[rgba(217,119,6,0.22)]'
                  : 'bg-surface-base border-white/[0.06]'
              }`}
            >
              <SectionHeader
                title="Gateway Verification & Attribution"
                subtitle={
                  c.state === 'RECOVERED'
                    ? c.case_source === 'CANONICAL_EVALUATION'
                      ? 'Controlled evaluation capture attribution'
                      : 'Independent confirmation of status: captured'
                    : c.state === 'ESCALATED'
                    ? 'Zero financial attribution (controlled risk escalation)'
                    : c.state === 'TERMINAL_NO_ACTION'
                    ? 'No gateway capture expected (terminal non-recoverable)'
                    : c.state === 'ACTION_EXECUTED'
                    ? 'Awaiting customer completion and webhook confirmation'
                    : 'Pending automated triage and guardrail evaluation'
                }
                badge={
                  c.state === 'RECOVERED'
                    ? 'Verified Cash'
                    : c.state === 'ESCALATED'
                    ? 'Escalated'
                    : c.state === 'TERMINAL_NO_ACTION'
                    ? 'No Attribution'
                    : c.state === 'ACTION_EXECUTED'
                    ? 'Awaiting Payment'
                    : 'Pending'
                }
              />

              {c.state === 'RECOVERED' ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-[rgba(5,150,105,0.08)] border border-[rgba(5,150,105,0.20)]">
                    <span className="text-[10px] font-mono text-recover-text uppercase tracking-wider font-semibold block">
                      Authoritative Attribution Confirmed
                    </span>
                    <div className="mt-1 flex items-baseline gap-2">
                      <MoneyValue
                        amountInr={c.recovered_amount_inr}
                        variant="recovered"
                        size="xl"
                      />
                      <span className="text-[11px] text-recover-text font-mono font-medium">
                        credited to revenue
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Gateway Payment Status" value="captured" mono />
                    <DataRow label="Recovered Payment ID" value={c.recovered_payment_id || 'pay_verified'} mono />
                    <DataRow label="Attributed Amount" value={`₹${c.recovered_amount_inr.toFixed(2)}`} mono />
                    <DataRow
                      label="Verification Basis"
                      value={
                        c.case_source === 'CANONICAL_EVALUATION'
                          ? 'Deterministic Verification Engine'
                          : 'Razorpay HMAC SHA-256 Webhook'
                      }
                      mono
                    />
                  </div>
                </div>
              ) : c.state === 'ACTION_EXECUTED' ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-[rgba(13,148,136,0.08)] border border-[rgba(13,148,136,0.20)]">
                    <span className="text-[10px] font-mono text-guard-text uppercase tracking-wider font-semibold block">
                      Awaiting Customer Payment (In-Flight Opportunity)
                    </span>
                    <p className="text-[11px] text-[#5EEAD4] mt-1 leading-snug">
                      {c.case_source === 'CANONICAL_EVALUATION'
                        ? 'Deterministic recovery link dispatched and currently active. Capture attribution will register upon customer checkout.'
                        : 'Genuine Razorpay Payment Link dispatched to customer. Attributed revenue will register immediately upon authoritative webhook delivery.'}
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Gateway Payment Status" value="issued / active" mono />
                    <DataRow label="Verification Status" value="AWAITING GATEWAY CAPTURE" mono />
                    <DataRow label="Attributed Amount" value="₹0.00 (In-Flight Opportunity)" mono />
                    <DataRow
                      label="Verification Basis"
                      value={
                        c.case_source === 'CANONICAL_EVALUATION'
                          ? 'Deterministic Verification Engine'
                          : 'Razorpay HMAC SHA-256 Webhook'
                      }
                      mono
                    />
                  </div>
                </div>
              ) : c.state === 'ESCALATED' ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-[rgba(217,119,6,0.08)] border border-[rgba(217,119,6,0.20)]">
                    <span className="text-[10px] font-mono text-risk-text uppercase tracking-wider font-semibold block">
                      Zero Financial Attribution (Controlled Escalation)
                    </span>
                    <p className="text-[11px] text-[#FCD34D] mt-1 leading-snug">
                      Automated recovery withheld under safety guardrails. Transaction routed to operations team for manual adjudication.
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Gateway Payment Status" value="NOT APPLICABLE (WITHHELD)" mono />
                    <DataRow label="Verification Status" value="ESCALATED TO OPERATIONS" mono />
                    <DataRow label="Attributed Amount" value="₹0.00" mono />
                    <DataRow
                      label="Escalation Basis"
                      value={c.eligibility_reason ? `Enforced: ${c.eligibility_reason}` : 'Safety / Compliance Policy'}
                      mono
                    />
                  </div>
                </div>
              ) : c.state === 'TERMINAL_NO_ACTION' ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-surface-raised border border-white/[0.04]">
                    <span className="text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider font-semibold block">
                      Zero Attribution (Terminal Non-Recoverable Defect)
                    </span>
                    <p className="text-[11px] text-[#9CA3AF] mt-1 leading-snug">
                      Deterministic policy invariants determined this transaction cannot or should not be recovered automatically. No payment link was dispatched; no gateway capture is expected.
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Gateway Payment Status" value="NOT APPLICABLE (WITHHELD)" mono />
                    <DataRow label="Verification Status" value="NO CAPTURE EXPECTED" mono />
                    <DataRow label="Attributed Amount" value="₹0.00" mono />
                    <DataRow
                      label="Policy Basis"
                      value={c.eligibility_reason ? `Enforced: ${c.eligibility_reason}` : 'Deterministic Policy Invariant (P_NO_ACTION)'}
                      mono
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-surface-raised border border-white/[0.04]">
                    <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider font-semibold block">
                      Pending Triage & Assessment
                    </span>
                    <p className="text-[11px] text-[#9CA3AF] mt-1 leading-snug">
                      Transaction failure ingested into pipeline. Triage evaluation has not executed yet. No payment link created, zero attribution registered.
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Gateway Payment Status" value="FAILED (INGESTED)" mono />
                    <DataRow label="Verification Status" value="PENDING TRIAGE" mono />
                    <DataRow label="Attributed Amount" value="₹0.00" mono />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Content: Immutable Audit Stream ───────────────────────────── */}
      {activeTab === 'audit' && (
        <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4 animate-fade-in">
          <SectionHeader
            title="Immutable Chronological Audit Stream"
            subtitle="Every diagnostic prompt, proposal, guardrail decision, and webhook verified in order"
            badge={`${audits.length} Records`}
          />
          <AuditTimeline events={audits} />
        </div>
      )}

      {/* ── Tab Content: Raw JSON Telemetry ───────────────────────────────── */}
      {activeTab === 'telemetry' && (
        <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 space-y-4 animate-fade-in">
          <SectionHeader
            title="Full Case Telemetry Payload"
            subtitle="GET /cases/{case_id} raw state machine and context attributes"
            action={
              <ActionButton
                label="Copy Raw Record"
                variant="secondary"
                size="sm"
                icon={Copy}
                onClick={() => handleCopy(JSON.stringify(c, null, 2), 'Case Telemetry')}
              />
            }
          />
          <pre className="json-block" style={{ maxHeight: '440px' }}>
            {JSON.stringify(c, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
