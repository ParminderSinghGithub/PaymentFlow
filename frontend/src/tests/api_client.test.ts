import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchHealth,
  fetchCases,
  fetchCaseDetail,
  triggerCaseTriage,
  processDueDelayedCases,
  ApiError,
} from '../api/client';

describe('PaymentFlow Frontend API Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('fetchHealth returns status and environment successfully', async () => {
    const mockHealth = {
      status: 'ok',
      environment: 'development',
      database: 'connected',
      version: '0.1.0',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await fetchHealth();
    expect(result.status).toBe('ok');
    expect(result.database).toBe('connected');
    expect(global.fetch).toHaveBeenCalledWith('/health', expect.anything());
  });

  it('fetchCases passes state filter and pagination query params', async () => {
    const mockCases = [
      {
        case_id: 'case_test_001',
        amount_paise: 250000,
        amount_inr: 2500.0,
        currency: 'INR',
        state: 'RECOVERED',
      },
    ];

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockCases,
    });

    const result = await fetchCases({ state: 'RECOVERED', limit: 20, offset: 10 });
    expect(result).toHaveLength(1);
    expect(result[0].case_id).toBe('case_test_001');
    expect(global.fetch).toHaveBeenCalledWith(
      '/cases?state=RECOVERED&limit=20&offset=10',
      expect.anything()
    );
  });

  it('fetchCaseDetail retrieves case detail and audit events', async () => {
    const mockDetail = {
      case: {
        case_id: 'case_detail_123',
        amount_paise: 500000,
        state: 'ACTION_EXECUTED',
      },
      audit_trail: [
        {
          id: 1,
          event_type: 'CONTEXT_ENRICHED',
          actor: 'recovery_service',
        },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockDetail,
    });

    const result = await fetchCaseDetail('case_detail_123');
    expect(result.case.case_id).toBe('case_detail_123');
    expect(result.audit_trail).toHaveLength(1);
    expect(global.fetch).toHaveBeenCalledWith('/cases/case_detail_123', expect.anything());
  });

  it('triggerCaseTriage sends POST request and receives triage outcome', async () => {
    const mockTriageResult = {
      success: true,
      case_id: 'case_triage_001',
      stage: 'EXECUTION',
      state: 'ACTION_EXECUTED',
      policy: 'P_CREATE_LINK_IMMEDIATE',
      payment_link_id: 'plink_001',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockTriageResult,
    });

    const result = await triggerCaseTriage('case_triage_001');
    expect(result.success).toBe(true);
    expect(result.policy).toBe('P_CREATE_LINK_IMMEDIATE');
    expect(global.fetch).toHaveBeenCalledWith(
      '/cases/case_triage_001/triage',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('processDueDelayedCases sends POST request to process due batch', async () => {
    const mockProcessResult = {
      processed_count: 3,
      results: [{ case_id: 'case_1' }, { case_id: 'case_2' }, { case_id: 'case_3' }],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockProcessResult,
    });

    const result = await processDueDelayedCases();
    expect(result.processed_count).toBe(3);
    expect(global.fetch).toHaveBeenCalledWith(
      '/cases/delayed/process',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('normalizes HTTP 404 and 500 error responses into ApiError', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: "Recovery case 'case_999' not found." }),
    });

    await expect(fetchCaseDetail('case_999')).rejects.toThrow(ApiError);
  });
});
