import React from 'react';
import type { CaseState } from '../../types';

interface StateBadgeProps {
  state: CaseState | string | null | undefined;
  size?: 'sm' | 'md';
}

type StateConfig = {
  label: string;
  dotClass: string;
  textClass: string;
  bgClass: string;
  borderClass: string;
  pulse?: boolean;
};

const STATE_CONFIG: Record<string, StateConfig> = {
  FAILED_INGESTED: {
    label: 'INGESTED',
    dotClass: 'bg-risk-base',
    textClass: 'text-risk-text',
    bgClass: 'bg-[rgba(217,119,6,0.10)]',
    borderClass: 'border-[rgba(217,119,6,0.25)]',
    pulse: true,
  },
  CONTEXT_RETRIEVED: {
    label: 'CONTEXT',
    dotClass: 'bg-[#4B5563]',
    textClass: 'text-[#9CA3AF]',
    bgClass: 'bg-[rgba(75,85,99,0.12)]',
    borderClass: 'border-[rgba(75,85,99,0.25)]',
  },
  ELIGIBILITY_CHECKED: {
    label: 'ELIGIBLE',
    dotClass: 'bg-guard-base',
    textClass: 'text-guard-text',
    bgClass: 'bg-[rgba(13,148,136,0.10)]',
    borderClass: 'border-[rgba(13,148,136,0.25)]',
  },
  AI_TRIAGE_COMPLETE: {
    label: 'AI ADVISED',
    dotClass: 'bg-ai-base',
    textClass: 'text-ai-text',
    bgClass: 'bg-[rgba(124,58,237,0.10)]',
    borderClass: 'border-[rgba(124,58,237,0.25)]',
  },
  AI_TRIAGED: {
    label: 'AI ADVISED',
    dotClass: 'bg-ai-base',
    textClass: 'text-ai-text',
    bgClass: 'bg-[rgba(124,58,237,0.10)]',
    borderClass: 'border-[rgba(124,58,237,0.25)]',
  },
  POLICY_VALIDATED: {
    label: 'VALIDATED',
    dotClass: 'bg-guard-base',
    textClass: 'text-guard-text',
    bgClass: 'bg-[rgba(13,148,136,0.10)]',
    borderClass: 'border-[rgba(13,148,136,0.25)]',
  },
  ACTION_APPROVED: {
    label: 'APPROVED',
    dotClass: 'bg-guard-base',
    textClass: 'text-guard-text',
    bgClass: 'bg-[rgba(13,148,136,0.10)]',
    borderClass: 'border-[rgba(13,148,136,0.25)]',
  },
  ACTION_EXECUTED: {
    label: 'LINK SENT',
    dotClass: 'bg-guard-base',
    textClass: 'text-guard-text',
    bgClass: 'bg-[rgba(13,148,136,0.10)]',
    borderClass: 'border-[rgba(13,148,136,0.25)]',
  },
  RECOVERED: {
    label: 'RECOVERED',
    dotClass: 'bg-recover-base',
    textClass: 'text-recover-text',
    bgClass: 'bg-[rgba(5,150,105,0.10)]',
    borderClass: 'border-[rgba(5,150,105,0.25)]',
  },
  ESCALATED: {
    label: 'ESCALATED',
    dotClass: 'bg-risk-base',
    textClass: 'text-risk-text',
    bgClass: 'bg-[rgba(217,119,6,0.10)]',
    borderClass: 'border-[rgba(217,119,6,0.25)]',
  },
  TERMINAL_NO_ACTION: {
    label: 'NO ACTION',
    dotClass: 'bg-halt-base',
    textClass: 'text-halt-text',
    bgClass: 'bg-[rgba(225,29,72,0.08)]',
    borderClass: 'border-[rgba(225,29,72,0.25)]',
  },
  ERROR: {
    label: 'ERROR',
    dotClass: 'bg-halt-base',
    textClass: 'text-halt-text',
    bgClass: 'bg-[rgba(225,29,72,0.08)]',
    borderClass: 'border-[rgba(225,29,72,0.25)]',
  },
};

const FALLBACK_CONFIG: StateConfig = {
  label: 'UNKNOWN',
  dotClass: 'bg-[#4B5563]',
  textClass: 'text-[#6B7280]',
  bgClass: 'bg-[rgba(75,85,99,0.10)]',
  borderClass: 'border-[rgba(75,85,99,0.20)]',
};

export const StateBadge: React.FC<StateBadgeProps> = ({ state, size = 'md' }) => {
  const cfg: StateConfig = (state ? STATE_CONFIG[state] : undefined) ?? FALLBACK_CONFIG;
  const label = cfg.label;

  return (
    <span
      className={`inline-flex items-center gap-1.5 border rounded font-mono font-medium uppercase tracking-wide
        ${cfg.bgClass} ${cfg.borderClass} ${cfg.textClass}
        ${size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-[11px]'}
      `}
    >
      <span
        className={`shrink-0 rounded-full ${cfg.dotClass} ${
          cfg.pulse ? 'animate-live-pulse' : ''
        } ${size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'}`}
      />
      {label}
    </span>
  );
};
