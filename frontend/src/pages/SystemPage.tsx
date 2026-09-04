import React, { useState } from 'react';
import {
  Activity,
  Database,
  Server,
  RefreshCw,
  CheckCircle2,
  XCircle,
  BrainCircuit,
  ShieldCheck,
  Network,
  Layers,
  FileCode2,
} from 'lucide-react';
import type { HealthResponse } from '../types';
import { PageHeader } from '../components/common/PageHeader';
import { ActionButton } from '../components/common/ActionButton';

interface SystemPageProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

type SystemTab = 'architecture' | 'guardrails' | 'mcp' | 'health' | 'contracts';

const ENDPOINTS = [
  { method: 'GET',  path: '/health',                                   desc: 'System health check & asyncpg database probe' },
  { method: 'GET',  path: '/cases',                                    desc: 'List recovery cases with state filtering & pagination' },
  { method: 'GET',  path: '/cases/metrics/summary',                    desc: 'Aggregate recovery KPIs and category/policy breakdown' },
  { method: 'GET',  path: '/cases/{case_id}',                          desc: 'Case detail + complete chronological audit stream' },
  { method: 'POST', path: '/cases/benchmark/run',                      desc: 'Execute canonical 15-scenario recovery workflow benchmark dynamically' },
  { method: 'GET',  path: '/cases/benchmark/latest',                   desc: 'Retrieve run-scoped metrics for the most recent benchmark run' },
  { method: 'POST', path: '/cases/{case_id}/triage',                   desc: 'Manually execute full AI + MCP recovery orchestration' },
  { method: 'POST', path: '/cases/delayed/process',                    desc: 'Restart-safely process due delayed recovery cases' },
  { method: 'POST', path: '/webhooks/razorpay',                        desc: 'HMAC-verified Razorpay payment.failed / payment.captured ingress' },
  { method: 'GET',  path: '/merchant/v1/verify',                       desc: 'Merchant configuration probe & API credential validation' },
  { method: 'POST', path: '/merchant/v1/checkout-context',             desc: 'Generate idempotent checkout context & sign orders' },
  { method: 'POST', path: '/merchant/v1/orders',                       desc: 'Initiate merchant order and bind customer contact' },
  { method: 'GET',  path: '/merchant/v1/orders/{order_id}/recovery-status', desc: 'Authoritative recovery status & attribution probe' },
  { method: 'GET',  path: '/merchant/checkout',                        desc: 'Demonstration checkout page using Razorpay Checkout.js in Test Mode' },
];

const INVARIANTS = [
  {
    invariant: 'Amount Immutability',
    rule: 'proposed_amount === original_amount',
    prevents: 'LLM discount offers, paise manipulation, unauthorized price deductions',
    enforcement: 'Hard guardrail rejection → P_NO_ACTION',
  },
  {
    invariant: 'Currency Immutability',
    rule: 'proposed_currency === original_currency',
    prevents: 'Currency switching to foreign currencies or alternate tender types',
    enforcement: 'Hard guardrail rejection → P_NO_ACTION',
  },
  {
    invariant: 'High-Value Escalation Cap',
    rule: 'amount > ₹50,000.00 (5,000,000 paise)',
    prevents: 'Automated recovery without manual human-in-the-loop review',
    enforcement: 'Unconditional override → P_ESCALATE_ONLY',
  },
  {
    invariant: 'Risk / AML Block (C4)',
    rule: 'failure_category === "C4"',
    prevents: 'Retrying flagged fraudulent, blacklisted, or stolen payment methods',
    enforcement: 'Automated retry forbidden → P_ESCALATE_ONLY',
  },
  {
    invariant: 'Technical Failure Halt (C5)',
    rule: 'failure_category === "C5"',
    prevents: 'Spamming customers on internal gateway 500 or schema bugs',
    enforcement: 'Halt recovery → P_NO_ACTION',
  },
  {
    invariant: 'Customer Cooldown Limit',
    rule: 'active_links_last_24h < 3',
    prevents: 'Payment link spamming and harassment of dropoff customers',
    enforcement: 'Rate limit gate → P_NO_ACTION',
  },
  {
    invariant: 'Captured-Only Attribution',
    rule: 'status === "captured" (verified via API/webhook)',
    prevents: 'Attributing uncaptured authorizations or fabricated recovered revenue',
    enforcement: 'PostgreSQL row-locked single-attribution ledger',
  },
];

