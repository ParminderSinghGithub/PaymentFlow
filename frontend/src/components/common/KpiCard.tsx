import React from 'react';
import type { ReactNode } from 'react';

interface KpiCardProps {
  label: string;
  value: ReactNode;
  subValue?: ReactNode;
  footer?: ReactNode;
  accent?: 'recover' | 'guard' | 'ai' | 'risk' | 'halt' | 'none';
  icon?: ReactNode;
}

const ACCENT_CLASSES: Record<string, string> = {
  recover: 'accent-recover',
  guard:   'accent-guard',
  ai:      'accent-ai',
  risk:    'accent-risk',
  halt:    'accent-halt',
  none:    '',
};

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  subValue,
  footer,
  accent = 'none',
  icon,
}) => {
  const accentClass = ACCENT_CLASSES[accent] ?? '';

  return (
    <div
      className={`
        relative flex flex-col justify-between
        bg-surface-base border border-white/[0.06] rounded-lg
        p-5 gap-3
        hover:border-white/[0.12] transition-colors duration-150
        ${accentClass}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-medium uppercase tracking-widest text-[#6B7280] font-sans leading-none">
          {label}
        </span>
        {icon && (
          <span className="text-[#4B5563] shrink-0">
            {icon}
          </span>
        )}
      </div>

      {/* Primary Value */}
      <div>
        <div className="font-mono font-semibold text-[22px] leading-none text-[#F0F2F5] tracking-tight">
          {value}
        </div>
        {subValue && (
          <div className="mt-1.5 text-[11px] text-[#6B7280] font-sans">
            {subValue}
          </div>
        )}
      </div>

      {/* Footer */}
      {footer && (
        <div className="pt-3 border-t border-white/[0.06] text-[11px] text-[#4B5563] font-sans">
          {footer}
        </div>
      )}
    </div>
  );
};

/** Loading skeleton for KPI card */
export const KpiCardSkeleton: React.FC = () => (
  <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 flex flex-col gap-3">
    <div className="skeleton-shimmer h-3 w-24 rounded" />
    <div className="skeleton-shimmer h-7 w-36 rounded" />
    <div className="skeleton-shimmer h-2.5 w-32 rounded" />
    <div className="pt-3 border-t border-white/[0.06]">
      <div className="skeleton-shimmer h-2.5 w-28 rounded" />
    </div>
  </div>
);
