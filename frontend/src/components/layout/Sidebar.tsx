import React from 'react';
import {
  LayoutDashboard,
  Layers,
  SearchCode,
  ShieldCheck,
  Activity,
  Zap,
} from 'lucide-react';

export type ActivePage = 'overview' | 'cases' | 'investigation' | 'mcp' | 'health';

interface SidebarProps {
  activePage: ActivePage;
  onNavigate: (page: ActivePage) => void;
  selectedCaseId?: string | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  selectedCaseId,
}) => {
  const navItems: Array<{
    id: ActivePage;
    label: string;
    icon: React.ReactNode;
    badge?: string;
    sublabel?: string;
  }> = [
    {
      id: 'overview',
      label: 'Executive Overview',
      sublabel: 'KPIs & Funnel',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: 'cases',
      label: 'Cases Explorer',
      sublabel: 'Failed Payment Stream',
      icon: <Layers className="w-4 h-4" />,
    },
    {
      id: 'investigation',
      label: 'Case Investigation',
      sublabel: selectedCaseId ? `Active: ${selectedCaseId.substring(0, 10)}...` : 'Story Mode Walkthrough',
      icon: <SearchCode className="w-4 h-4" />,
      badge: selectedCaseId ? 'Active' : undefined,
    },
    {
      id: 'mcp',
      label: 'MCP & Guardrails',
      sublabel: 'Agent Boundaries',
      icon: <ShieldCheck className="w-4 h-4" />,
    },
    {
      id: 'health',
      label: 'System Health',
      sublabel: 'Operational Diagnostic',
      icon: <Activity className="w-4 h-4" />,
    },
  ];

  return (
    <aside className="w-64 bg-background-subtle border-r border-border flex flex-col justify-between h-screen shrink-0 sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-border flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-glow-brand text-background font-bold">
            <Zap className="w-5 h-5 text-gray-950 fill-current" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-sm text-gray-100 tracking-tight">PaymentFlow</h1>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20">
                v1.0
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 font-medium">Recovery Intelligence Console</p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1">
          <div className="px-3 py-2 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase font-mono">
            Navigation
          </div>
          {navItems.map((item) => {
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
                  isActive
                    ? 'bg-brand-500/10 text-brand-300 border border-brand-500/30 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-background-elevated/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`${isActive ? 'text-brand-400' : 'text-zinc-400 group-hover:text-zinc-200'}`}>
                    {item.icon}
                  </span>
                  <div className="text-left">
                    <div className="leading-none">{item.label}</div>
                    {item.sublabel && (
                      <div className="text-[10px] text-zinc-400 mt-1 font-normal font-mono truncate max-w-[120px]">
                        {item.sublabel}
                      </div>
                    )}
                  </div>
                </div>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-brand-500/20 text-brand-300 border border-brand-500/40">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Safety Invariant Footer */}
      <div className="p-4 m-3 rounded-xl bg-background-surface border border-border-subtle text-[11px] space-y-2">
        <div className="flex items-center gap-1.5 text-zinc-300 font-semibold text-xs">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Deterministic Guardrails</span>
        </div>
        <p className="text-zinc-400 text-[10px] leading-relaxed">
          AI reasoning remains advisory. Direct Razorpay writes are strictly blocked; all recovery policies are verified by <span className="text-zinc-300 font-mono">PolicyGuardrailEngine</span>.
        </p>
      </div>
    </aside>
  );
};
