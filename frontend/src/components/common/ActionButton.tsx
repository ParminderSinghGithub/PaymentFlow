/**
 * ActionButton — typed action hierarchy for PaymentFlow operations console.
 *
 * Variants:
 *   primary     — principal call-to-action (Launch recovery, Verify payment)
 *   secondary   — supporting actions (Inspect, View audit, Refresh)
 *   ghost       — low-emphasis tertiary (Back, Cancel)
 *   destructive — exceptional / irreversible (Reset interactive case)
 *
 * Sizes:
 *   sm — compact, for use inside cards and table rows
 *   md — default toolbar/page action
 *   lg — hero-level action (e.g., primary CTA on interactive page)
 */

import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Loader2 } from 'lucide-react';

export type ActionVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
export type ActionSize = 'sm' | 'md' | 'lg';

interface ActionButtonProps {
  label: string;
  onClick?: () => void;
  variant?: ActionVariant;
  size?: ActionSize;
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  loading?: boolean;
  disabled?: boolean;
  type?: 'button' | 'submit';
  className?: string;
  'aria-label'?: string;
  id?: string;
}

const VARIANT_CLASSES: Record<ActionVariant, string> = {
  primary:
    'bg-guard-base hover:bg-[#0f9e91] active:bg-[#0b7a72] text-white border border-transparent ' +
    'shadow-[0_1px_3px_rgba(0,0,0,0.4)] hover:shadow-guard',
  secondary:
    'bg-transparent text-[#9CA3AF] hover:text-[#F0F2F5] ' +
    'border border-white/[0.10] hover:border-white/[0.18] hover:bg-white/[0.04]',
  ghost:
    'bg-transparent text-[#4B5563] hover:text-[#9CA3AF] border border-transparent hover:border-white/[0.06]',
  destructive:
    'bg-transparent text-halt-text hover:text-[#FDA4AF] ' +
    'border border-halt-border hover:border-[rgba(225,29,72,0.40)] hover:bg-halt-muted',
};

const SIZE_CLASSES: Record<ActionSize, string> = {
  sm: 'h-7 px-3 text-[11px] gap-1.5 rounded',
  md: 'h-8 px-4 text-[12px] gap-2 rounded-md',
  lg: 'h-10 px-5 text-[13px] gap-2.5 rounded-md',
};

const ICON_SIZE: Record<ActionSize, string> = {
  sm: 'w-3 h-3',
  md: 'w-3.5 h-3.5',
  lg: 'w-4 h-4',
};

export const ActionButton: React.FC<ActionButtonProps> = ({
  label,
  onClick,
  variant = 'secondary',
  size = 'md',
  icon: Icon,
  iconRight: IconRight,
  loading = false,
  disabled = false,
  type = 'button',
  className = '',
  'aria-label': ariaLabel,
  id,
}) => {
  const isDisabled = disabled || loading;

  return (
    <button
      id={id}
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      aria-label={ariaLabel ?? label}
      aria-busy={loading ? 'true' : undefined}
      className={[
        'inline-flex items-center justify-center font-medium',
        'transition-all duration-100 cursor-pointer',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      ].join(' ')}
    >
      {loading ? (
        <Loader2 className={`${ICON_SIZE[size]} animate-spin shrink-0`} />
      ) : (
        Icon && <Icon className={`${ICON_SIZE[size]} shrink-0`} aria-hidden="true" />
      )}
      {label}
      {!loading && IconRight && (
        <IconRight className={`${ICON_SIZE[size]} shrink-0`} aria-hidden="true" />
      )}
    </button>
  );
};
