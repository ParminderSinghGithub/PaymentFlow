import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title = 'Failed to load data',
  message,
  onRetry,
}) => (
  <div className="flex items-start gap-4 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 my-4 animate-fade-in">
    <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
    <div className="flex-1">
      <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
      <p className="text-xs text-rose-300/80 mt-0.5 font-mono">{message}</p>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 transition-colors shrink-0"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Retry</span>
      </button>
    )}
  </div>
);
