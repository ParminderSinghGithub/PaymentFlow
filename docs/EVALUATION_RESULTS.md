# PaymentFlow Recovery Agent — Evaluation Results

## 1. Executive Summary & Comparative Scorecard

PaymentFlow was rigorously evaluated across multiple tiers: a naive deterministic baseline, a deterministic heuristic scaffold, a real Google Gemini LLM validation suite, and an interactive 15-scenario controlled benchmark.

All quantitative figures below have been **100% verified against raw evaluation result artifacts** (`baseline_results.json`, `mock_agent_results.json`, and database test records):

| Evaluation Tier | Scope & Modality | Recovery Rate (%) | Recovered Revenue (INR) | Total Opportunity (INR) | Opportunity Share (%) | Guardrail Fallbacks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Layer 5B: Naive Baseline** | 75 Cases $\times$ 50 CRN Draws (3,750 Sims) | **31.73%** (1,190 / 3,750) | **₹1,67,699.16** | ₹1,196,623.00 | 14.01% | 0 (Static Rules) |
| **Layer 5C: Mock Agent** | 75 Cases $\times$ 50 CRN Draws (3,750 Sims) | **61.71%** (2,314 / 3,750) | **₹8,43,619.04** | ₹1,196,623.00 | 70.50% | 4 Interventions |
| **Layer 5E: Real Gemini LLM** | 15 Cases (Controlled Validation) | **93.3%** Accuracy | Telemetry Verified | N/A (Live LLM Probe) | 100% Schema Valid | 0 Interventions |
| **Controlled Dashboard Benchmark** | 15 Canonical Scenarios (Live Runtime) | **90.84%** Eligible Opp | **₹28,648.00** | ₹31,538.00 (Eligible) | 90.84% of Eligible | 8 Gated / Safe Halts |

> [!NOTE]
> **Why Mock-Agent Results Differ from Real LLM Results**: The Layer 5C mock agent is a deterministic testing scaffold used to verify the Common Random Numbers (CRN) simulation and guardrail downgrades. Real LLM performance was validated in Layer 5E on live Google Gemini endpoints to measure schema adherence, categorization accuracy, and token latency.

---

## 2. Layer 5B: Deterministic Baseline Evaluation Report

The baseline evaluates a naive rule-based strategy:
$$\text{Policy} = \begin{cases} \text{P\_CREATE\_LINK\_IMMEDIATE} & \text{if case is eligible} \\ \text{P\_NO\_ACTION} & \text{otherwise} \end{cases}$$

### Key Metrics
- **Dataset**: 75 synthetic failed payment cases
- **Simulation Draws**: 50 draws per case ($75 \times 50 = 3,750$ total simulations)
- **Overall Recovery Rate**: **31.73%** (1,190 / 3,750 draws recovered)
- **Total Opportunity Value**: **₹1,196,623.00** (119,662,300 paise)
- **Expected Recovered Revenue**: **₹167,699.16** (16,769,916 paise)
- **Opportunity Share Recovered**: **14.01%**

### Policy & Eligibility Distribution
- **Eligible Cases**: 46 (61.3%) $\rightarrow$ `P_CREATE_LINK_IMMEDIATE`
- **Ineligible Cases**: 29 (38.7%) $\rightarrow$ `P_NO_ACTION`

#### Ineligibility Breakdown
| Reason Code | Count | Explanation |
| :--- | :--- | :--- |
| `INELIGIBLE_UNSUPPORTED_FAILURE` | 15 | C4 Risk and C5 Technical failures ineligible for automated link |
| `INELIGIBLE_HIGH_VALUE` | 8 | Transaction amount $> ₹50,000$ (requires human escalation) |
| `INELIGIBLE_CURRENCY` | 3 | Unsupported non-INR currency (USD, EUR) |
| `INELIGIBLE_COOLDOWN` | 2 | Customer exceeded maximum daily recovery limit |
| `INELIGIBLE_ALREADY_ATTEMPTED` | 1 | Active unpaid recovery link already exists |

### Baseline Failure Category Performance
| Category | Cases | Eligible | Action | Opportunity (INR) | Expected Recovered (INR) | Recovery Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1 (User Friction)** | 18 | 15 | 15 Immediate / 3 None | ₹292,791.00 | ₹49,133.02 | 28.89% (260 / 900) |
| **C2 (Network Timeout)** | 20 | 17 | 17 Immediate / 3 None | ₹208,541.00 | ₹89,829.80 | 80.30% (803 / 1,000) |
| **C3 (Balance Limits)** | 16 | 14 | 14 Immediate / 2 None | ₹263,396.00 | ₹28,736.34 | 15.88% (127 / 800) |
| **C4 (Risk Rejection)** | 11 | 0 | 0 Immediate / 11 None | ₹397,898.00 | ₹0.00 | 0.00% (0 / 550) |
| **C5 (Technical Fault)** | 10 | 0 | 0 Immediate / 10 None | ₹33,997.00 | ₹0.00 | 0.00% (0 / 500) |

