import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionText,
  onAction,
  icon = <Inbox className="w-10 h-10 text-zinc-500" />,
}) => (
  <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl border border-dashed border-border bg-background-subtle/50 my-4">
    <div className="p-3 rounded-full bg-background-elevated mb-3">{icon}</div>
    <h3 className="text-base font-semibold text-zinc-200">{title}</h3>
    <p className="text-sm text-zinc-400 max-w-sm mt-1 mb-4">{description}</p>
    {actionText && onAction && (
      <button
        onClick={onAction}
        className="px-4 py-2 text-xs font-semibold rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/30 hover:bg-brand-500/20 transition-colors"
      >
        {actionText}
      </button>
    )}
  </div>
);
