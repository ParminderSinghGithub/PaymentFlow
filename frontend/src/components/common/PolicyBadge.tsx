import React from 'react';
import { Zap, Clock, AlertTriangle, ShieldAlert } from 'lucide-react';
import type { RecoveryPolicy } from '../../types';

interface PolicyBadgeProps {
  policy: RecoveryPolicy | string | null;
  className?: string;
  showIcon?: boolean;
}

export const PolicyBadge: React.FC<PolicyBadgeProps> = ({
  policy,
  className = '',
  showIcon = true,
}) => {
  if (!policy) {
    return (
      <span className={`inline-flex items-center text-xs text-zinc-500 font-mono ${className}`}>
        NONE
      </span>
    );
  }

  switch (policy) {
    case 'P_CREATE_LINK_IMMEDIATE':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 ${className}`}
        >
          {showIcon && <Zap className="w-3 h-3 text-emerald-400" />}
          <span>CREATE_LINK_IMMEDIATE</span>
        </span>
      );
    case 'P_CREATE_LINK_DELAYED':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 ${className}`}
        >
          {showIcon && <Clock className="w-3 h-3 text-blue-400" />}
          <span>CREATE_LINK_DELAYED</span>
        </span>
      );
    case 'P_ESCALATE_ONLY':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 ${className}`}
        >
          {showIcon && <AlertTriangle className="w-3 h-3 text-rose-400" />}
          <span>ESCALATE_ONLY</span>
        </span>
      );
    case 'P_NO_ACTION':
      return (
        <span
          className={`inline-flex items-center gap-1 font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-700/30 text-zinc-400 border border-zinc-700/40 ${className}`}
        >
          {showIcon && <ShieldAlert className="w-3 h-3 text-zinc-400" />}
          <span>NO_ACTION</span>
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center font-mono text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 ${className}`}
        >
          {policy}
        </span>
      );
  }
};
