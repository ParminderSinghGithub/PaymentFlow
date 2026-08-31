import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from './components/layout/AppShell';
import type { ActivePage } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { CasesPage } from './pages/CasesPage';
import { CaseInvestigationPage } from './pages/CaseInvestigationPage';
import { ArchitecturePage } from './pages/ArchitecturePage';
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
import type { CaseDetailResponse, CaseSummaryItem, HealthResponse, MetricsSummary } from './types';

// ─── Page title map ───────────────────────────────────────────────────

const PAGE_TITLES: Record<ActivePage, { title: string; subtitle: string }> = {
  overview: {
    title: 'Recovery Overview',
    subtitle: 'Autonomous revenue recovery performance and pipeline state',
  },
  cases: {
    title: 'Cases Explorer',
    subtitle: 'Failed payment pipeline — state machine registry',
  },
  investigation: {
    title: 'Case Investigation',
    subtitle: 'Decision story — from gateway failure to revenue attribution',
  },
  architecture: {
    title: 'System Architecture',
    subtitle: 'AI advisory + MCP boundary + deterministic guardrails',
  },
  system: {
    title: 'System Diagnostics',
    subtitle: 'Backend health, layer status, and API contract reference',
  },
};

// ─── App Content ──────────────────────────────────────────────────────

const AppContent: React.FC = () => {
  const { showToast } = useToast();

  // Navigation
  const [activePage, setActivePage] = useState<ActivePage>('overview');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  // Data states
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  const [cases, setCases] = useState<CaseSummaryItem[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);

  const [caseDetail, setCaseDetail] = useState<CaseDetailResponse | null>(null);
  const [caseDetailLoading, setCaseDetailLoading] = useState(false);
  const [caseDetailError, setCaseDetailError] = useState<string | null>(null);

  // Action states
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [triageLoadingCaseId, setTriageLoadingCaseId] = useState<string | null>(null);
  const [delayedProcessing, setDelayedProcessing] = useState(false);

  // ── Hash routing ──────────────────────────────────────────────────

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      if (hash.startsWith('investigation')) {
        const params = new URLSearchParams(hash.split('?')[1]);
        const id = params.get('id');
        setActivePage('investigation');
        if (id) setSelectedCaseId(id);
      } else if (['overview', 'cases', 'investigation', 'architecture', 'system'].includes(hash)) {
        setActivePage(hash as ActivePage);
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = useCallback((page: ActivePage, caseId?: string | null) => {
    setActivePage(page);
    if (caseId !== undefined) setSelectedCaseId(caseId);
    if (page === 'investigation') {
      const id = caseId ?? selectedCaseId;
      window.location.hash = id
        ? `investigation?id=${encodeURIComponent(id)}`
        : 'investigation';
    } else {
      window.location.hash = page;
    }
  }, [selectedCaseId]);

  // ── Data fetchers ─────────────────────────────────────────────────

  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      setHealth(await fetchHealth());
    } catch {
      setHealth({ status: 'degraded', environment: 'offline', database: 'disconnected', version: '—' });
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const loadMetrics = useCallback(async () => {
    setMetricsLoading(true);
    try {
      setMetrics(await fetchMetricsSummary());
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Metrics unavailable';
      showToast('error', 'Metrics Error', msg);
    } finally {
      setMetricsLoading(false);
    }
  }, [showToast]);

  const loadCases = useCallback(async () => {
    setCasesLoading(true);
    try {
      setCases(await fetchCases({ limit: 100 }));
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Cases unavailable';
      showToast('error', 'Cases Error', msg);
    } finally {
      setCasesLoading(false);
    }
  }, [showToast]);

  const loadCaseDetail = useCallback(async (id: string) => {
    setCaseDetailLoading(true);
    setCaseDetailError(null);
    try {
      setCaseDetail(await fetchCaseDetail(id));
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to load case';
      setCaseDetailError(msg);
      showToast('error', 'Case Detail Error', msg);
    } finally {
      setCaseDetailLoading(false);
    }
  }, [showToast]);

  // Auto-load case detail when navigating to investigation
  useEffect(() => {
    if (selectedCaseId && activePage === 'investigation') {
      loadCaseDetail(selectedCaseId);
    }
  }, [selectedCaseId, activePage, loadCaseDetail]);

  // Initial load
  useEffect(() => {
    loadHealth();
    loadMetrics();
    loadCases();
  }, [loadHealth, loadMetrics, loadCases]);

  // ── Actions ───────────────────────────────────────────────────────

  const handleGlobalRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      loadHealth(),
      loadMetrics(),
      loadCases(),
      selectedCaseId && activePage === 'investigation'
        ? loadCaseDetail(selectedCaseId)
        : Promise.resolve(),
    ]);
    setIsRefreshing(false);
    showToast('success', 'Synchronized', 'Latest operational state refreshed from backend.');
  };

  const handleTriggerTriage = async (caseId: string) => {
    setTriageLoadingCaseId(caseId);
    try {
      const result = await triggerCaseTriage(caseId);
      if (result.success) {
        showToast(
          'success',
          'Recovery Triage Complete',
          `Policy: ${result.policy ?? 'enforced'} · State: ${result.state ?? 'updated'}`
        );
      } else {
        showToast('warning', 'Triage Outcome', result.error ?? 'Triage completed — no action taken.');
      }
      loadMetrics();
      loadCases();
      if (selectedCaseId === caseId) loadCaseDetail(caseId);
    } catch (err) {
      showToast('error', 'Triage Error', err instanceof ApiError ? err.detail : 'Triage failed');
    } finally {
      setTriageLoadingCaseId(null);
    }
  };

  const handleProcessDelayed = async () => {
    setDelayedProcessing(true);
    try {
      const result = await processDueDelayedCases();
      showToast(
        'success',
        'Delayed Processing Complete',
        `${result.processed_count} due delayed cases processed.`
      );
      loadMetrics();
      loadCases();
      if (selectedCaseId) loadCaseDetail(selectedCaseId);
    } catch (err) {
      showToast('error', 'Delayed Processing Error', err instanceof ApiError ? err.detail : 'Processing failed');
    } finally {
      setDelayedProcessing(false);
    }
  };

  const handleSelectCase = (caseId: string) => navigateTo('investigation', caseId);

  const { title, subtitle } = PAGE_TITLES[activePage];

  return (
    <AppShell
      activePage={activePage}
      onNavigate={navigateTo}
      selectedCaseId={selectedCaseId}
      pageTitle={activePage === 'investigation' && selectedCaseId ? `Investigation · ${selectedCaseId}` : title}
      pageSubtitle={subtitle}
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
          onNavigateToArchitecture={() => navigateTo('architecture')}
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
        <CaseInvestigationPage
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

      {activePage === 'architecture' && <ArchitecturePage />}

      {activePage === 'system' && (
        <SystemHealthPage
          health={health}
          loading={healthLoading}
          onRefresh={loadHealth}
        />
      )}
    </AppShell>
  );
};

// ─── Root ─────────────────────────────────────────────────────────────

export const App: React.FC = () => (
  <ToastProvider>
    <AppContent />
  </ToastProvider>
);

export default App;
