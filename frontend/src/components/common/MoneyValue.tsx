/**
 * MoneyValue — canonical monetary display for PaymentFlow.
 *
 * Financial data must receive stronger visual hierarchy than metadata.
 * This component ensures consistent formatting, font, and semantic color
 * for all INR amounts displayed in the application.
 *
 * Semantic variants:
 *   recovered — emerald, for verified captured/attributed revenue
 *   at-risk   — amber,   for unrecovered revenue at risk
 *   neutral   — white,   for neutral amounts (no recovery outcome yet)
 *   negative  — rose,    for failed/lost amounts
 *
 * NEVER render INR amounts inline without this component in financial contexts.
 */

import React from 'react';

export type MoneyVariant = 'recovered' | 'at-risk' | 'neutral' | 'negative';
export type MoneySize = 'sm' | 'md' | 'lg' | 'xl';

interface MoneyValueProps {
  /** Amount in INR (not paise). Pass 0 if unknown. */
  amountInr: number;
  /** Visual semantic: what does this amount represent? */
  variant?: MoneyVariant;
  /** Display size */
  size?: MoneySize;
  /** Show INR symbol prefix */
  showSymbol?: boolean;
  /** If true, show paise (2 decimal places). Default: 0 decimals for clean display. */
  showPaise?: boolean;
  className?: string;
}

const VARIANT_CLASSES: Record<MoneyVariant, string> = {
  recovered: 'text-recover-text',
  'at-risk':  'text-risk-text',
  neutral:    'text-[#F0F2F5]',
  negative:   'text-halt-text',
};

const SIZE_CLASSES: Record<MoneySize, string> = {
  sm: 'text-[12px] font-medium',
  md: 'text-[14px] font-semibold',
  lg: 'text-[18px] font-semibold',
  xl: 'text-[24px] font-bold',
};

export const MoneyValue: React.FC<MoneyValueProps> = ({
  amountInr,
  variant = 'neutral',
  size = 'md',
  showSymbol = true,
  showPaise = false,
  className = '',
}) => {
  const formatted = new Intl.NumberFormat('en-IN', {
    style: showSymbol ? 'currency' : 'decimal',
    currency: showSymbol ? 'INR' : undefined,
    maximumFractionDigits: showPaise ? 2 : 0,
    minimumFractionDigits: showPaise ? 2 : 0,
  }).format(amountInr);

  return (
    <span
      className={[
        'font-mono inline-block tabular-nums leading-none',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      ].join(' ')}
      aria-label={`${formatted} Indian Rupees`}
    >
      {formatted}
    </span>
  );
};

/** Zero-value placeholder when amount is not yet determined */
export const MoneyPending: React.FC<{ size?: MoneySize }> = ({ size = 'md' }) => (
  <span className={`font-mono text-[#4B5563] leading-none ${SIZE_CLASSES[size]}`}>
    ₹ —
  </span>
);
