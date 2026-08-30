# PaymentFlow Recovery Agent — Agent Evaluation Methodology (Layer 5C)

## 1. Purpose of Layer 5C
Layer 5C establishes the evaluation contract, deterministic safety validation boundary, and offline evaluation harness required to benchmark agentic recovery policies against the naive deterministic baseline (established in Layer 5B).

This layer implements the architectural integration without introducing external LLM API calls, live MCP network transport, or production side-effects.

```text
DecisionContext
      ↓
AgentDecisionProvider (Abstract Interface)
      ↓
Structured AgentDecision (Proposal)
      ↓
PolicyGuardrailEngine (Deterministic Validation Boundary)
      ↓
Authorized RecoveryPolicy (Approved / Downgraded / Fallback)
      ↓
CustomerResponseSimulator (Exact L5A Simulator + CRN Seeds)
      ↓
Simulated Outcome (Recovered / Unrecovered)
```

---

## 2. AgentDecision Contract
The [`AgentDecision`](file:///c:/Projects/Razorpay/src/paymentflow/eval/models.py) model represents the agent's **structured advisory proposal**. It explicitly conveys intent rather than an executed financial command:

- `case_id: str`: The unique case identifier.
- `failure_category: FailureCategory`: The agent's classified failure category (`C1` through `C5`).
- `proposed_policy_id: RecoveryPolicy`: The proposed recovery intervention (`P_CREATE_LINK_IMMEDIATE`, `P_CREATE_LINK_DELAYED`, `P_ESCALATE_ONLY`, `P_NO_ACTION`).
- `reasoning: str`: Bounded natural language explanation justifying the policy selection.
- `confidence_score: float`: Calibrated probability score ($0.0 \dots 1.0$).
- `proposed_amount: int | None`: Target recovery amount in paise.
- `proposed_currency: str | None`: Target recovery currency (e.g., `INR`).

**Strict Validation Invariant**: `AgentDecision` enforces `extra="forbid"` and rejects unallowed policy IDs, missing fields, or out-of-range confidence scores.

---

## 3. AgentDecisionProvider Abstraction
The [`AgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/agent_evaluator.py) is an abstract base class defining the standard evaluation interface:

```python
class AgentDecisionProvider(ABC):
    @abstractmethod
    def decide(self, context: DecisionContext) -> AgentDecision:
        """Produce a structured recovery policy proposal solely from decision context."""
        ...
```

This abstraction isolates the evaluation pipeline from concrete LLM client details. Later layers (e.g., Layer 5D) can plug in an `LLMAgentDecisionProvider` without altering the evaluation harness, stochastic simulator, or validation boundary.

---

## 4. Mock Agent Decision Provider
The [`MockAgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/agent_evaluator.py) is a deterministic evaluation scaffold used to validate contract compliance and guardrail interactions:

- **C1 (Transient Gateway/Issuer)**: Proposes `P_CREATE_LINK_DELAYED` to allow upstream systems to recover.
- **C2 (Soft User/Friction)**: Proposes `P_CREATE_LINK_IMMEDIATE` while customer purchase intent is warm.
- **C3 (Instrument/Balance Limits)**: Proposes `P_CREATE_LINK_DELAYED` to allow account replenishment.
- **C4 (Risk/AML Rejection)**: Proposes `P_ESCALATE_ONLY` for compliance review.
- **C5 (Technical/Integration Errors)**: Proposes `P_NO_ACTION`.
- **High-Value (> ₹50,000)**: Proposes `P_ESCALATE_ONLY`.

> [!IMPORTANT]
> The mock provider is **NOT an AI model** and does not represent machine learning intelligence. It is a deterministic testing scaffold.

---

## 5. Deterministic Validation Boundary
In alignment with the core architecture, **agent proposals have zero authority to execute financial actions directly**.

The [`EvaluationSafetyValidator`](file:///c:/Projects/Razorpay/src/paymentflow/eval/agent_evaluator.py) routes every proposal through the authoritative production [`PolicyGuardrailEngine`](file:///c:/Projects/Razorpay/src/paymentflow/domain/policy_engine.py):

1. **Eligibility Enforcement**: Non-INR transactions, active cooldown limits, and duplicate links cannot be overridden by the agent.
2. **High-Value Cap**: Automated links proposed for transactions > ₹50,000 are deterministically downgraded to `P_ESCALATE_ONLY`.
3. **Category Restrictions**: Automated links proposed for C4 Risk failures are downgraded to `P_ESCALATE_ONLY`; C5 Technical failures are downgraded to `P_NO_ACTION`.
4. **Amount/Currency Mutation Protection**: Any attempt to alter the verified transaction amount or currency results in immediate rejection and safe fallback to `P_NO_ACTION`.
5. **Malformed Output Handling**: Any unparseable or schema-violating proposal fails closed to `P_NO_ACTION`.

---

## 6. Ground-Truth Isolation (No-Leakage Guarantee)
- `AgentDecisionProvider.decide()` accepts only [`DecisionContext`](file:///c:/Projects/Razorpay/src/paymentflow/eval/models.py).
- `DecisionContext` sets `extra="forbid"` and cannot contain latent customer intent scores, response probabilities, or simulation ground truth.
- Automated unit tests verify that altering `SimulationGroundTruth` produces zero change in agent proposals.

---

## 7. Common Random Numbers (CRN) Methodology
The agent evaluator uses the exact same seed indexing as Layer 5B:
$$\text{seed} = \text{draw\_index} \quad (0 \le \text{draw\_index} < 50)$$
$$\text{RNG Seed} = \text{SHA-256}(\text{case\_id} : \text{seed})$$

This guarantees that:
$$\text{Stochastic State}(\text{case}_i, \text{draw}_j)_{\text{Baseline}} \equiv \text{Stochastic State}(\text{case}_i, \text{draw}_j)_{\text{Agent}}$$

Correlating the stochastic draws for the same underlying case reduces the variance of policy differences, enabling precise counterfactual evaluation.

---

## 8. Evaluation Flow
For each of the 75 evaluation cases:
1. Extract `DecisionContext` via `case.get_decision_context()`.
2. Query `AgentDecisionProvider.decide(dc)` for `AgentDecision`.
3. Execute `EvaluationSafetyValidator.validate_proposal(dc, proposal)`.
4. Obtain authorized `RecoveryPolicy`.
5. For each `draw_index` from 0 to 49:
   - Invoke `CustomerResponseSimulator.simulate(case, authorized_policy, seed=draw_index)`.
   - Record `AgentDrawResult`.
6. Aggregate results per case, category, and evaluation run.

---

## 9. Result Schema & Artifacts
The evaluation produces a complete JSON artifact ([`src/paymentflow/eval/data/mock_agent_results.json`](file:///c:/Projects/Razorpay/src/paymentflow/eval/data/mock_agent_results.json)) containing:
- **`metadata`**: Run timestamps, provider identifier, case and draw counts.
- **`summary`**: Overall recovery rates, expected recovered revenue in paise, proposal counts, authorized counts, and fallback statistics.
- **`decision_records`**: 75 audit records documenting proposed vs. authorized policies, reason codes, and guardrails checked.
- **`case_aggregates`**: 75 per-case performance summaries.
- **`draw_results`**: Exactly 3,750 individual Monte Carlo draw outcomes.

---

## 10. Why Mock-Agent Results Are NOT Evidence of LLM Performance
The mock provider uses a hardcoded heuristic mapping. It does not measure:
- LLM prompt adherence or schema compliance rates.
- Model latency, token economics, or inference cost.
- Reasoning capability under nuanced, ambiguous failure descriptions.

This layer's purpose is strictly to establish and verify the **evaluation contract, safety guardrails, and simulation reproducibility**.

---

## 11. Real Provider & MCP Boundary Integration (Layer 5D)
In Layer 5D, [`LLMAgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/llm_provider.py) connects real LLM reasoning to the evaluation framework:
- Implements the exact same `AgentDecisionProvider` interface.
- Accepts `DecisionContext` only (strictly no ground-truth leakage).
- Enforces strict structured output parsing into `AgentDecision`.
- Gathers telemetry on latency and token usage.
- Integrates with Model Context Protocol (`MCPServer` & `RecoveryAgentClient`) for decoupled tool execution.
- Evaluates against the identical 75 cases and 50 stochastic CRN draws per case.

