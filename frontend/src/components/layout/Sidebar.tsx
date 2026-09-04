import React from 'react';
import {
  LayoutDashboard,
  ListChecks,
  Activity,
  Search,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Store,
  ExternalLink,
  Github,
  Radio,
  X,
} from 'lucide-react';
import { getMerchantStorefrontUrl } from '../../api/client';

export type ActivePage = 'overview' | 'live' | 'cases' | 'investigation' | 'system';

interface NavItem {
  id: 'overview' | 'live' | 'cases' | 'system';
  label: string;
  Icon: React.FC<{ className?: string }>;
  description: string;
  badge?: string;
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview',       Icon: LayoutDashboard, description: 'Recovery metrics & KPI' },
  { id: 'live',     label: 'Live Tracker',   Icon: Radio,           description: 'Active recovery queue' },
  { id: 'cases',    label: 'Cases',          Icon: ListChecks,      description: 'Pipeline state machine' },
  { id: 'system',   label: 'System & Trust', Icon: Activity,        description: 'Guardrails & architecture' },
];

interface SidebarProps {
  activePage: ActivePage;
  onNavigate: (page: ActivePage) => void;
  selectedCaseId?: string | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  selectedCaseId,
  collapsed = false,
  onToggleCollapse,
  onCloseMobile,
}) => {

  return (
    <aside
      className={`
        flex flex-col shrink-0 bg-void border-r border-white/[0.06]
        transition-all duration-200 select-none h-full
        ${collapsed ? 'w-14' : 'w-[236px]'}
      `}
    >
      {/* Product Identity Header */}
      <div className={`flex items-center justify-between px-4 py-4 border-b border-white/[0.06] ${collapsed ? 'px-2.5 justify-center' : ''}`}>
        {collapsed ? (
          <div
            className="w-8 h-8 rounded-md bg-teal-500/10 border border-teal-500/25 flex items-center justify-center cursor-pointer"
            onClick={onToggleCollapse}
            title="PaymentFlow Console (Click to expand)"
          >
            <span className="text-guard-text font-mono font-bold text-[11px]">PF</span>
          </div>
        ) : (
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-bold text-[#F0F2F5] tracking-tight leading-none">
              PaymentFlow
            </div>
            <div className="text-[10px] text-guard-text font-medium mt-1 font-sans truncate">
              AI Revenue Recovery
            </div>
          </div>
        )}

        {onCloseMobile ? (
          <button
            onClick={onCloseMobile}
            className="p-1 rounded text-[#9CA3AF] hover:text-[#F0F2F5] hover:bg-white/[0.06] transition-colors"
            title="Close navigation menu"
            aria-label="Close navigation menu"
          >
            <X className="w-4 h-4" />
          </button>
        ) : !collapsed && onToggleCollapse ? (
          <button
            onClick={onToggleCollapse}
            className="p-1 rounded text-[#4B5563] hover:text-[#9CA3AF] hover:bg-white/[0.04] transition-colors"
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        ) : null}
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto space-y-0.5" aria-label="Main navigation">
        {PRIMARY_NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id;
          const { Icon } = item;

          return (
            <React.Fragment key={item.id}>
              <button
                onClick={() => {
                  onNavigate(item.id);
                  onCloseMobile?.();
                }}
                aria-label={item.label}
                aria-current={isActive ? 'page' : undefined}
                className={`
                  w-full flex items-center gap-3 transition-colors duration-100 text-left
                  ${collapsed ? 'px-3 py-2.5 justify-center' : 'px-4 py-2.5'}
                  ${
                    isActive
                      ? 'bg-surface-raised text-[#F0F2F5] border-l-[3px] border-l-guard-base'
                      : 'text-[#6B7280] hover:text-[#9CA3AF] hover:bg-white/[0.02] border-l-[3px] border-l-transparent'
                  }
                `}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? 'text-guard-text' : 'text-[#4B5563]'
                  }`}
                />
                {!collapsed && (
                  <>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-[12px] font-medium leading-none truncate ${isActive ? 'text-[#F0F2F5] font-semibold' : ''}`}>
                          {item.label}
                        </span>
                        {item.badge && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-ai-base/20 text-ai-text border border-ai-base/30">
                            {item.badge}
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-[#4B5563] mt-0.5 leading-none truncate">
                        {item.description}
                      </div>
                    </div>
                    {isActive && <ChevronRight className="w-3.5 h-3.5 text-[#4B5563] shrink-0" />}
                  </>
                )}
              </button>

              {/* Contextual Drill-down for Case Investigation under Cases */}
              {item.id === 'cases' && activePage === 'investigation' && !collapsed && (
                <div className="ml-4 pl-4 border-l border-white/[0.08] my-1">
                  <button
                    onClick={() => {
                      onNavigate('investigation');
                      onCloseMobile?.();
                    }}
                    className="w-full flex items-center gap-2 py-1.5 px-2 rounded bg-surface-overlay/60 text-[#F0F2F5] border border-ai-border/40 text-left"
                  >
                    <Search className="w-3.5 h-3.5 text-ai-text shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-[11px] font-mono font-semibold text-ai-text block truncate">
                        {selectedCaseId ? `Investigation · ${selectedCaseId}` : 'Investigation'}
                      </span>
                      <span className="text-[9px] text-[#6B7280] block">
                        Causal decision story
                      </span>
                    </div>
                  </button>
                </div>
              )}
            </React.Fragment>
          );
        })}

        {/* External Merchant Storefront Demo Link */}
        <div className="pt-2 mt-2 border-t border-white/[0.04]">
          <a
            href={getMerchantStorefrontUrl()}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => onCloseMobile?.()}
            title="Open External Merchant Storefront (New Tab)"
            className={`
              w-full flex items-center gap-3 transition-colors duration-100 text-[#6B7280] hover:text-guard-text hover:bg-white/[0.02] border-l-[3px] border-l-transparent
              ${collapsed ? 'px-3 py-2.5 justify-center' : 'px-4 py-2.5'}
            `}
          >
            <Store className="w-4 h-4 shrink-0 text-[#4B5563]" />
            {!collapsed && (
              <>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[12px] font-medium leading-none truncate">
                      Merchant Demo
                    </span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-teal-500/10 text-guard-text border border-teal-500/20">
                      LIVE
                    </span>
                  </div>
                  <div className="text-[10px] text-[#4B5563] mt-0.5 leading-none truncate">
                    External customer checkout
                  </div>
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-[#4B5563] shrink-0" />
              </>
            )}
          </a>
        </div>
      </nav>

      {/* Footer: Engineer Attribution & GitHub Profile */}
      <div
        className={`border-t border-white/[0.06] py-3 ${
          collapsed
            ? 'px-2.5 flex flex-col items-center gap-2'
            : 'px-4 flex items-center justify-between'
        }`}
      >
        {collapsed ? (
          <>
            <a
              href="https://github.com/ParminderSinghGithub"
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded text-[#6B7280] hover:text-[#F0F2F5] hover:bg-white/[0.04] transition-colors"
              title="Engineered by Parminder Singh (GitHub Profile)"
              aria-label="Parminder Singh GitHub Profile"
            >
              <Github className="w-4 h-4" />
            </a>
            {onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                className="p-1 rounded text-[#4B5563] hover:text-[#9CA3AF] transition-colors mt-0.5"
                title="Expand sidebar"
                aria-label="Expand sidebar"
              >
                <PanelLeftOpen className="w-3.5 h-3.5" />
              </button>
            )}
          </>
        ) : (
          <>
            <div className="min-w-0 pr-2">
              <span className="text-[10px] text-[#6B7280] block font-sans leading-tight">
                Engineered by
              </span>
              <span className="text-[12px] font-semibold text-[#E5E7EB] block font-sans leading-snug truncate">
                Parminder Singh
              </span>
            </div>
            <a
              href="https://github.com/ParminderSinghGithub"
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded text-[#6B7280] hover:text-[#F0F2F5] hover:bg-white/[0.06] transition-colors shrink-0"
              title="Visit Parminder Singh's GitHub Profile"
              aria-label="Parminder Singh GitHub Profile"
            >
              <Github className="w-4 h-4" />
            </a>
          </>
        )}
      </div>
    </aside>
  );
};
