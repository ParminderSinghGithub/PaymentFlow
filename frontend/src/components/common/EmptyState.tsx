import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Inbox,
  actionText,
  onAction,
}) => (
  <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
    <div className="w-12 h-12 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-4">
      <Icon className="w-6 h-6 text-[#4B5563]" />
    </div>
    <h3 className="text-[14px] font-semibold text-[#9CA3AF] mb-1">{title}</h3>
    <p className="text-[12px] text-[#4B5563] max-w-xs leading-relaxed">{description}</p>
    {actionText && onAction && (
      <button
        onClick={onAction}
        className="mt-6 px-4 py-2 text-[12px] font-medium text-[#9CA3AF] hover:text-[#F0F2F5] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] hover:border-white/[0.14] rounded-md transition-colors"
      >
        {actionText}
      </button>
    )}
  </div>
);
