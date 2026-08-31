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
  subtitle,
  health,
  healthLoading,
  onRefresh,
  isRefreshing,
}) => {
  const isHealthy = health?.status === 'ok';
  const isOffline = !health;

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-void shrink-0">
      {/* Title */}
      <div>
        <h1 className="text-[16px] font-bold text-[#F0F2F5] leading-tight tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-[11px] text-[#4B5563] mt-0.5 font-sans leading-none">{subtitle}</p>
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {/* Backend status */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          {healthLoading ? (
            <span className="text-[#4B5563]">Connecting…</span>
          ) : isOffline ? (
            <>
              <WifiOff className="w-3.5 h-3.5 text-halt-text" />
              <span className="text-halt-text">Offline</span>
            </>
          ) : (
            <>
              <Wifi className={`w-3.5 h-3.5 ${isHealthy ? 'text-recover-text' : 'text-risk-text'}`} />
              <span className={isHealthy ? 'text-[#4B5563]' : 'text-risk-text'}>
                {health?.environment ?? 'connected'}
              </span>
            </>
          )}
        </div>

        {/* Divider */}
        <div className="w-px h-4 bg-white/[0.08]" />

        {/* Refresh */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh data"
          className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#6B7280] hover:text-[#9CA3AF] bg-transparent hover:bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.14] rounded-md transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Syncing…' : 'Refresh'}
        </button>
      </div>
    </header>
  );
};
