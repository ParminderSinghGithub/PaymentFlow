# PaymentFlow Recovery Agent — Merchant Demo & Integration

## 1. Overview & Architecture

The **PaymentFlow Merchant Demo** (`apps/merchant-demo/`) is a standalone e-commerce storefront simulating real merchant checkout flows, payment failures, and end-to-end recovery loops. It proves that PaymentFlow integrates with existing Razorpay merchants with **zero code modifications to merchant core checkout code**.

```text
┌───────────────────────────┐                    ┌───────────────────────────┐
│    Merchant Storefront    │                    │    PaymentFlow Backend    │
│  (apps/merchant-demo/)    │                    │     (src/paymentflow/)    │
└─────────────┬─────────────┘                    └─────────────┬─────────────┘
              │                                                │
              │ 1. Customer initiates checkout                 │
              │ 2. Payment fails at gateway                    │
              │                                                │
              │ 3. payment.failed Webhook (HMAC-SHA256 signed) │
              ├───────────────────────────────────────────────►│
              │                                                │ 4. Triage & Classify
              │                                                │ 5. Guardrail Gate
              │                                                │ 6. Create Payment Link
              │ 7. Payment Link Generated                      │
              │◄───────────────────────────────────────────────┤
              │                                                │
              │ 8. Customer pays via Recovery Link             │
              │ 9. payment_link.paid Webhook                   │
              ├───────────────────────────────────────────────►│
              │                                                │ 10. Verify Captured
              │                                                │ 11. Attribute Revenue
              │ 12. Order Marked Paid                          │
              │◄───────────────────────────────────────────────┤
```

---

## 2. Webhook Ingestion & Cryptographic Verification

PaymentFlow consumes standard Razorpay webhooks over HTTPS:

- **Endpoint**: `POST /webhooks/razorpay`
- **Supported Events**:
  - `payment.failed`: Triggers the recovery triage and action pipeline.
  - `payment_link.paid`: Triggers capture verification and revenue attribution.
  - `payment.authorized` / `payment.captured`: Updates order and payment settlement status.

### Cryptographic Signature Verification
To prevent replay attacks and spoofed webhook injections, every webhook payload is verified using HMAC-SHA256:

```python
import hmac
import hashlib

def verify_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

If the signature header is missing, malformed, or does not match, the request is rejected immediately with HTTP 400.

---

## 3. Merchant Configuration & Key Binding

Merchants configure their Razorpay account in PaymentFlow via standard credentials:

```bash
# Razorpay Merchant Credentials
RAZORPAY_KEY_ID="rzp_test_..."
RAZORPAY_KEY_SECRET="your_rzp_secret"
RAZORPAY_WEBHOOK_SECRET="your_webhook_secret"

# Merchant App Configuration
MERCHANT_API_BASE_URL="http://localhost:8001"
PAYMENTFLOW_BACKEND_URL="http://localhost:8000"
```

### Zero Secrets Shipped to Customer Browsers
Merchant API secrets are used exclusively on the server side by the backend `RazorpayAdapter`. The merchant storefront frontend communicates only with the merchant backend and Razorpay Checkout JS.

---

## 4. Interactive Failure Simulation in Merchant Demo

The Merchant Demo storefront provides a built-in **Failure Simulation Toolbar** enabling evaluators to trigger specific failure scenarios with a single click:

| Button / Trigger | Category | Error Code Simulated | Amount | Expected Agent Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **"Simulate OTP Timeout"** | C1 | `OTP_TIMEOUT` | ₹2,499.00 | Immediate recovery link dispatched |
| **"Simulate Gateway Timeout"** | C2 | `GATEWAY_TIMEOUT` | ₹3,850.00 | Delayed link scheduled with backoff |
| **"Simulate Balance Limit"** | C3 | `INSUFFICIENT_FUNDS` | ₹1,299.00 | Delayed link scheduled for replenishment |
| **"Simulate High-Ticket VIP"** | C1 | `BAD_REQUEST_ERROR` | ₹65,000.00 | **Guardrail Escalate**: Forced to human review |
| **"Simulate AML Rejection"** | C4 | `RISK_CHECK_FAILED` | ₹4,750.00 | **Guardrail Escalate**: Automated link blocked |
| **"Simulate Technical Defect"** | C5 | `INVALID_REQUEST_ERROR`| ₹1,890.00 | **Terminal Stop**: No action permitted |

---

## 5. End-to-End Live Demonstration Workflow

To demonstrate the full merchant loop:

1. **Open Merchant Demo**: Visit `https://merchant-demo-production.up.railway.app` (or `http://localhost:8001` locally).
2. **Add Item to Cart & Checkout**: Select any product (e.g., "Smart Noise-Cancelling Headphones" ₹2,499.00).
3. **Trigger Failure**: In the checkout modal, choose **"Simulate OTP Dropoff"**.
4. **Inspect Operator Console**:
   - Open the Operator Console (`https://paymentflow-recovery-agent.vercel.app`).
   - Notice the new failed transaction appears in the Live Cases Stream within seconds.
   - Click the case to open the **Decision Story**: observe the classification (`C1`), AI recommendation (`P_CREATE_LINK_IMMEDIATE`), guardrail validation (`APPROVE`), and link creation.
5. **Complete Recovery**:
   - In the Decision Story, click the generated Razorpay Payment Link short URL (or simulated payment button in test mode).
   - Complete the recovery payment.
6. **Verify Attribution**:
   - Return to the Operator Console: the case transitions to `RECOVERED`.
   - The recovered amount (₹2,499.00) is credited to the merchant's Recovered Revenue KPI.
   - The Merchant Demo order status automatically updates to **"Order Confirmed & Paid"**.
