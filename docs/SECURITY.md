# PaymentFlow Recovery Agent — Security & Privacy Architecture

## 1. Threat Model in AI Financial Recovery

Autonomous revenue recovery agents introduce unique attack surfaces requiring defense-in-depth security:

| Threat Vector | Description | PaymentFlow Defense Layer |
| :--- | :--- | :--- |
| **Prompt Injection / Tampering** | Adversarial payload tricking LLM into generating discounted payment links | **Amount Immutability**: Reject any amount mutation (`proposed != original`) |
| **Currency Arbitrage** | Malicious input requesting link in a cheaper foreign currency | **Currency Immutability**: Enforce strictly `INR` |
| **High-Ticket Automation Risk** | Bot or compromised order generating automated links for $> ₹50,000$ | **High-Value Cap**: Deterministic forced escalation to human review |
| **Webhook Replay Attack** | Intercepted webhook re-delivered to trigger multiple duplicate recovery links | **Idempotency Engine**: Deduplication on `event_id` & Single-Link Invariant |
| **Customer Spamming / Harassment** | Repeatedly triggering recovery links to a target phone/email | **Customer Cooldown**: Enforce max 3 attempts per rolling 24-hour window |
| **Phantom Revenue Inflation** | Crediting recovered revenue before money is actually captured | **Captured-Only Attribution**: Require verified Razorpay `captured` webhook |
| **PII / Card Data Leakage** | Exposing customer PANs, CVVs, or phone numbers to external LLM providers | **Sanitized DecisionContext**: Zero cardholder data ingested or passed to AI |

---

## 2. Cryptographic Webhook Security

All external communication from Razorpay to PaymentFlow is cryptographically authenticated:

- **Algorithm**: HMAC-SHA256
- **Header**: `X-Razorpay-Signature`
- **Verification Logic**: Computed using the shared secret (`RAZORPAY_WEBHOOK_SECRET`) against the raw request body bytes.
- **Timing Attack Defense**: Uses `hmac.compare_digest` to prevent timing-based side-channel attacks.
- **Fail-Closed**: Requests with invalid or missing signatures are rejected immediately with HTTP 400.

---

## 3. Defense-in-Depth Pre-Write Validation

PaymentFlow enforces **Defense-in-Depth**: safety checks are executed multiple times across the transaction pipeline:

1. **Initial Eligibility Evaluation (Layer 2)**: Rejects stale, multi-currency, or unrecoverable technical defects.
2. **PolicyGuardrailEngine (Layer 4)**: Intercepts the LLM's proposal, verifying all 5 mathematical invariants.
3. **RecoveryExecutor Pre-Write Check (Layer 5)**: Re-validates the case state and executes a `SELECT ... FOR UPDATE` row lock immediately before calling the Razorpay Gateway API, ensuring concurrent requests cannot trigger race conditions.

---

## 4. PCI-DSS Compliance & Cardholder Data Boundaries

PaymentFlow is architecturally exempt from PCI-DSS scope requirements because **it never handles, processes, transmits, or stores raw cardholder data**:

- **No Card PANs**: Primary Account Numbers never enter the PaymentFlow application or database.
- **No CVVs or PINs**: Authentication credentials remain solely on the customer device and Razorpay's PCI-DSS Level 1 certified checkout environment.
- **Tokenized Identifiers**: PaymentFlow operates exclusively on opaque gateway references:
  - `pay_...` (Payment ID)
  - `order_...` (Order ID)
  - `plink_...` (Payment Link ID)
  - `cust_...` (Customer ID)

---

## 5. PII Masking & AI Provider Privacy

When delegating advisory reasoning to Google Gemini via the MCP boundary, PaymentFlow strips all customer personal data:

- **Excluded Fields**: Customer names, email addresses, phone numbers, shipping addresses, and IP addresses are **strictly excluded** from `DecisionContext`.
- **Allowed Diagnostics**: The model receives only:
  - Transaction amount in paise
  - Normalized failure code (e.g., `OTP_TIMEOUT`)
  - Gateway error step (e.g., `payment_authentication`)
  - Generic tenure bracket (e.g., `customer_tenure_months: 12`)
- **Zero Training on Merchant Data**: Live API calls utilize Google Gemini commercial endpoints where customer prompts are not used for model training or retained.

---

## 6. Immutable Audit Trail & Non-Repudiation

Every transition in a case's lifecycle creates a permanent, append-only record in the `audit_events` PostgreSQL table:

```sql
CREATE TABLE audit_events (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    actor VARCHAR(64) NOT NULL,
    decision VARCHAR(64) NOT NULL,
    policy VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    outcome VARCHAR(64) NOT NULL,
    details JSONB NOT NULL,
    guardrail_result JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

- **Append-Only Invariant**: The database role for the application service does not possess `UPDATE` or `DELETE` permissions on `audit_events`.
- **Complete Provenance**: Every row records what happened, which subsystem acted (`ai_agent`, `policy_engine`, `razorpay_adapter`, `system`), the exact policy evaluated, and full diagnostic payloads.
