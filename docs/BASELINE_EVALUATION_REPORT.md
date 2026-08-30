# Baseline Evaluation Report (Layer 5B)

## 1. Executive Summary
- **Policy**: Deterministic Naive Baseline (`if eligible -> P_CREATE_LINK_IMMEDIATE, else -> P_NO_ACTION`)
- **Dataset Size**: 75 synthetic failed payment cases
- **Monte Carlo Draws**: 3,750 total simulations (50 draws/case)
- **Overall Recovery Rate**: 31.73% (1,190 / 3,750 draws recovered)
- **Total Opportunity Value**: ₹1,196,623.00
- **Expected Recovered Revenue**: ₹167,699.16 (14.01% of opportunity)

---

## 2. Policy & Eligibility Distribution
| Metric | Count | Share | Policy Applied |
| :--- | :--- | :--- | :--- |
| **Eligible Cases** | 46 | 61.3% | `P_CREATE_LINK_IMMEDIATE` |
| **Ineligible Cases** | 29 | 38.7% | `P_NO_ACTION` |
| **Total Cases** | 75 | 100.0% | — |

### Ineligibility Breakdown
| Reason Code | Count | Explanation |
| :--- | :--- | :--- |
| `INELIGIBLE_HIGH_VALUE` | 8 | Amount > ₹50,000 threshold (requires human escalation) |
| `INELIGIBLE_CURRENCY` | 3 | Unsupported non-INR currency (e.g. USD, EUR) |
| `INELIGIBLE_ALREADY_ATTEMPTED` | 1 | Recovery link previously attempted / active cooldown |
| `INELIGIBLE_UNSUPPORTED_FAILURE` | 15 | C4 Risk / C5 Technical failures ineligible for automated link |
| `INELIGIBLE_COOLDOWN` | 2 | Customer reached maximum daily recovery attempt limit |

---

## 3. Failure Category Breakdown
| Category | Cases | Eligible | Action | Opportunity (₹) | Expected Recovered (₹) | Recovery Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | 18 | 15 | 15 Link / 3 None | ₹292,791.00 | ₹49,133.02 | 28.89% |
| **C2** | 20 | 17 | 17 Link / 3 None | ₹208,541.00 | ₹89,829.80 | 80.30% |
| **C3** | 16 | 14 | 14 Link / 2 None | ₹263,396.00 | ₹28,736.34 | 15.88% |
| **C4** | 11 | 0 | 0 Link / 11 None | ₹397,898.00 | ₹0.00 | 0.00% |
| **C5** | 10 | 0 | 0 Link / 10 None | ₹33,997.00 | ₹0.00 | 0.00% |

---

## 4. Evaluation Methodology & Reproducibility
- **Simulator**: `CustomerResponseSimulator` (L5A hardened with SHA-256)
- **Common Random Numbers (CRN)**: Draw seeds are indexed `0..49` for each `case_id`, allowing future agent evaluations to use identical stochastic draws.
- **Ground-Truth Isolation**: Baseline decision logic had zero access to `SimulationGroundTruth` (latent customer intent or recovery probabilities).
- **Economic Integrity**: Failed recovery yields ₹0; successful recovery yields exact case amount.
