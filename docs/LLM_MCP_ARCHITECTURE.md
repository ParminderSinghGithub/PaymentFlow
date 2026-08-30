# PaymentFlow Recovery Agent — LLM & MCP Architecture (Layer 5D)

---

## 1. Why the LLM Exists
Payment failures on Razorpay occur across heterogeneous channels (cards, UPI, netbanking, wallets) with varied error semantics from hundreds of issuing banks and payment gateways. 

The LLM serves as an **intelligent context interpreter and strategy advisor**:
- Disentangles cryptic gateway error codes, failure sources, and diagnostic reasons.
- Classifies failures into nuanced recovery categories (C1–C5).
- Proposes calibrated recovery timing (immediate vs. delayed) based on customer intent vs. technical stabilization requirements.

---

## 2. Exact LLM Responsibility
The LLM operates strictly as an **advisory decision maker**. Its responsibilities are bounded to:
1. Interpreting sanitized payment failure diagnostics (`error_code`, `error_source`, `error_step`, `error_reason`).
2. Classifying the failure category (`C1` through `C5`).
3. Proposing an allowed recovery policy (`P_CREATE_LINK_IMMEDIATE`, `P_CREATE_LINK_DELAYED`, `P_ESCALATE_ONLY`, `P_NO_ACTION`).
4. Supplying concise reasoning and a confidence score ($0.0 \dots 1.0$).

---

## 3. Exact Deterministic Responsibility
The deterministic application layer maintains **absolute authority** over financial execution:
- **Eligibility**: Enforces currency (INR only), state validity, and maximum 72-hour staleness.
- **High-Value Escalation**: Mandatory human review for transactions $> ₹50,000$ (5,000,000 paise).
- **Anti-Spam / Cooldown**: Caps customer recovery attempts at 3 per 24-hour window.
- **Link Limits**: Strictly enforces 1 active recovery link per original payment failure.
- **Tampering Protection**: Rejects any proposal attempting amount or currency mutation.
- **Financial Write Execution**: Only the deterministic backend (`RecoveryExecutor`) can call Razorpay APIs.

```text
DecisionContext
      ↓
LLM Agent / Advisory Reasoner
      ↓
Structured Proposal (AgentDecision)
      ↓
PolicyGuardrailEngine (Deterministic Gatekeeper)
      ↓
APPROVE / DOWNGRADE / ESCALATE / REJECT
      ↓
Deterministic Authorized Policy
```

---

## 4. MCP Architecture
The system integrates the **Model Context Protocol (MCP)** standard (`mcp>=1.0.0`) to decouple agent reasoning from internal database schemas and private business logic:

```text
┌────────────────────────────────────────────────────────┐
│                      LLM Agent                         │
└──────────────────────────┬─────────────────────────────┘
                           │ (MCP Protocol / JSON-RPC)
┌──────────────────────────▼─────────────────────────────┐
│                 RecoveryAgentClient                    │
│           (Tool Discovery & Call Handling)             │
└──────────────────────────┬─────────────────────────────┘
                           │ (Typed Tool Boundary)
┌──────────────────────────▼─────────────────────────────┐
│                   MCPServer Boundary                   │
│   - get_payment_context       - get_recovery_status    │
│   - get_recovery_case         - request_recovery_action│
│   - get_allowed_recovery_policies                      │
└──────────────────────────┬─────────────────────────────┘
                           │ (Deterministic Authorization)
┌──────────────────────────▼─────────────────────────────┐
│               PolicyGuardrailEngine                    │
│        (Immutability, Cooldowns, High-Value)           │
└────────────────────────────────────────────────────────┘
```

---

## 5. MCP Tools & Contracts

### 5.1 Read Tools
1. `get_allowed_recovery_policies()`: Returns the 4 allowed policy IDs and their operational constraints.
2. `get_payment_context(payment_id: str)`: Returns sanitized payment details, amounts, currency, and failure diagnostics.
3. `get_recovery_case(case_id: str)`: Returns structured recovery case state, failure category, and eligibility status.
4. `get_recovery_status(case_id: str)`: Returns current state machine state, terminal status, and workflow flags.

