import React from 'react';
import { Bot, ShieldCheck } from 'lucide-react';

interface PolicyBadgeProps {
  policy: string | null | undefined;
  /** 'ai' = violet zone, 'guard' = teal zone, 'auto' = plain neutral */
  context?: 'ai' | 'guard' | 'auto';
  showIcon?: boolean;
}

const POLICY_LABELS: Record<string, string> = {
  P_CREATE_LINK_IMMEDIATE: 'LINK · IMMEDIATE',
  P_CREATE_LINK_DELAYED:   'LINK · DELAYED',
  P_ESCALATE_ONLY:         'ESCALATE ONLY',
  P_NO_ACTION:             'NO ACTION',
};

export const PolicyBadge: React.FC<PolicyBadgeProps> = ({
  policy,
  context = 'auto',
  showIcon = true,
}) => {
  if (!policy) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono text-[#4B5563] bg-[rgba(75,85,99,0.08)] border border-[rgba(75,85,99,0.20)] rounded">
        —
      </span>
    );
  }

  const label = POLICY_LABELS[policy] ?? policy;

  if (context === 'ai') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-medium text-ai-text bg-[rgba(124,58,237,0.12)] border border-[rgba(124,58,237,0.30)] rounded">
        {showIcon && <Bot className="w-2.5 h-2.5 shrink-0" />}
        {label}
      </span>
    );
  }

  if (context === 'guard') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-medium text-guard-text bg-[rgba(13,148,136,0.12)] border border-[rgba(13,148,136,0.30)] rounded">
        {showIcon && <ShieldCheck className="w-2.5 h-2.5 shrink-0" />}
        {label}
      </span>
    );
  }

  // 'auto' — neutral
  return (
    <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-medium text-[#9CA3AF] bg-[rgba(75,85,99,0.12)] border border-[rgba(75,85,99,0.20)] rounded">
      {label}
    </span>
  );
};
