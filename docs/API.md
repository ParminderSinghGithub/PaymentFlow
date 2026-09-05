# PaymentFlow Recovery Agent — REST API Reference

## 1. Overview & Conventions

The PaymentFlow backend service exposes an asynchronous RESTful API built on FastAPI.

- **Base URL (Local)**: `http://localhost:8000`
- **Base URL (Live Production)**: `https://paymentflow-backend-production.up.railway.app`
- **Content-Type**: `application/json`
- **Interactive Documentation**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)

### Standard Error Response Format
All error responses return structured JSON:
```json
{
  "detail": "Descriptive error explanation",
  "status_code": 400
}
```

---

## 2. Health & Diagnostics Endpoints

### `GET /health`
Returns system operational diagnostics across backend components.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "ai_provider": "gemini",
  "ai_provider_status": "ready",
  "alembic_head": "0006_case_source_eval_runs"
}
```

---

## 3. Recovery Cases Endpoints

### `GET /cases`
List recovery cases with optional filtering, search, and pagination.

**Query Parameters**:
- `state` (optional, string): Filter by case state (`FAILED_INGESTED`, `ACTION_APPROVED`, `ACTION_EXECUTED`, `RECOVERED`, `ESCALATED`, `TERMINAL_NO_ACTION`).
- `case_source` (optional, string): Filter by source (`LIVE_CHECKOUT`, `CANONICAL_EVALUATION`).
- `eval_run_id` (optional, string): Filter by specific benchmark evaluation run ID.
- `search` (optional, string): Full-text query matching Case ID, Payment ID, Order ID, or Customer ID.
- `limit` (optional, int, default 50): Maximum records to return.
- `offset` (optional, int, default 0): Number of records to skip.

**Response `200 OK`**:
```json
[
  {
    "case_id": "eval_case_eval_run_20260905_120000_abc123_cs01",
    "failed_payment_id": "eval_opp_eval_run_20260905_120000_abc123_cs01",
    "order_id": "eval_ord_eval_run_20260905_120000_abc123_cs01",
    "customer_id": "cust_eval_cs01_checkout",
    "amount": 249900,
    "currency": "INR",
    "failure_category": "C1",
    "failure_code": "OTP_TIMEOUT",
    "failure_description": "OTP expired on customer checkout",
    "eligibility_status": "ELIGIBLE",
    "ai_policy_id": "P_CREATE_LINK_IMMEDIATE",
    "validated_policy_id": "P_CREATE_LINK_IMMEDIATE",
    "action_status": "EXECUTED",
    "payment_link_id": "eval_link_eval_run_20260905_120000_abc123_cs01",
    "payment_link_status": "issued",
    "payment_link_short_url": "https://pay.paymentflow.internal/eval/...",
    "recovered_payment_id": "eval_rec_eval_run_20260905_120000_abc123_cs01",
    "recovered_amount": 249900,
    "state": "RECOVERED",
    "case_source": "CANONICAL_EVALUATION",
    "created_at": "2026-09-05T12:00:00Z",
    "updated_at": "2026-09-05T12:02:00Z"
  }
]
```

---

### `GET /cases/{case_id}`
Retrieve a single recovery case including its complete decision story and chronological audit events.

**Response `200 OK`**:
```json
{
  "case": {
    "case_id": "case_live_cs01_xyz",
    "amount": 250000,
    "currency": "INR",
    "state": "RECOVERED",
    "failure_category": "C1",
    "ai_policy_id": "P_CREATE_LINK_IMMEDIATE",
    "ai_explanation": "Transient user checkout dropoff; immediate link provides frictionless retry.",
    "validated_policy_id": "P_CREATE_LINK_IMMEDIATE"
  },
  "audit_events": [
    {
      "event_type": "WEBHOOK_INGESTED",
      "actor": "system",
      "decision": "CASE_CREATED",
      "timestamp": "2026-09-05T12:00:00Z"
    },
    {
      "event_type": "POLICY_GUARDRAIL_VALIDATED",
      "actor": "policy_engine",
      "decision": "APPROVE",
      "policy": "P_CREATE_LINK_IMMEDIATE",
      "timestamp": "2026-09-05T12:00:03Z"
    },
    {
      "event_type": "RAZORPAY_PAYMENT_LINK_CREATED",
      "actor": "razorpay_adapter",
      "decision": "SUCCESS",
      "timestamp": "2026-09-05T12:00:05Z"
    },
    {
      "event_type": "PAYMENT_VERIFIED",
      "actor": "system",
      "decision": "VERIFIED",
      "timestamp": "2026-09-05T12:15:00Z"
    }
  ]
}
```

---

### `POST /cases/{case_id}/triage`
Manually trigger end-to-end triage and guardrail evaluation for a specific case.

**Response `200 OK`**:
```json
{
  "case_id": "case_live_cs01_xyz",
  "status": "TRIAGED",
  "state": "ACTION_EXECUTED",
  "failure_category": "C1",
  "effective_policy": "P_CREATE_LINK_IMMEDIATE"
}
```

---

### `POST /cases/delayed/process`
Trigger execution of all matured delayed recovery cases (`state == 'ACTION_APPROVED'` and `scheduled_at <= NOW()`).

**Response `200 OK`**:
```json
{
  "status": "success",
  "processed_count": 2,
  "executed_cases": ["case_delayed_001", "case_delayed_002"]
}
```

---

### `GET /cases/metrics/summary`
Retrieve aggregated operational metrics for the Operator Console.

**Query Parameters**:
- `case_source` (optional, string): Scope by `LIVE_CHECKOUT` or `CANONICAL_EVALUATION`.
- `eval_run_id` (optional, string): Scope by specific evaluation run.

**Response `200 OK`**:
```json
{
  "total_cases": 15,
  "total_at_risk_amount_inr": 122117.0,
  "total_recovered_amount_inr": 28648.0,
  "recovered_cases": 6,
  "eligible_cases": 7,
  "eligible_opportunity_amount_inr": 31538.0,
  "escalated_cases": 2,
  "terminal_no_action_cases": 6,
  "recovery_rate_pct": 23.46,
  "eligible_case_recovery_rate_pct": 85.71,
  "eligible_opportunity_recovery_rate_pct": 90.84,
  "overall_case_recovery_rate_pct": 40.0,
  "portfolio_revenue_recovery_rate_pct": 23.46,
  "case_source": "CANONICAL_EVALUATION"
}
```

---

## 4. Benchmark Execution Endpoints

### `POST /cases/benchmark/run`
Dynamically executes all 15 canonical scenarios through the full decision and guardrail layers.

**Response `200 OK`**:
```json
{
  "eval_run_id": "eval_run_20260905_120000_1a2b3c",
  "status": "COMPLETED",
  "case_source": "CANONICAL_EVALUATION",
  "total_cases": 15,
  "total_at_risk_amount_inr": 122117.0,
  "eligible_cases": 7,
  "eligible_opportunity_amount_inr": 31538.0,
  "recovery_actions_executed": 7,
  "recovery_actions_blocked": 8,
  "evaluation_recovered_cases": 6,
  "evaluation_recovered_amount_inr": 28648.0,
  "escalated_cases": 2,
  "escalated_amount_inr": 69750.0,
  "terminal_cases": 6,
  "terminal_amount_inr": 20829.0,
  "overall_case_recovery_rate_pct": 40.0,
  "eligible_case_recovery_rate_pct": 85.71,
  "portfolio_revenue_recovery_rate_pct": 23.46,
  "eligible_opportunity_recovery_rate_pct": 90.84,
  "cases": [...]
}
```

---

### `GET /cases/benchmark/latest`
Retrieve run-scoped metrics for the most recent canonical benchmark evaluation run.

**Response `200 OK`**: Returns the latest `BenchmarkLatestResponse` metrics object.

---

## 5. Webhook Ingestion Endpoints

### `POST /webhooks/razorpay`
Consumes signed Razorpay webhook notifications.

**Headers Required**:
- `X-Razorpay-Signature`: HMAC-SHA256 signature generated with `RAZORPAY_WEBHOOK_SECRET`.
- `X-Razorpay-Event-Id`: Unique event delivery identifier for idempotency.

**Response `200 OK`**:
```json
{
  "status": "acknowledged",
  "event_id": "evt_rzp_1234567890",
  "event_type": "payment.failed"
}
```

---

## 6. Merchant Integration API Endpoints (`/merchant/v1`)

These endpoints provide a secure server-to-server boundary for external merchant storefronts to register checkout context, initiate Razorpay orders, and poll safe customer recovery status.

**Authentication**:
All `/merchant/v1/*` endpoints require standard HTTP Bearer token authentication using the merchant's PaymentFlow API Key:
```http
Authorization: Bearer <PAYMENTFLOW_API_KEY>
```

### `GET /merchant/v1/verify`
Verify that merchant server credentials are authentic and active.

**Headers**:
- `Authorization: Bearer <PAYMENTFLOW_API_KEY>`

**Response `200 OK`**:
```json
{
  "status": "authenticated",
  "merchant_id": "merchant_demo_apex",
  "merchant_name": "Apex Gear Co.",
  "razorpay_key_id": "rzp_test_...",
  "is_active": true,
  "message": "Merchant API credential authenticated successfully."
}
```

---

### `POST /merchant/v1/checkout-context`
Register checkout metadata from the merchant server when a customer begins checkout, enabling enhanced diagnostics upon subsequent failure.

**Headers**:
- `Authorization: Bearer <PAYMENTFLOW_API_KEY>`
- `Content-Type: application/json`

**Request Body**:
```json
{
  "external_order_id": "order_M12345",
  "amount": 299900,
  "currency": "INR",
  "customer_email": "alex@example.com",
  "customer_phone": "+919876543210",
  "merchant_reference": "CART-9941"
}
```

**Response `200 OK`**:
```json
{
  "status": "accepted",
  "context_id": "mctx_a1b2c3d4e5f67890",
  "merchant_id": "merchant_demo_apex",
  "external_order_id": "order_M12345",
  "amount": 299900,
  "currency": "INR",
  "registered_at": "2026-09-05T12:00:00Z",
  "message": "Merchant checkout context registered successfully for recovery monitoring."
}
```

---

### `POST /merchant/v1/orders`
Initiates an official Razorpay Order using the merchant's server-side credentials and binds the checkout context in PaymentFlow.

**Headers**:
- `Authorization: Bearer <PAYMENTFLOW_API_KEY>`
- `Content-Type: application/json`

**Request Body**:
```json
{
  "amount": 249900,
  "currency": "INR",
  "external_order_id": "ORD-APEX-001",
  "customer_name": "Alex Sharma",
  "customer_email": "alex@example.com",
  "customer_phone": "+919876543210"
}
```

**Response `201 Created`**:
```json
{
  "status": "created",
  "context_id": "mctx_9876543210abcdef",
  "razorpay_order_id": "order_RzpOrder12345",
  "external_order_id": "ORD-APEX-001",
  "amount": 249900,
  "currency": "INR",
  "razorpay_key_id": "rzp_test_...",
  "checkout_url": "/merchant/checkout?context_id=mctx_9876543210abcdef",
  "message": "Razorpay order created and checkout context registered successfully."
}
```

---

### `GET /merchant/v1/orders/{order_id}/recovery-status`
Polls safe recovery status for an order. Returns high-level customer status without exposing internal AI reasoning, database IDs, or sensitive gateway tokens.

**Path Parameters**:
- `order_id` (required, string): Razorpay Order ID or Merchant External Order ID.

**Headers**:
- `Authorization: Bearer <PAYMENTFLOW_API_KEY>`

**Response `200 OK`**:
```json
{
  "order_id": "order_RzpOrder12345",
  "case_id": "case_live_001",
  "case_source": "MERCHANT_CHECKOUT",
  "state": "RECOVERED",
  "amount": 249900,
  "currency": "INR",
  "payment_link_sent": true,
  "payment_link_url": "https://rzp.io/rzp/rec001",
  "payment_link_status": "paid",
  "recovered_amount": 249900,
  "recovered_payment_id": "pay_rec12345",
  "notification_medium": "sms",
  "notification_status": "SENT",
  "masked_contact": "+91 98*** **210",
  "delivery_verified": true,
  "message": "Payment recovered successfully! Recovered amount: INR 2499.00."
}
```