### 5.2 Action Tool
- `request_recovery_action(case_id, proposed_policy, proposed_amount, proposed_currency, explanation)`:
  - Submits an advisory proposal to `PolicyGuardrailEngine`.
  - Returns: `{"authorized": bool, "decision": str, "effective_policy": str, "reason_code": str}`.
  - **Zero Financial Side Effects**: Does NOT create Razorpay links, charge cards, or execute refunds.

---

## 6. Credential Boundary & Safety
- **Zero In-Code Secrets**: All credentials are loaded exclusively from environment variables via `Settings`.
- **Placeholder Safety**: If `LLM_API_KEY` is missing or contains placeholder values, the system operates in safe fallback mode (`P_NO_ACTION` or `P_ESCALATE_ONLY`).
- **No Direct Razorpay Access for LLM**: The LLM agent has no visibility into `RAZORPAY_KEY_ID` or `RAZORPAY_KEY_SECRET`.

---

## 7. Ground-Truth Isolation (No-Leakage Guarantee)
- `LLMAgentDecisionProvider` serializes only decision-visible fields via `serialize_decision_context()`.
- Simulation ground truth (`p_recovery_immediate_link`, `p_recovery_delayed_link`, `p_recovery_no_action`, latent intent) is excluded by schema invariants (`extra="forbid"`).
- Regression tests ([`test_llm_input_strictly_zero_ground_truth_leakage`](file:///c:/Projects/Razorpay/tests/test_llm_provider.py#L22-L48)) verify zero ground truth leakage.

---

## 8. Failure Handling & Safe Fallbacks
Every failure mode is handled fail-closed:
- **HTTP Timeout / Network Error**: Safe fallback to `P_NO_ACTION` (or `P_ESCALATE_ONLY` if high-value).
- **HTTP 4xx / 5xx Status**: Safe fallback with logged error metadata.
- **Malformed JSON / Schema Errors**: Safe fallback.
- **Unknown Policy ID**: Safe fallback.
- **Confidence Out of Bounds**: Safe fallback.

---

## 9. Structured-Output Validation
LLM responses are strictly validated against [`AgentDecision`](file:///c:/Projects/Razorpay/src/paymentflow/eval/models.py):
- Rejects unexpected extra fields (`extra="forbid"`).
- Restricts policy IDs to the enum allowlist.
- Enforces confidence range $[0.0, 1.0]$.

---

## 10. Mock Provider vs. Real LLM Provider
Both providers implement the exact same [`AgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/agent_evaluator.py) interface:
- [`MockAgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/agent_evaluator.py): Deterministic, fast, zero-dependency scaffold for CI/CD regression testing.
- [`LLMAgentDecisionProvider`](file:///c:/Projects/Razorpay/src/paymentflow/eval/llm_provider.py): Real model-calling provider supporting Google Gemini and OpenAI REST protocols with latency and token telemetry.

---

## 11. Offline vs. Live Execution
- **Offline Mode**: Evaluates datasets using `CustomerResponseSimulator` and Common Random Numbers (CRN).
- **Live Mode**: Used in production webhook ingestion and triage workflows.
- In Layer 5D, all evaluation and tool calling operate in **offline/non-side-effecting mode**.

---

## 12. Why MCP Is Meaningful Rather Than Decorative
MCP provides:
1. **Protocol Standard**: Formal tool discovery and schema contracts consumable by any standard agent.
2. **Context Isolation**: LLMs receive clean, sanitized payment diagnostics without raw database access or arbitrary query capabilities.
3. **Strict Policy Mediation**: The agent cannot bypass guardrails because actions are submitted to a validated tool endpoint rather than directly executed.

---

## 13. Why No Financial Side Effects Occur in L5D
Layer 5D tests and validates the agent's reasoning, tool calling, and guardrail enforcement. Production write paths (creating real Razorpay Payment Links) are isolated in `RecoveryExecutor` (Layer 4A) and cannot be triggered by the offline evaluation harness.
