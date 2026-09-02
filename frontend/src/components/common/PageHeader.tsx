/**
 * PageHeader — standard page-level heading pattern for PaymentFlow.
 *
 * Establishes consistent page identity:
 *   - Page title (h2, large)
 *   - Supporting description
 *   - Optional right-aligned action slot
 *
 * This is NOT the global app header (Header.tsx). PageHeader lives inside
 * the scrollable main content area, at the top of each page.
 *
 * Usage note: Only include a breadcrumb when navigation context is ambiguous
 * (e.g. drill-down from Cases to Investigation).
 */

import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { ChevronRight } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  breadcrumbs?: BreadcrumbItem[];
  /** Right-aligned action buttons or controls */
  actions?: React.ReactNode;
  /** Reduce bottom margin (for pages where content immediately follows) */
  compact?: boolean;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  icon: Icon,
  breadcrumbs,
  actions,
  compact = false,
}) => {
  return (
    <div className={compact ? 'mb-5' : 'mb-7'}>
      {/* Breadcrumb trail */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav
          className="flex items-center gap-1 mb-3"
          aria-label="Breadcrumb"
        >
          {breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && (
                <ChevronRight className="w-3 h-3 text-[#374151] shrink-0" aria-hidden="true" />
              )}
              {crumb.onClick ? (
                <button
                  onClick={crumb.onClick}
                  className="text-[11px] text-[#4B5563] hover:text-[#9CA3AF] transition-colors font-mono"
                >
                  {crumb.label}
                </button>
              ) : (
                <span className="text-[11px] text-[#6B7280] font-mono">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* Title row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="w-9 h-9 rounded-lg bg-white/[0.03] border border-white/[0.07] flex items-center justify-center shrink-0">
              <Icon className="w-5 h-5 text-[#4B5563]" aria-hidden="true" />
            </div>
          )}
          <div>
            <h2 className="text-[20px] font-bold text-[#F0F2F5] leading-tight tracking-tight">
              {title}
            </h2>
            {description && (
              <p className="text-[12px] text-[#4B5563] mt-1 leading-relaxed max-w-2xl">
                {description}
              </p>
            )}
          </div>
        </div>

        {actions && (
          <div className="flex items-center gap-2 shrink-0 mt-0.5">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};
