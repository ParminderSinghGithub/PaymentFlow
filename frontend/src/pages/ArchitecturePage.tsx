import React from 'react';
import {
  BrainCircuit,
  ShieldCheck,
  Network,
  ArrowDown,
  CheckCircle2,
  XCircle,
  Lock,
  Database,
} from 'lucide-react';

// ─── Flow Step ────────────────────────────────────────────────────────

interface FlowStepProps {
  label: string;
  desc: string;
  zone: 'teal' | 'violet' | 'neutral' | 'external';
  icon: React.FC<{ className?: string }>;
}

const FLOW_ZONE_CLASSES: Record<string, string> = {
  teal:     'border-[rgba(13,148,136,0.25)] bg-[rgba(13,148,136,0.06)] text-guard-text',
  violet:   'border-[rgba(124,58,237,0.30)] bg-[rgba(124,58,237,0.08)] text-ai-text',
  neutral:  'border-white/[0.08] bg-surface-raised text-[#9CA3AF]',
  external: 'border-white/[0.06] bg-surface-base text-[#6B7280] border-dashed',
};

const FlowStep: React.FC<FlowStepProps> = ({ label, desc, zone, icon: Icon }) => (
  <div className={`flex items-center gap-3 p-3.5 border rounded-lg ${FLOW_ZONE_CLASSES[zone]}`}>
    <Icon className="w-4 h-4 shrink-0" />
    <div>
      <div className="text-[12px] font-semibold leading-tight">{label}</div>
      <div className="text-[10px] text-[#4B5563] mt-0.5">{desc}</div>
    </div>
  </div>
);

const Connector: React.FC<{ fromZone?: string; toZone?: string }> = ({ fromZone, toZone }) => (
  <div className="flex flex-col items-center gap-1 py-1">
    <ArrowDown className={`w-4 h-4 ${
      toZone === 'violet' ? 'text-ai-base/60' :
      fromZone === 'violet' ? 'text-ai-base/60' :
      'text-[#4B5563]'
    }`} />
  </div>
);

// ─── MCP Tool Row ─────────────────────────────────────────────────────

interface McpToolProps {
  name: string;
  access: 'READ ONLY' | 'PROPOSAL (GUARDED)';
  desc: string;
  input: string;
}

const McpToolRow: React.FC<McpToolProps> = ({ name, access, desc, input }) => {
  const isReadOnly = access === 'READ ONLY';

  return (
    <div className="border border-white/[0.06] rounded-lg overflow-hidden bg-surface-base">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.04]">
        <code className={`text-[12px] font-mono font-semibold ${isReadOnly ? 'text-guard-text' : 'text-risk-text'}`}>
          {name}
        </code>
        <span className={`ml-auto px-2 py-0.5 text-[9px] font-mono uppercase tracking-widest border rounded ${
          isReadOnly
            ? 'text-guard-text bg-[rgba(13,148,136,0.10)] border-[rgba(13,148,136,0.25)]'
            : 'text-risk-text bg-[rgba(217,119,6,0.10)] border-[rgba(217,119,6,0.25)]'
        }`}>
          {access}
        </span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <p className="text-[11px] text-[#6B7280] leading-relaxed">{desc}</p>
        <div className="font-mono text-[10px] text-[#4B5563] bg-surface-raised px-3 py-2 rounded border border-white/[0.04]">
          {input}
        </div>
      </div>
    </div>
  );
};

// ─── Safety Invariant Row ─────────────────────────────────────────────

interface InvariantProps {
  invariant: string;
  rule: string;
  prevents: string;
  enforcement: string;
}

