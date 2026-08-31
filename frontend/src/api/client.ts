/**
 * PaymentFlow Recovery Console — Typed API Client Layer
 * Communicates with the frozen Layer 5G FastAPI backend.
 */

import type {
  CaseDetailResponse,
  CaseSummaryItem,
  DelayedProcessResult,
  HealthResponse,
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
        // use fallback statusText
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

/**
 * Health Check API
 */
export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

/**
 * List Recovery Cases with optional state filtering and pagination
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
 * Get detailed case record and complete chronological audit trail
 */
export async function fetchCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  return request<CaseDetailResponse>(`/cases/${encodeURIComponent(caseId)}`);
}

/**
 * Get aggregated recovery performance metrics
 */
export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  return request<MetricsSummary>('/cases/metrics/summary');
}

/**
 * Manually trigger full AI/MCP recovery orchestration for a case
 */
export async function triggerCaseTriage(caseId: string): Promise<TriageResult> {
  return request<TriageResult>(`/cases/${encodeURIComponent(caseId)}/triage`, {
    method: 'POST',
  });
}

/**
 * Execute all due delayed recovery cases restart-safely
 */
export async function processDueDelayedCases(): Promise<DelayedProcessResult> {
  return request<DelayedProcessResult>('/cases/delayed/process', {
    method: 'POST',
  });
}
