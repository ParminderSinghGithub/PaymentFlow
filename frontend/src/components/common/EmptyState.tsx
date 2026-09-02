import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Inbox } from 'lucide-react';
import { ActionButton } from './ActionButton';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
  compact?: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Inbox,
  actionText,
  onAction,
  compact = false,
}) => (
  <div className={`flex flex-col items-center justify-center text-center select-none ${compact ? 'py-10 px-4' : 'py-16 px-8'}`}>
    <div className="w-10 h-10 rounded-lg bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
      <Icon className="w-5 h-5 text-[#4B5563]" aria-hidden="true" />
    </div>
    <h4 className="text-[13px] font-semibold text-[#9CA3AF] mb-1">{title}</h4>
    <p className="text-[11px] text-[#4B5563] max-w-sm leading-relaxed">{description}</p>
    {actionText && onAction && (
      <div className="mt-4">
        <ActionButton
          label={actionText}
          onClick={onAction}
          variant="secondary"
          size="sm"
        />
      </div>
    )}
  </div>
);
