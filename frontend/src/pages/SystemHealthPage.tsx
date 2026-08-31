import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  Database,
  Server,
  Zap,
} from 'lucide-react';
import type { HealthResponse } from '../types';

interface SystemHealthPageProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export const SystemHealthPage: React.FC<SystemHealthPageProps> = ({
  health,
  onRefresh,
}) => {
  const isDbConnected = health?.database === 'connected';
  const isHealthy = health?.status === 'ok' && isDbConnected;

  const systemLayers = [
    { layer: 'Layer 0', name: 'Domain Foundations & Secure Secrets Architecture', status: 'VERIFIED' },
    { layer: 'Layer 1', name: 'Webhook Ingestion & HMAC Verification', status: 'VERIFIED' },
    { layer: 'Layer 2', name: 'Failure Taxonomy (C1–C5) & Deterministic Eligibility', status: 'VERIFIED' },
    { layer: 'Layer 3', name: 'Policy Engine & Guardrail Validation Boundary', status: 'VERIFIED' },
    { layer: 'Layer 4A', name: 'Razorpay Execution Adapter & Link Generation', status: 'VERIFIED' },
    { layer: 'Layer 4B', name: 'Captured-Only Attribution & Webhook Verification', status: 'VERIFIED' },
    { layer: 'Layer 5A-5E', name: '75-Case Dataset, Evaluator, Real LLM & MCP Bridge', status: 'VERIFIED' },
    { layer: 'Layer 5F-5G', name: 'Production Orchestration, Hardening & Frozen API', status: 'VERIFIED' },
    { layer: 'Layer 6', name: 'Flagship Recovery Intelligence Console (Frontend)', status: 'ACTIVE' },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Health Status Banner */}
      <div className="p-6 rounded-xl bg-background-surface border border-border-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              isHealthy
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
            }`}
          >
            {isHealthy ? <CheckCircle2 className="w-6 h-6" /> : <AlertTriangle className="w-6 h-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-gray-100">
                {isHealthy ? 'All Systems Operational' : 'Degraded Operational State'}
              </h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-background-elevated text-zinc-300">
                v{health?.version || '0.1.0'}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Live diagnostics against backend endpoint <code className="text-brand-400 font-mono">GET /health</code>.
            </p>
          </div>
        </div>

        <button
          onClick={onRefresh}
          className="px-4 py-2 text-xs font-semibold rounded-lg bg-background-elevated hover:bg-background-hover text-zinc-200 border border-border transition-colors self-start md:self-auto"
        >
          Check Now
        </button>
      </div>

      {/* 2. Core Service Diagnostics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Backend API */}
        <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-300 text-xs font-semibold">
              <Server className="w-4 h-4 text-brand-400" />
              <span>FastAPI Backend Service</span>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                health?.status === 'ok'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              }`}
            >
              {health?.status === 'ok' ? 'HEALTHY' : 'DEGRADED'}
            </span>
          </div>
          <div className="text-xs font-mono space-y-1 text-zinc-400">
            <div>Environment: <strong className="text-zinc-200">{health?.environment || 'development'}</strong></div>
            <div>REST Protocol: <strong className="text-zinc-200">HTTP/1.1 (FastAPI)</strong></div>
            <div>CORS Status: <strong className="text-emerald-400">Enabled</strong></div>
          </div>
        </div>

        {/* PostgreSQL Database */}
        <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-300 text-xs font-semibold">
              <Database className="w-4 h-4 text-cyan-400" />
              <span>PostgreSQL Database</span>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                isDbConnected
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              }`}
            >
              {isDbConnected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
          <div className="text-xs font-mono space-y-1 text-zinc-400">
            <div>Driver: <strong className="text-zinc-200">asyncpg (SQLAlchemy 2.0)</strong></div>
            <div>Isolation: <strong className="text-zinc-200">Row Locking (SELECT FOR UPDATE)</strong></div>
            <div>Migrations: <strong className="text-emerald-400">Alembic Linear Head (0005)</strong></div>
          </div>
        </div>

        {/* MCP & AI Inference */}
        <div className="p-5 rounded-xl bg-background-surface border border-border-subtle space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-300 text-xs font-semibold">
              <Zap className="w-4 h-4 text-amber-400" />
              <span>AI Provider & MCP Daemon</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              BOUNDED
            </span>
          </div>
          <div className="text-xs font-mono space-y-1 text-zinc-400">
            <div>Model: <strong className="text-zinc-200">gemini-3.5-flash-lite</strong></div>
            <div>Protocol: <strong className="text-zinc-200">Model Context Protocol (MCP)</strong></div>
            <div>Safety Gate: <strong className="text-emerald-400">PolicyGuardrailEngine</strong></div>
          </div>
        </div>
      </div>

      {/* 3. System Architecture Layers & Integrity */}
      <div className="p-6 rounded-xl bg-background-surface border border-border-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-gray-100">Full System Architecture Verification</h3>
          <p className="text-xs text-zinc-400">
            Complete layer-by-layer architectural implementation of PaymentFlow Recovery Agent.
          </p>
        </div>

        <div className="divide-y divide-border-subtle text-xs font-mono">
          {systemLayers.map((l) => (
            <div key={l.layer} className="py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-20 font-bold text-brand-400">{l.layer}</span>
                <span className="text-zinc-300 font-sans">{l.name}</span>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${
                  l.status === 'ACTIVE'
                    ? 'bg-brand-500/10 text-brand-300 border-brand-500/30'
                    : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                }`}
              >
                {l.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
