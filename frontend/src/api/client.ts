/**
 * PaymentFlow Recovery Console — Typed API Client Layer
 * Communicates with the FastAPI backend @ http://localhost:8001
 */

import type {
  BenchmarkLatestResponse,
  BenchmarkRunResponse,
  CaseDetailResponse,
  CaseSummaryItem,
  DelayedProcessResult,
  DemoSeedResponse,
  HealthResponse,
  MetricsSummary,
  TriageResult,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim();
  }
  if (typeof window !== 'undefined' && window.location.origin) {
    return window.location.origin;
  }
  return 'http://localhost:8001';
}

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
  case_source?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<CaseSummaryItem[]> {
  const searchParams = new URLSearchParams();
  if (params.state) searchParams.set('state', params.state);
  if (params.case_source) searchParams.set('case_source', params.case_source);
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
export async function fetchMetricsSummary(params?: {
  case_source?: string;
  eval_run_id?: string;
}): Promise<MetricsSummary> {
  const searchParams = new URLSearchParams();
  if (params?.case_source) searchParams.set('case_source', params.case_source);
  if (params?.eval_run_id) searchParams.set('eval_run_id', params.eval_run_id);
  const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : '';
  return request<MetricsSummary>(`/cases/metrics/summary${queryStr}`);
}

/**
 * Get latest canonical benchmark evaluation metrics (GET /cases/benchmark/latest)
 */
export async function fetchBenchmarkLatest(): Promise<BenchmarkLatestResponse> {
  return request<BenchmarkLatestResponse>('/cases/benchmark/latest');
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
// 2. Merchant Storefront Navigation Helper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns the configured external merchant storefront checkout URL.
 * Defaults to VITE_MERCHANT_STOREFRONT_URL or derives from host topology.
 */
export function getMerchantStorefrontUrl(): string {
  const configured = import.meta.env.VITE_MERCHANT_STOREFRONT_URL;
  if (configured && configured.trim().length > 0) {
    return configured.trim();
  }
  const apiBase = import.meta.env.VITE_API_BASE_URL || '';
  if (apiBase) {
    // If API is on port 8000/8001, external merchant server runs on port 8002
    return `${apiBase.replace(/:800[01]/, ':8002')}/checkout`;
  }
  return 'http://localhost:8002/checkout';
}
