import React, { useState } from 'react';
import {
  ArrowLeft,
  Zap,
  RefreshCw,
  CheckCircle2,
  Circle,
  BrainCircuit,
  ShieldCheck,
  Copy,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Clock,
  IndianRupee,
  Bot,
  Lock,
  ListChecks,
  GitMerge,
} from 'lucide-react';
import type { CaseDetailResponse, CaseState, AuditEvent } from '../types';
import { StateBadge } from '../components/common/StateBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { Skeleton } from '../components/common/Skeleton';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../components/common/Toast';

// ─── Types ───────────────────────────────────────────────────────────────────

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

type Tab = 'story' | 'audit' | 'raw';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const formatInr = (amount: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount);

const formatTime = (ts: string | null | undefined) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return ts;
  }
};

function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

// ─── Pipeline Progress ─────────────────────────────────────────────────────

interface PipelineStage {
  num: string;
  label: string;
  zone: 'teal' | 'violet';
  isDone: (c: CaseDetailResponse['case']) => boolean;
}

const PIPELINE_STAGES: PipelineStage[] = [
  { num: '01', label: 'INGESTED',  zone: 'teal',   isDone: () => true },
  { num: '02', label: 'CONTEXT',   zone: 'teal',   isDone: (c) => !!c.failure_category },
  { num: '03', label: 'ELIGIBLE',  zone: 'teal',   isDone: (c) => !!c.eligibility_status },
  { num: '04', label: 'AI TRIAGE', zone: 'violet', isDone: (c) => !!c.ai_policy_id },
  { num: '05', label: 'GUARDRAIL', zone: 'teal',   isDone: (c) => !!c.validated_policy_id },
  { num: '06', label: 'EXECUTED',  zone: 'teal',   isDone: (c) => !!c.payment_link_id },
  { num: '07', label: 'VERIFIED',  zone: 'teal',   isDone: (c) => !!c.recovered_payment_id },
  { num: '08', label: 'ATTRIBUTED',zone: 'teal',   isDone: (c) => c.state === 'RECOVERED' },
];

const PipelineProgress: React.FC<{ caseData: CaseDetailResponse['case'] }> = ({ caseData }) => (
  <div className="flex items-center gap-0 overflow-x-auto">
    {PIPELINE_STAGES.map((stage, idx) => {
      const done = stage.isDone(caseData);
      const isAiStage = stage.zone === 'violet';

      return (
        <React.Fragment key={stage.num}>
          {/* Stage node */}
          <div className="flex flex-col items-center gap-1 shrink-0">
            <div
              className={`
                w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-mono font-bold border
                transition-colors
                ${done
                  ? isAiStage
                    ? 'bg-[rgba(124,58,237,0.20)] border-[rgba(124,58,237,0.50)] text-ai-text'
                    : 'bg-[rgba(13,148,136,0.20)] border-[rgba(13,148,136,0.50)] text-guard-text'
                  : 'bg-surface-raised border-white/[0.08] text-[#4B5563]'
                }
              `}
            >
              {done ? (
                isAiStage ? <BrainCircuit className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                stage.num
              )}
            </div>
            <span
              className={`text-[9px] font-mono uppercase tracking-wider ${
                done
                  ? isAiStage ? 'text-ai-text' : 'text-guard-text'
                  : 'text-[#4B5563]'
              }`}
            >
              {stage.label}
            </span>
          </div>

          {/* Connector between stages */}
          {idx < PIPELINE_STAGES.length - 1 && (
            <div
              className={`h-px flex-1 min-w-[16px] mx-1 ${
                // connector color: between 03→04 and 04→05 transitions
                idx === 2 ? 'bg-gradient-to-r from-guard-base to-ai-base'
                : idx === 3 ? 'bg-gradient-to-r from-ai-base to-guard-base'
                : stage.zone === 'violet' ? 'bg-ai-base/40'
                : done ? 'bg-guard-base/40' : 'bg-white/[0.06]'
              }`}
            />
          )}
        </React.Fragment>
      );
    })}
  </div>
);

// ─── Story Stage Card ─────────────────────────────────────────────────────

