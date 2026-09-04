"""Canonical benchmark evaluation scenarios for PaymentFlow Recovery Agent.

Defines 15 realistic scenarios with distinct INR amounts, realistic failure codes,
and authentic conditions to exercise detection, classification, deterministic eligibility,
advisory policy, guardrails, and recovery actions.
"""

from typing import Any

CANONICAL_BENCHMARK_SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "CS01",
        "title": "Checkout OTP Dropout",
        "category": "C1",
        "failure_code": "OTP_TIMEOUT",
        "failure_description": "OTP expired on customer checkout",
        "amount_paise": 249900,  # ₹2,499.00
        "currency": "INR",
        "customer_id": "cust_eval_cs01_checkout",
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "otp_timeout",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": (
            "Customer dropped off due to OTP timeout on checkout; immediate link authorized."
        ),
        "proposed_amount_paise": 249900,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Link Executed -> Evaluation Recovered
    },
    {
        "scenario_id": "CS02",
        "title": "Gateway PSP Network Drop",
        "category": "C2",
        "failure_code": "GATEWAY_ERROR",
        "failure_description": "Payment failed due to PSP network drop / timeout during auth",
        "amount_paise": 385000,  # ₹3,850.00
        "currency": "INR",
        "customer_id": "cust_eval_cs02_psp",
        "failure_context": {
            "error_source": "gateway",
            "error_step": "payment_authorization",
            "error_reason": "network_timeout",
        },
        "advisory_policy": "P_CREATE_LINK_DELAYED",
        "advisory_explanation": (
            "Network timeout during auth; scheduled delayed recovery link with backoff cooldown."
        ),
        "proposed_amount_paise": 385000,
        "proposed_currency": "INR",
        "is_delayed": True,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Delayed Scheduled -> Evaluation Recovered
    },
    {
        "scenario_id": "CS03",
        "title": "Card Limit Threshold Exceeded",
        "category": "C3",
        "failure_code": "CARD_NOT_SUPPORTED",
        "failure_description": "Insufficient limit or card balance ceiling hit",
        "amount_paise": 129900,  # ₹1,299.00
        "currency": "INR",
        "customer_id": "cust_eval_cs03_balance",
        "failure_context": {
            "error_source": "bank",
            "error_step": "payment_authorization",
            "error_reason": "card_limit_exceeded",
        },
        "advisory_policy": "P_CREATE_LINK_DELAYED",
        "advisory_explanation": (
            "Card balance ceiling hit; delayed link scheduled for replenishment window."
        ),
        "proposed_amount_paise": 129900,
        "proposed_currency": "INR",
        "is_delayed": True,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Delayed Scheduled -> Evaluation Recovered
    },
    {
        "scenario_id": "CS04",
        "title": "High-Ticket Purchase Escalation",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "High-value commercial transaction checkout cancellation",
        "amount_paise": 6500000,  # ₹65,000.00 (> ₹50,000 threshold!)
        "currency": "INR",
        "customer_id": "cust_eval_cs04_vip",
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "payment_cancelled",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "High-value transaction dropout; proposed immediate link.",
        "proposed_amount_paise": 6500000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "ESCALATED",  # High-value guardrail escalates to P_ESCALATE_ONLY
    },
    {
        "scenario_id": "CS05",
        "title": "AML / Risk Filter Rejection",
        "category": "C4",
        "failure_code": "RISK_CHECK_FAILED",
        "failure_description": "Anti-money laundering / risk filter rejected transaction",
        "amount_paise": 475000,  # ₹4,750.00
        "currency": "INR",
        "customer_id": "cust_eval_cs05_risk",
        "failure_context": {
            "error_source": "risk",
            "error_step": "payment_risk_check",
            "error_reason": "aml_velocity_flag",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Risk review flagged velocity limit; proposed link.",
        "proposed_amount_paise": 475000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "ESCALATED",  # C4 category guardrail downgrades to P_ESCALATE_ONLY
    },
    {
        "scenario_id": "CS06",
        "title": "Acquiring Gateway Internal Failure",
        "category": "C5",
        "failure_code": "INVALID_REQUEST_ERROR",
        "failure_description": "Acquiring gateway HTTP 500 internal server error / malformed auth",
        "amount_paise": 189000,  # ₹1,890.00
        "currency": "INR",
        "customer_id": "cust_eval_cs06_sys",
        "failure_context": {
            "error_source": "gateway",
            "error_step": "payment_processing",
            "error_reason": "internal_error",
        },
        "advisory_policy": "P_NO_ACTION",
        "advisory_explanation": "Technical failure; no automated recovery link permitted.",
        "proposed_amount_paise": 189000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # C5 category -> TERMINAL_NO_ACTION
    },
    {
        "scenario_id": "CS07",
        "title": "Amount Mutation Guardrail Rejection",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Interrupted checkout; adversarial discount mutation attempted",
        "amount_paise": 599900,  # ₹5,999.00
        "currency": "INR",
        "customer_id": "cust_eval_cs07_mut",
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "payment_failed",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Proposed 10% discounted recovery link.",
        "proposed_amount_paise": 539900,  # ₹5,399.00 (MUTATION! DOES NOT MATCH ORIGINAL)
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # Amount mutation fails -> TERMINAL_NO_ACTION
    },
    {
        "scenario_id": "CS08",
        "title": "Currency Mutation Guardrail Rejection",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Checkout dropoff; adversarial currency mutation attempted",
        "amount_paise": 420000,  # ₹4,200.00
        "currency": "INR",
        "customer_id": "cust_eval_cs08_cur",
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "payment_cancelled",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Proposed USD denominated recovery link.",
        "proposed_amount_paise": 420000,
        "proposed_currency": "USD",  # MUTATION! CURRENCY DOES NOT MATCH INR
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # Currency mutation fails -> TERMINAL_NO_ACTION
    },
    {
        "scenario_id": "CS09",
        "title": "Recovery Attempt Cooldown Stop",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "4th repeated checkout failure within 24-hour window",
        "amount_paise": 215000,  # ₹2,150.00
        "currency": "INR",
        "customer_id": "cust_eval_cs09_frequent",
        "setup_prior_attempts": 3,
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "payment_cancelled",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Customer repeatedly failed; attempt link.",
        "proposed_amount_paise": 215000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # Cooldown triggers -> TERMINAL_NO_ACTION
    },
    {
        "scenario_id": "CS10",
        "title": "Already-Paid Order Stop",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Order already settled via secondary parallel transaction",
        "amount_paise": 349000,  # ₹3,490.00
        "currency": "INR",
        "customer_id": "cust_eval_cs10_paid",
        "order_id": "order_eval_cs10_paid",
        "setup_order_already_paid": True,
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "order_already_paid": True,
            "error_reason": "secondary_success",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Order marked paid; attempted recovery link.",
        "proposed_amount_paise": 349000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # Order already paid -> TERMINAL_NO_ACTION
    },
    {
        "scenario_id": "CS11",
        "title": "Delayed Recovery Matured & Executed",
        "category": "C2",
        "failure_code": "BANK_UNAVAILABLE",
        "failure_description": "Late-night payment drop during core banking downtime",
        "amount_paise": 175000,  # ₹1,750.00
        "currency": "INR",
        "customer_id": "cust_eval_cs11_matured",
        "failure_context": {
            "error_source": "bank",
            "error_step": "payment_authorization",
            "error_reason": "scheduled_maintenance",
        },
        "advisory_policy": "P_CREATE_LINK_DELAYED",
        "advisory_explanation": "Bank maintenance scheduled; delayed recovery link authorized.",
        "proposed_amount_paise": 175000,
        "proposed_currency": "INR",
        "is_delayed": True,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Delayed Scheduled -> Evaluation Recovered
    },
    {
        "scenario_id": "CS12",
        "title": "Recovery Link In-Flight Unpaid (Unrecovered Opportunity)",
        "category": "C2",
        "failure_code": "GATEWAY_ERROR",
        "failure_description": "PSP dropoff during payment processing",
        "amount_paise": 289000,  # ₹2,890.00
        "currency": "INR",
        "customer_id": "cust_eval_cs12_unpaid",
        "failure_context": {
            "error_source": "gateway",
            "error_step": "payment_authorization",
            "error_reason": "network_timeout",
        },
        "advisory_policy": "P_CREATE_LINK_DELAYED",
        "advisory_explanation": (
            "Delayed payment link scheduled with banking cooldown; awaiting customer response."
        ),
        "proposed_amount_paise": 289000,
        "proposed_currency": "INR",
        "is_delayed": True,
        "evaluation_outcome": "NOT_RECOVERED",  # Delayed Scheduled -> In-Flight Unpaid
    },
    {
        "scenario_id": "CS13",
        "title": "Duplicate Webhook Replay Rejection",
        "category": "C2",
        "failure_code": "GATEWAY_ERROR",
        "failure_description": "Duplicate payment failure event received from network replay",
        "amount_paise": 310000,  # ₹3,100.00
        "currency": "INR",
        "customer_id": "cust_eval_cs13_replay",
        "setup_has_existing_link": True,
        "failure_context": {
            "error_source": "gateway",
            "error_step": "payment_authorization",
            "is_duplicate_event": True,
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "Attempt duplicate link for existing case.",
        "proposed_amount_paise": 310000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "NOT_RECOVERED",  # Has link -> Ineligible ALREADY_ATTEMPTED -> STOP
    },
    {
        "scenario_id": "CS14",
        "title": "Commercial B2B Receivables",
        "category": "C1",
        "failure_code": "BAD_REQUEST_ERROR",
        "failure_description": "Overdue commercial B2B merchant invoice session timeout",
        "amount_paise": 1475000,  # ₹14,750.00
        "currency": "INR",
        "customer_id": "cust_eval_cs14_corp",
        "failure_context": {
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "session_expired",
        },
        "advisory_policy": "P_CREATE_LINK_IMMEDIATE",
        "advisory_explanation": "B2B commercial receivable; authorized immediate recovery link.",
        "proposed_amount_paise": 1475000,
        "proposed_currency": "INR",
        "is_delayed": False,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Link Executed -> Evaluation Recovered
    },
    {
        "scenario_id": "CS15",
        "title": "Promise-to-Pay (PTP) Tracker Maturation",
        "category": "C3",
        "failure_code": "CARD_NOT_SUPPORTED",
        "failure_description": "Card limit temporary hold, promise to pay next business day",
        "amount_paise": 450000,  # ₹4,500.00
        "currency": "INR",
        "customer_id": "cust_eval_cs15_ptp",
        "failure_context": {
            "error_source": "bank",
            "error_step": "payment_authorization",
            "error_reason": "temporary_hold",
        },
        "advisory_policy": "P_CREATE_LINK_DELAYED",
        "advisory_explanation": (
            "Promise-to-pay reached; scheduled delayed link for agreed morning hour."
        ),
        "proposed_amount_paise": 450000,
        "proposed_currency": "INR",
        "is_delayed": True,
        "evaluation_outcome": "RECOVERED",  # Eligible -> Delayed Scheduled -> Evaluation Recovered
    },
]
