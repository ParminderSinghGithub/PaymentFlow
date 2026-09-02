/**
 * ZoneCard — reusable semantic zone card for PaymentFlow.
 *
 * The two-zone visual language is the core visual identity of PaymentFlow:
 *   Violet zone  → AI Advisory (LLM recommends)
 *   Teal zone    → Guardrail Authorization (deterministic policy authorizes)
 *   Emerald zone → Verified Recovery (money captured & attributed)
 *   Neutral      → informational content without semantic zone meaning
 *
 * Structure:
 *   ZoneCard wraps content in a card with zone-appropriate border, background,
 *   and optional header with zone label + icon.
 *
 * This is the primary layout primitive for the Investigation and Interactive pages.
 */

import React from 'react';
import type { LucideIcon } from 'lucide-react';

export type ZoneVariant = 'ai' | 'guard' | 'recover' | 'risk' | 'halt' | 'neutral';

interface ZoneCardProps {
  zone: ZoneVariant;
  /** Short zone label, e.g. "AI Advisory" or "Guardrail Gate" */
  label?: string;
  icon?: LucideIcon;
  /** Supporting description under the label */
  description?: string;
  children: React.ReactNode;
  /** Additional classes on the outer wrapper */
  className?: string;
  /** Collapse internal padding */
  noPadding?: boolean;
  id?: string;
}

const ZONE_CONFIG: Record<ZoneVariant, {
  headerClass: string;
  bodyClass: string;
  borderClass: string;
  labelClass: string;
  iconClass: string;
}> = {
  ai: {
    headerClass: 'bg-[rgba(124,58,237,0.10)] border-b border-[rgba(124,58,237,0.20)]',
    bodyClass:   'bg-[rgba(124,58,237,0.05)]',
    borderClass: 'border border-[rgba(124,58,237,0.20)]',
    labelClass:  'text-ai-text',
    iconClass:   'text-ai-text',
  },
  guard: {
    headerClass: 'bg-[rgba(13,148,136,0.10)] border-b border-[rgba(13,148,136,0.20)]',
    bodyClass:   'bg-[rgba(13,148,136,0.05)]',
    borderClass: 'border border-[rgba(13,148,136,0.20)]',
    labelClass:  'text-guard-text',
    iconClass:   'text-guard-text',
  },
  recover: {
    headerClass: 'bg-[rgba(5,150,105,0.10)] border-b border-[rgba(5,150,105,0.18)]',
    bodyClass:   'bg-[rgba(5,150,105,0.04)]',
    borderClass: 'border border-[rgba(5,150,105,0.18)]',
    labelClass:  'text-recover-text',
    iconClass:   'text-recover-text',
  },
  risk: {
    headerClass: 'bg-[rgba(217,119,6,0.10)] border-b border-[rgba(217,119,6,0.20)]',
    bodyClass:   'bg-[rgba(217,119,6,0.04)]',
    borderClass: 'border border-[rgba(217,119,6,0.20)]',
    labelClass:  'text-risk-text',
    iconClass:   'text-risk-text',
  },
  halt: {
    headerClass: 'bg-[rgba(225,29,72,0.08)] border-b border-[rgba(225,29,72,0.18)]',
    bodyClass:   'bg-[rgba(225,29,72,0.04)]',
    borderClass: 'border border-[rgba(225,29,72,0.18)]',
    labelClass:  'text-halt-text',
    iconClass:   'text-halt-text',
  },
  neutral: {
    headerClass: 'bg-surface-raised border-b border-white/[0.06]',
    bodyClass:   'bg-surface-base',
    borderClass: 'border border-white/[0.08]',
    labelClass:  'text-[#9CA3AF]',
    iconClass:   'text-[#4B5563]',
  },
};

export const ZoneCard: React.FC<ZoneCardProps> = ({
  zone,
  label,
  icon: Icon,
  description,
  children,
  className = '',
  noPadding = false,
  id,
}) => {
  const cfg = ZONE_CONFIG[zone];
  const hasHeader = label || description;

  return (
    <div
      id={id}
      className={`rounded-lg overflow-hidden ${cfg.borderClass} ${className}`}
    >
      {hasHeader && (
        <div className={`flex items-start gap-2.5 px-4 py-3 ${cfg.headerClass}`}>
          {Icon && (
            <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.iconClass}`} aria-hidden="true" />
          )}
          <div className="flex-1 min-w-0">
            {label && (
              <div className={`text-[11px] font-mono font-semibold uppercase tracking-widest leading-none ${cfg.labelClass}`}>
                {label}
              </div>
            )}
            {description && (
              <div className="text-[11px] text-[#4B5563] mt-1 leading-snug">
                {description}
              </div>
            )}
          </div>
        </div>
      )}
      <div className={`${cfg.bodyClass} ${noPadding ? '' : 'p-4'}`}>
        {children}
      </div>
    </div>
  );
};

/**
 * ZoneLabel — inline zone identifier (non-card).
 * Use to label sections within a larger layout without a full card boundary.
 */
export const ZoneLabel: React.FC<{
  zone: ZoneVariant;
  children: React.ReactNode;
  icon?: LucideIcon;
}> = ({ zone, children, icon: Icon }) => {
  const cfg = ZONE_CONFIG[zone];
  return (
    <div className={`inline-flex items-center gap-1.5 ${cfg.labelClass}`}>
      {Icon && <Icon className={`w-3.5 h-3.5 shrink-0 ${cfg.iconClass}`} aria-hidden="true" />}
      <span className="text-[10px] font-mono font-semibold uppercase tracking-widest">{children}</span>
    </div>
  );
};
