# Mock Agent Evaluation Report (Layer 5C)

> **IMPORTANT NOTICE**: This evaluation uses a deterministic mock provider as an architectural scaffold to validate the Agent Decision Contract, Common Random Numbers (CRN), and deterministic guardrail boundaries. It does **NOT** represent LLM benchmark results.

## 1. Executive Summary
- **Provider**: `MockAgentDecisionProvider`
- **Dataset Size**: 75 synthetic failed payment cases
- **Monte Carlo Draws**: 3,750 total simulations (50 draws/case)
- **Overall Recovery Rate**: 61.71% (2,314 / 3,750 draws recovered)
- **Total Opportunity Value**: ₹1,196,623.00
- **Expected Recovered Revenue**: ₹843,619.04 (70.50% of opportunity)

---

## 2. Policy Proposals vs. Authorized Actions
| Policy | Proposed by Agent | Authorized by Guardrails | Rejections / Downgrades |
| :--- | :--- | :--- | :--- |
| `P_CREATE_LINK_IMMEDIATE` | 18 | 17 | +1 |
| `P_CREATE_LINK_DELAYED` | 30 | 29 | +1 |
| `P_ESCALATE_ONLY` | 17 | 17 | 0 |
| `P_NO_ACTION` | 10 | 12 | -2 |

- **Total Guardrail Fallbacks / Downgrades**: 4
- **Total Rejections**: 4

---

## 3. Failure Category Breakdown
| Category | Cases | Proposed | Authorized | Opportunity (₹) | Expected Recovered (₹) | Recovery Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | 18 | DELAYED:16, ONLY:2 | DELAYED:15, ONLY:2, ACTION:1 | ₹292,791.00 | ₹271,880.36 | 81.44% |
| **C2** | 20 | IMMEDIATE:18, ONLY:2 | IMMEDIATE:17, ONLY:2, ACTION:1 | ₹208,541.00 | ₹196,029.80 | 86.90% |
| **C3** | 16 | DELAYED:14, ONLY:2 | DELAYED:14, ONLY:2 | ₹263,396.00 | ₹226,987.36 | 70.50% |
| **C4** | 11 | ONLY:11 | ONLY:11 | ₹397,898.00 | ₹148,721.52 | 26.91% |
| **C5** | 10 | ACTION:10 | ACTION:10 | ₹33,997.00 | ₹0.00 | 0.00% |

---

## 4. Evaluation Methodology & Verification
- **Simulator**: `CustomerResponseSimulator` (L5A hardened with SHA-256)
- **CRN Alignment**: Uses identical `seed = draw_index` ($0 \dots 49$) per `case_id` to hold the stochastic customer response constant.
- **Guardrail Enforcement**: Agent proposals cannot bypass eligibility, cooldowns, or high-value constraints.
- **Economic Integrity**: Failed recovery yields ₹0; successful recovery yields exact case amount.
