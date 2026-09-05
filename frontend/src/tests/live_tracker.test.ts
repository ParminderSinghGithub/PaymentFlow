import { describe, it, expect } from 'vitest';
import type { CaseSummaryItem } from '../types';

describe('PaymentFlow Live Recovery Tracker Metric & Queue Semantics', () => {
  // Helper to compute active queue and metrics matching LiveTrackerPage logic
  function computeLiveTrackerState(liveCases: CaseSummaryItem[]) {
    const activeQueue = liveCases;

    const amountAtRisk = activeQueue
      .filter((c) => c.state !== 'RECOVERED' && c.state !== 'TERMINAL_NO_ACTION')
      .reduce((sum, c) => sum + (c.amount_inr || 0), 0);

    const recoveryLinkSentCount = activeQueue.filter(
      (c) =>
        Boolean(c.payment_link_id) ||
        Boolean(c.payment_link_short_url) ||
        c.state === 'ACTION_EXECUTED' ||
        c.state === 'RECOVERED'
    ).length;

    const amountRecovered = activeQueue
      .filter((c) => c.state === 'RECOVERED')
      .reduce((sum, c) => sum + (c.recovered_amount_inr || c.amount_inr || 0), 0);

    const activeRecoveriesCount = activeQueue.filter(
      (c) => c.state !== 'RECOVERED' && c.state !== 'TERMINAL_NO_ACTION'
    ).length;

    return {
      activeQueue,
      amountAtRisk,
      recoveryLinkSentCount,
      amountRecovered,
      activeRecoveriesCount,
    };
  }

  it('initial/empty state returns exact ₹0 and 0 counts with empty active queue', () => {
    const liveCases: CaseSummaryItem[] = [];
    const state = computeLiveTrackerState(liveCases);

    expect(state.activeQueue).toHaveLength(0);
    expect(state.amountAtRisk).toBe(0);
    expect(state.recoveryLinkSentCount).toBe(0);
    expect(state.amountRecovered).toBe(0);
    expect(state.activeRecoveriesCount).toBe(0);
  });

  it('FAILED_INGESTED case displays Amount at Risk and increments Active Recoveries', () => {
    const liveCases: CaseSummaryItem[] = [
      {
        case_id: 'case_live_001',
        failed_payment_id: 'pay_fail_001',
        order_id: 'ORD-2026-1001',
        customer_id: null,
        amount_paise: 250000,
        amount_inr: 2500.0,
        currency: 'INR',
        payment_method: 'netbanking',
        failure_category: 'C1',
        state: 'FAILED_INGESTED',
        validated_policy_id: null,
        payment_link_id: null,
        payment_link_short_url: null,
        recovered_amount_paise: null,
        recovered_amount_inr: 0,
        case_source: 'MERCHANT_CHECKOUT',
        created_at: new Date().toISOString(),
        scheduled_at: null,
      },
    ];

    const state = computeLiveTrackerState(liveCases);

    expect(state.activeQueue).toHaveLength(1);
    expect(state.amountAtRisk).toBe(2500.0);
    expect(state.activeRecoveriesCount).toBe(1);
    expect(state.recoveryLinkSentCount).toBe(0);
    expect(state.amountRecovered).toBe(0);
  });

  it('ACTION_EXECUTED case increments Recovery Link Sent without declaring recovered money', () => {
    const liveCases: CaseSummaryItem[] = [
      {
        case_id: 'case_live_001',
        failed_payment_id: 'pay_fail_001',
        order_id: 'ORD-2026-1001',
        customer_id: null,
        amount_paise: 250000,
        amount_inr: 2500.0,
        currency: 'INR',
        payment_method: 'netbanking',
        failure_category: 'C1',
        state: 'ACTION_EXECUTED',
        validated_policy_id: 'P_CREATE_LINK_IMMEDIATE',
        payment_link_id: 'plink_test_123',
        payment_link_short_url: 'https://rzp.io/i/test123',
        recovered_amount_paise: null,
        recovered_amount_inr: 0,
        case_source: 'MERCHANT_CHECKOUT',
        created_at: new Date().toISOString(),
        scheduled_at: null,
      },
    ];

    const state = computeLiveTrackerState(liveCases);

    expect(state.activeQueue).toHaveLength(1);
    expect(state.amountAtRisk).toBe(2500.0);
    expect(state.recoveryLinkSentCount).toBe(1);
    // Crucial: ACTION_EXECUTED must NEVER declare recovered money
    expect(state.amountRecovered).toBe(0);
    expect(state.activeRecoveriesCount).toBe(1);
  });

  it('RECOVERED case displays recovered amount and sustains indefinitely in the live queue', () => {
    const recoveredCase: CaseSummaryItem = {
      case_id: 'case_live_001',
      failed_payment_id: 'pay_fail_001',
      order_id: 'ORD-2026-1001',
      customer_id: null,
      amount_paise: 250000,
      amount_inr: 2500.0,
      currency: 'INR',
      payment_method: 'netbanking',
      failure_category: 'C1',
      state: 'RECOVERED',
      validated_policy_id: 'P_CREATE_LINK_IMMEDIATE',
      payment_link_id: 'plink_test_123',
      payment_link_short_url: 'https://rzp.io/i/test123',
      recovered_amount_paise: 250000,
      recovered_amount_inr: 2500.0,
      case_source: 'MERCHANT_CHECKOUT',
      created_at: new Date().toISOString(),
      scheduled_at: null,
    };

    // Sustains indefinitely in the live active queue
    const state = computeLiveTrackerState([recoveredCase]);
    expect(state.activeQueue).toHaveLength(1);
    expect(state.amountRecovered).toBe(2500.0);
    expect(state.amountAtRisk).toBe(0); // Risk cleared upon recovery
    expect(state.activeRecoveriesCount).toBe(0); // No unresolved cases remaining
    expect(state.recoveryLinkSentCount).toBe(1); // Link dispatched and captured
  });

  it('aggregates multiple active cases correctly and excludes terminal states from risk', () => {
    const cases: CaseSummaryItem[] = [
      {
        case_id: 'case_live_001',
        failed_payment_id: 'pay_fail_001',
        order_id: 'ORD-001',
        customer_id: null,
        amount_paise: 150000,
        amount_inr: 1500.0,
        currency: 'INR',
        payment_method: 'card',
        failure_category: 'C1',
        state: 'ACTION_EXECUTED',
        validated_policy_id: 'P_CREATE_LINK_IMMEDIATE',
        payment_link_id: 'plink_001',
        payment_link_short_url: 'https://rzp.io/i/001',
        recovered_amount_paise: null,
        recovered_amount_inr: 0,
        case_source: 'MERCHANT_CHECKOUT',
        created_at: new Date().toISOString(),
        scheduled_at: null,
      },
      {
        case_id: 'case_live_002',
        failed_payment_id: 'pay_fail_002',
        order_id: 'ORD-002',
        customer_id: null,
        amount_paise: 350000,
        amount_inr: 3500.0,
        currency: 'INR',
        payment_method: 'netbanking',
        failure_category: 'C2',
        state: 'FAILED_INGESTED',
        validated_policy_id: null,
        payment_link_id: null,
        payment_link_short_url: null,
        recovered_amount_paise: null,
        recovered_amount_inr: 0,
        case_source: 'MERCHANT_CHECKOUT',
        created_at: new Date().toISOString(),
        scheduled_at: null,
      },
      {
        case_id: 'case_live_003',
        failed_payment_id: 'pay_fail_003',
        order_id: 'ORD-003',
        customer_id: null,
        amount_paise: 500000,
        amount_inr: 5000.0,
        currency: 'INR',
        payment_method: 'upi',
        failure_category: 'C3',
        state: 'TERMINAL_NO_ACTION',
        validated_policy_id: 'P_NO_ACTION',
        payment_link_id: null,
        payment_link_short_url: null,
        recovered_amount_paise: null,
        recovered_amount_inr: 0,
        case_source: 'MERCHANT_CHECKOUT',
        created_at: new Date().toISOString(),
        scheduled_at: null,
      },
    ];

    const state = computeLiveTrackerState(cases);

    expect(state.activeQueue).toHaveLength(3);
    expect(state.amountAtRisk).toBe(5000.0); // 1500 + 3500 (terminal state excluded from risk)
    expect(state.activeRecoveriesCount).toBe(2);
    expect(state.recoveryLinkSentCount).toBe(1); // Only case_live_001 has payment_link_id
    expect(state.amountRecovered).toBe(0);
  });
});