const MCP_TOOLS = [
  {
    name: 'get_payment_context',
    access: 'READ ONLY',
    desc: 'Retrieves sanitized payment gateway error code, failure step, and customer metadata with zero write authority.',
    input: '{ "case_id": "string" }',
  },
  {
    name: 'get_recovery_case',
    access: 'READ ONLY',
    desc: 'Fetches database recovery case entity, lifecycle state, amount at risk, and prior attempt history.',
    input: '{ "case_id": "string" }',
  },
  {
    name: 'get_recovery_status',
    access: 'READ ONLY',
    desc: 'Queries current payment link state and gateway status before AI triage reasoning.',
    input: '{ "case_id": "string" }',
  },
  {
    name: 'request_recovery_action',
    access: 'PROPOSAL (GUARDED)',
    desc: 'Submits recovery policy recommendation to PolicyGuardrailEngine. Does NOT write to payment gateways directly.',
    input: '{ "case_id": "string", "proposed_policy": "P_...", "proposed_amount": 250000, "proposed_currency": "INR" }',
  },
];

export const SystemPage: React.FC<SystemPageProps> = ({ health, loading, onRefresh }) => {
  const [activeTab, setActiveTab] = useState<SystemTab>('architecture');
  const isHealthy = health?.status === 'ok';

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <PageHeader
        title="System Architecture & Trust Engine"
        description="Inspect the zero-trust recovery architecture: strict AI advisory boundaries, deterministic guardrail invariants, and standardized Model Context Protocol (MCP) contracts."
        icon={Layers}
        actions={
          <ActionButton
            label={loading ? 'Probing…' : 'Probe Backend'}
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            loading={loading}
            onClick={onRefresh}
          />
        }
      />

      {/* ── Subnav Tabs ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 border-b border-white/[0.08] pb-3 overflow-x-auto">
        {[
          { id: 'architecture', label: 'Architecture & AI Boundary', icon: Network },
          { id: 'guardrails',   label: 'Guardrail Invariants',        icon: ShieldCheck },
          { id: 'mcp',          label: 'MCP Tool Contracts',          icon: BrainCircuit },
          { id: 'health',       label: 'Health & Diagnostics',        icon: Activity },
          { id: 'contracts',    label: 'REST API Contracts',          icon: FileCode2 },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          const { icon: Icon } = tab;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as SystemTab)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                isActive
                  ? 'bg-surface-raised text-[#F0F2F5] border border-white/[0.12]'
                  : 'text-[#6B7280] hover:text-[#9CA3AF] hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab 1: Architecture & AI Boundary ─────────────────────────── */}
      {activeTab === 'architecture' && (
        <div className="space-y-6">
          <div className="bg-surface rounded-xl border border-white/[0.08] p-6">
            <h3 className="text-base font-semibold text-[#F0F2F5] mb-1">
              Zero-Trust Architecture: AI Advisory + Deterministic Gate
            </h3>
            <p className="text-xs text-[#6B7280] mb-6">
              PaymentFlow enforces a strict separation of concerns. The LLM acts purely as an advisory reasoning engine over sanitized MCP data, while the deterministic PolicyGuardrailEngine holds 100% write authorization authority.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Violet Zone Card */}
              <div className="p-5 rounded-xl bg-surface-raised border border-ai-base/30 space-y-3 relative overflow-hidden">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-ai-text" />
                  <span className="text-xs font-mono font-bold text-ai-text uppercase tracking-wider">
                    AI Advisory Zone (Violet)
                  </span>
                </div>
                <ul className="text-xs text-[#9CA3AF] space-y-2">
                  <li>• Structured JSON output via Google Gemini REST API</li>
                  <li>• Sanitized context ingestion via MCP read-only tools</li>
                  <li>• Recommends failure category (C1–C5) and recovery policy</li>
                  <li>• Zero direct payment gateway write permissions</li>
                  <li>• Deterministic fail-closed fallback on timeout or error</li>
                </ul>
              </div>

              {/* Teal Zone Card */}
              <div className="p-5 rounded-xl bg-surface-raised border border-guard-base/30 space-y-3 relative overflow-hidden">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-guard-text" />
                  <span className="text-xs font-mono font-bold text-guard-text uppercase tracking-wider">
                    Deterministic Guardrails (Teal)
                  </span>
                </div>
                <ul className="text-xs text-[#9CA3AF] space-y-2">
                  <li>• Absolute gatekeeper over all state machine transitions</li>
                  <li>• Validates amount & currency immutability</li>
                  <li>• Unconditional human escalation on amounts &gt; ₹50,000</li>
                  <li>• Mandatory halt on C4 Risk and C5 Gateway defects</li>
                  <li>• Authorizes RecoveryExecutor write to Razorpay API</li>
                </ul>
              </div>
            </div>

            {/* Boundaries: Merchant Integration & Evidence */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-white/[0.06]">
              {/* Merchant Integration Boundary */}
              <div className="p-4 rounded-lg bg-surface-raised border border-white/[0.06] space-y-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-teal-400" />
                  <span className="text-xs font-semibold text-[#F0F2F5]">
                    Merchant Integration Boundary
                  </span>
                </div>
                <p className="text-xs text-[#9CA3AF] leading-relaxed">
                  Server-to-server merchant integration boundary; operator console is optional. External merchant store (<code>127.0.0.1:8002</code>) interacts via <code>/merchant/v1/*</code> REST contracts using merchant-bound Razorpay credentials. PaymentFlow operates out-of-band via standard webhooks (<code>payment.failed</code>) and dispatches native recovery links directly to customer contacts.
                </p>
              </div>

              {/* Evidence Boundary */}
              <div className="p-4 rounded-lg bg-surface-raised border border-white/[0.06] space-y-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-xs font-semibold text-[#F0F2F5]">
                    Authoritative Evidence Boundary
                  </span>
                </div>
                <p className="text-xs text-[#9CA3AF] leading-relaxed">
                  Zero manufactured attribution. Benchmark metrics derive strictly from <code>CANONICAL_EVALUATION</code> runs, while operational metrics reflect genuine <code>MERCHANT_CHECKOUT</code> webhooks verified via Razorpay REST API captures and PostgreSQL row locks.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 2: Guardrail Invariants ───────────────────────────────── */}
      {activeTab === 'guardrails' && (
        <div className="bg-surface rounded-xl border border-white/[0.08] p-6 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-[#F0F2F5]">
              Deterministic Financial Guardrail Safety Invariants
            </h3>
            <p className="text-xs text-[#6B7280] mt-1">
              Every recovery proposal is checked against these mathematical invariants before any transaction write.
            </p>
          </div>

          <div className="space-y-3">
            {INVARIANTS.map((inv) => (
              <div
                key={inv.invariant}
                className="p-4 rounded-lg bg-surface-raised border border-white/[0.04] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#F0F2F5] flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-guard-text" />
                    {inv.invariant}
                  </span>
                  <code className="text-[11px] font-mono text-guard-text bg-guard-base/10 px-2 py-0.5 rounded border border-guard-base/20">
                    {inv.rule}
                  </code>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-[#9CA3AF]">
                  <div><strong className="text-[#6B7280]">Prevents:</strong> {inv.prevents}</div>
                  <div><strong className="text-[#6B7280]">Enforcement:</strong> <span className="text-[#D1D5DB]">{inv.enforcement}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab 3: MCP Tool Contracts ─────────────────────────────────── */}
      {activeTab === 'mcp' && (
        <div className="bg-surface rounded-xl border border-white/[0.08] p-6 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-[#F0F2F5]">
              Model Context Protocol (MCP) Standardized Tools
            </h3>
            <p className="text-xs text-[#6B7280] mt-1">
              Read-only inspection tools vs guarded action proposals exposed to the agent client.
            </p>
          </div>

          <div className="space-y-3">
            {MCP_TOOLS.map((tool) => (
              <div
                key={tool.name}
                className="p-4 rounded-lg bg-surface-raised border border-white/[0.04] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <code className="text-xs font-mono font-bold text-ai-text">{tool.name}</code>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                    tool.access === 'READ ONLY'
                      ? 'bg-guard-base/10 text-guard-text border border-guard-base/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {tool.access}
                  </span>
                </div>
                <p className="text-xs text-[#9CA3AF]">{tool.desc}</p>
                <div className="text-[11px] font-mono text-[#6B7280] bg-void p-2 rounded border border-white/[0.04]">
                  Input: {tool.input}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab 4: Health & Diagnostics ───────────────────────────────── */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          <div className="bg-surface rounded-xl border border-white/[0.08] overflow-hidden">
            <div className={`flex items-center justify-between px-6 py-4 border-b ${
              isHealthy ? 'bg-emerald-950/20 border-emerald-500/20' : 'bg-rose-950/20 border-rose-500/20'
            }`}>
              <div className="flex items-center gap-3">
                {loading ? (
                  <div className="w-3 h-3 rounded-full bg-[#4B5563] animate-pulse" />
                ) : isHealthy ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-rose-400" />
                )}
                <div>
                  <h4 className="text-sm font-semibold text-[#F0F2F5]">
                    {loading ? 'Probing Backend...' : isHealthy ? 'System Operational' : 'Backend Degraded'}
                  </h4>
                  <div className="text-xs text-[#6B7280] font-mono">
                    Target: http://localhost:8001
                  </div>
                </div>
              </div>

              <button
                onClick={onRefresh}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors flex items-center gap-2"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Recheck
              </button>
            </div>

            <div className="p-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Status', value: health?.status ?? '—', icon: Activity },
                { label: 'Database', value: health?.database ?? '—', icon: Database },
                { label: 'Environment', value: health?.environment ?? '—', icon: Server },
                { label: 'Version', value: health?.version ?? '—', icon: Layers },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="p-3.5 rounded-lg bg-surface-raised border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[#6B7280] uppercase tracking-wider font-mono">
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </div>
                  <div className={`text-sm font-mono font-bold mt-1 ${
                    value === 'ok' || value === 'connected' ? 'text-emerald-400' : 'text-[#F0F2F5]'
                  }`}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 5: REST API Contracts ─────────────────────────────────── */}
      {activeTab === 'contracts' && (
        <div className="bg-surface rounded-xl border border-white/[0.08] p-6 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-[#F0F2F5]">
              Authoritative FastAPI REST API Contract ({ENDPOINTS.length} Endpoints)
            </h3>
            <p className="text-xs text-[#6B7280] mt-1">
              Authoritative backend contracts consumed by this frontend intelligence console.
            </p>
          </div>

          <div className="space-y-2">
            {ENDPOINTS.map((ep) => (
              <div
                key={ep.path}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-raised border border-white/[0.04]"
              >
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    ep.method === 'GET'
                      ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  }`}>
                    {ep.method}
                  </span>
                  <code className="text-xs font-mono text-[#D1D5DB]">{ep.path}</code>
                </div>
                <span className="text-xs text-[#6B7280]">{ep.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
