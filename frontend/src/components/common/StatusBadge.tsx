import React from 'react';
import {
  CheckCircle2,
  Clock,
  ExternalLink,
  ShieldCheck,
  Search,
  AlertCircle,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import type { CaseState } from '../../types';

interface StatusBadgeProps {
  state: CaseState | string;
  className?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, className = '', size = 'md' }) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  switch (state) {
    case 'RECOVERED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 ${sizeClasses} ${className}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>RECOVERED</span>
        </span>
      );
    case 'ACTION_EXECUTED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/30 ${sizeClasses} ${className}`}
        >
          <ExternalLink className="w-3.5 h-3.5" />
          <span>LINK EXECUTED</span>
        </span>
      );
    case 'ACTION_APPROVED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/30 ${sizeClasses} ${className}`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>ACTION APPROVED</span>
        </span>
      );
    case 'ELIGIBILITY_CHECKED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 ${sizeClasses} ${className}`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>ELIGIBILITY CHECKED</span>
        </span>
      );
    case 'CONTEXT_RETRIEVED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 ${sizeClasses} ${className}`}
        >
          <Search className="w-3.5 h-3.5" />
          <span>CONTEXT ENRICHED</span>
        </span>
      );
    case 'FAILED_INGESTED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 ${sizeClasses} ${className}`}
        >
          <AlertCircle className="w-3.5 h-3.5" />
          <span>FAILED INGESTED</span>
        </span>
      );
    case 'ESCALATED':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 ${sizeClasses} ${className}`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>ESCALATED</span>
        </span>
      );
    case 'TERMINAL_NO_ACTION':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-zinc-500/10 text-zinc-400 border border-zinc-500/30 ${sizeClasses} ${className}`}
        >
          <XCircle className="w-3.5 h-3.5" />
          <span>TERMINAL NO ACTION</span>
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700 ${sizeClasses} ${className}`}
        >
          <span>{state || 'UNKNOWN'}</span>
        </span>
      );
  }
};