const InvariantRow: React.FC<InvariantProps> = ({ invariant, rule, prevents, enforcement }) => (
  <div className="flex items-start gap-4 py-3 border-b border-white/[0.04] last:border-0">
    <CheckCircle2 className="w-4 h-4 text-guard-text shrink-0 mt-0.5" />
    <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4">
      <div>
        <div className="text-[12px] font-semibold text-[#F0F2F5]">{invariant}</div>
        <code className="text-[10px] font-mono text-guard-text mt-0.5 block">{rule}</code>
      </div>
      <div className="text-[11px] text-[#6B7280] leading-relaxed">{prevents}</div>
      <div className="text-[10px] font-mono text-[#4B5563]">{enforcement}</div>
    </div>
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────

export const ArchitecturePage: React.FC = () => {
  const mcpTools: McpToolProps[] = [
    {
      name: 'get_payment_context',
      access: 'READ ONLY',
      desc: 'Retrieves sanitized payment gateway error code, failure step, and customer context without any write access to payment systems.',
      input: '{ "case_id": "string" }',
    },
    {
      name: 'get_recovery_case',
      access: 'READ ONLY',
      desc: 'Fetches the database recovery case entity, current lifecycle state, amount, and prior attempt counts.',
      input: '{ "case_id": "string" }',
    },
    {
      name: 'get_recovery_status',
      access: 'READ ONLY',
      desc: 'Queries real-time payment link status and gateway state to verify payment before decision-making.',
      input: '{ "case_id": "string" }',
    },
    {
      name: 'request_recovery_action',
      access: 'PROPOSAL (GUARDED)',
      desc: 'Submits recovery policy proposal to the PolicyGuardrailEngine. Does NOT create payment links. Requires guardrail authorization. All invariants are re-checked before any financial write.',
      input: '{ "case_id": "string", "proposed_policy": "P_...", "proposed_amount": 250000, "proposed_currency": "INR" }',
    },
  ];

  const invariants: InvariantProps[] = [
    { invariant: 'Amount Immutability', rule: 'proposed_amount === original_amount', prevents: 'LLM discounts, paise manipulation, transaction amount mutation', enforcement: 'Hard rejection → P_NO_ACTION' },
    { invariant: 'Currency Immutability', rule: 'proposed_currency === "INR"', prevents: 'Currency switching to foreign currencies or alternate tenders', enforcement: 'Hard guardrail rejection' },
    { invariant: 'Customer Cooldown', rule: 'attempts ≤ 2 per 24 hours', prevents: 'Spamming customers with repeated automated payment links', enforcement: 'Eligibility: EXHAUSTED_COOLDOWN' },
    { invariant: 'High-Value Escalation', rule: 'amount ≤ ₹50,000', prevents: 'Automated AI recovery on high-value transactions without human review', enforcement: 'Override → P_ESCALATE_ONLY' },
    { invariant: 'Single Active Link', rule: 'payment_link_id === null', prevents: 'Double-charging via idempotency violation', enforcement: 'DB lock + guardrail invariant' },
    { invariant: 'Captured-Only Attribution', rule: 'verified_status === "captured"', prevents: 'Phantom revenue attribution on authorized-but-uncaptured payments', enforcement: 'Direct API verification barrier' },
  ];

  const flow: Array<{ step: FlowStepProps; connector?: { fromZone?: string; toZone?: string } }> = [
    { step: { label: 'payment.failed', desc: 'Webhook received from Razorpay', zone: 'external', icon: Network }, connector: {} },
    { step: { label: 'Webhook + Idempotency', desc: 'Signature verified, deduplicated', zone: 'teal', icon: ShieldCheck }, connector: {} },
    { step: { label: 'Context Enrichment', desc: 'Order, customer, gateway context fetched', zone: 'teal', icon: Database }, connector: {} },
    { step: { label: 'Eligibility Engine', desc: '8 deterministic rules — amount, cooldown, state', zone: 'teal', icon: CheckCircle2 }, connector: { toZone: 'violet' } },
    { step: { label: 'MCP Client → LLM (Gemini)', desc: 'AI reads context via MCP tools (read-only) · proposes policy', zone: 'violet', icon: BrainCircuit }, connector: { fromZone: 'violet' } },
    { step: { label: 'PolicyGuardrailEngine', desc: 'Deterministic validation · enforces all invariants', zone: 'teal', icon: ShieldCheck }, connector: {} },
    { step: { label: 'RecoveryExecutor', desc: 'Creates Razorpay Payment Link (if authorized)', zone: 'teal', icon: Lock }, connector: { fromZone: 'teal' } },
    { step: { label: 'Razorpay API', desc: 'Payment Link created · customer notified', zone: 'external', icon: Network }, connector: {} },
    { step: { label: 'Captured-Only Attribution', desc: 'Verified capture → revenue attributed', zone: 'teal', icon: CheckCircle2 }, connector: undefined },
  ];

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl">

      {/* ── Intro ─────────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-[18px] font-bold text-[#F0F2F5] mb-1 tracking-tight">
          AI recommends. Deterministic policy authorizes.
        </h2>
        <p className="text-[13px] text-[#6B7280] max-w-2xl leading-relaxed">
          PaymentFlow's core architectural claim: the LLM is an advisory component inside a
          deterministic financial workflow. It can classify, reason, and propose — but it has no
          direct write authority over any payment operation.
        </p>
      </section>

      {/* ── CAN / CANNOT ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.20)] rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(124,58,237,0.12)]">
            <BrainCircuit className="w-4 h-4 text-ai-text" />
            <span className="text-[12px] font-semibold text-ai-text">LLM is allowed to</span>
          </div>
          <ul className="px-4 py-3 space-y-2">
            {[
              'Classify failure into C1–C5 taxonomy',
              'Select one policy ID from allowed list',
              'Provide merchant-facing explanation',
              'Read sanitized context via MCP tools',
              'Propose recovery plan to guardrail engine',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-[12px] text-[#C4B5FD]">
                <CheckCircle2 className="w-3.5 h-3.5 text-ai-text shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-[rgba(225,29,72,0.05)] border border-[rgba(225,29,72,0.18)] rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(225,29,72,0.10)]">
            <XCircle className="w-4 h-4 text-halt-text" />
            <span className="text-[12px] font-semibold text-halt-text">LLM is NOT allowed to</span>
          </div>
          <ul className="px-4 py-3 space-y-2">
            {[
              'Call Razorpay API directly',
              'Create or cancel Payment Links',
              'Set payment amounts or currencies',
              'Override guardrail invariants',
              'Access PAN, bank account, or sensitive data',
              'Capture, refund, or transfer funds',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-[12px] text-[#FDA4AF]">
                <XCircle className="w-3.5 h-3.5 text-halt-text shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* ── System Flow ───────────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <h3 className="text-[13px] font-semibold text-[#F0F2F5] mb-1">System Flow</h3>
        <p className="text-[11px] text-[#4B5563] mb-5">
          End-to-end pipeline from webhook ingestion to revenue attribution
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Flow diagram */}
          <div className="space-y-0">
            {flow.map(({ step, connector }, idx) => (
              <React.Fragment key={step.label}>
                <FlowStep {...step} />
                {connector !== undefined && idx < flow.length - 1 && (
                  <Connector fromZone={step.zone} toZone={flow[idx + 1]?.step.zone} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* MCP boundary explanation */}
          <div className="space-y-4">
            <div className="bg-[rgba(124,58,237,0.06)] border border-[rgba(124,58,237,0.20)] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Network className="w-4 h-4 text-ai-text" />
                <span className="text-[12px] font-semibold text-ai-text">MCP Boundary</span>
              </div>
              <p className="text-[11px] text-[#6B7280] leading-relaxed mb-3">
                The Model Context Protocol (MCP) defines the exact interface the LLM can see.
                It exposes only read-only tools for context retrieval and a guarded action proposal
                channel. The MCP server enforces that the LLM never receives raw Razorpay credentials
                or write-capable API surfaces.
              </p>
              <div className="text-[10px] font-mono text-[#4B5563] space-y-1">
                <div>MCP Client ↔ MCP Server</div>
                <div className="text-[#4B5563]">All tools return sanitized, read-only payloads</div>
                <div className="text-[#4B5563]">Action proposals flow to PolicyGuardrailEngine</div>
              </div>
            </div>

            <div className="bg-[rgba(13,148,136,0.05)] border border-[rgba(13,148,136,0.18)] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck className="w-4 h-4 text-guard-text" />
                <span className="text-[12px] font-semibold text-guard-text">PolicyGuardrailEngine</span>
              </div>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">
                The deterministic authority layer. Every LLM proposal passes through the guardrail
                engine before any financial write occurs. It validates all 6 safety invariants,
                can override the AI recommendation, and is the sole source of authorized policy.
              </p>
            </div>

            <div className="bg-surface-raised border border-white/[0.06] rounded-lg p-4">
              <div className="text-[11px] font-mono text-[#6B7280] space-y-1">
                <div className="text-[10px] text-[#4B5563] uppercase tracking-widest mb-2">LLM failure policy</div>
                <div>Model unavailable → deterministic fallback</div>
                <div>Malformed output → deterministic fallback</div>
                <div>Schema validation failure → deterministic fallback</div>
                <div className="text-[9px] text-[#4B5563] mt-2">System never executes unvalidated model output</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── MCP Tools ─────────────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <h3 className="text-[13px] font-semibold text-[#F0F2F5] mb-1">MCP Tool Surface</h3>
        <p className="text-[11px] text-[#4B5563] mb-4">
          The LLM-visible interface is deliberately minimal. 3 read-only tools + 1 guarded proposal channel.
        </p>
        <div className="space-y-3">
          {mcpTools.map((tool) => <McpToolRow key={tool.name} {...tool} />)}
        </div>
      </section>

      {/* ── Safety Invariants ─────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <div className="flex items-center gap-2 mb-1">
          <ShieldCheck className="w-4 h-4 text-guard-text" />
          <h3 className="text-[13px] font-semibold text-[#F0F2F5]">Safety Invariants</h3>
        </div>
        <p className="text-[11px] text-[#4B5563] mb-4">
          Enforced deterministically by PolicyGuardrailEngine — cannot be overridden by the LLM
        </p>
        <div className="text-[10px] font-mono text-[#4B5563] grid grid-cols-3 gap-4 pb-2 mb-2 border-b border-white/[0.06]">
          <span>Invariant</span>
          <span>Prevents</span>
          <span>Enforcement</span>
        </div>
        {invariants.map((inv) => <InvariantRow key={inv.invariant} {...inv} />)}
      </section>
    </div>
  );
};
