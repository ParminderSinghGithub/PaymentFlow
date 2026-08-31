import React from 'react';
import { clsx } from 'clsx';

interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className }) => (
  <div className={clsx('skeleton-shimmer rounded', className)} />
);

interface TableRowSkeletonProps {
  columns?: number;
}

export const TableRowSkeleton: React.FC<TableRowSkeletonProps> = ({ columns = 6 }) => (
  <tr className="border-b border-white/[0.04]">
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="py-3 px-3">
        <div className="skeleton-shimmer h-3 rounded" style={{ width: `${60 + (i % 3) * 20}%` }} />
      </td>
    ))}
  </tr>
);

export const KpiCardSkeleton: React.FC = () => (
  <div className="bg-surface-base border border-white/[0.06] rounded-lg p-5 flex flex-col gap-3">
    <div className="skeleton-shimmer h-3 w-24 rounded" />
    <div className="skeleton-shimmer h-7 w-36 rounded" />
    <div className="skeleton-shimmer h-2.5 w-32 rounded" />
  </div>
);
