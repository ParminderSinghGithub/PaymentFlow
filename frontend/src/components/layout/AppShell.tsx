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
  selectedCaseId,
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
      {/* Persistent Sidebar */}
      <div className="hidden md:flex">
        <Sidebar
          activePage={activePage}
          onNavigate={onNavigate}
          selectedCaseId={selectedCaseId}
          healthStatus={health?.status}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
        />
      </div>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden bg-void">
        {/* Global Operational Header */}
        <Header
          title={pageTitle}
          subtitle={pageSubtitle}
          health={health}
          healthLoading={healthLoading}
          onRefresh={onRefresh}
          isRefreshing={isRefreshing}
        />

        {/* Scrollable Main Content with responsive padding and maximum width */}
        <main
          className="flex-1 overflow-y-auto animate-fade-in"
          key={activePage}
        >
          <div className="max-w-[1440px] mx-auto w-full p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export type { ActivePage };
