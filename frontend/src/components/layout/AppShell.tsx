import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import type { ActivePage } from './Sidebar';
import type { HealthResponse } from '../../types';

interface AppShellProps {
  activePage: ActivePage;
  onNavigate: (page: ActivePage) => void;
  selectedCaseId?: string | null;
  pageTitle: string;
  pageSubtitle?: string;
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefresh: () => void;
  isRefreshing: boolean;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  activePage,
  onNavigate,
  pageTitle,
  pageSubtitle,
  health,
  healthLoading,
  onRefresh,
  isRefreshing,
  children,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-void">
      {/* Sidebar — hidden on small screens */}
      <div className="hidden md:flex">
        <Sidebar
          activePage={activePage}
          onNavigate={onNavigate}
          healthStatus={health?.status}
          collapsed={sidebarCollapsed}
        />
      </div>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Collapse toggle — subtle */}
        <div className="absolute left-0 top-1/2 z-10 hidden md:block">
          <button
            onClick={() => setSidebarCollapsed((v) => !v)}
            className="w-3 h-8 bg-white/[0.04] hover:bg-white/[0.08] border-r border-y border-white/[0.06] rounded-r flex items-center justify-center transition-colors"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          />
        </div>

        <Header
          title={pageTitle}
          subtitle={pageSubtitle}
          health={health}
          healthLoading={healthLoading}
          onRefresh={onRefresh}
          isRefreshing={isRefreshing}
        />

        {/* Scrollable content */}
        <main
          className="flex-1 overflow-y-auto p-6 animate-fade-in"
          key={activePage}
        >
          {children}
        </main>
      </div>
    </div>
  );
};

export type { ActivePage };
