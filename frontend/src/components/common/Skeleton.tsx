import React from 'react';

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-background-elevated/70 rounded ${className}`} />
);

export const KpiCardSkeleton: React.FC = () => (
  <div className="p-5 rounded-xl bg-background-surface border border-border-subtle flex flex-col gap-3">
    <Skeleton className="h-4 w-28" />
    <Skeleton className="h-8 w-36" />
    <Skeleton className="h-3 w-48" />
  </div>
);

export const TableRowSkeleton: React.FC<{ columns?: number }> = ({ columns = 6 }) => (
  <tr className="border-b border-border-subtle">
    {Array.from({ length: columns }).map((_, idx) => (
      <td key={idx} className="p-4">
        <Skeleton className="h-4 w-full" />
      </td>
    ))}
  </tr>
);