---

## 3. Layer 5C: Mock Agent Evaluation Report

The mock agent introduces nuanced timing and human escalation:
- C1: Immediate or delayed recovery based on customer context.
- C2 & C3: `P_CREATE_LINK_DELAYED` to allow network recovery and balance replenishment.
- C4: `P_ESCALATE_ONLY` for compliance review.
- C5: `P_NO_ACTION`.

### Key Metrics
- **Dataset**: 75 synthetic failed payment cases
- **Simulation Draws**: 50 draws per case (3,750 total simulations)
- **Overall Recovery Rate**: **61.71%** (2,314 / 3,750 draws recovered)
- **Total Opportunity Value**: **₹1,196,623.00**
- **Expected Recovered Revenue**: **₹843,619.04** (84,361,904 paise)
- **Opportunity Share Recovered**: **70.50%**
- **Net Uplift vs. Baseline**: $+29.98\%$ absolute recovery rate ($+56.49\%$ opportunity share, $+₹675,919.88$ expected revenue)

### Guardrail Interventions & Proposal vs. Authorized Distribution
| Policy | Proposed by Agent | Authorized by Guardrails | Difference / Fallback |
| :--- | :--- | :--- | :--- |
| `P_CREATE_LINK_DELAYED` | 30 | 29 | -1 (1 downgraded to NO_ACTION via cooldown) |
| `P_CREATE_LINK_IMMEDIATE` | 18 | 17 | -1 (1 downgraded to NO_ACTION via cooldown) |
| `P_ESCALATE_ONLY` | 17 | 17 | 0 (High-value cases correctly preserved) |
| `P_NO_ACTION` | 10 | 12 | +2 (Guardrails enforced safe halts) |

- **Total Guardrail Fallbacks Applied**: 4
- **Total Validation Rejections**: 4

### Mock Agent Category Performance
| Category | Cases | Proposed | Authorized | Opportunity (INR) | Expected Recovered (INR) | Recovery Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | 18 | DELAYED:16, ESCALATE:2 | DELAYED:15, ESCALATE:2, NO_ACTION:1 | ₹292,791.00 | ₹271,880.36 | **81.44%** (733 / 900) |
| **C2** | 20 | IMMED:18, ESCALATE:2 | IMMED:17, ESCALATE:2, NO_ACTION:1 | ₹208,541.00 | ₹196,029.80 | **86.90%** (869 / 1,000) |
| **C3** | 16 | DELAYED:14, ESCALATE:2 | DELAYED:14, ESCALATE:2 | ₹263,396.00 | ₹226,987.36 | **70.50%** (564 / 800) |
| **C4** | 11 | ESCALATE:11 | ESCALATE:11 | ₹397,898.00 | ₹148,721.52 | **26.91%** (148 / 550) |
| **C5** | 10 | NO_ACTION:10 | NO_ACTION:10 | ₹33,997.00 | ₹0.00 | **0.00%** (0 / 500) |

---

## 4. Layer 5E: Real Google Gemini LLM Validation Report

In Layer 5E, the system connected live to Google Gemini (`gemini-3.5-flash-lite`) via the MCP protocol boundary:

### Model & Configuration
- **Model**: `gemini-3.5-flash-lite`
- **Protocol**: Model Context Protocol (MCP standard)
- **Credential Storage**: Managed securely via environment variable `GEMINI_API_KEY` (zero keys committed or logged)

### Controlled LLM Validation (15 Diverse Cases)
- **Sample Cohort**: 15 cases (exactly 3 cases per category C1 through C5)
- **Schema Validity Rate**: **100.0%** (15 / 15 returned valid `AgentDecision` JSON)
- **Failure Category Classification Accuracy**: **93.3%** (14 / 15 matched expert ground truth)
- **Guardrail Intervention Rate**: **0.0%** (all 15 proposals complied with safety invariants)
- **Average LLM Latency**: **1,802.52 ms**
- **Token Economics**:
  - **Total Tokens Consumed**: 18,666 tokens
  - **Prompt Tokens**: 15,855 tokens (avg. 1,057 tokens/request)
  - **Completion Tokens**: 2,811 tokens (avg. 187 tokens/request)
  - **Estimated Inference Cost**: $<\$0.01$ total

---

## 5. Controlled Dashboard Benchmark Summary

The live benchmark accessible on the Operator Console dashboard executes the authentic production decision layers against 15 canonical scenarios:

- **Total Cohort**: 15 scenarios (₹1,22,117.00 at risk)
- **Eligible Opportunity**: 7 cases (₹31,538.00)
- **Evaluation Recovered**: 6 cases (₹28,648.00)
- **Protected Volume (Escalated + Terminal)**: ₹90,579.00
- **★ Primary Metric — Eligible Opportunity Recovery Rate**: **90.84%**
- **Eligible Case Recovery Rate**: **85.71%**
- **Overall Case Recovery Rate**: **40.00%**
- **Gross Portfolio Recovery Rate**: **23.46%**
