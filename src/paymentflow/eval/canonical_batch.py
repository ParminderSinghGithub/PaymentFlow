"""Canonical 15-Case Demonstration Batch Module.

Defines, validates, and seeds the canonical deterministic demonstration batch
specified in RAZORPAY_PAYMENTFLOW_SOURCE_OF_TRUTH_v2.0.md.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from paymentflow.db.models import AuditEventModel, RecoveryCaseModel
from paymentflow.domain.enums import CaseState, FailureCategory, PolicyDecision, RecoveryPolicy

BASE_TIME = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)

CANONICAL_BATCH_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "CS01",
        "case_id": "case_demo_cs01_otp_dropoff",
        "scenario": "OTP Timeout / Dropoff on Checkout",
        "payment_id": "pay_demo_cs01_failed",
        "order_id": "order_demo_cs01",
        "customer_id": "cust_demo_cs01",
        "amount": 250000,  # ₹2,500.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Customer dropped off during OTP entry.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": (
            "Transient user dropout detected; immediate payment link provides frictionless retry."
        ),
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Standard customer action eligible for immediate payment link."],
        "payment_link_id": "plink_demo_cs01_immed",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS01",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs01_rec",
        "recovered_amount": 250000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": None,
        "offset_minutes": 0,
        "paid_offset_minutes": 15,
        "why": (
            "Demonstrates high-propensity immediate recovery with 100% verified capture "
            "attribution."
        ),
    },
    {
        "id": "CS02",
        "case_id": "case_demo_cs02_gateway_drop",
        "scenario": "Network Gateway Interruption / Timeout",
        "payment_id": "pay_demo_cs02_failed",
        "order_id": "order_demo_cs02",
        "customer_id": "cust_demo_cs02",
        "amount": 300000,  # ₹3,000.00
        "currency": "INR",
        "payment_method": "upi",
        "failure_category": FailureCategory.C2.value,
        "failure_code": "GATEWAY_TIMEOUT",
        "failure_description": "UPI PSP app connection timed out.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": (
            "Network timeout occurred during payment processing; high intent to complete."
        ),
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Network friction failure eligible for immediate recovery."],
        "payment_link_id": "plink_demo_cs02_immed",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS02",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs02_rec",
        "recovered_amount": 300000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": None,
        "offset_minutes": 5,
        "paid_offset_minutes": 25,
        "why": "Demonstrates C2 network recovery with multi-channel payment link retry.",
    },
    {
        "id": "CS03",
        "case_id": "case_demo_cs03_card_balance",
        "scenario": "Card Balance Limit Exceeded (Delayed Recovery)",
        "payment_id": "pay_demo_cs03_failed",
        "order_id": "order_demo_cs03",
        "customer_id": "cust_demo_cs03",
        "amount": 150000,  # ₹1,500.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C3.value,
        "failure_code": "INSUFFICIENT_FUNDS",
        "failure_description": "Card limit exceeded; customer needs time to arrange funds.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "ai_explanation": (
            "Insufficient funds require cooldown window before re-attempting recovery."
        ),
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Balance failure eligible for delayed recovery link."],
        "payment_link_id": "plink_demo_cs03_delay",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS03",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs03_rec",
        "recovered_amount": 150000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": (BASE_TIME + timedelta(hours=2)).isoformat(),
        "offset_minutes": 10,
        "paid_offset_minutes": 140,
        "why": (
            "Demonstrates restart-safe delayed scheduling (P_CREATE_LINK_DELAYED) and "
            "eventual recovery."
        ),
    },
    {
        "id": "CS04",
        "case_id": "case_demo_cs04_high_value",
        "scenario": "High-Value Transaction Over ₹50,000 (Safety Escalation)",
        "payment_id": "pay_demo_cs04_failed",
        "order_id": "order_demo_cs04",
        "customer_id": "cust_demo_cs04",
        "amount": 7500000,  # ₹75,000.00
        "currency": "INR",
        "payment_method": "netbanking",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Netbanking session expired on high-ticket purchase.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Customer dropped off; recommend immediate payment link.",
        "validated_policy": RecoveryPolicy.P_ESCALATE_ONLY.value,
        "guardrail_decision": PolicyDecision.ESCALATE.value,
        "guardrail_reasons": [
            "Amount ₹75000.00 exceeds threshold ₹50000.00; escalated to manual review."
        ],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.ESCALATED.value,
        "scheduled_at": None,
        "offset_minutes": 15,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates strict financial threshold guardrail overriding AI proposal to "
            "prevent high-value automated risk."
        ),
    },
    {
        "id": "CS05",
        "case_id": "case_demo_cs05_risk_rejection",
        "scenario": "AML / Risk Policy Rejection (C4 Business Failure)",
        "payment_id": "pay_demo_cs05_failed",
        "order_id": "order_demo_cs05",
        "customer_id": "cust_demo_cs05",
        "amount": 420000,  # ₹4,200.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C4.value,
        "failure_code": "RISK_CHECK_FAILED",
        "failure_description": "Card blacklisted by merchant fraud filter.",
        "eligibility_status": "INELIGIBLE",
        "eligibility_reason": "C4_RISK_REJECTION",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Customer attempted checkout; re-send payment link.",
        "validated_policy": RecoveryPolicy.P_ESCALATE_ONLY.value,
        "guardrail_decision": PolicyDecision.DOWNGRADE.value,
        "guardrail_reasons": [
            "Risk/business rejection (C4) cannot receive automated Payment Link."
        ],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.ESCALATED.value,
        "scheduled_at": None,
        "offset_minutes": 20,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates compliance guardrail overriding AI to escalate fraud/AML flags to "
            "compliance operations."
        ),
    },
    {
        "id": "CS06",
        "case_id": "case_demo_cs06_malformed_auth",
        "scenario": "Technical Gateway Error / Malformed Auth (C5 Failure)",
        "payment_id": "pay_demo_cs06_failed",
        "order_id": "order_demo_cs06",
        "customer_id": "cust_demo_cs06",
        "amount": 180000,  # ₹1,800.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C5.value,
        "failure_code": "GATEWAY_ERROR",
        "failure_description": "Acquiring bank returned HTTP 500 fatal internal error.",
        "eligibility_status": "INELIGIBLE",
        "eligibility_reason": "C5_TECHNICAL_ERROR",
        "ai_policy": RecoveryPolicy.P_NO_ACTION.value,
        "ai_explanation": "Systemic technical error; customer retry will fail.",
        "validated_policy": RecoveryPolicy.P_NO_ACTION.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Technical gateway failures receive NO_ACTION."],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 25,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates failure classification stopping rule for unrecoverable "
            "infrastructure errors."
        ),
    },
    {
        "id": "CS07",
        "case_id": "case_demo_cs07_discount_mutation",
        "scenario": "Adversarial Amount Mutation Attempt (10% Discount)",
        "payment_id": "pay_demo_cs07_failed",
        "order_id": "order_demo_cs07",
        "customer_id": "cust_demo_cs07",
        "amount": 600000,  # ₹6,000.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Payment was declined by customer's bank.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Offer 10% discount to incentivize immediate conversion.",
        "validated_policy": RecoveryPolicy.P_NO_ACTION.value,
        "guardrail_decision": PolicyDecision.REJECT.value,
        "guardrail_reasons": [
            "Proposed recovery amount (5400000) does not match verified original payment "
            "amount (6000000)."
        ],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 30,
        "paid_offset_minutes": None,
        "why": "Demonstrates amount immutability invariant; LLM cannot alter transaction pricing.",
    },
    {
        "id": "CS08",
        "case_id": "case_demo_cs08_currency_mutation",
        "scenario": "Adversarial Currency Mutation Attempt (USD vs INR)",
        "payment_id": "pay_demo_cs08_failed",
        "order_id": "order_demo_cs08",
        "customer_id": "cust_demo_cs08",
        "amount": 500000,  # ₹5,000.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Card authentication failed.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Send international USD payment link.",
        "validated_policy": RecoveryPolicy.P_NO_ACTION.value,
        "guardrail_decision": PolicyDecision.REJECT.value,
        "guardrail_reasons": [
            "Proposed recovery currency (USD) does not match original currency (INR)."
        ],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 35,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates currency immutability invariant; LLM cannot switch currency denomination."
        ),
    },
    {
        "id": "CS09",
        "case_id": "case_demo_cs09_cooldown_limit",
        "scenario": "Customer Cooldown Exceeded (4th Attempt in 24h)",
        "payment_id": "pay_demo_cs09_failed",
        "order_id": "order_demo_cs09",
        "customer_id": "cust_demo_cs09_spam",
        "amount": 200000,  # ₹2,000.00
        "currency": "INR",
        "payment_method": "upi",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "User cancelled UPI prompt.",
        "eligibility_status": "INELIGIBLE",
        "eligibility_reason": "MAX_ATTEMPTS_EXCEEDED",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Retry customer with new link.",
        "validated_policy": RecoveryPolicy.P_NO_ACTION.value,
        "guardrail_decision": PolicyDecision.REJECT.value,
        "guardrail_reasons": [
            "Customer exceeded maximum recovery link attempts in 24-hour window."
        ],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 40,
        "paid_offset_minutes": None,
        "why": "Demonstrates customer fatigue & spam prevention stopping rule.",
    },
    {
        "id": "CS10",
        "case_id": "case_demo_cs10_already_paid",
        "scenario": "Order Already Paid (Superfluous Retry Rejection)",
        "payment_id": "pay_demo_cs10_failed",
        "order_id": "order_demo_cs10_paid",
        "customer_id": "cust_demo_cs10",
        "amount": 350000,  # ₹3,500.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": (
            "Initial card attempt failed, but secondary attempt on same order succeeded."
        ),
        "eligibility_status": "INELIGIBLE",
        "eligibility_reason": "ORDER_ALREADY_PAID",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Send recovery link for failed payment.",
        "validated_policy": RecoveryPolicy.P_NO_ACTION.value,
        "guardrail_decision": PolicyDecision.REJECT.value,
        "guardrail_reasons": ["Order order_demo_cs10_paid is already paid; recovery suppressed."],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 45,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates order-level payment verification preventing double-charge/superfluous "
            "recovery."
        ),
    },
    {
        "id": "CS11",
        "case_id": "case_demo_cs11_delayed_due",
        "scenario": "Scheduled Delayed Recovery Matured & Executed",
        "payment_id": "pay_demo_cs11_failed",
        "order_id": "order_demo_cs11",
        "customer_id": "cust_demo_cs11",
        "amount": 120000,  # ₹1,200.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "CARD_DECLINED",
        "failure_description": "Temporary bank downtime during transaction.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "ai_explanation": "Schedule retry after bank maintenance window.",
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Scheduled delayed recovery authorized."],
        "payment_link_id": "plink_demo_cs11_delay",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS11",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs11_rec",
        "recovered_amount": 120000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": (BASE_TIME + timedelta(minutes=50)).isoformat(),
        "offset_minutes": 50,
        "paid_offset_minutes": 110,
        "why": (
            "Demonstrates scheduled delayed case maturation and autonomous restart-safe "
            "batch execution."
        ),
    },
    {
        "id": "CS12",
        "case_id": "case_demo_cs12_link_unpaid",
        "scenario": "Recovery Link Sent but Currently Unpaid (In-Flight)",
        "payment_id": "pay_demo_cs12_failed",
        "order_id": "order_demo_cs12",
        "customer_id": "cust_demo_cs12",
        "amount": 280000,  # ₹2,800.00
        "currency": "INR",
        "payment_method": "upi",
        "failure_category": FailureCategory.C2.value,
        "failure_code": "USER_DROPOUT",
        "failure_description": "Customer exited UPI checkout app.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": "Send immediate recovery link.",
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Immediate link authorized."],
        "payment_link_id": "plink_demo_cs12_active",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS12",
        "payment_link_status": "created",
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.ACTION_EXECUTED.value,
        "scheduled_at": None,
        "offset_minutes": 55,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates in-flight active recovery link state where link is created but "
            "not yet counted as recovered revenue."
        ),
    },
    {
        "id": "CS13",
        "case_id": "case_demo_cs13_duplicate_replay",
        "scenario": "Duplicate Webhook Replay (Idempotency Defense)",
        "payment_id": "pay_demo_cs13_failed",
        "order_id": "order_demo_cs13",
        "customer_id": "cust_demo_cs13",
        "amount": 300000,  # ₹3,000.00
        "currency": "INR",
        "payment_method": "upi",
        "failure_category": FailureCategory.C2.value,
        "failure_code": "GATEWAY_TIMEOUT",
        "failure_description": "Duplicate delivery of payment.failed webhook.",
        "eligibility_status": "INELIGIBLE",
        "eligibility_reason": "DUPLICATE_EVENT",
        "ai_policy": None,
        "ai_explanation": None,
        "validated_policy": None,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Duplicate webhook suppressed by event_id idempotency check."],
        "payment_link_id": None,
        "payment_link_short_url": None,
        "payment_link_status": None,
        "recovered_payment_id": None,
        "recovered_amount": None,
        "state": CaseState.TERMINAL_NO_ACTION.value,
        "scheduled_at": None,
        "offset_minutes": 60,
        "paid_offset_minutes": None,
        "why": (
            "Demonstrates duplicate event suppression; zero duplicate links or "
            "double-attribution allowed."
        ),
    },
    {
        "id": "CS14",
        "case_id": "case_demo_cs14_b2b_invoice",
        "scenario": "B2B Overdue Invoice Recovery",
        "payment_id": "pay_demo_cs14_failed",
        "order_id": "inv_demo_cs14_b2b",
        "customer_id": "cust_demo_cs14_corp",
        "amount": 1850000,  # ₹18,500.00
        "currency": "INR",
        "payment_method": "netbanking",
        "failure_category": FailureCategory.C1.value,
        "failure_code": "INVOICE_OVERDUE",
        "failure_description": "B2B commercial invoice unpaid at net-30 term expiration.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "ai_explanation": (
            "Overdue commercial invoice with positive credit record; dispatch direct link."
        ),
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_IMMEDIATE.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["B2B receivables recovery link authorized under ₹50,000 threshold."],
        "payment_link_id": "plink_demo_cs14_b2b",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS14",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs14_rec",
        "recovered_amount": 1850000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": None,
        "offset_minutes": 65,
        "paid_offset_minutes": 95,
        "why": "Demonstrates B2B receivables chaser direction within bounded autonomy guardrails.",
    },
    {
        "id": "CS15",
        "case_id": "case_demo_cs15_promise_to_pay",
        "scenario": "Promise-to-Pay (PTP) Tracker Scheduled Recovery",
        "payment_id": "pay_demo_cs15_failed",
        "order_id": "order_demo_cs15",
        "customer_id": "cust_demo_cs15",
        "amount": 400000,  # ₹4,000.00
        "currency": "INR",
        "payment_method": "card",
        "failure_category": FailureCategory.C3.value,
        "failure_code": "INSUFFICIENT_FUNDS",
        "failure_description": "Customer committed to pay on salary date.",
        "eligibility_status": "ELIGIBLE",
        "eligibility_reason": "ELIGIBLE",
        "ai_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "ai_explanation": (
            "Customer recorded promise to pay; pause aggressive retries until scheduled maturity."
        ),
        "validated_policy": RecoveryPolicy.P_CREATE_LINK_DELAYED.value,
        "guardrail_decision": PolicyDecision.APPROVE.value,
        "guardrail_reasons": ["Promise-to-pay scheduled recovery link authorized."],
        "payment_link_id": "plink_demo_cs15_ptp",
        "payment_link_short_url": "https://rzp.io/rzp/demoCS15",
        "payment_link_status": "paid",
        "recovered_payment_id": "pay_demo_cs15_rec",
        "recovered_amount": 400000,
        "state": CaseState.RECOVERED.value,
        "scheduled_at": (BASE_TIME + timedelta(hours=3)).isoformat(),
        "offset_minutes": 70,
        "paid_offset_minutes": 200,
        "why": "Demonstrates Promise-to-Pay workflow extension tracking customer commitments.",
    },
]


def generate_case_audit_trail(
    scenario: dict[str, Any], created_at: datetime
) -> list[dict[str, Any]]:
    """Generate chronological audit events for a canonical demonstration scenario."""
    case_id = scenario["case_id"]
    state = scenario["state"]
    val_policy = scenario["validated_policy"]
    events: list[dict[str, Any]] = []

    # 1. WEBHOOK_INGESTED
    t0 = created_at
    events.append(
        {
            "case_id": case_id,
            "event_type": "WEBHOOK_INGESTED",
            "actor": "system",
            "decision": "CASE_CREATED",
            "policy": None,
            "action": "INGEST",
            "outcome": "SUCCESS",
            "timestamp": t0,
            "details": {
                "payment_id": scenario["payment_id"],
                "amount_paise": scenario["amount"],
                "currency": scenario["currency"],
                "payment_method": scenario["payment_method"],
            },
            "guardrail_result": None,
        }
    )

    # 2. CONTEXT_ENRICHED
    t1 = t0 + timedelta(seconds=2)
    events.append(
        {
            "case_id": case_id,
            "event_type": "CONTEXT_ENRICHED",
            "actor": "system",
            "decision": "CONTEXT_RETRIEVED",
            "policy": None,
            "action": "ENRICH",
            "outcome": "SUCCESS",
            "timestamp": t1,
            "details": {
                "order_id": scenario["order_id"],
                "customer_id": scenario["customer_id"],
                "error_code": scenario["failure_code"],
                "error_description": scenario["failure_description"],
            },
            "guardrail_result": None,
        }
    )

    # 3. FAILURE_CLASSIFIED
    t2 = t1 + timedelta(seconds=1)
    events.append(
        {
            "case_id": case_id,
            "event_type": "FAILURE_CLASSIFIED",
            "actor": "system",
            "decision": scenario["failure_category"],
            "policy": None,
            "action": "CLASSIFY",
            "outcome": "SUCCESS",
            "timestamp": t2,
            "details": {
                "category": scenario["failure_category"],
                "classification_rule": f"RULE_{scenario['failure_category']}",
            },
            "guardrail_result": None,
        }
    )

    # 4. ELIGIBILITY_EVALUATED
    t3 = t2 + timedelta(seconds=1)
    events.append(
        {
            "case_id": case_id,
            "event_type": "ELIGIBILITY_EVALUATED",
            "actor": "system",
            "decision": scenario["eligibility_status"],
            "policy": None,
            "action": "CHECK_ELIGIBILITY",
            "outcome": "SUCCESS" if scenario["eligibility_status"] == "ELIGIBLE" else "TERMINATED",
            "timestamp": t3,
            "details": {
                "reason": scenario["eligibility_reason"],
                "passed_rules": 8 if scenario["eligibility_status"] == "ELIGIBLE" else 4,
            },
            "guardrail_result": None,
        }
    )

    if (
        scenario["eligibility_status"] == "INELIGIBLE"
        and state == CaseState.TERMINAL_NO_ACTION.value
    ):
        return events

    # 5. LLM_DECISION_PROPOSED
    if scenario["ai_policy"]:
        t4 = t3 + timedelta(seconds=2)
        events.append(
            {
                "case_id": case_id,
                "event_type": "LLM_DECISION_PROPOSED",
                "actor": "ai_agent",
                "decision": scenario["ai_policy"],
                "policy": scenario["ai_policy"],
                "action": "PROPOSE_ACTION",
                "outcome": "PROPOSAL_GENERATED",
                "timestamp": t4,
                "details": {
                    "model": "gemini-3.5-flash-lite",
                    "confidence_score": 0.95,
                    "reasoning": scenario["ai_explanation"],
                },
                "guardrail_result": None,
            }
        )

    # 6. POLICY_GUARDRAIL_VALIDATED
    t5 = t3 + timedelta(seconds=3)
    events.append(
        {
            "case_id": case_id,
            "event_type": "POLICY_GUARDRAIL_VALIDATED",
            "actor": "policy_engine",
            "decision": scenario["guardrail_decision"],
            "policy": val_policy,
            "action": "AUTHORIZE",
            "outcome": "SUCCESS" if scenario["guardrail_decision"] == "APPROVE" else "MODIFIED",
            "timestamp": t5,
            "details": {
                "effective_policy": val_policy,
                "reasons": scenario["guardrail_reasons"],
            },
            "guardrail_result": {
                "decision": scenario["guardrail_decision"],
                "passed": scenario["guardrail_decision"] == "APPROVE",
                "reasons": scenario["guardrail_reasons"],
            },
        }
    )

    if state == CaseState.ESCALATED.value or val_policy == RecoveryPolicy.P_NO_ACTION.value:
        return events

    # 7. RAZORPAY_PAYMENT_LINK_CREATED
    if scenario["payment_link_id"]:
        t6 = t5 + timedelta(seconds=2)
        events.append(
            {
                "case_id": case_id,
                "event_type": "RAZORPAY_PAYMENT_LINK_CREATED",
                "actor": "razorpay_adapter",
                "decision": "SUCCESS",
                "policy": val_policy,
                "action": "CREATE_LINK",
                "outcome": "LINK_CREATED",
                "timestamp": t6,
                "details": {
                    "link_id": scenario["payment_link_id"],
                    "short_url": scenario["payment_link_short_url"],
                    "amount_paise": scenario["amount"],
                },
                "guardrail_result": None,
            }
        )

    if state == CaseState.ACTION_EXECUTED.value:
        return events

    # 8. PAYMENT_VERIFIED
    if scenario["paid_offset_minutes"] and scenario["recovered_payment_id"]:
        t7 = t0 + timedelta(minutes=scenario["paid_offset_minutes"])
        events.append(
            {
                "case_id": case_id,
                "event_type": "PAYMENT_VERIFIED",
                "actor": "system",
                "decision": "VERIFIED",
                "policy": None,
                "action": "VERIFY_CAPTURE",
                "outcome": "CAPTURED",
                "timestamp": t7,
                "details": {
                    "recovered_payment_id": scenario["recovered_payment_id"],
                    "payment_link_id": scenario["payment_link_id"],
                    "status": "captured",
                },
                "guardrail_result": None,
            }
        )

        # 9. RECOVERY_ATTRIBUTED
        t8 = t7 + timedelta(seconds=1)
        events.append(
            {
                "case_id": case_id,
                "event_type": "RECOVERY_ATTRIBUTED",
                "actor": "system",
                "decision": "ATTRIBUTED",
                "policy": None,
                "action": "ATTRIBUTE_REVENUE",
                "outcome": "SUCCESS",
                "timestamp": t8,
                "details": {
                    "recovered_amount_paise": scenario["recovered_amount"],
                    "recovered_amount_inr": scenario["recovered_amount"] / 100.0,
                    "case_id": case_id,
                },
                "guardrail_result": None,
            }
        )

    return events


async def seed_canonical_demonstration_batch(
    session: AsyncSession,
    reset_first: bool = True,
) -> dict[str, Any]:
    """Seed the 15 canonical demonstration cases into PostgreSQL."""
    if reset_first:
        demo_case_ids = [sc["case_id"] for sc in CANONICAL_BATCH_SCENARIOS]
        await session.execute(
            delete(AuditEventModel).where(AuditEventModel.case_id.in_(demo_case_ids))
        )
        await session.execute(
            delete(RecoveryCaseModel).where(RecoveryCaseModel.case_id.in_(demo_case_ids))
        )
        await session.flush()

    seeded_cases: list[str] = []
    total_revenue_at_risk_paise = 0
    total_recovered_paise = 0

    for sc in CANONICAL_BATCH_SCENARIOS:
        created_at = BASE_TIME + timedelta(minutes=sc["offset_minutes"])
        updated_at = (
            BASE_TIME + timedelta(minutes=sc["paid_offset_minutes"])
            if sc["paid_offset_minutes"]
            else created_at + timedelta(minutes=5)
        )

        case = RecoveryCaseModel(
            case_id=sc["case_id"],
            failed_payment_id=sc["payment_id"],
            order_id=sc["order_id"],
            customer_id=sc["customer_id"],
            amount=sc["amount"],
            currency=sc["currency"],
            payment_method=sc["payment_method"],
            failure_category=sc["failure_category"],
            failure_code=sc["failure_code"],
            failure_description=sc["failure_description"],
            failure_context={"scenario": sc["scenario"], "why": sc["why"]},
            eligibility_status=sc["eligibility_status"],
            eligibility_reason=sc["eligibility_reason"],
            classification_evidence={"rule": f"RULE_{sc['failure_category']}"},
            ai_policy_id=sc["ai_policy"],
            ai_explanation=sc["ai_explanation"],
            validated_policy_id=sc["validated_policy"],
            action_status="EXECUTED" if sc["payment_link_id"] else "SKIPPED",
            payment_link_id=sc["payment_link_id"],
            payment_link_reference_id=f"FP-{sc['payment_id']}" if sc["payment_link_id"] else None,
            payment_link_short_url=sc["payment_link_short_url"],
            payment_link_status=sc["payment_link_status"],
            recovered_payment_id=sc["recovered_payment_id"],
            recovered_amount=sc["recovered_amount"],
            state=sc["state"],
            case_source="CANONICAL_EVALUATION",
            scheduled_at=datetime.fromisoformat(sc["scheduled_at"]) if sc["scheduled_at"] else None,
            created_at=created_at,
            updated_at=updated_at,
        )
        session.add(case)
        seeded_cases.append(sc["case_id"])
        total_revenue_at_risk_paise += sc["amount"]
        if sc["recovered_amount"]:
            total_recovered_paise += sc["recovered_amount"]

        # Add audit events
        audit_events = generate_case_audit_trail(sc, created_at)
        for ev in audit_events:
            audit = AuditEventModel(
                case_id=ev["case_id"],
                event_type=ev["event_type"],
                actor=ev["actor"],
                decision=ev["decision"],
                policy=ev["policy"],
                action=ev["action"],
                outcome=ev["outcome"],
                details=ev["details"],
                guardrail_result=ev["guardrail_result"],
                timestamp=ev["timestamp"],
            )
            session.add(audit)

    await session.commit()

    return {
        "status": "success",
        "seeded_cases_count": len(seeded_cases),
        "total_revenue_at_risk_inr": total_revenue_at_risk_paise / 100.0,
        "total_recovered_inr": total_recovered_paise / 100.0,
        "recovery_rate_pct": round((total_recovered_paise / total_revenue_at_risk_paise) * 100, 2),
        "cases": seeded_cases,
    }
