import React from 'react';
import {
  ShieldCheck,
  Bot,
  Database,
  CheckCircle2,
  Lock,
  Zap,
} from 'lucide-react';

export const McpArchitecturePage: React.FC = () => {
  const tools = [
    {
      name: 'get_payment_context',
      type: 'READ ONLY',
      desc: 'Retrieves payment gateway error code, error reason, failure step, and customer context without write access.',
      input: '{ "case_id": "string" }',
      badgeClass: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    },
    {
      name: 'get_recovery_case',
      type: 'READ ONLY',
      desc: 'Fetches database recovery case entity, current lifecycle state, amount, and attempt counts.',
      input: '{ "case_id": "string" }',
      badgeClass: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    },
    {
      name: 'get_recovery_status',
      type: 'READ ONLY',
      desc: 'Queries real-time payment link and gateway status to verify payment state before decision making.',
      input: '{ "case_id": "string" }',
      badgeClass: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    },
    {
      name: 'request_recovery_action',
      type: 'ACTION PROPOSAL (GUARDED)',
      desc: 'Submits recovery policy proposal to PolicyGuardrailEngine. Does NOT directly create links; requires guardrail authorization.',
      input: '{ "case_id": "string", "proposed_policy": "P_...", "proposed_amount": 250000, "proposed_currency": "INR" }',
      badgeClass: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    },
  ];

  const safetyInvariants = [
    {
      invariant: 'Amount Immutability',
      rule: 'proposed_amount === original_amount',
      description: 'LLM cannot offer discounts, modify paise values, or mutate transaction amounts.',
      enforcement: 'Deterministic rejection (P_NO_ACTION) on mismatch.',
    },
    {
      invariant: 'Currency Immutability',
      rule: 'proposed_currency === "INR"',
      description: 'Transaction currency cannot be switched to foreign currencies or alternate tenders.',
      enforcement: 'Hard guardrail rejection on alteration.',
    },
    {
      invariant: 'Customer Cooldown',
      rule: 'attempt_count <= 2 per 24 hours',
      description: 'Protects customers against spamming or repetitive automated payment link generation.',
      enforcement: 'Eligibility engine marks EXHAUSTED_COOLDOWN.',
    },
    {
      invariant: 'High-Value Escalation',
      rule: 'amount > ₹50,000 (5,000,000 paise)',
      description: 'Transactions exceeding high-value ceiling automatically downgrade from link creation to manual escalation.',
      enforcement: 'PolicyGuardrailEngine overrides to P_ESCALATE_ONLY.',
    },
    {
      invariant: 'Single Active Link',
      rule: 'payment_link_id === null',
      description: 'Enforces idempotency and prevents double-charging by restricting recovery to max 1 active link per case.',
      enforcement: 'Pre-write database lock and guardrail invariant.',
    },
    {
      invariant: 'Captured-Only Attribution',
      rule: 'verified_status === "captured"',
      description: 'Revenue is attributed only when direct Razorpay API confirms captured settlement. Authorized-only yields ₹0.',
      enforcement: 'Direct API verification webhook barrier.',
    },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="p-6 rounded-xl bg-background-surface border border-brand-500/20 shadow-glow-brand space-y-2">
        <div className="flex items-center gap-2 text-brand-400 font-bold text-sm">
          <ShieldCheck className="w-5 h-5" />
          <span>MCP Protocol Boundary & Deterministic Guardrails</span>
        </div>
        <h2 className="text-xl font-extrabold text-gray-100 tracking-tight">
          Defense-in-Depth Architecture
        </h2>
        <p className="text-xs text-zinc-300 max-w-3xl leading-relaxed">
          The PaymentFlow architecture strictly isolates the AI Agent behind the Model Context Protocol (MCP). The LLM is an <strong>advisory inference engine</strong> with zero direct Razorpay write credentials. All financial writes must pass through the deterministic <code className="text-brand-400 font-mono">PolicyGuardrailEngine</code>.
        </p>
      </div>

      {/* 2. Interactive MCP Architecture Flow Diagram */}
      <div className="p-6 rounded-xl bg-background-surface border border-border-subtle space-y-5">
        <h3 className="text-sm font-bold text-gray-100">End-to-End Decision & Execution Boundary</h3>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
          {/* Box 1: Ingestion & Context */}
          <div className="p-4 rounded-xl bg-background-elevated/40 border border-border space-y-2.5">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-bold font-mono">
              <Database className="w-4 h-4" />
              <span>1. Ingestion</span>
            </div>
            <p className="text-xs font-semibold text-gray-200">Context Enrichment</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Webhook HMAC-SHA256 verified, case created, gateway error retrieved, and C1–C5 taxonomy classified.
            </p>
            <div className="text-[10px] font-mono text-zinc-500 pt-1 border-t border-border-subtle">
              Input: payment.failed
            </div>
          </div>

          {/* Box 2: AI / MCP Read Tools */}
          <div className="p-4 rounded-xl bg-background-elevated/40 border border-brand-500/30 space-y-2.5 shadow-sm">
            <div className="flex items-center gap-2 text-brand-400 text-xs font-bold font-mono">
              <Bot className="w-4 h-4" />
              <span>2. AI & MCP Read</span>
            </div>
            <p className="text-xs font-semibold text-gray-200">Advisory Inference</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Gemini LLM queries MCP read tools to analyze failure context and proposes structured recovery policy.
            </p>
            <div className="text-[10px] font-mono text-brand-400 pt-1 border-t border-border-subtle">
              Zero write credentials
            </div>
          </div>

          {/* Box 3: Policy Guardrail Engine */}
          <div className="p-4 rounded-xl bg-background-elevated/40 border border-emerald-500/30 space-y-2.5 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold font-mono">
              <Lock className="w-4 h-4" />
              <span>3. Guardrails</span>
            </div>
            <p className="text-xs font-semibold text-gray-200">Deterministic Gate</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              PolicyGuardrailEngine validates amount, currency, cooldown, and risk limits before authorization.
            </p>
            <div className="text-[10px] font-mono text-emerald-400 pt-1 border-t border-border-subtle">
              Authoritative Decider
            </div>
          </div>

          {/* Box 4: Execution & Attribution */}
          <div className="p-4 rounded-xl bg-background-elevated/40 border border-border space-y-2.5">
            <div className="flex items-center gap-2 text-sky-400 text-xs font-bold font-mono">
              <Zap className="w-4 h-4" />
              <span>4. Execution</span>
            </div>
            <p className="text-xs font-semibold text-gray-200">Razorpay Write Path</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              RecoveryExecutor generates Payment Link. Attribution triggered only on captured payment verification.
            </p>
            <div className="text-[10px] font-mono text-zinc-500 pt-1 border-t border-border-subtle">
              Output: Captured ₹
            </div>
          </div>
        </div>
      </div>

      {/* 3. Registered MCP Tools */}
      <div className="p-6 rounded-xl bg-background-surface border border-border-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-gray-100">MCP Protocol Tools Specification</h3>
          <p className="text-xs text-zinc-400">
            Registered tools exposed through the MCP Server boundary.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tools.map((t) => (
            <div
              key={t.name}
              className="p-4 rounded-xl bg-background-elevated/40 border border-border space-y-2 font-mono text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-gray-100 text-sm font-mono">{t.name}</span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${t.badgeClass}`}>
                  {t.type}
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 font-sans leading-relaxed">{t.desc}</p>
              <div className="bg-background-subtle p-2 rounded border border-border-subtle text-[10px] text-zinc-300 overflow-x-auto">
                <span className="text-zinc-500">Schema: </span>
                {t.input}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Guardrail Safety Invariants Table */}
      <div className="p-6 rounded-xl bg-background-surface border border-border-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-gray-100">Deterministic Guardrail Safety Invariants</h3>
          <p className="text-xs text-zinc-400">
            Mathematical constraints enforced prior to any Razorpay API write.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-mono">
            <thead>
              <tr className="border-b border-border bg-background-subtle/50 text-zinc-400 text-[11px]">
                <th className="py-3 pl-3 font-medium">Invariant</th>
                <th className="py-3 font-medium">Rule Expression</th>
                <th className="py-3 font-medium">Description</th>
                <th className="py-3 pr-3 font-medium">Enforcement Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {safetyInvariants.map((s, idx) => (
                <tr key={idx} className="hover:bg-background-elevated/30 transition-colors">
                  <td className="py-3 pl-3 font-semibold text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{s.invariant}</span>
                  </td>
                  <td className="py-3 text-brand-300 font-bold">{s.rule}</td>
                  <td className="py-3 text-zinc-300 font-sans text-[11px]">{s.description}</td>
                  <td className="py-3 pr-3 text-zinc-400 font-sans text-[11px]">{s.enforcement}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
