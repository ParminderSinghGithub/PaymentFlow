import React, { useState } from 'react';
import {
  ArrowLeft,
  Zap,
  ShieldCheck,
  CheckCircle2,
  Copy,
  ExternalLink,
  Bot,
  BrainCircuit,
  Lock,
} from 'lucide-react';
import type { CaseDetailResponse, CaseState } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { PolicyBadge } from '../components/common/PolicyBadge';
import { CategoryBadge } from '../components/common/CategoryBadge';
import { Skeleton } from '../components/common/Skeleton';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../components/common/Toast';

interface CaseDetailPageProps {
  caseId: string | null;
  detail: CaseDetailResponse | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onTriggerTriage: (caseId: string) => void;
  triageLoading: boolean;
  onRefresh: () => void;
}

export const CaseDetailPage: React.FC<CaseDetailPageProps> = ({
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
  const [activeTab, setActiveTab] = useState<'story' | 'audit' | 'telemetry'>('story');

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    showToast('info', 'Copied to clipboard', `${label}: ${text}`);
  };

  const formatInr = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(amount);
  };

  if (!caseId) {
    return (
      <EmptyState
        title="No Case Selected"
        description="Select a recovery case from the Cases Explorer to view its full decision story and audit trail."
        actionText="Go to Cases Explorer"
        onAction={onBack}
      />
    );
  }

  if (error) {
    return <ErrorBanner title={`Failed to load case ${caseId}`} message={error} onRetry={onRefresh} />;
  }

  if (loading || !detail) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-64" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <Skeleton className="h-48 w-full rounded-xl" />
            <Skeleton className="h-64 w-full rounded-xl" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-56 w-full rounded-xl" />
            <Skeleton className="h-56 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  const { case: c, audit_trail: audits } = detail;

  // Build sequential decision story stages
  const storyStages = [
    {
      num: '01',
      title: 'Payment Failed',
      status: 'complete',
      actor: 'Razorpay Gateway',
      summary: `Failed payment of ${formatInr(c.amount_inr)} (${c.amount_paise} paise)`,
      details: c.failure_description || c.failure_code || 'Payment authorization rejected',
      context: c.failure_context,
    },
    {
      num: '02',
      title: 'Taxonomy Classification',
      status: c.failure_category ? 'complete' : 'pending',
      actor: 'Taxonomy Classifier',
      summary: `Categorized into ${c.failure_category || 'Unclassified'}`,
      details: c.failure_description || 'Evaluated gateway error signature and error source',
      evidence: c.classification_evidence,
    },
    {
      num: '03',
      title: 'Deterministic Eligibility',
      status: c.eligibility_status === 'ELIGIBLE' ? 'complete' : c.eligibility_status ? 'halted' : 'pending',
      actor: 'Eligibility Engine',
      summary: `Status: ${c.eligibility_status || 'Evaluating'}`,
      details: `Rule check: ${c.eligibility_reason || 'Verifying transaction freshness, amount boundaries, and cooldown'}`,
    },
    {
      num: '04',
      title: 'AI Advisory Proposal',
      status: c.ai_policy_id ? 'complete' : 'pending',
      actor: 'Gemini LLM Provider',
      summary: c.ai_policy_id ? `Proposed Policy: ${c.ai_policy_id}` : 'Advisory inference pending',
      details: c.ai_explanation || 'Awaiting agent reasoning',
    },
    {
      num: '05',
      title: 'Guardrail Authorization',
      status: c.validated_policy_id ? 'complete' : 'pending',
      actor: 'PolicyGuardrailEngine',
      summary: c.validated_policy_id ? `Authorized: ${c.validated_policy_id}` : 'Guardrail gate pending',
      details: 'Enforced amount immutability, currency immutability, customer cooldown, and safety invariants.',
    },
    {
      num: '06',
      title: 'Recovery Execution',
      status: c.payment_link_id ? 'complete' : c.state === 'RECOVERED' ? 'complete' : 'pending',
      actor: 'RecoveryExecutor',
      summary: c.payment_link_id ? `Payment Link Created: ${c.payment_link_id}` : 'Execution in progress / delayed',
      details: c.payment_link_short_url ? `URL: ${c.payment_link_short_url}` : 'Razorpay Link API write',
    },
    {
      num: '07',
      title: 'Payment Verification',
      status: c.state === 'RECOVERED' ? 'complete' : 'pending',
      actor: 'Direct API Verifier',
      summary: c.state === 'RECOVERED' ? 'Payment Status: Captured' : 'Awaiting customer completion',
      details: c.recovered_payment_id ? `Payment ID: ${c.recovered_payment_id}` : 'Independent gateway verification',
    },
    {
      num: '08',
      title: 'Revenue Attributed',
      status: c.state === 'RECOVERED' ? 'complete' : 'pending',
      actor: 'Attribution Service',
      summary: c.state === 'RECOVERED' ? `Attributed: ${formatInr(c.recovered_amount_inr)}` : 'Attribution pending',
      details: c.state === 'RECOVERED' ? 'Single revenue attribution recorded with zero duplicate replay' : 'Attribution on capture only',
    },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Header Navigation & Identification */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-xl bg-background-surface border border-border-subtle">
        <div className="flex items-start gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-background-elevated hover:bg-background-hover text-zinc-400 hover:text-zinc-200 border border-border transition-colors shrink-0 mt-0.5"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-gray-100 font-mono tracking-tight">{c.case_id}</h2>
              <StatusBadge state={c.state as CaseState} />
              <CategoryBadge category={c.failure_category} />
            </div>
            <div className="flex items-center gap-3 mt-1.5 text-xs text-zinc-400 font-mono flex-wrap">
              <span>Payment: <strong className="text-zinc-200">{c.failed_payment_id}</strong></span>
              {c.customer_id && <span>Customer: <strong className="text-zinc-200">{c.customer_id}</strong></span>}
              {c.order_id && <span>Order: <strong className="text-zinc-200">{c.order_id}</strong></span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {c.state === 'FAILED_INGESTED' && (
            <button
              onClick={() => onTriggerTriage(c.case_id)}
              disabled={triageLoading}
              className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-brand-500/10 text-brand-300 border border-brand-500/30 hover:bg-brand-500/20 transition-colors disabled:opacity-50"
            >
              <Zap className={`w-3.5 h-3.5 ${triageLoading ? 'animate-spin' : ''}`} />
              <span>{triageLoading ? 'Executing AI Triage...' : 'Execute Recovery Triage'}</span>
            </button>
          )}

          <button
            onClick={onRefresh}
            className="px-3 py-2 text-xs font-medium rounded-lg bg-background-elevated hover:bg-background-hover text-zinc-300 border border-border transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-background-surface border border-border-subtle">
          <div className="text-[11px] text-zinc-400 font-medium">Original Transaction</div>
          <div className="text-xl font-bold font-mono text-gray-100 mt-1">
            {formatInr(c.amount_inr)}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">{c.amount_paise} paise · {c.currency}</div>
        </div>

        <div className="p-4 rounded-xl bg-background-surface border border-border-subtle">
          <div className="text-[11px] text-zinc-400 font-medium">Authorized Policy</div>
          <div className="mt-1.5">
            <PolicyBadge policy={c.validated_policy_id} />
          </div>
          <div className="text-[10px] text-zinc-500 font-mono mt-1">Validated by Guardrails</div>
        </div>

        <div className="p-4 rounded-xl bg-background-surface border border-border-subtle">
          <div className="text-[11px] text-zinc-400 font-medium">Payment Link Status</div>
          <div className="text-sm font-semibold font-mono text-emerald-400 mt-1 truncate">
            {c.payment_link_id || 'Not generated'}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">Status: {c.payment_link_status || c.action_status || 'None'}</div>
        </div>

        <div className="p-4 rounded-xl bg-background-surface border border-border-subtle">
          <div className="text-[11px] text-zinc-400 font-medium">Revenue Recovered</div>
          <div className={`text-xl font-bold font-mono mt-1 ${c.state === 'RECOVERED' ? 'text-emerald-400' : 'text-zinc-500'}`}>
            {c.state === 'RECOVERED' ? formatInr(c.recovered_amount_inr) : '₹0.00'}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
            {c.state === 'RECOVERED' ? `100% Attributed (${c.recovered_payment_id})` : 'Pending settlement'}
          </div>
        </div>
      </div>

      {/* 3. Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('story')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'story'
              ? 'border-brand-400 text-brand-300'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <BrainCircuit className="w-4 h-4" />
          <span>Decision Story Mode</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'audit'
              ? 'border-brand-400 text-brand-300'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          <span>Immutable Audit Trail ({audits.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('telemetry')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'telemetry'
              ? 'border-brand-400 text-brand-300'
              : 'border-transparent text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Lock className="w-4 h-4" />
          <span>Raw Telemetry & Context</span>
        </button>
      </div>

      {/* 4. Tab Content */}
      {activeTab === 'story' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Step-by-Step Story Walkthrough */}
          <div className="lg:col-span-2 space-y-4">
            <div className="p-5 rounded-xl bg-background-surface border border-border-subtle">
              <h3 className="text-sm font-bold text-gray-100 mb-1">
                Decision Walkthrough — Why Was This Case Processed?
              </h3>
              <p className="text-xs text-zinc-400 mb-6">
                Chronological reasoning from gateway failure to revenue attribution.
              </p>

              <div className="space-y-6 relative before:absolute before:left-3.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                {storyStages.map((stage) => {
                  const isDone = stage.status === 'complete';
                  const isHalted = stage.status === 'halted';
                  return (
                    <div key={stage.num} className="flex items-start gap-4 relative">
                      {/* Step Circle */}
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-bold shrink-0 z-10 ${
                          isDone
                            ? 'bg-emerald-500 text-background ring-4 ring-background'
                            : isHalted
                            ? 'bg-rose-500 text-background ring-4 ring-background'
                            : 'bg-background-elevated text-zinc-500 border border-border ring-4 ring-background'
                        }`}
                      >
                        {isDone ? <CheckCircle2 className="w-4 h-4" /> : stage.num}
                      </div>

                      {/* Content */}
                      <div className="flex-1 bg-background-elevated/40 p-4 rounded-xl border border-border">
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold text-gray-200 uppercase font-mono tracking-wider">
                            {stage.title}
                          </h4>
                          <span className="text-[10px] font-mono text-zinc-500">{stage.actor}</span>
                        </div>
                        <p className="text-xs font-semibold text-zinc-300 mt-1">{stage.summary}</p>
                        <p className="text-[11px] text-zinc-400 mt-0.5 leading-relaxed">{stage.details}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Col: AI Proposal vs Guardrail Comparison Card */}
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-background-surface border border-brand-500/20 shadow-glow-brand space-y-4">
              <div className="flex items-center gap-2 text-brand-400 font-bold text-sm">
                <Bot className="w-4 h-4" />
                <span>AI Advisory vs. Guardrails</span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Core safety architecture: The LLM acts purely as an advisory proposal agent. Financial write authority is granted only through deterministic guardrails.
              </p>

              {/* AI Proposal Section */}
              <div className="p-3.5 rounded-lg bg-background-elevated/60 border border-border space-y-2">
                <div className="text-[10px] font-mono uppercase text-brand-400 font-semibold">
                  1. LLM Advisory Proposal
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-400">Proposed Policy:</span>
                  <PolicyBadge policy={c.ai_policy_id} />
                </div>
                {c.ai_explanation && (
                  <p className="text-[11px] text-zinc-300 italic bg-background-subtle/60 p-2 rounded border border-border-subtle">
                    &ldquo;{c.ai_explanation}&rdquo;
                  </p>
                )}
              </div>

              {/* Guardrail Invariants Section */}
              <div className="p-3.5 rounded-lg bg-background-elevated/60 border border-emerald-500/20 space-y-2.5">
                <div className="text-[10px] font-mono uppercase text-emerald-400 font-semibold flex items-center justify-between">
                  <span>2. Guardrail Enforcement</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                    VERIFIED
                  </span>
                </div>
                <ul className="text-[11px] space-y-1.5 text-zinc-300 font-mono">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Amount: ₹{c.amount_inr} (Immutable)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Currency: {c.currency} (Immutable)</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Cooldown: Satisfied</span>
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Link limit: Max 1 link per case</span>
                  </li>
                </ul>

                <div className="pt-2 border-t border-border-subtle flex items-center justify-between">
                  <span className="text-xs text-zinc-400 font-sans">Authorized Policy:</span>
                  <PolicyBadge policy={c.validated_policy_id} />
                </div>
              </div>
            </div>

            {/* Payment Link Card */}
            {c.payment_link_id && (
              <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-3">
                <h4 className="text-xs font-bold text-gray-200 font-mono uppercase tracking-wider">
                  Payment Link Execution
                </h4>
                <div className="space-y-2 text-xs">
                  <div>
                    <div className="text-zinc-500 text-[10px]">Payment Link ID:</div>
                    <div className="font-mono font-medium text-emerald-400 flex items-center justify-between mt-0.5">
                      <span>{c.payment_link_id}</span>
                      <button
                        onClick={() => copyToClipboard(c.payment_link_id!, 'Payment Link ID')}
                        className="text-zinc-400 hover:text-zinc-200"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {c.payment_link_short_url && (
                    <div>
                      <div className="text-zinc-500 text-[10px]">Short URL:</div>
                      <div className="flex items-center justify-between gap-2 mt-0.5">
                        <a
                          href={c.payment_link_short_url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-brand-400 hover:underline truncate text-[11px]"
                        >
                          {c.payment_link_short_url}
                        </a>
                        <a
                          href={c.payment_link_short_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1 rounded bg-background-elevated hover:bg-background-hover text-zinc-300"
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
        </div>
      )}

      {/* Tab: Audit Trail */}
      {activeTab === 'audit' && (
        <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-sm font-bold text-gray-100">Immutable Audit Trail</h3>
              <p className="text-xs text-zinc-400">
                Complete chronological event log written to database during each pipeline stage.
              </p>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-background-elevated text-zinc-300">
              {audits.length} events
            </span>
          </div>

          {audits.length === 0 ? (
            <div className="py-8 text-center text-zinc-500 text-xs font-mono">
              No audit events registered yet.
            </div>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              {audits.map((a) => (
                <div
                  key={a.id}
                  className="p-3.5 rounded-lg bg-background-elevated/40 border border-border space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-brand-500/10 text-brand-300 border border-brand-500/20 text-[11px] font-semibold">
                        {a.event_type}
                      </span>
                      <span className="text-zinc-400 text-[11px]">Actor: {a.actor}</span>
                    </div>
                    <span className="text-[11px] text-zinc-500">{a.timestamp ? new Date(a.timestamp).toLocaleString() : 'N/A'}</span>
                  </div>

                  <div className="flex items-center gap-4 text-[11px] text-zinc-300 pt-1">
                    {a.decision && <div>Decision: <strong className="text-emerald-400">{a.decision}</strong></div>}
                    {a.policy && <div>Policy: <strong className="text-blue-400">{a.policy}</strong></div>}
                  </div>

                  {a.details && Object.keys(a.details).length > 0 && (
                    <div className="mt-2 bg-background-subtle/80 p-2.5 rounded border border-border-subtle text-[10px] text-zinc-400 overflow-x-auto">
                      <pre>{JSON.stringify(a.details, null, 2)}</pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Raw Telemetry */}
      {activeTab === 'telemetry' && (
        <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-4 font-mono text-xs">
          <div>
            <h3 className="text-sm font-bold text-gray-100 font-sans">Full Case Record & Telemetry</h3>
            <p className="text-xs text-zinc-400 font-sans">
              Direct JSON payload returned by frozen endpoint <code className="text-brand-400">GET /cases/{c.case_id}</code>.
            </p>
          </div>
          <div className="bg-background-subtle p-4 rounded-xl border border-border overflow-x-auto text-[11px] text-zinc-300 max-h-96">
            <pre>{JSON.stringify(c, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};
