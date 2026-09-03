/**
 * PaymentFlow Recovery Console — Typed API Client Layer
 * Communicates with the FastAPI backend @ http://localhost:8001
 */

import type {
  BenchmarkRunResponse,
  CaseDetailResponse,
  CaseSummaryItem,
  DelayedProcessResult,
  DemoSeedResponse,
  HealthResponse,
  InteractiveResetResponse,
  InteractiveStatusResponse,
  InteractiveVerifyResponse,
  LaunchScenarioRequest,
  LaunchScenarioResponse,
  MetricsSummary,
  TriageResult,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail: string
  ) {
    super(`API Error ${status} (${statusText}): ${detail}`);
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const errorJson = await response.json();
        if (errorJson && errorJson.detail) {
          detail = typeof errorJson.detail === 'string'
            ? errorJson.detail
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // fallback statusText
      }
      throw new ApiError(response.status, response.statusText, detail);
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiError(0, 'NetworkError', message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Core Operational Endpoints
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Health Check API (GET /health)
 */
export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

/**
 * List Recovery Cases with optional state filtering and pagination (GET /cases)
 */
export async function fetchCases(params: {
  state?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<CaseSummaryItem[]> {
  const searchParams = new URLSearchParams();
  if (params.state) searchParams.set('state', params.state);
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
  if (params.offset !== undefined) searchParams.set('offset', String(params.offset));

  const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : '';
  return request<CaseSummaryItem[]>(`/cases${queryStr}`);
}

/**
 * Get detailed case record and complete chronological audit trail (GET /cases/{case_id})
 */
export async function fetchCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(caseId)}`);
}

/**
 * Get aggregated recovery performance metrics (GET /cases/metrics/summary)
 */
export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  return request<MetricsSummary>('/cases/metrics/summary');
}

/**
 * Run Canonical Recovery Workflow Benchmark Execution (POST /cases/benchmark/run)
 */
export async function runBenchmarkBatch(): Promise<BenchmarkRunResponse> {
  return request<BenchmarkRunResponse>('/cases/benchmark/run', {
    method: 'POST',
  });
}

/**
 * Seed Canonical 15-Case Demonstration Batch (POST /cases/demo/seed)
 * @deprecated Use runBenchmarkBatch instead
 */
export async function seedDemoBatch(resetFirst: boolean = true): Promise<DemoSeedResponse> {
  return request<DemoSeedResponse>(`/cases/demo/seed?reset_first=${resetFirst}`, {
    method: 'POST',
  });
}

/**
 * Manually trigger full AI/MCP recovery orchestration for a case (POST /cases/{case_id}/triage)
 */
export async function triggerCaseTriage(caseId: string): Promise<TriageResult> {
  return request<TriageResult>(`/cases/${encodeURIComponent(caseId)}/triage`, {
    method: 'POST',
  });
}

/**
 * Execute all due delayed recovery cases restart-safely (POST /cases/delayed/process)
 */
export async function processDueDelayedCases(): Promise<DelayedProcessResult> {
  return request<DelayedProcessResult>('/cases/delayed/process', {
    method: 'POST',
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Interactive Recovery Demonstration Endpoints
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Launch Interactive CS01 Demonstration Scenario (POST /cases/interactive/launch)
 */
export async function launchInteractiveScenario(
  payload: LaunchScenarioRequest = {}
): Promise<LaunchScenarioResponse> {
  return request<LaunchScenarioResponse>('/cases/interactive/launch', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Query Interactive Demonstration Case Status & Audit Trail (GET /cases/interactive/status)
 */
export async function fetchInteractiveStatus(): Promise<InteractiveStatusResponse> {
  return request<InteractiveStatusResponse>('/cases/interactive/status');
}

/**
 * Authoritatively Verify Payment Capture on Gateway (POST /cases/interactive/verify)
 */
export async function verifyInteractivePayment(): Promise<InteractiveVerifyResponse> {
  return request<InteractiveVerifyResponse>('/cases/interactive/verify', {
    method: 'POST',
  });
}

/**
 * Safely Reset Interactive Demonstration Run (POST /cases/interactive/reset)
 */
export async function resetInteractiveCase(): Promise<InteractiveResetResponse> {
  return request<InteractiveResetResponse>('/cases/interactive/reset', {
    method: 'POST',
  });
}
