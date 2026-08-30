# PaymentFlow Recovery Agent — Evaluation Methodology (Layer 5)

## 1. Dataset Design & Purpose
The Layer 5 evaluation environment uses a reproducible synthetic dataset of **75 failed-payment cases** to benchmark recovery strategies (Rule-Based Baseline vs. LLM Agent + Policy Guardrails).

The dataset is constructed to reflect real-world failed payment dynamics across Razorpay's normalized **C1–C5 failure taxonomy**:
- **C1 (18 cases, 24%)**: Temporary / Retryable Issuer or Gateway Degradation (e.g., `GATEWAY_ERROR`, `BAD_REQUEST_GATEWAY_TIMEOUT`, `NETWORK_ERROR`).
- **C2 (20 cases, 27%)**: Soft User / Infrastructure Friction (e.g., `USER_DROPPED_OFF`, `OTP_TIMEOUT`, `AUTHENTICATION_FAILED`).
- **C3 (16 cases, 21%)**: Hard Payment-Instrument Failure (e.g., `INSUFFICIENT_FUNDS`, `CARD_EXPIRED`, `LIMIT_EXCEEDED`).
- **C4 (11 cases, 15%)**: Business / Risk / Limit Rejection (e.g., `FRAUD_SUSPECTED`, `CARD_BLOCKED_RISK`, `AML_CHECK_FAILED`).
- **C5 (10 cases, 13%)**: Technical Integration / Non-Recoverable Failure (e.g., `INVALID_MERCHANT_KEY`, `INVALID_REQUEST_PARAMETERS`, `UNSUPPORTED_CURRENCY`).

The dataset includes **8 high-value cases** (> ₹50,000 / 5,000,000 paise) across categories C1, C2, C3, and C4, 3 multi-currency cases (USD, EUR), and active cooldown cases.

---

## 2. Strict Ground-Truth Isolation & No-Leakage Controls
The schema maintains explicit separation between what is visible at decision time vs. what the simulator uses:
```text
┌─────────────────────────────────────────────────────────────┐
│                       EvaluationCase                        │
├──────────────────────────────┬──────────────────────────────┤
│       DecisionContext        │    SimulationGroundTruth     │
│   (Agent & Baseline Visible) │       (Simulator Only)       │
├──────────────────────────────┼──────────────────────────────┤
│ • case_id                    │ • customer_intent_score      │
│ • failed_payment_id          │ • p_recovery_no_action       │
│ • amount (paise)             │ • p_recovery_immediate_link  │
│ • currency                   │ • p_recovery_delayed_link    │
│ • payment_method             │ • p_recovery_escalate        │
│ • failure_code/desc/source   │ • notes                      │
│ • failure_category (C1-C5)   │                              │
│ • customer_tenure_months     │                              │
│ • prior_failed_count_24h     │                              │
│ • prior_recovered_count_24h │                              │
│ • last_attempt_at            │                              │
└──────────────────────────────┴──────────────────────────────┘
```
- **Isolation Controls**:
  1. Typed schema separation between `DecisionContext` and `SimulationGroundTruth`.
  2. Pydantic `extra="forbid"` on `DecisionContext`, preventing accidental injection or serialization of ground-truth variables.
  3. Strict programmatic interface: `case.get_decision_context()` returns only `DecisionContext`.
  4. Automated leakage tests enforcing that no ground-truth key exists in decision context.

---

## 3. Customer Response Simulator
The `CustomerResponseSimulator` is **policy-independent**:
- It accepts only `(case, policy, seed)`.
- It has **zero awareness** of whether the policy was chosen by `baseline`, `agent`, or `human`.
- It evaluates recovery probabilistically using the ground-truth response model for the chosen intervention:
  - `P_NO_ACTION`: Natural recovery (customer retries independently).
  - `P_CREATE_LINK_IMMEDIATE`: Recovery via immediate Payment Link while customer intent is warm.
  - `P_CREATE_LINK_DELAYED`: Recovery via delayed Payment Link allowing gateway/issuer/funds to settle.
  - `P_ESCALATE_ONLY`: Recovery via merchant human intervention (effective for high-value VIP transactions).
- **Economic Invariant**:
  $$\text{recovered\_amount} = \begin{cases} \text{case.amount} & \text{if recovered} \\ 0 & \text{if unrecovered} \end{cases}$$

---

## 4. Reproducibility & Common Random Numbers (CRN)
- **Cross-Process Deterministic Randomness**: The simulator derives RNG seeds via `SHA-256(case_id:seed)`, ensuring identical outcomes across separate Python processes and environments without reliance on Python's process-dependent `hash()`.
- **Variance Reduction**: Common random numbers can reduce the variance of policy differences by correlating the stochastic draws used for the same underlying case; they do not eliminate Monte Carlo uncertainty.
