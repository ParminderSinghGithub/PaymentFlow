# PaymentFlow Recovery Agent — Evaluation Methodology

## 1. Dataset Design & Purpose

Evaluating payment recovery algorithms against live merchants during hackathon development is unsafe and introduces live financial risk. To benchmark agent performance rigorously, PaymentFlow incorporates a reproducible, statistically balanced synthetic evaluation dataset of **75 failed-payment cases**.

The dataset models authentic Indian digital commerce dynamics across Razorpay's normalized **C1–C5 failure taxonomy**:

- **C1 (18 cases, 24.0%)**: Customer Checkout Dropoff & Authentication Friction (e.g., `OTP_TIMEOUT`, `BAD_REQUEST_ERROR`, `USER_DROPPED_OFF`).
- **C2 (20 cases, 26.7%)**: Network & Gateway Interruption (e.g., `GATEWAY_TIMEOUT`, `GATEWAY_ERROR`, `BANK_UNAVAILABLE`).
- **C3 (16 cases, 21.3%)**: Instrument & Balance Limits (e.g., `INSUFFICIENT_FUNDS`, `CARD_NOT_SUPPORTED`, `LIMIT_EXCEEDED`).
- **C4 (11 cases, 14.7%)**: Business & Risk Rejection (e.g., `RISK_CHECK_FAILED`, `AML_FLAG`, `FRAUD_SUSPECTED`).
- **C5 (10 cases, 13.3%)**: Technical Integration & Systemic Defect (e.g., `INVALID_REQUEST_ERROR`, `GATEWAY_INTERNAL_ERROR`).

### Stress Scenarios Included
- **High-Value Transactions**: 8 cases with amount $> ₹50,000$ (5,000,000 paise) across C1, C2, C3, and C4 to test financial guardrail escalation.
- **Multi-Currency Transactions**: 3 non-INR transactions (USD, EUR) to test domestic currency enforcement.
- **Customer Fatigue & Anti-Spam**: Cases with prior recovery links within 24 hours to test cooldown stopping rules.
- **Already-Paid Orders**: Cases where an order was settled via a secondary attempt to test idempotency defenses.

---

## 2. Ground-Truth Isolation & Zero-Leakage Guarantee

A common flaw in agent evaluation is accidental data leakage, where ground-truth simulation variables (such as latent customer willingness to pay) bleed into the agent's prompt or context.

PaymentFlow prevents leakage through strict schema architecture:

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

### Invariant Controls
1. **Typed Schema Boundary**: `DecisionContext` and `SimulationGroundTruth` are distinct Pydantic models.
2. **Forbidden Extra Keys**: `DecisionContext` sets `extra="forbid"`. Accidental insertion of ground-truth fields raises an unhandled validation error.
3. **Extraction Method**: Agents and baselines receive context solely via `case.get_decision_context()`, which filters out all ground truth.
4. **Automated Leakage Tests**: Unit test `test_llm_input_strictly_zero_ground_truth_leakage` validates that mutating ground-truth values produces zero change in serialized model inputs.

---

## 3. Customer Response Simulator

The `CustomerResponseSimulator` models stochastic customer behavior upon receiving an authorized recovery policy:

- **Policy Independence**: The simulator accepts `(case, authorized_policy, seed)` and has zero knowledge of whether the policy was chosen by a baseline rule, an AI agent, or a human.
- **Intervention-Specific Probabilities**:
  - `P_NO_ACTION`: Natural recovery baseline (customer retries independently).
  - `P_CREATE_LINK_IMMEDIATE`: Immediate link while purchase intent is hot (effective for C1).
  - `P_CREATE_LINK_DELAYED`: Delayed link allowing banking recovery or fund replenishment (effective for C2/C3).
  - `P_ESCALATE_ONLY`: High-touch human outreach by merchant operations (effective for high-value VIP accounts).
- **Economic Invariant**:
  $$\text{recovered\_amount} = \begin{cases} \text{case.amount} & \text{if customer completes payment} \\ 0 & \text{if customer drops off} \end{cases}$$

---

## 4. Common Random Numbers (CRN) Variance Reduction

Evaluating stochastic systems with independent random seeds creates high variance, making it difficult to distinguish policy improvements from lucky random rolls.

PaymentFlow employs **Common Random Numbers (CRN)**:
$$\text{Seed} = \text{SHA-256}(\text{case\_id} : \text{draw\_index}) \quad \text{for } \text{draw\_index} \in [0, 49]$$

### Why CRN Guarantees True Counterfactual Measurement
- Every case is simulated across exactly **50 Monte Carlo draws**.
- Draw $j$ of Case $i$ in the **Baseline Evaluation** uses the exact same seed as Draw $j$ of Case $i$ in the **Agent Evaluation**.
- Consequently:
  $$\text{Customer Latent State}(\text{Case}_i, \text{Draw}_j)_{\text{Baseline}} \equiv \text{Customer Latent State}(\text{Case}_i, \text{Draw}_j)_{\text{Agent}}$$
- Any observed difference in recovery rate is **100% attributable to policy differences**, not simulation noise.
- Using cryptographic `SHA-256` hashing rather than Python's built-in `hash()` ensures identical seed generation across distinct operating systems, platforms, and Python processes.

### Estimator Definitions & Denominators
- **Overall Recovery Rate**: Evaluated over all case-draw events ($N_{\text{total}} = N_{\text{cases}} \times N_{\text{draws}} = 75 \times 50 = 3,750$ draws):
  $$\text{Recovery Rate} = \frac{\sum_{i=1}^{75} \sum_{d=0}^{49} \mathbb{I}(\text{Recovered}_{i, d})}{3,750}$$
- **Expected Recovered Revenue**: The sample mean ($\hat{\mathbb{E}}$) across the 50 simulated portfolio realizations:
  $$\hat{\mathbb{E}}[\text{Revenue}] = \frac{1}{50} \sum_{d=0}^{49} \left( \sum_{i=1}^{75} \text{Recovered Amount}_{i, d} \right)$$
  (For the Mock Agent, this equals **₹843,619.04**; for the Baseline, **₹167,699.16**). This represents the expected payout per 75-case portfolio, NOT a cumulative sum across 50 runs.
- **Opportunity Share Recovered**: Scaled against the single-portfolio total face value ($₹1,196,623.00$):
  $$\text{Opportunity Share} = \frac{\hat{\mathbb{E}}[\text{Revenue}]}{\sum_{i=1}^{75} \text{Amount}_i} = \frac{₹843,619.04}{₹1,196,623.00} = 70.50\%$$
- **Paired Hypothesis Testing**: Because draws are strictly paired via CRN ($N=50$), the mean recovery rate uplift (+29.98 pp) yields a 95% confidence interval of $[+28.86\%, +31.09\%]$ ($p < 0.0001$). Net revenue uplift (+₹675,919.88) yields a 95% confidence interval of $[+₹624,696.24, +₹727,143.52]$.

---

## 5. Offline Evaluation Artifacts

Every evaluation run generates a machine-readable JSON artifact:
- Baseline: `src/paymentflow/eval/data/baseline_results.json`
- Mock Agent: `src/paymentflow/eval/data/mock_agent_results.json`

Artifact schema contains:
- `metadata`: Evaluated timestamp, dataset case count (75), draws per case (50), total draws (3,750), RNG seed convention.
- `summary`: Recovery rate, expected recovered revenue in paise, total opportunity, ineligibility reasons, and proposal counts.
- `categories`: Granular performance breakdown per category (C1 through C5).
- `decision_records`: Exact audit record of proposed policy vs authorized policy for every case.
- `draw_results`: Complete ledger of all 3,750 simulation outcomes.
