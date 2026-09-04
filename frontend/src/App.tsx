import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from './components/layout/AppShell';
import type { ActivePage } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { CasesPage } from './pages/CasesPage';
import { CaseInvestigationPage } from './pages/CaseInvestigationPage';
import { InteractivePage } from './pages/InteractivePage';
import { SystemPage } from './pages/SystemPage';
import { ToastProvider, useToast } from './components/common/Toast';
import {
  fetchCases,
  fetchCaseDetail,
  fetchHealth,
  fetchMetricsSummary,
  processDueDelayedCases,
  triggerCaseTriage,
  runBenchmarkBatch,
  ApiError,
} from './api/client';
import type { CaseDetailResponse, CaseSummaryItem, HealthResponse, MetricsSummary } from './types';

// ─── Page Title & Subtitle Mapping ─────────────────────────────────────────

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
  interactive: {
    title: 'Interactive Demonstration',
    subtitle: 'Live CS01 recovery journey with genuine Razorpay Test Mode checkout',
  },
  system: {
    title: 'System & Trust',
    subtitle: 'AI boundary, deterministic guardrails, MCP contracts, and diagnostics',
  },
};

// ─── App Content ───────────────────────────────────────────────────────────

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
  const [seedingBatch, setSeedingBatch] = useState(false);

  // ── Hash Routing ─────────────────────────────────────────────────────────

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      if (hash.startsWith('investigation')) {
        const params = new URLSearchParams(hash.split('?')[1]);
        const id = params.get('id');
        setActivePage('investigation');
        if (id) setSelectedCaseId(id);
      } else if (['overview', 'cases', 'investigation', 'interactive', 'system'].includes(hash)) {
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

  // ── Data Fetchers ────────────────────────────────────────────────────────

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

  const loadMetrics = useCallback(
    async (scope?: { case_source?: string; eval_run_id?: string }) => {
      setMetricsLoading(true);
      try {
        const targetScope =
          scope ??
          (activePage === 'overview' ? { case_source: 'CANONICAL_EVALUATION' } : undefined);
        setMetrics(await fetchMetricsSummary(targetScope));
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : 'Metrics unavailable';
        showToast('error', 'Metrics Error', msg);
      } finally {
        setMetricsLoading(false);
      }
    },
    [activePage, showToast]
  );

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

  // ── Actions ──────────────────────────────────────────────────────────────

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

  // Re-fetch metrics whenever active page changes to ensure appropriate scope
  useEffect(() => {
    loadMetrics();
  }, [activePage, loadMetrics]);

  const handleSeedCanonicalBatch = async () => {
    setSeedingBatch(true);
    try {
      const result = await runBenchmarkBatch();
      showToast(
        'success',
        'Benchmark Batch Executed',
        `Run ID: ${result.eval_run_id} · ${result.evaluation_recovered_cases}/${result.total_cases} recovered (₹${result.evaluation_recovered_amount_inr.toLocaleString('en-IN')}).`
      );
      await Promise.all([
        loadMetrics({ case_source: 'CANONICAL_EVALUATION', eval_run_id: result.eval_run_id }),
        loadCases(),
      ]);
    } catch (err) {
      showToast('error', 'Benchmark Error', err instanceof ApiError ? err.detail : 'Benchmark execution failed');
    } finally {
      setSeedingBatch(false);
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
          onNavigateToArchitecture={() => navigateTo('system')}
          onNavigateToInteractive={() => navigateTo('interactive')}
          onTriggerTriage={handleTriggerTriage}
          triageLoadingCaseId={triageLoadingCaseId}
          onSeedDemoBatch={handleSeedCanonicalBatch}
          seedingBatch={seedingBatch}
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

      {activePage === 'interactive' && (
        <InteractivePage
          onNavigateToInvestigation={handleSelectCase}
          onRefreshGlobalMetrics={loadMetrics}
        />
      )}

      {activePage === 'system' && (
        <SystemPage
          health={health}
          loading={healthLoading}
          onRefresh={loadHealth}
        />
      )}
    </AppShell>
  );
};

// ─── Root ──────────────────────────────────────────────────────────────────

export const App: React.FC = () => (
  <ToastProvider>
    <AppContent />
  </ToastProvider>
);

export default App;
