# PaymentFlow Recovery Agent — Recovery Engine

## 1. End-to-End Recovery Lifecycle

The PaymentFlow Recovery Engine manages the complete stateful lifecycle of a failed payment from initial gateway event to verified captured cash:

```text
1. INGESTION
   Razorpay webhook (payment.failed) delivers failed transaction payload
   │
   ▼
2. ENRICHMENT & CLASSIFICATION
   RecoveryContext enriched; failure categorized into C1–C5 taxonomy
   │
   ▼
3. DETERMINISTIC ELIGIBILITY
   Validates currency (INR), age (<72h), and unpaid status
   │
   ▼
4. ADVISORY AI PROPOSAL & GUARDRAIL GATE
   LLM proposes strategy; PolicyGuardrailEngine validates invariants
   │
   ▼
5. ACTION DISPATCH
   Immediate Link Dispatch OR Restart-Safe Delayed Scheduling
   │
   ▼
6. CAPTURED REVENUE ATTRIBUTION
   payment_link.paid webhook verified; 100% captured revenue attributed
```

---

## 2. Failure Classification & Taxonomy (C1–C5)

PaymentFlow categorizes failures into five normalized failure classes:

| Category | Name | Diagnostic Signals | Default Strategy | Target Recovery Window |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | Customer Checkout Dropoff | `OTP_TIMEOUT`, `BAD_REQUEST_ERROR`, `USER_DROPPED_OFF` | `P_CREATE_LINK_IMMEDIATE` | Immediate ($< 15$ minutes) |
| **C2** | Network & Gateway Timeout | `GATEWAY_TIMEOUT`, `GATEWAY_ERROR`, `BANK_UNAVAILABLE` | `P_CREATE_LINK_DELAYED` | Cooldown ($15\text{m} \dots 2\text{h}$) |
| **C3** | Instrument / Balance Limits | `INSUFFICIENT_FUNDS`, `CARD_NOT_SUPPORTED`, `LIMIT_EXCEEDED`| `P_CREATE_LINK_DELAYED` | Replenishment ($2\text{h} \dots 24\text{h}$) |
| **C4** | Risk & AML Rejection | `RISK_CHECK_FAILED`, `AML_FLAG`, `FRAUD_SUSPECTED` | `P_ESCALATE_ONLY` | Human Compliance Review |
| **C5** | Technical & Integration Defect | `INVALID_REQUEST_ERROR`, `GATEWAY_INTERNAL_ERROR` | `P_NO_ACTION` | Engineering Triage |

---

## 3. Deterministic Eligibility Rules

Before any AI advisory reasoning occurs, `RecoveryTriageService` evaluates eight deterministic eligibility criteria:

1. **Currency**: Transaction currency must strictly be `INR`. Non-INR transactions are marked `INELIGIBLE_CURRENCY`.
2. **Transaction Freshness**: The failed payment must have occurred within the last 72 hours. Stale records are marked `INELIGIBLE_STALE`.
3. **Current Payment Status**: The associated order must not have already been settled via a parallel or secondary attempt. Marked `INELIGIBLE_ORDER_ALREADY_PAID`.
4. **Prior Attempt Cooldown**: The customer must not have exceeded 3 recovery links in the preceding 24 hours. Marked `INELIGIBLE_COOLDOWN`.
5. **Single Active Link**: The case must not already have an open, unpaid recovery link. Marked `INELIGIBLE_ALREADY_ATTEMPTED`.
6. **Failure Recoverability**: C5 technical defects and non-recoverable API configuration errors are marked `INELIGIBLE_UNSUPPORTED_FAILURE`.
7. **High-Value Cap**: Transactions exceeding ₹50,000 are marked `REQUIRES_ESCALATION` rather than eligible for automated payment links.
8. **State Freshness**: The case must be in a valid pre-execution state (`FAILED_INGESTED` or `CONTEXT_RETRIEVED`).

---

## 4. Execution Strategies: Immediate vs. Delayed

### Immediate Recovery (`P_CREATE_LINK_IMMEDIATE`)
- **Use Case**: High-intent customer dropoffs, expired OTPs, or soft checkout abandonment (C1).
- **Execution**:
  1. Acquires database row lock via `SELECT ... FOR UPDATE` on `recovery_cases`.
  2. Invokes Razorpay Payment Link API (`POST /v1/payment_links`).
  3. Attaches tracking metadata: `case_id`, `failed_payment_id`, and `recovery_source`.
  4. Stores `payment_link_id`, `payment_link_short_url`, and sets state to `ACTION_EXECUTED`.
  5. Appends `RAZORPAY_PAYMENT_LINK_CREATED` event to audit trail.

### Restart-Safe Delayed Recovery (`P_CREATE_LINK_DELAYED`)
- **Use Case**: Transient network timeouts (C2) or card balance limits (C3) where an immediate retry would fail against an unrecovered banking pipe or unreplenished balance.
- **The Problem with In-Memory Delays**: Standard Python `asyncio.sleep()` or celery timers drop jobs if containers restart, deploy, or autoscale.
- **The PaymentFlow Solution**:
  1. Computes target maturity timestamp (e.g., $T_0 + 30\text{ minutes}$ or $T_0 + 2\text{ hours}$).
  2. Persists `scheduled_at` in the PostgreSQL database record with state `ACTION_APPROVED`.
  3. Releasing the process immediately with zero blocked threads.
  4. Background worker polls `SELECT * FROM recovery_cases WHERE state = 'ACTION_APPROVED' AND scheduled_at <= NOW()`.
  5. **Pre-Write Freshness Re-check**: At execution time, the worker re-queries Razorpay Gateway APIs to verify that the customer has not already paid through another channel before dispatching the link.

---

## 5. Razorpay Adapter & API Integration

The `RazorpayAdapter` abstracts all interactions with Razorpay Gateway APIs:

- **Authentication**: HTTP Basic Auth with `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
- **Payment Link Payload**:
  ```json
  {
    "amount": 250000,
    "currency": "INR",
    "accept_partial": false,
    "reference_id": "FP-pay_demo_cs01_failed",
    "description": "Payment Recovery for Order order_demo_cs01",
    "customer": {
      "name": "Customer cust_demo_cs01",
      "contact": "+919876543210"
    },
    "notify": {"sms": true, "email": true},
    "reminder_enable": true,
    "notes": {
      "case_id": "case_demo_cs01_otp_dropoff",
      "recovery_agent": "paymentflow-v1"
    }
  }
  ```
- **Error Handling**: Gracefully maps gateway rate limits (HTTP 429), authentication errors (HTTP 401), and upstream timeouts with exponential backoff.

---

## 6. Captured-Only Revenue Attribution

A cornerstone of financial integrity in PaymentFlow is **captured-only revenue attribution**:

> **Rule**: No revenue is ever attributed upon link creation, SMS delivery, or link opening. Revenue is attributed if and only if funds are verified as `captured` by Razorpay.

### Attribution Verification Flow
1. **Webhook Ingestion**: Razorpay delivers a signed `payment_link.paid` webhook.
2. **Signature Check**: Verified via HMAC-SHA256 signature verification.
3. **Gateway Verification**: The adapter queries `GET /v1/payments/{payment_id}` to confirm `status === "captured"`.
4. **Amount Verification**: The captured amount must match the original failed transaction amount exactly.
5. **State Transition**: Case transitions to `RECOVERED`; `recovered_amount` and `recovered_payment_id` are persisted.
6. **Audit Event**: Appends `RECOVERY_ATTRIBUTED` event documenting exact paise and INR credited.
