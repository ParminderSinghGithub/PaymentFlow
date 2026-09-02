import React from 'react';
import { RefreshCw, Wifi, WifiOff } from 'lucide-react';
import type { HealthResponse } from '../../types';

interface HeaderProps {
  title: string;
  subtitle?: string;
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  health,
  healthLoading,
  onRefresh,
  isRefreshing,
}) => {
  const isHealthy = health?.status === 'ok';
  const isOffline = !health;

  return (
    <header className="flex items-center justify-between px-6 py-2.5 border-b border-white/[0.06] bg-void shrink-0 z-20 select-none">
      {/* Left: Breadcrumb / Active Context Indicator */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-mono text-[#6B7280]">
          PaymentFlow
        </span>
        <span className="text-[#374151] text-xs">/</span>
        <span className="text-[12px] font-mono font-semibold text-[#D1D5DB]">
          {title}
        </span>
      </div>

      {/* Right: Operational Telemetry & Sync Controls */}
      <div className="flex items-center gap-3">
        {/* Backend & DB status */}
        <div className="flex items-center gap-2 text-[10px] font-mono">
          {healthLoading ? (
            <span className="text-[#4B5563]">Probing…</span>
          ) : isOffline ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400">
              <WifiOff className="w-3 h-3" />
              <span>Backend Offline</span>
            </div>
          ) : isHealthy ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Wifi className="w-3 h-3" />
              <span>{health.environment.toUpperCase()} · PG OK</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <Wifi className="w-3 h-3" />
              <span>{health.environment.toUpperCase()} · DEGRADED</span>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="w-px h-3.5 bg-white/[0.08]" />

        {/* Global Sync Refresh */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh application state"
          className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] hover:border-white/[0.14] rounded transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin text-guard-text' : ''}`} />
          <span>{isRefreshing ? 'Syncing…' : 'Sync'}</span>
        </button>
      </div>
    </header>
  );
};
