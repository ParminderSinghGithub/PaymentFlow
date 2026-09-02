import React from 'react';
import {
  LayoutDashboard,
  ListChecks,
  Search,
  Sparkles,
  Activity,
  ChevronRight,
} from 'lucide-react';

export type ActivePage = 'overview' | 'cases' | 'investigation' | 'interactive' | 'system';

interface NavItem {
  id: ActivePage;
  label: string;
  Icon: React.FC<{ className?: string }>;
  description: string;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview',      label: 'Overview',       Icon: LayoutDashboard, description: 'Recovery performance' },
  { id: 'cases',         label: 'Cases',           Icon: ListChecks,      description: 'Pipeline explorer' },
  { id: 'investigation', label: 'Investigation',   Icon: Search,          description: 'Decision story' },
  { id: 'interactive',   label: 'Interactive Demo',Icon: Sparkles,        description: 'Live CS01 recovery', badge: 'DEMO' },
  { id: 'system',        label: 'System & Trust',  Icon: Activity,        description: 'Architecture & health' },
];

interface SidebarProps {
  activePage: ActivePage;
  onNavigate: (page: ActivePage) => void;
  healthStatus?: 'ok' | 'degraded' | 'offline' | string | null;
  collapsed?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  healthStatus,
  collapsed = false,
}) => {
  const healthDot =
    healthStatus === 'ok'
      ? 'bg-recover-base'
      : healthStatus === 'degraded'
      ? 'bg-risk-base'
      : 'bg-halt-base';

  return (
    <aside
      className={`
        flex flex-col shrink-0 bg-void border-r border-white/[0.06]
        transition-all duration-200
        ${collapsed ? 'w-14' : 'w-[230px]'}
      `}
    >
      {/* Wordmark */}
      <div className={`px-4 py-5 border-b border-white/[0.06] ${collapsed ? 'px-3' : ''}`}>
        {collapsed ? (
          <div className="w-8 h-8 rounded-lg bg-[rgba(13,148,136,0.15)] border border-[rgba(13,148,136,0.25)] flex items-center justify-center">
            <span className="text-guard-text font-mono font-bold text-[10px]">PF</span>
          </div>
        ) : (
          <div>
            <div className="text-[15px] font-bold text-[#F0F2F5] tracking-tight leading-none">
              PaymentFlow
            </div>
            <div className="text-[10px] text-[#4B5563] mt-0.5 font-sans">
              AI Revenue Recovery Agent
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id;
          const { Icon } = item;

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
              className={`
                w-full flex items-center gap-3 transition-colors duration-100
                ${collapsed ? 'px-3 py-2.5 justify-center' : 'px-4 py-2.5'}
                ${
                  isActive
                    ? 'bg-surface-raised text-[#F0F2F5] border-l-[2px] border-l-ai-base'
                    : 'text-[#6B7280] hover:text-[#9CA3AF] hover:bg-white/[0.02] border-l-[2px] border-l-transparent'
                }
              `}
            >
              <Icon
                className={`w-4 h-4 shrink-0 transition-colors ${
                  isActive ? 'text-[#F0F2F5]' : 'text-[#4B5563]'
                }`}
              />
              {!collapsed && (
                <>
                  <div className="flex-1 text-left">
                    <div className="flex items-center gap-1.5">
                      <span className={`text-[13px] font-medium leading-none ${isActive ? 'text-[#F0F2F5]' : ''}`}>
                        {item.label}
                      </span>
                      {item.badge && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-ai-base/20 text-ai-text border border-ai-base/30">
                          {item.badge}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-[#4B5563] mt-0.5 leading-none">
                      {item.description}
                    </div>
                  </div>
                  {isActive && <ChevronRight className="w-3 h-3 text-[#4B5563] shrink-0" />}
                </>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom: Health Indicator */}
      <div className={`border-t border-white/[0.06] py-3 ${collapsed ? 'px-3' : 'px-4'}`}>
        {collapsed ? (
          <div
            className={`w-2 h-2 rounded-full mx-auto ${healthDot}`}
            title={`System ${healthStatus ?? 'unknown'}`}
          />
        ) : (
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full shrink-0 ${healthDot}`} />
            <span className="text-[10px] text-[#4B5563] font-mono">
              {healthStatus === 'ok' ? 'System operational' :
               healthStatus === 'degraded' ? 'System degraded' : 'Offline'}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
};
