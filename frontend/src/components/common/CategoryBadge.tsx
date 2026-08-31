import React from 'react';
import type { FailureCategory } from '../../types';

interface CategoryBadgeProps {
  category: FailureCategory | string | null | undefined;
}

type CategoryConfig = {
  label: string;
  textClass: string;
  bgClass: string;
  borderClass: string;
};

const CAT_CONFIG: Record<string, CategoryConfig> = {
  C1: {
    label: 'C1 · CUSTOMER',
    textClass: 'text-[#FCD34D]',
    bgClass: 'bg-[rgba(217,119,6,0.12)]',
    borderClass: 'border-[rgba(217,119,6,0.30)]',
  },
  C2: {
    label: 'C2 · GATEWAY',
    textClass: 'text-[#93C5FD]',
    bgClass: 'bg-[rgba(37,99,235,0.12)]',
    borderClass: 'border-[rgba(37,99,235,0.30)]',
  },
  C3: {
    label: 'C3 · INSTRUMENT',
    textClass: 'text-[#FDBA74]',
    bgClass: 'bg-[rgba(234,88,12,0.12)]',
    borderClass: 'border-[rgba(234,88,12,0.30)]',
  },
  C4: {
    label: 'C4 · RISK',
    textClass: 'text-[#FDA4AF]',
    bgClass: 'bg-[rgba(225,29,72,0.10)]',
    borderClass: 'border-[rgba(225,29,72,0.30)]',
  },
  C5: {
    label: 'C5 · TECHNICAL',
    textClass: 'text-[#A1A1AA]',
    bgClass: 'bg-[rgba(82,82,91,0.15)]',
    borderClass: 'border-[rgba(82,82,91,0.30)]',
  },
};

const FALLBACK: CategoryConfig = {
  label: 'UNCLASSIFIED',
  textClass: 'text-[#6B7280]',
  bgClass: 'bg-[rgba(75,85,99,0.10)]',
  borderClass: 'border-[rgba(75,85,99,0.20)]',
};

export const CategoryBadge: React.FC<CategoryBadgeProps> = ({ category }) => {
  const cfg: CategoryConfig = (category ? CAT_CONFIG[category] : undefined) ?? FALLBACK;

  return (
    <span
      className={`inline-flex items-center border rounded font-mono font-medium uppercase tracking-wide
        px-2 py-0.5 text-[10px]
        ${cfg.textClass} ${cfg.bgClass} ${cfg.borderClass}
      `}
    >
      {cfg.label}
    </span>
  );
};
