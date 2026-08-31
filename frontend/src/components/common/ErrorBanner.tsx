import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBannerProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({ title, message, onRetry }) => (
  <div className="flex items-start gap-4 p-5 bg-[rgba(225,29,72,0.06)] border border-[rgba(225,29,72,0.20)] rounded-lg">
    <AlertCircle className="w-5 h-5 text-halt-text shrink-0 mt-0.5" />
    <div className="flex-1">
      <div className="text-[13px] font-semibold text-halt-text">{title}</div>
      <div className="text-[12px] text-[#9CA3AF] mt-0.5">{message}</div>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] rounded transition-colors shrink-0"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Retry
      </button>
    )}
  </div>
);
