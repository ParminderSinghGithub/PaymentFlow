import React from 'react';
import { Activity, Database, Server, RefreshCw, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { HealthResponse } from '../types';

interface SystemHealthPageProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

const ENDPOINTS = [
  { method: 'GET',  path: '/health',                       desc: 'System health check' },
  { method: 'GET',  path: '/cases',                        desc: 'List recovery cases (filterable, paginated)' },
  { method: 'GET',  path: '/cases/{case_id}',              desc: 'Case detail + complete audit trail' },
  { method: 'GET',  path: '/cases/metrics/summary',        desc: 'Aggregate recovery metrics' },
  { method: 'POST', path: '/cases/{case_id}/triage',       desc: 'Execute full AI + MCP recovery orchestration' },
  { method: 'POST', path: '/cases/delayed/process',        desc: 'Process all due delayed recovery cases' },
];

const LAYERS = [
  { id: '5A–5C', label: 'Evaluation Framework',    desc: 'Synthetic eval, baseline comparison, agent evaluator, Monte Carlo simulation',       status: 'complete' },
  { id: '5D',    label: 'LLM Decision Provider',    desc: 'Gemini structured output with schema validation and deterministic fallback',           status: 'complete' },
  { id: '5E',    label: 'MCP Boundary',             desc: 'MCP client/server with read-only tools and guarded action proposals',                  status: 'complete' },
  { id: '5F',    label: 'Runtime Hardening',        desc: 'PolicyGuardrailEngine, RecoveryExecutor, production orchestration',                   status: 'complete' },
  { id: '5G',    label: 'Backend API Contract',     desc: 'Frozen REST endpoints, observability, deployment readiness',                           status: 'complete' },
  { id: '6',     label: 'Frontend Intelligence Console', desc: 'This interface — decision story, observability, AI/guardrail visualization',     status: 'active' },
];

export const SystemHealthPage: React.FC<SystemHealthPageProps> = ({ health, loading, onRefresh }) => {
  const isHealthy = health?.status === 'ok';
  const isOffline = !health && !loading;

  return (
    <div className="space-y-6 animate-fade-in max-w-3xl">

      {/* ── System Status Card ────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg overflow-hidden">
        <div className={`flex items-center gap-4 px-5 py-4 border-b ${
          isHealthy ? 'border-[rgba(5,150,105,0.15)] bg-[rgba(5,150,105,0.04)]' :
          isOffline ? 'border-[rgba(225,29,72,0.15)] bg-[rgba(225,29,72,0.04)]' :
          'border-[rgba(217,119,6,0.15)] bg-[rgba(217,119,6,0.04)]'
        }`}>
          {loading ? (
            <>
              <div className="w-3 h-3 rounded-full bg-[#4B5563] animate-live-pulse" />
              <span className="text-[13px] font-semibold text-[#9CA3AF]">Connecting to backend…</span>
            </>
          ) : isHealthy ? (
            <>
              <CheckCircle2 className="w-5 h-5 text-recover-text shrink-0" />
              <span className="text-[13px] font-semibold text-recover-text">System Operational</span>
            </>
          ) : isOffline ? (
            <>
              <XCircle className="w-5 h-5 text-halt-text shrink-0" />
              <span className="text-[13px] font-semibold text-halt-text">Backend Unreachable</span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-5 h-5 text-risk-text shrink-0" />
              <span className="text-[13px] font-semibold text-risk-text">System Degraded</span>
            </>
          )}

          <button
            onClick={onRefresh}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#6B7280] hover:text-[#9CA3AF] bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.08] rounded-md transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {/* Health details */}
        <div className="p-5 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Status',      value: health?.status ?? '—',       icon: Activity },
            { label: 'Database',    value: health?.database ?? '—',      icon: Database },
            { label: 'Environment', value: health?.environment ?? '—',   icon: Server },
            { label: 'Version',     value: health?.version ?? '—',       icon: Server },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="space-y-1">
              <div className="flex items-center gap-1.5">
                <Icon className="w-3 h-3 text-[#4B5563]" />
                <span className="text-[10px] font-mono text-[#4B5563] uppercase tracking-widest">{label}</span>
              </div>
              <div className={`font-mono text-[13px] font-semibold ${
                value === 'ok' || value === 'connected' ? 'text-recover-text' :
                value === 'disconnected' ? 'text-halt-text' :
                'text-[#F0F2F5]'
              }`}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Layer Status ──────────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <h3 className="text-[13px] font-semibold text-[#F0F2F5] mb-4">Implementation Layers</h3>
        <div className="space-y-2">
          {LAYERS.map((layer) => (
            <div
              key={layer.id}
              className={`flex items-start gap-4 p-3.5 border rounded-lg ${
                layer.status === 'active'
                  ? 'border-[rgba(124,58,237,0.25)] bg-[rgba(124,58,237,0.05)]'
                  : 'border-white/[0.06] bg-surface-raised'
              }`}
            >
              <span className={`text-[10px] font-mono px-2 py-1 rounded border shrink-0 ${
                layer.status === 'active'
                  ? 'text-ai-text bg-[rgba(124,58,237,0.12)] border-[rgba(124,58,237,0.25)]'
                  : 'text-recover-text bg-[rgba(5,150,105,0.10)] border-[rgba(5,150,105,0.20)]'
              }`}>
                L{layer.id}
              </span>
              <div>
                <div className="text-[12px] font-semibold text-[#F0F2F5]">{layer.label}</div>
                <div className="text-[11px] text-[#4B5563] mt-0.5 leading-relaxed">{layer.desc}</div>
              </div>
              <div className="ml-auto shrink-0">
                {layer.status === 'active' ? (
                  <span className="text-[9px] font-mono text-ai-text uppercase tracking-widest">Active</span>
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-recover-text" />
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Endpoint Reference ────────────────────────────────────────── */}
      <section className="bg-surface-base border border-white/[0.06] rounded-lg p-5">
        <h3 className="text-[13px] font-semibold text-[#F0F2F5] mb-1">Frozen API Contract (Layer 5G)</h3>
        <p className="text-[11px] text-[#4B5563] mb-4">REST endpoints — backend contract is frozen and must not be modified by frontend</p>
        <div className="space-y-2">
          {ENDPOINTS.map((ep) => (
            <div key={ep.path} className="flex items-center gap-3 py-2.5 border-b border-white/[0.04] last:border-0">
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded shrink-0 ${
                ep.method === 'GET'
                  ? 'text-guard-text bg-[rgba(13,148,136,0.12)]'
                  : 'text-ai-text bg-[rgba(124,58,237,0.12)]'
              }`}>
                {ep.method}
              </span>
              <code className="text-[11px] font-mono text-[#9CA3AF] flex-1">{ep.path}</code>
              <span className="text-[11px] text-[#4B5563] hidden md:block">{ep.desc}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
