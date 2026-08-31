import React from 'react';
import { Sidebar, type ActivePage } from './Sidebar';
import { Header } from './Header';
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
  isRefreshing?: boolean;
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
  return (
    <div className="flex min-h-screen bg-background text-gray-100 selection:bg-brand-500/20 selection:text-brand-300">
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        selectedCaseId={selectedCaseId}
      />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Header
          title={pageTitle}
          subtitle={pageSubtitle}
          health={health}
          healthLoading={healthLoading}
          onRefresh={onRefresh}
          isRefreshing={isRefreshing}
        />
        <main className="p-6 max-w-7xl w-full mx-auto space-y-6 animate-fade-in">
          {children}
        </main>
      </div>
    </div>
  );
};
