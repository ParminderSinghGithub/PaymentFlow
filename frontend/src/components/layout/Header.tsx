import React from 'react';
import { RefreshCw, Activity, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { HealthResponse } from '../../types';

interface HeaderProps {
  title: string;
  subtitle?: string;
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  health,
  healthLoading,
  onRefresh,
  isRefreshing = false,
}) => {
  const isHealthy = health?.status === 'ok' && health?.database === 'connected';

  return (
    <header className="h-16 border-b border-border bg-background/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      <div>
        <h2 className="text-base font-bold text-gray-100 tracking-tight">{title}</h2>
        {subtitle && <p className="text-xs text-zinc-400 font-mono mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Health status pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-background-surface border border-border text-xs">
          {healthLoading ? (
            <Activity className="w-3.5 h-3.5 text-zinc-400 animate-spin" />
          ) : isHealthy ? (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-live-dot" />
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-300 font-medium">System Healthy</span>
              <span className="text-zinc-500 font-mono text-[10px]">({health?.environment})</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-amber-300 font-medium">Degraded Mode</span>
            </div>
          )}
        </div>

        {/* Global manual refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh operational data"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-background-surface border border-border hover:bg-background-elevated hover:text-gray-100 text-zinc-300 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-brand-400' : 'text-zinc-400'}`} />
          <span>Sync</span>
        </button>
      </div>
    </header>
  );
};
