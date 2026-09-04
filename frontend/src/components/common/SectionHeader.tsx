/**
 * SectionHeader — standard section-level heading pattern for PaymentFlow.
 * 
 * Provides consistent typography, subtitle/counter badges, and optional trailing actions
 * within cards, tables, and page subsections.
 */

import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  badge?: string | number;
  icon?: LucideIcon;
  action?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  badge,
  icon: Icon,
  action,
  className = '',
}) => {
  return (
    <div className={`flex items-start justify-between gap-3 mb-3 ${className}`}>
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex items-center gap-2 flex-wrap">
          {Icon && <Icon className="w-4 h-4 text-[#6B7280] shrink-0" aria-hidden="true" />}
          <h3 className="text-[13px] font-semibold text-[#F0F2F5] tracking-tight">
            {title}
          </h3>
          {badge !== undefined && (
            <span className="px-1.5 py-0.5 text-[10px] font-mono font-medium rounded bg-white/[0.06] text-[#9CA3AF] border border-white/[0.08]">
              {badge}
            </span>
          )}
        </div>
        {subtitle && (
          <p className="text-[11px] text-[#6B7280] leading-normal">
            {subtitle}
          </p>
        )}
      </div>
      {action && <div className="shrink-0 flex items-center gap-2">{action}</div>}
    </div>
  );
};
