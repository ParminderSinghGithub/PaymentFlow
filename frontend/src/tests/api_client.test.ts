import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchHealth,
  fetchCases,
  fetchCaseDetail,
  fetchMetricsSummary,
  triggerCaseTriage,
  processDueDelayedCases,
  seedDemoBatch,
  launchInteractiveScenario,
  fetchInteractiveStatus,
  verifyInteractivePayment,
  resetInteractiveCase,
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

  it('launchInteractiveScenario triggers CS01 launch', async () => {
    const mockLaunch = {
      status: 'success',
      case_id: 'case_interactive_cs01',
      scenario_id: 'CS01',
      state: 'ACTION_EXECUTED',
      failure_category: 'C1',
      amount_paise: 250000,
      amount_inr: 2500.0,
      payment_link_id: 'plink_123',
      payment_link_url: 'https://rzp.io/rzp/test',
      audit_trail_count: 5,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockLaunch,
    });

    const result = await launchInteractiveScenario({ scenario_id: 'CS01' });
    expect(result.status).toBe('success');
    expect(result.case_id).toBe('case_interactive_cs01');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/interactive/launch'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('fetchInteractiveStatus retrieves status and audit trail', async () => {
    const mockStatus = {
      case_id: 'case_interactive_cs01',
      exists: true,
      state: 'ACTION_EXECUTED',
      amount_inr: 2500.0,
      audit_trail: [],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockStatus,
    });

    const result = await fetchInteractiveStatus();
    expect(result.exists).toBe(true);
    expect(result.case_id).toBe('case_interactive_cs01');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/interactive/status'),
      expect.anything()
    );
  });

  it('verifyInteractivePayment posts to interactive verify', async () => {
    const mockVerify = {
      case_id: 'case_interactive_cs01',
      verified: true,
      state: 'RECOVERED',
      recovered_amount_inr: 2500.0,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockVerify,
    });

    const result = await verifyInteractivePayment();
    expect(result.verified).toBe(true);
    expect(result.state).toBe('RECOVERED');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/interactive/verify'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('resetInteractiveCase posts to interactive reset', async () => {
    const mockReset = {
      status: 'success',
      message: 'Interactive demonstration case reset successfully.',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockReset,
    });

    const result = await resetInteractiveCase();
    expect(result.status).toBe('success');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/interactive/reset'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('verifyInteractivePayment handles unpaid payment link state', async () => {
    const mockUnpaid = {
      case_id: 'case_interactive_cs01',
      verified: false,
      state: 'ACTION_EXECUTED',
      payment_link_id: 'plink_123',
      payment_link_status: 'created',
      message: 'Payment link is currently unpaid. Complete the payment in Razorpay checkout.',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockUnpaid,
    });

    const result = await verifyInteractivePayment();
    expect(result.verified).toBe(false);
    expect(result.state).toBe('ACTION_EXECUTED');
    expect(result.message).toContain('unpaid');
  });

  it('launchInteractiveScenario formats custom customer details correctly', async () => {
    const mockLaunch = {
      status: 'success',
      case_id: 'case_interactive_cs01',
      scenario_id: 'CS01',
      state: 'ACTION_EXECUTED',
      amount_paise: 250000,
      amount_inr: 2500.0,
      payment_link_id: 'plink_custom',
      payment_link_url: 'https://rzp.io/rzp/custom',
      audit_trail_count: 5,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockLaunch,
    });

    const result = await launchInteractiveScenario({
      scenario_id: 'CS01',
      amount_paise: 250000,
      customer_email: 'evaluator@razorpay.com',
      customer_contact: '+919876543210',
      reset_previous: true,
    });

    expect(result.status).toBe('success');
    expect(result.payment_link_id).toBe('plink_custom');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/cases/interactive/launch'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          scenario_id: 'CS01',
          amount_paise: 250000,
          customer_email: 'evaluator@razorpay.com',
          customer_contact: '+919876543210',
          reset_previous: true,
        }),
      })
    );
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
