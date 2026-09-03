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

    return {
      aiProposed,
      guardrailAuth,
      isOverridden,
      isApproved,
      isEscalated,
      isHalted,
      reasons,
      decision: validationEvent?.decision || (isOverridden ? 'DOWNGRADE' : isApproved ? 'APPROVE' : 'EVALUATE'),
    };
  }, [c, audits]);

  // Dynamic "Why this happened" narrative derivation
  const causalNarrative = useMemo(() => {
    if (!c) return '';
    const cat = c.failure_category || 'Unclassified';
    const desc = c.failure_description || 'Payment failure detected at checkout.';

    if (c.state === 'RECOVERED') {
      return `Transaction failed due to ${cat} (${desc}). The AI advisory proposed immediate recovery via ${c.ai_policy_id}. Deterministic guardrails verified all safety checks (amount & currency lock, cooldown, single-link limit) and authorized link creation. The customer completed checkout, and Razorpay captured webhook verified authentic revenue of ₹${c.recovered_amount_inr.toLocaleString('en-IN')}.`;
    }
    if (c.state === 'ESCALATED') {
      return `Transaction failed with code ${c.failure_code || 'RISK_CHECK_FAILED'} (${cat}: ${desc}). Although the AI proposed ${c.ai_policy_id || 'recovery'}, the deterministic policy engine enforced compliance invariants (${c.eligibility_reason || 'AML / Fraud Gate'}), downgraded the policy to P_ESCALATE_ONLY, and safely halted automated writes to protect merchant risk.`;
    }
    if (c.state === 'TERMINAL_NO_ACTION') {
      return `Transaction failed with ${cat} (${desc}). The eligibility engine determined this case is non-recoverable (${c.eligibility_reason || 'Terminal defect'}). Guardrails enforced P_NO_ACTION, preventing wasteful customer messaging or duplicate payment links.`;
    }
    if (c.state === 'ACTION_EXECUTED') {
      return `Transaction failed with ${cat} (${desc}). The AI proposed ${c.ai_policy_id}, which was verified and authorized by deterministic guardrails. A genuine Razorpay Hosted Payment Link was generated and dispatched. Currently in-flight awaiting customer checkout.`;
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
                {c.currency} · {c.amount_paise} paise
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
                {c.ai_explanation ? 'Rationale logged' : 'Pending triage'}
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
                {guardrailAnalysis?.isOverridden ? 'Proposal Downgraded' : 'Safety Verified'}
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
                : 'bg-surface-raised border-white/[0.06]'
            }`}
          >
            <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
              {c.state === 'RECOVERED' ? 'Verified Cash Won' : 'Recovery Outcome'}
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
              ) : (
                <>
                  <span className="text-[15px] font-mono font-bold text-[#9CA3AF]">
                    {c.state.replace(/_/g, ' ')}
                  </span>
                  <div className="text-[10px] font-mono text-[#4B5563] mt-0.5">
                    {c.payment_link_id ? 'In-Flight' : 'No Financial Credit'}
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
                {c.failed_payment_id}
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
              Read-Only Proposal
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
                {c.payment_link_id ? 'Link Dispatched' : c.state === 'ESCALATED' ? 'Escalated' : 'No Action'}
              </p>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.payment_link_id ? 'Link Active' : c.state === 'ESCALATED' ? 'Safeguarded' : 'No Action'}
            </div>
          </div>

          {/* Stage 6: Verification */}
          <div className="bg-surface-raised border border-white/[0.06] rounded-md p-3 flex flex-col justify-between">
            <div>
              <div className="text-[9px] font-mono text-[#6B7280] uppercase">06 VERIFY</div>
              <div className="text-[12px] font-semibold text-[#F0F2F5] mt-0.5">Gateway Capture</div>
              <p className="text-[10px] text-[#6B7280] mt-1 leading-snug">
                {c.recovered_payment_id ? 'Captured Webhook' : 'Unverified'}
              </p>
            </div>
            <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] font-mono text-[#4B5563]">
              {c.recovered_payment_id ? 'Capture Confirmed' : c.state === 'ESCALATED' ? 'Zero Attribution' : 'Awaiting Payment'}
            </div>
          </div>

          {/* Stage 7: Outcome */}
          <div
            className={`rounded-md p-3 flex flex-col justify-between border ${
              c.state === 'RECOVERED'
                ? 'bg-[rgba(5,150,105,0.06)] border-[rgba(5,150,105,0.25)]'
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
              ) : (
                <span className="text-[#6B7280]">Closed</span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── Sub-navigation Tab Bar ────────────────────────────────────────── */}
      <div className="flex items-center gap-1 border-b border-white/[0.06]">
        <button
          onClick={() => setActiveTab('story')}
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all ${
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
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all ${
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
          className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all ${
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

                {c.ai_explanation && (
                  <div className="p-3 bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.18)] rounded-md">
                    <div className="text-[10px] font-mono text-ai-text uppercase font-semibold mb-1">
                      LLM Reasoning Explanation
                    </div>
                    <p className="text-[11px] text-[#C4B5FD] italic leading-relaxed">
                      &ldquo;{c.ai_explanation}&rdquo;
                    </p>
                  </div>
                )}

                <div className="space-y-1.5 text-[11px] pt-1">
                  <DataRow label="Diagnosed Category" value={c.failure_category || 'C1'} mono />
                  <DataRow label="Diagnosis Rule" value={c.failure_code || 'BAD_REQUEST_ERROR'} mono />
                  <DataRow label="Advisory Provider" value="gemini-3.5-flash-lite via MCP" mono />
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
                      {guardrailAnalysis?.isOverridden ? 'AI Proposal Overridden' : 'Authorized as Proposed'}
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
                    <span className="font-mono text-[11px] text-guard-text">
                      ₹{c.amount_inr.toFixed(2)} Lock
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-[#6B7280]">Currency Lock:</span>
                    <span className="font-mono text-[11px] text-guard-text">
                      {c.currency || 'INR'} Constant
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-[#6B7280]">Single-Link Idempotency:</span>
                    <span className="font-mono text-[11px] text-guard-text">
                      Max 1 Link Enforced
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <span className="text-[#6B7280]">High-Value & AML Gate:</span>
                    <span className="font-mono text-[11px] text-guard-text">
                      {c.amount_inr > 50000 || c.failure_category === 'C4'
                        ? 'Mandatory Escalation'
                        : 'Passed (<₹50k)'}
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
                subtitle="Gateway write dispatched under deterministic policy"
                badge={c.payment_link_id ? 'Executed' : c.state === 'ESCALATED' ? 'Escalated' : 'Halted'}
              />

              <div className="space-y-2 text-[11px]">
                <DataRow label="Action Status" value={c.action_status || (c.payment_link_id ? 'EXECUTED' : 'SKIPPED')} mono />
                <DataRow label="Payment Link ID" value={c.payment_link_id || 'None created (safeguarded)'} mono />
                <DataRow label="Reference ID" value={c.payment_link_reference_id || '—'} mono />
                <DataRow label="Link State" value={c.payment_link_status?.toUpperCase() || '—'} mono />
                {c.payment_link_short_url && (
                  <div className="data-row">
                    <span className="data-row__label">Payment Link URL</span>
                    <span className="data-row__value flex items-center gap-2">
                      <a
                        href={c.payment_link_short_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-ai-text hover:underline truncate text-[11px] font-mono"
                      >
                        {c.payment_link_short_url}
                      </a>
                      <a
                        href={c.payment_link_short_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#6B7280] hover:text-[#F0F2F5] shrink-0"
                        aria-label="Open payment link"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </span>
                  </div>
                )}
              </div>

              {c.payment_link_short_url && (
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

            {/* Panel G: Verification & Revenue Outcome (Emerald if Recovered) */}
            <div
              className={`border rounded-lg p-5 space-y-4 ${
                c.state === 'RECOVERED'
                  ? 'bg-[rgba(5,150,105,0.04)] border-[rgba(5,150,105,0.22)]'
                  : 'bg-surface-base border-white/[0.06]'
              }`}
            >
              <SectionHeader
                title="Gateway Verification & Attribution"
                subtitle="Independent confirmation of status: captured"
                badge={c.state === 'RECOVERED' ? 'Verified Cash' : 'Pending'}
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
                    <DataRow label="Verification Basis" value="Razorpay HMAC SHA-256 Webhook" mono />
                  </div>
                </div>
              ) : c.state === 'ESCALATED' ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-[rgba(217,119,6,0.08)] border border-[rgba(217,119,6,0.20)]">
                    <span className="text-[10px] font-mono text-risk-text uppercase tracking-wider font-semibold block">
                      No Financial Credit (Controlled Escalation)
                    </span>
                    <p className="text-[11px] text-[#FCD34D] mt-1 leading-snug">
                      This transaction was blocked from automated link generation. No revenue attributed.
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Verification Status" value="PAYMENT NOT VERIFIED" mono />
                    <DataRow label="Captured Amount" value="₹0.00" mono />
                    <DataRow label="Operations Action" value="Human compliance review required" mono />
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 rounded-md bg-surface-raised border border-white/[0.04]">
                    <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider font-semibold block">
                      Awaiting Customer Payment
                    </span>
                    <p className="text-[11px] text-[#9CA3AF] mt-1 leading-snug">
                      Payment link dispatched. Attributed revenue will register immediately upon confirmed gateway webhook.
                    </p>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <DataRow label="Verification Status" value="AWAITING CAPTURE" mono />
                    <DataRow label="Recovered Amount" value="₹0.00 (Pending)" mono />
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
