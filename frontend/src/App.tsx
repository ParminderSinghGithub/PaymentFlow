import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from './components/layout/AppShell';
import { type ActivePage } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { CasesPage } from './pages/CasesPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { McpArchitecturePage } from './pages/McpArchitecturePage';
import { SystemHealthPage } from './pages/SystemHealthPage';
import { ToastProvider, useToast } from './components/common/Toast';
import {
  fetchCases,
  fetchCaseDetail,
  fetchHealth,
  fetchMetricsSummary,
  processDueDelayedCases,
  triggerCaseTriage,
  ApiError,
} from './api/client';
import type {
  CaseDetailResponse,
  CaseSummaryItem,
  HealthResponse,
  MetricsSummary,
} from './types';

const AppContent: React.FC = () => {
  const { showToast } = useToast();

  // Navigation State
  const [activePage, setActivePage] = useState<ActivePage>('overview');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  // Data States
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  const [cases, setCases] = useState<CaseSummaryItem[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);

  const [caseDetail, setCaseDetail] = useState<CaseDetailResponse | null>(null);
  const [caseDetailLoading, setCaseDetailLoading] = useState(false);
  const [caseDetailError, setCaseDetailError] = useState<string | null>(null);

  // Action / Mutation States
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [triageLoadingCaseId, setTriageLoadingCaseId] = useState<string | null>(null);
  const [delayedProcessing, setDelayedProcessing] = useState(false);

  // URL Hash Sync for bookmarkable navigation
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      if (hash.startsWith('investigation')) {
        const params = new URLSearchParams(hash.split('?')[1]);
        const id = params.get('id');
        setActivePage('investigation');
        if (id) setSelectedCaseId(id);
      } else if (['overview', 'cases', 'mcp', 'health'].includes(hash)) {
        setActivePage(hash as ActivePage);
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = useCallback((page: ActivePage, caseId?: string | null) => {
    setActivePage(page);
    if (caseId !== undefined) {
      setSelectedCaseId(caseId);
    }
    if (page === 'investigation' && (caseId || selectedCaseId)) {
      const id = caseId || selectedCaseId;
      window.location.hash = `investigation?id=${encodeURIComponent(id!)}`;
    } else {
      window.location.hash = page;
    }
  }, [selectedCaseId]);

  // Load Health
  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch {
      setHealth({
        status: 'degraded',
        environment: 'offline',
        database: 'disconnected',
        version: '0.1.0',
      });
    } finally {
      setHealthLoading(false);
    }
  }, []);

  // Load Metrics
  const loadMetrics = useCallback(async () => {
    setMetricsLoading(true);
    try {
      const data = await fetchMetricsSummary();
      setMetrics(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to fetch metrics';
      showToast('error', 'Metrics Sync Error', msg);
    } finally {
      setMetricsLoading(false);
    }
  }, [showToast]);

  // Load Cases
  const loadCases = useCallback(async () => {
    setCasesLoading(true);
    try {
      const data = await fetchCases({ limit: 100 });
      setCases(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to fetch cases';
      showToast('error', 'Cases Sync Error', msg);
    } finally {
      setCasesLoading(false);
    }
  }, [showToast]);

  // Load Case Detail
  const loadCaseDetail = useCallback(async (id: string) => {
    setCaseDetailLoading(true);
    setCaseDetailError(null);
    try {
      const data = await fetchCaseDetail(id);
      setCaseDetail(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to load case detail';
      setCaseDetailError(msg);
      showToast('error', 'Case Detail Error', msg);
    } finally {
      setCaseDetailLoading(false);
    }
  }, [showToast]);

  // Fetch when selected case changes
  useEffect(() => {
    if (selectedCaseId && activePage === 'investigation') {
      loadCaseDetail(selectedCaseId);
    }
  }, [selectedCaseId, activePage, loadCaseDetail]);

  // Initial Data Load
  useEffect(() => {
    loadHealth();
    loadMetrics();
    loadCases();
  }, [loadHealth, loadMetrics, loadCases]);

  // Global Refresh Handler
  const handleGlobalRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      loadHealth(),
      loadMetrics(),
      loadCases(),
      selectedCaseId && activePage === 'investigation' ? loadCaseDetail(selectedCaseId) : Promise.resolve(),
    ]);
    setIsRefreshing(false);
    showToast('success', 'Data Synchronized', 'Latest operational states refreshed from backend.');
  };

  // Trigger Triage Mutation
  const handleTriggerTriage = async (caseId: string) => {
    setTriageLoadingCaseId(caseId);
    try {
      const result = await triggerCaseTriage(caseId);
      if (result.success) {
        showToast(
          'success',
          'AI Triage Orchestration Complete',
          `Policy: ${result.policy || 'Enforced'} · State: ${result.state || 'Updated'}`
        );
      } else {
        showToast('warning', 'Triage Outcome Non-Recoverable', result.error || 'Triage completed safely.');
      }
      // Invalidate and refresh
      loadMetrics();
      loadCases();
      if (selectedCaseId === caseId) {
        loadCaseDetail(caseId);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Triage execution failed';
      showToast('error', 'Triage Error', msg);
    } finally {
      setTriageLoadingCaseId(null);
    }
  };

  // Process Due Delayed Cases Mutation
  const handleProcessDelayed = async () => {
    setDelayedProcessing(true);
    try {
      const result = await processDueDelayedCases();
      showToast(
        'success',
        'Batch Delayed Execution Completed',
        `Processed ${result.processed_count} due delayed recovery cases restart-safely.`
      );
      loadMetrics();
      loadCases();
      if (selectedCaseId) loadCaseDetail(selectedCaseId);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Delayed processing failed';
      showToast('error', 'Batch Execution Error', msg);
    } finally {
      setDelayedProcessing(false);
    }
  };

  // Select case handler from tables
  const handleSelectCase = (caseId: string) => {
    navigateTo('investigation', caseId);
  };

  // Titles mapping
  const pageTitles: Record<ActivePage, { title: string; subtitle: string }> = {
    overview: {
      title: 'Executive Recovery Overview',
      subtitle: 'Autonomous Revenue Recovery Intelligence & Funnel Analytics',
    },
    cases: {
      title: 'Failed Payment Cases Explorer',
      subtitle: 'Real-time Payment Failure Stream & State Machine Registry',
    },
    investigation: {
      title: 'Case Decision Story & Investigation',
      subtitle: selectedCaseId ? `Active Case: ${selectedCaseId}` : 'Step-by-step Decision Reasoning Walkthrough',
    },
    mcp: {
      title: 'MCP Boundary & Guardrail Architecture',
      subtitle: 'Advisory AI Isolation & Deterministic Policy Enforcement Invariants',
    },
    health: {
      title: 'System Operational Diagnostics',
      subtitle: 'FastAPI Backend, PostgreSQL Connection & Layer Status',
    },
  };

  return (
    <AppShell
      activePage={activePage}
      onNavigate={navigateTo}
      selectedCaseId={selectedCaseId}
      pageTitle={pageTitles[activePage].title}
      pageSubtitle={pageTitles[activePage].subtitle}
      health={health}
      healthLoading={healthLoading}
      onRefresh={handleGlobalRefresh}
      isRefreshing={isRefreshing}
    >
      {activePage === 'overview' && (
        <OverviewPage
          metrics={metrics}
          metricsLoading={metricsLoading}
          recentCases={cases}
          casesLoading={casesLoading}
          onSelectCase={handleSelectCase}
          onNavigateToCases={() => navigateTo('cases')}
          onNavigateToMcp={() => navigateTo('mcp')}
          onTriggerTriage={handleTriggerTriage}
          triageLoadingCaseId={triageLoadingCaseId}
        />
      )}

      {activePage === 'cases' && (
        <CasesPage
          cases={cases}
          loading={casesLoading}
          onSelectCase={handleSelectCase}
          onProcessDelayed={handleProcessDelayed}
          delayedProcessing={delayedProcessing}
          onRefresh={loadCases}
          onTriggerTriage={handleTriggerTriage}
          triageLoadingCaseId={triageLoadingCaseId}
        />
      )}

      {activePage === 'investigation' && (
        <CaseDetailPage
          caseId={selectedCaseId}
          detail={caseDetail}
          loading={caseDetailLoading}
          error={caseDetailError}
          onBack={() => navigateTo('cases')}
          onTriggerTriage={handleTriggerTriage}
          triageLoading={Boolean(triageLoadingCaseId && triageLoadingCaseId === selectedCaseId)}
          onRefresh={() => selectedCaseId && loadCaseDetail(selectedCaseId)}
        />
      )}

      {activePage === 'mcp' && <McpArchitecturePage />}

      {activePage === 'health' && (
        <SystemHealthPage
          health={health}
          loading={healthLoading}
          onRefresh={loadHealth}
        />
      )}
    </AppShell>
  );
};

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
};

export default App;