interface StoryStageConfig {
  num: string;
  title: string;
  actor: string;
  zone: 'teal' | 'violet' | 'neutral';
  status: 'complete' | 'pending' | 'halted';
  summary: string;
  detail?: string | null;
  evidence?: Record<string, unknown> | null | string;
  contextData?: Record<string, unknown> | null;
}

const StoryStageCard: React.FC<{ stage: StoryStageConfig }> = ({ stage }) => {
  const [expanded, setExpanded] = useState(false);

  const accentClass =
    stage.zone === 'violet' ? 'accent-ai' :
    stage.zone === 'teal'   ? 'accent-guard' : 'accent-neutral';

  const dotClass =
    stage.status === 'complete'
      ? stage.zone === 'violet' ? 'bg-ai-base' : 'bg-guard-base'
      : stage.status === 'halted'
      ? 'bg-halt-base'
      : 'bg-[#4B5563]';

  const hasExtra = stage.evidence || stage.contextData;

  return (
    <div className={`bg-surface-base border border-white/[0.06] rounded-lg overflow-hidden hover:border-white/[0.10] transition-colors ${accentClass}`}>
      {/* Header row */}
      <div className="flex items-start justify-between px-4 py-3 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          {/* Status dot + number */}
          <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${dotClass}`}>
            {stage.status === 'complete' ? (
              stage.zone === 'violet'
                ? <BrainCircuit className="w-3 h-3 text-[#1A1030]" />
                : <CheckCircle2 className="w-3 h-3 text-[#071A14]" />
            ) : (
              <Circle className="w-3 h-3 text-[#F0F2F5]" />
            )}
          </div>

          <div className="min-w-0">
            {/* Zone label */}
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className={`text-[9px] font-mono uppercase tracking-widest font-semibold ${
                  stage.zone === 'violet' ? 'text-ai-text' :
                  stage.zone === 'teal' ? 'text-guard-text' : 'text-[#4B5563]'
                }`}
              >
                {stage.zone === 'violet' ? '⬡ AI ADVISORY' :
                 stage.zone === 'teal' ? '◆ DETERMINISTIC' : `STAGE ${stage.num}`}
              </span>
              <span className="text-[9px] font-mono text-[#4B5563]">·</span>
              <span className="text-[10px] font-mono text-[#4B5563]">{stage.actor}</span>
            </div>

            {/* Stage title */}
            <h4 className="text-[13px] font-semibold text-[#F0F2F5] leading-tight">
              {stage.title}
            </h4>
          </div>
        </div>

        {/* Stage number badge */}
        <span className="text-[10px] font-mono text-[#4B5563] shrink-0 mt-1">{stage.num}</span>
      </div>

      {/* Summary */}
      <div className="px-4 pb-3">
        <p className="text-[12px] text-[#9CA3AF] leading-relaxed">{stage.summary}</p>
        {stage.detail && (
          <p className="text-[11px] text-[#6B7280] mt-1 leading-relaxed">{stage.detail}</p>
        )}
      </div>

      {/* Expandable extra data */}
      {hasExtra && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-full flex items-center gap-2 px-4 py-2 text-[10px] font-mono text-[#4B5563] hover:text-[#6B7280] hover:bg-white/[0.02] border-t border-white/[0.04] transition-colors"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? 'Hide evidence' : 'View evidence'}
          </button>
          {expanded && (
            <div className="px-4 pb-3">
              <pre className="json-block text-[10px]">
                {JSON.stringify(stage.evidence ?? stage.contextData, null, 2)}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── Audit Event ──────────────────────────────────────────────────────────

const AuditEventRow: React.FC<{ event: AuditEvent }> = ({ event }) => {
  const [showDetails, setShowDetails] = useState(false);

  const eventZoneClass =
    event.event_type?.startsWith('AI_') || event.event_type?.includes('LLM')
      ? 'text-ai-text bg-[rgba(124,58,237,0.10)] border-[rgba(124,58,237,0.25)]'
      : event.event_type?.startsWith('GUARDRAIL_') || event.event_type?.startsWith('POLICY_')
      ? 'text-guard-text bg-[rgba(13,148,136,0.10)] border-[rgba(13,148,136,0.25)]'
      : event.event_type?.startsWith('RECOVERY_') || event.actor === 'attribution'
      ? 'text-recover-text bg-[rgba(5,150,105,0.10)] border-[rgba(5,150,105,0.25)]'
      : event.event_type?.startsWith('ERROR')
      ? 'text-halt-text bg-[rgba(225,29,72,0.08)] border-[rgba(225,29,72,0.25)]'
      : 'text-[#9CA3AF] bg-[rgba(75,85,99,0.10)] border-[rgba(75,85,99,0.20)]';

  const hasDetails =
    event.details && Object.keys(event.details).length > 0;
  const hasGuardrail =
    event.guardrail_result && Object.keys(event.guardrail_result).length > 0;

  return (
    <div className="border border-white/[0.06] rounded-lg overflow-hidden bg-surface-base">
      <div className="flex items-start justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-semibold border rounded ${eventZoneClass}`}>
            {event.event_type}
          </span>
          {event.actor && (
            <span className="text-[11px] text-[#4B5563] font-mono">
              by {event.actor}
            </span>
          )}
        </div>
        <span className="text-[10px] font-mono text-[#4B5563] shrink-0 whitespace-nowrap">
          {formatTime(event.timestamp)}
        </span>
      </div>

      {/* Decision / Policy row */}
      {(event.decision || event.policy || event.action || event.outcome) && (
        <div className="flex items-center gap-4 px-4 pb-2.5 text-[11px] font-mono flex-wrap">
          {event.decision && (
            <span className="text-[#C4B5FD]">decision: <strong>{event.decision}</strong></span>
          )}
          {event.policy && (
            <span className="text-[#5EEAD4]">policy: <strong>{event.policy}</strong></span>
          )}
          {event.outcome && (
            <span className="text-[#6EE7B7]">outcome: <strong>{event.outcome}</strong></span>
          )}
        </div>
      )}

      {/* Toggle details */}
      {(hasDetails || hasGuardrail) && (
        <>
          <button
            onClick={() => setShowDetails((v) => !v)}
            className="w-full flex items-center gap-2 px-4 py-2 text-[10px] font-mono text-[#4B5563] hover:text-[#6B7280] hover:bg-white/[0.02] border-t border-white/[0.04] transition-colors"
          >
            {showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showDetails ? 'Hide details' : 'View details'}
          </button>
          {showDetails && (
            <div className="px-4 pb-3 space-y-2">
              {hasDetails && (
                <pre className="json-block">{JSON.stringify(event.details, null, 2)}</pre>
              )}
              {hasGuardrail && (
                <div>
                  <div className="text-[9px] font-mono uppercase text-guard-text tracking-widest mb-1">
                    Guardrail Result
                  </div>
                  <pre className="json-block">{JSON.stringify(event.guardrail_result, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── AI vs Guardrail Panel ────────────────────────────────────────────────

const AiGuardrailPanel: React.FC<{ c: CaseDetailResponse['case'] }> = ({ c }) => {
  const aiProposed = c.ai_policy_id;
  const guardrailAuthorized = c.validated_policy_id;
  const wasOverridden = aiProposed && guardrailAuthorized && aiProposed !== guardrailAuthorized;
  const wasAccepted = aiProposed && guardrailAuthorized && aiProposed === guardrailAuthorized;

  return (
    <div className="space-y-3">
      {/* AI Proposal */}
      <div className="bg-surface-base border border-[rgba(124,58,237,0.20)] rounded-lg overflow-hidden accent-ai">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(124,58,237,0.12)]">
          <Bot className="w-4 h-4 text-ai-text" />
          <span className="text-[11px] font-semibold text-ai-text uppercase tracking-wider font-mono">
            AI Advisory
          </span>
          <span className="ml-auto text-[9px] font-mono text-[#7C3AED]/60 uppercase tracking-widest">
            LLM · MCP
          </span>
        </div>
        <div className="px-4 py-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-[#6B7280]">Proposed policy</span>
            <PolicyBadge policy={c.ai_policy_id} context="ai" />
          </div>
          {c.failure_category && (
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-[#6B7280]">Classified as</span>
              <CategoryBadge category={c.failure_category} />
            </div>
          )}
          {c.ai_explanation && (
            <div className="mt-2 p-3 rounded-md bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.15)]">
              <p className="text-[11px] text-[#C4B5FD] italic leading-relaxed">
                &ldquo;{c.ai_explanation}&rdquo;
              </p>
            </div>
          )}
          {!c.ai_policy_id && (
            <p className="text-[11px] text-[#4B5563] italic">AI advisory pending — run triage to invoke</p>
          )}
        </div>
      </div>

      {/* Override indicator */}
      {wasOverridden && (
        <div className="flex items-center gap-2 px-3 py-2 bg-[rgba(217,119,6,0.08)] border border-[rgba(217,119,6,0.25)] rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 text-risk-text shrink-0" />
          <span className="text-[11px] font-mono text-risk-text font-semibold uppercase tracking-wider">
            Proposal overridden
          </span>
          <span className="text-[10px] text-[#6B7280] ml-auto font-mono">
            {c.ai_policy_id} → {c.validated_policy_id}
          </span>
        </div>
      )}

      {wasAccepted && (
        <div className="flex items-center gap-2 px-3 py-2 bg-[rgba(13,148,136,0.08)] border border-[rgba(13,148,136,0.20)] rounded-lg">
          <CheckCircle2 className="w-3.5 h-3.5 text-guard-text shrink-0" />
          <span className="text-[11px] font-mono text-guard-text font-semibold uppercase tracking-wider">
            Proposal accepted
          </span>
        </div>
      )}

      {/* Guardrail enforcement */}
      <div className="bg-surface-base border border-[rgba(13,148,136,0.20)] rounded-lg overflow-hidden accent-guard">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(13,148,136,0.10)]">
          <ShieldCheck className="w-4 h-4 text-guard-text" />
          <span className="text-[11px] font-semibold text-guard-text uppercase tracking-wider font-mono">
            Guardrail Enforcement
          </span>
          <span className="ml-auto px-1.5 py-0.5 text-[9px] font-mono text-guard-text bg-[rgba(13,148,136,0.12)] border border-[rgba(13,148,136,0.25)] rounded uppercase">
            {c.validated_policy_id ? 'verified' : 'pending'}
          </span>
        </div>
        <div className="px-4 py-3 space-y-2">
          {[
            { label: 'Amount', value: c.amount_inr > 0 ? `₹${c.amount_inr.toFixed(2)} immutable` : 'Pending', ok: c.amount_inr > 0 },
            { label: 'Currency', value: `${c.currency || 'INR'} immutable`, ok: true },
            { label: 'Cooldown', value: 'Satisfied', ok: !!c.validated_policy_id },
            { label: 'Link limit', value: 'Max 1 per case', ok: true },
          ].map((inv) => (
            <div key={inv.label} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 ${inv.ok ? 'text-guard-text' : 'text-[#4B5563]'}`} />
                <span className="text-[11px] text-[#6B7280]">{inv.label}</span>
              </div>
              <span className="text-[11px] font-mono text-[#9CA3AF]">{inv.value}</span>
            </div>
          ))}

          <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
            <span className="text-[11px] text-[#6B7280]">Authorized policy</span>
            <PolicyBadge policy={c.validated_policy_id} context="guard" />
          </div>
        </div>
      </div>

      {/* Payment link card */}
      {c.payment_link_id && (
        <div className="bg-surface-base border border-white/[0.08] rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
            <Lock className="w-3.5 h-3.5 text-recover-text" />
            <span className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-wider font-mono">
              Payment Link
            </span>
            {c.payment_link_status && (
              <span className="ml-auto text-[9px] font-mono text-[#4B5563] uppercase">{c.payment_link_status}</span>
            )}
          </div>
          <div className="px-4 py-3 space-y-2.5 font-mono text-[11px]">
            <div>
              <div className="text-[9px] text-[#4B5563] uppercase tracking-widest mb-1">Link ID</div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-recover-text truncate">{c.payment_link_id}</span>
                <button
                  onClick={() => copyText(c.payment_link_id!)}
                  className="shrink-0 text-[#4B5563] hover:text-[#9CA3AF] transition-colors"
                  aria-label="Copy payment link ID"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {c.payment_link_short_url && (
              <div>
                <div className="text-[9px] text-[#4B5563] uppercase tracking-widest mb-1">Short URL</div>
                <div className="flex items-center gap-2">
                  <a
                    href={c.payment_link_short_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-ai-text hover:underline truncate text-[11px]"
                  >
                    {c.payment_link_short_url}
                  </a>
                  <a
                    href={c.payment_link_short_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-[#4B5563] hover:text-[#9CA3AF]"
                    aria-label="Open payment link"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────

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
    copyText(text);
    showToast('info', 'Copied', `${label}: ${text.slice(0, 40)}…`);
  };

  if (!caseId) {
    return (
      <EmptyState
        icon={GitMerge}
        title="No case selected"
        description="Select a recovery case from the Cases explorer to view its full decision story and audit trail."
        actionText="Go to Cases"
        onAction={onBack}
      />
    );
  }

  if (error) {
    return <ErrorBanner title={`Failed to load case ${caseId}`} message={error} onRetry={onRefresh} />;
  }

  if (loading || !detail) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-5 w-64" />
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        <Skeleton className="h-16 rounded-lg" />
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-3">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 rounded-lg" />)}
          </div>
          <div className="space-y-3">
            <Skeleton className="h-48 rounded-lg" />
            <Skeleton className="h-36 rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  const { case: c, audit_trail: audits } = detail;

  // Build story stages
  const storyStages: StoryStageConfig[] = [
    {
      num: '01',
      title: 'Payment Failed',
      actor: 'Razorpay Gateway',
      zone: 'neutral',
      status: 'complete',
      summary: `${formatInr(c.amount_inr)} payment rejected by gateway`,
      detail: c.failure_description || c.failure_code || 'Authorization rejected',
      contextData: c.failure_context,
    },
    {
      num: '02',
      title: 'Context Retrieved',
      actor: 'Context Service',
      zone: 'neutral',
      status: c.failure_category ? 'complete' : 'pending',
      summary: `Payment and order context enriched from Razorpay API`,
      detail: `Method: ${c.payment_method || 'unknown'} · Code: ${c.failure_code || '—'}`,
    },
    {
      num: '03',
      title: 'Failure Classified',
      actor: 'Taxonomy Classifier',
      zone: 'neutral',
      status: c.failure_category ? 'complete' : 'pending',
      summary: c.failure_category
        ? `Classified as ${c.failure_category} — deterministic rule-based mapping`
        : 'Classification pending',
      detail: c.failure_description || 'Gateway error code mapped to C1–C5 taxonomy',
      evidence: c.classification_evidence,
    },
    {
      num: '04',
      title: 'Eligibility Evaluated',
      actor: 'Eligibility Engine',
      zone: 'neutral',
      status: c.eligibility_status === 'ELIGIBLE'
        ? 'complete'
        : c.eligibility_status
        ? 'halted'
        : 'pending',
      summary: c.eligibility_status
        ? `Status: ${c.eligibility_status} — ${c.eligibility_reason || ''}`
        : 'Eligibility check pending',
      detail: 'Checked: amount threshold, currency, customer cooldown, prior links, state validity',
    },
    {
      num: '05',
      title: 'AI Advisory Proposal',
      actor: 'LLM Provider (Gemini)',
      zone: 'violet',   // ← THE KEY VISUAL MOMENT
      status: c.ai_policy_id ? 'complete' : 'pending',
      summary: c.ai_policy_id
        ? `Proposed: ${c.ai_policy_id} based on failure analysis`
        : 'AI advisory pending — execute triage to invoke',
      detail: c.ai_explanation || undefined,
    },
    {
      num: '06',
      title: 'Guardrail Authorization',
      actor: 'PolicyGuardrailEngine',
      zone: 'teal',     // ← BACK TO DETERMINISTIC
      status: c.validated_policy_id ? 'complete' : 'pending',
      summary: c.validated_policy_id
        ? `Authorized: ${c.validated_policy_id} — all invariants satisfied`
        : 'Guardrail gate pending',
      detail: 'Enforced: amount immutability, currency lock, customer cooldown, single-link limit, state validity',
    },
    {
      num: '07',
      title: 'Recovery Action',
      actor: 'RecoveryExecutor',
      zone: 'neutral',
      status: c.payment_link_id ? 'complete' : c.state === 'TERMINAL_NO_ACTION' || c.state === 'ESCALATED' ? 'halted' : 'pending',
      summary: c.payment_link_id
        ? `Payment Link created: ${c.payment_link_id}`
        : c.state === 'ESCALATED'
        ? 'Escalated to manual review — no automated link created'
        : c.state === 'TERMINAL_NO_ACTION'
        ? 'No action taken — guardrail determined recovery unsafe'
        : 'Awaiting authorization',
      detail: c.payment_link_short_url ? `URL: ${c.payment_link_short_url}` : undefined,
    },
    {
      num: '08',
      title: 'Revenue Attributed',
      actor: 'Attribution Service',
      zone: 'neutral',
      status: c.state === 'RECOVERED' ? 'complete' : 'pending',
      summary: c.state === 'RECOVERED'
        ? `Recovered: ${formatInr(c.recovered_amount_inr)} — captured & verified`
        : 'Attribution pending customer payment',
      detail: c.recovered_payment_id
        ? `Verified payment ID: ${c.recovered_payment_id} — captured-only attribution`
        : 'Revenue attributed only on confirmed Razorpay capture event',
    },
  ];

  const tabs: { id: Tab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: 'story',  label: 'Decision Story', icon: BrainCircuit },
    { id: 'audit',  label: `Audit Trail (${audits.length})`, icon: ListChecks },
    { id: 'raw',    label: 'Raw Data',        icon: Lock },
  ];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Case Header ──────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 p-4 bg-surface-base border border-white/[0.06] rounded-lg">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={onBack}
              className="p-2 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] text-[#6B7280] hover:text-[#9CA3AF] transition-colors shrink-0"
              aria-label="Back to cases"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-[14px] font-bold font-mono text-[#F0F2F5] truncate">
                  {c.case_id}
                </h2>
                <StateBadge state={c.state as CaseState} />
                {c.failure_category && <CategoryBadge category={c.failure_category} />}
                <button
                  onClick={() => handleCopy(c.case_id, 'Case ID')}
                  className="text-[#4B5563] hover:text-[#6B7280] transition-colors"
                  aria-label="Copy case ID"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex items-center gap-3 mt-1 flex-wrap">
                <span className="text-[10px] font-mono text-[#4B5563]">
                  Payment: <span className="text-[#6B7280]">{c.failed_payment_id}</span>
                </span>
                {c.customer_id && (
                  <span className="text-[10px] font-mono text-[#4B5563]">
                    Customer: <span className="text-[#6B7280]">{c.customer_id}</span>
                  </span>
                )}
                {c.order_id && (
                  <span className="text-[10px] font-mono text-[#4B5563]">
                    Order: <span className="text-[#6B7280]">{c.order_id}</span>
                  </span>
                )}
                <span className="text-[10px] font-mono text-[#4B5563]">
                  <Clock className="w-3 h-3 inline mr-1" />
                  {formatTime(c.created_at)}
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {c.state === 'FAILED_INGESTED' && (
              <button
                onClick={() => onTriggerTriage(c.case_id)}
                disabled={triageLoading}
                className="flex items-center gap-2 px-3 py-1.5 text-[12px] font-semibold text-ai-text bg-[rgba(124,58,237,0.12)] hover:bg-[rgba(124,58,237,0.20)] border border-[rgba(124,58,237,0.35)] hover:border-[rgba(124,58,237,0.55)] rounded-md transition-colors disabled:opacity-50"
              >
                <Zap className={`w-3.5 h-3.5 ${triageLoading ? 'animate-spin-slow' : ''}`} />
                {triageLoading ? 'Executing…' : 'Execute Triage'}
              </button>
            )}
            <button
              onClick={onRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#6B7280] hover:text-[#9CA3AF] bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.08] rounded-md transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* ── 4 Metric Strip ─────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* Transaction amount */}
          <div className="p-3 bg-surface-raised border border-white/[0.06] rounded-lg">
            <div className="text-[9px] font-mono text-[#4B5563] uppercase tracking-widest mb-1">Transaction</div>
            <div className="flex items-center gap-1.5">
              <IndianRupee className="w-3.5 h-3.5 text-[#6B7280]" />
              <span className="font-mono font-semibold text-[15px] text-[#F0F2F5]">
                {c.amount_inr.toFixed(2)}
              </span>
            </div>
            <div className="text-[9px] font-mono text-[#4B5563] mt-0.5">{c.currency} · {c.amount_paise}p</div>
          </div>

          {/* AI proposed */}
          <div className="p-3 bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.18)] rounded-lg">
            <div className="text-[9px] font-mono text-ai-text/70 uppercase tracking-widest mb-1.5 flex items-center gap-1">
              <Bot className="w-2.5 h-2.5" /> AI Proposed
            </div>
            <PolicyBadge policy={c.ai_policy_id} context="ai" showIcon={false} />
          </div>

          {/* Guardrail authorized */}
          <div className="p-3 bg-[rgba(13,148,136,0.06)] border border-[rgba(13,148,136,0.18)] rounded-lg">
            <div className="text-[9px] font-mono text-guard-text/70 uppercase tracking-widest mb-1.5 flex items-center gap-1">
              <ShieldCheck className="w-2.5 h-2.5" /> Authorized
            </div>
            <PolicyBadge policy={c.validated_policy_id} context="guard" showIcon={false} />
          </div>

          {/* Recovered */}
          <div className={`p-3 border rounded-lg ${
            c.state === 'RECOVERED'
              ? 'bg-[rgba(5,150,105,0.08)] border-[rgba(5,150,105,0.25)]'
              : 'bg-surface-raised border-white/[0.06]'
          }`}>
            <div className="text-[9px] font-mono text-[#4B5563] uppercase tracking-widest mb-1">Recovered</div>
            <div className={`font-mono font-semibold text-[15px] ${
              c.state === 'RECOVERED' ? 'text-recover-text' : 'text-[#4B5563]'
            }`}>
              {c.state === 'RECOVERED' ? `₹${c.recovered_amount_inr.toFixed(2)}` : '₹0.00'}
            </div>
            <div className="text-[9px] font-mono text-[#4B5563] mt-0.5">
              {c.state === 'RECOVERED' ? 'Captured · Attributed' : 'Pending'}
            </div>
          </div>
        </div>

        {/* ── Pipeline Progress ───────────────────────────────────────── */}
        <div className="p-3 bg-surface-raised border border-white/[0.05] rounded-lg">
          <PipelineProgress caseData={c} />
        </div>
      </div>

      {/* ── Tab Bar ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-0 border-b border-white/[0.06]">
        {tabs.map((tab) => {
          const { icon: Icon } = tab;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-all ${
                activeTab === tab.id
                  ? 'border-b-ai-base text-[#F0F2F5]'
                  : 'border-b-transparent text-[#6B7280] hover:text-[#9CA3AF]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab: Decision Story ───────────────────────────────────────── */}
      {activeTab === 'story' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 animate-fade-in">
          {/* Left: Timeline */}
          <div className="lg:col-span-2 space-y-0">
            {/* Zone legend */}
            <div className="flex items-center gap-4 mb-4 px-1">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-guard-base" />
                <span className="text-[10px] text-[#4B5563] font-mono">Deterministic</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-ai-base" />
                <span className="text-[10px] text-ai-text font-mono">AI Advisory</span>
              </div>
              <span className="text-[9px] text-[#4B5563] font-mono ml-auto">8 pipeline stages</span>
            </div>

            {/* Stages with connectors */}
            <div className="relative">
              {storyStages.map((stage, idx) => {
                const isAiStage = stage.zone === 'violet';
                const nextStage = storyStages[idx + 1];
                const isBeforeAi = nextStage?.zone === 'violet';
                const isAiStageNow = isAiStage;
                const isAfterAi = !isAiStage && idx > 4;

                return (
                  <React.Fragment key={stage.num}>
                    {/* Zone transition divider: before AI (03→04) */}
                    {isBeforeAi && (
                      <div className="flex items-center gap-3 my-2 px-1">
                        <div className="flex-1 h-px bg-gradient-to-r from-guard-base/40 to-ai-base/40" />
                        <div className="flex items-center gap-1.5 px-3 py-1 bg-[rgba(124,58,237,0.08)] border border-[rgba(124,58,237,0.20)] rounded-full">
                          <BrainCircuit className="w-3 h-3 text-ai-text" />
                          <span className="text-[9px] font-mono text-ai-text uppercase tracking-widest">
                            AI advisory boundary
                          </span>
                        </div>
                        <div className="flex-1 h-px bg-gradient-to-r from-ai-base/40 to-ai-base/20" />
                      </div>
                    )}

                    {/* Zone transition divider: after AI (04→05) */}
                    {isAiStageNow && (
                      <>
                        <StoryStageCard stage={stage} />
                        <div className="flex items-center gap-3 my-2 px-1">
                          <div className="flex-1 h-px bg-gradient-to-r from-ai-base/40 to-guard-base/40" />
                          <div className="flex items-center gap-1.5 px-3 py-1 bg-[rgba(13,148,136,0.08)] border border-[rgba(13,148,136,0.20)] rounded-full">
                            <ShieldCheck className="w-3 h-3 text-guard-text" />
                            <span className="text-[9px] font-mono text-guard-text uppercase tracking-widest">
                              Guardrail boundary
                            </span>
                          </div>
                          <div className="flex-1 h-px bg-gradient-to-r from-guard-base/40 to-guard-base/20" />
                        </div>
                      </>
                    )}

                    {!isAiStageNow && (
                      <>
                        <StoryStageCard stage={stage} />
                        {/* Connector line between cards */}
                        {idx < storyStages.length - 1 && !isBeforeAi && (
                          <div className="flex justify-center">
                            <div
                              className={`w-px h-3 ${
                                isAfterAi || idx >= 5
                                  ? 'bg-guard-base/30'
                                  : idx < 3
                                  ? 'bg-guard-base/20'
                                  : 'bg-white/[0.06]'
                              }`}
                            />
                          </div>
                        )}
                      </>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Right: AI vs Guardrail Panel */}
          <div className="space-y-0">
            <AiGuardrailPanel c={c} />
          </div>
        </div>
      )}

      {/* ── Tab: Audit Trail ─────────────────────────────────────────── */}
      {activeTab === 'audit' && (
        <div className="space-y-2 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-[13px] font-semibold text-[#F0F2F5]">Immutable Audit Trail</h3>
              <p className="text-[11px] text-[#4B5563] mt-0.5">
                Complete chronological event log — written during each pipeline stage
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-1 bg-surface-raised border border-white/[0.06] rounded text-[#6B7280]">
              {audits.length} events
            </span>
          </div>

          {audits.length === 0 ? (
            <EmptyState
              title="No audit events"
              description="Audit events will appear here after the recovery pipeline runs."
            />
          ) : (
            <div className="space-y-2">
              {audits.map((event) => (
                <AuditEventRow key={event.id} event={event} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Raw Data ─────────────────────────────────────────────── */}
      {activeTab === 'raw' && (
        <div className="space-y-4 animate-fade-in">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-[13px] font-semibold text-[#F0F2F5]">Full Case Record</h3>
              <p className="text-[11px] text-[#4B5563] mt-0.5 font-mono">
                GET /cases/{c.case_id}
              </p>
            </div>
            <button
              onClick={() => handleCopy(JSON.stringify(c, null, 2), 'Case JSON')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-[#6B7280] hover:text-[#9CA3AF] bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.08] rounded-md transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
              Copy JSON
            </button>
          </div>
          <pre className="json-block" style={{ maxHeight: '480px' }}>
            {JSON.stringify(c, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
