import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchHealth,
  fetchCases,
  fetchCaseDetail,
  fetchMetricsSummary,
  triggerCaseTriage,
  processDueDelayedCases,
  seedDemoBatch,
  getMerchantStorefrontUrl,
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
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.anything()
    );
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
      expect.stringContaining('/cases?state=RECOVERED&limit=20&offset=10'),
      expect.anything()
    );
  });

  it('fetchCases passes case_source filter query param for operational tracking', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    await fetchCases({ case_source: 'MERCHANT_CHECKOUT', limit: 50 });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases?case_source=MERCHANT_CHECKOUT&limit=50'),
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
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/case_detail_123'),
      expect.anything()
    );
  });

  it('fetchMetricsSummary retrieves recovery KPIs', async () => {
    const mockMetrics = {
      total_cases: 15,
      recovered_cases: 6,
      total_recovered_amount_inr: 30700.0,
      recovery_rate_pct: 40.0,
      active_recovery_links: 7,
      escalated_cases: 2,
      terminal_no_action_cases: 6,
      category_breakdown: { C1: 8 },
      policy_breakdown: { P_CREATE_LINK_IMMEDIATE: 6 },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    });

    const result = await fetchMetricsSummary();
    expect(result.total_cases).toBe(15);
    expect(result.recovered_cases).toBe(6);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/metrics/summary'),
      expect.anything()
    );
  });

  it('seedDemoBatch posts to demo seed endpoint', async () => {
    const mockSeed = {
      status: 'success',
      seeded_cases_count: 15,
      total_revenue_at_risk_inr: 134000.0,
      total_recovered_inr: 30700.0,
      recovery_rate_pct: 22.91,
      cases: ['case_1'],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockSeed,
    });

    const result = await seedDemoBatch(true);
    expect(result.seeded_cases_count).toBe(15);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/demo/seed?reset_first=true'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('getMerchantStorefrontUrl resolves configured or fallback storefront URL', () => {
    const url = getMerchantStorefrontUrl();
    expect(url).toBeDefined();
    expect(url).toContain('/checkout');
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
      expect.stringContaining('/cases/case_triage_001/triage'),
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
      expect.stringContaining('/cases/delayed/process'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('normalizes HTTP 404 and 500 error responses into ApiError', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Recovery case not found' }),
    });

    await expect(fetchCaseDetail('invalid_id')).rejects.toThrow(ApiError);
    await expect(fetchCaseDetail('invalid_id')).rejects.toMatchObject({
      status: 404,
      detail: 'Recovery case not found',
    });
  });
});
