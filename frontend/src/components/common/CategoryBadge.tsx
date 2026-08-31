import React from 'react';
import { CATEGORY_INFO, type FailureCategory } from '../../types';

interface CategoryBadgeProps {
  category: FailureCategory | string | null;
  className?: string;
  showFullName?: boolean;
}

export const CategoryBadge: React.FC<CategoryBadgeProps> = ({
  category,
  className = '',
  showFullName = false,
}) => {
  const catCode = (category || 'UNKNOWN') as FailureCategory;
  const meta = CATEGORY_INFO[catCode] || CATEGORY_INFO.UNKNOWN;

  return (
    <span
      title={`${meta.name}: ${meta.description}`}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold border ${meta.badgeClass} ${className}`}
    >
      <span className="font-mono">{meta.code}</span>
      {showFullName && <span className="font-normal text-zinc-300">· {meta.name}</span>}
    </span>
  );
};
