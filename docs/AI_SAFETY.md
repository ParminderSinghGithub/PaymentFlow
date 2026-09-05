# PaymentFlow Recovery Agent — AI Safety & Guardrails

## 1. Why the LLM Exists & Bounded Responsibility

Payment failures on payment gateways like Razorpay stem from complex, multi-party interactions across customer checkout devices, issuing banks, card networks, and acquiring platforms. Error codes are frequently ambiguous, cryptic, or misleading (e.g., a generic `BAD_REQUEST_ERROR` may represent a voluntary user dropoff, an expired OTP, or a network disconnection).

The Large Language Model (LLM) serves as an **intelligent context interpreter and strategy advisor**:
- Translates unstructured error descriptions and gateway context into normalized failure categories (**C1–C5**).
- Determines recovery propensity and recommends calibrated intervention timing (immediate vs. delayed).
- Provides explainable, human-readable rationale for every decision.

### Strict Advisory Boundary
The LLM operates **strictly as an advisory proposal generator**. It possesses:
- **ZERO direct database access**: Cannot write, update, or query internal tables.
- **ZERO Razorpay write permissions**: Cannot call `payment_links.create` or trigger bank refunds.
- **ZERO unmediated execution authority**: Every proposal must pass through the deterministic `PolicyGuardrailEngine`.

```text
DecisionContext (Sanitized Diagnostics)
          │
          ▼
┌───────────────────────────────────────┐
│     Advisory AI Agent (LLM)           │
│     - Model: gemini-2.5-flash         │
│     - Interprets error semantics      │
│     - Proposes AgentDecision          │
└──────────────────┬────────────────────┘
                   │
                   ▼ (request_recovery_action via MCP)
┌───────────────────────────────────────┐
│     PolicyGuardrailEngine Gate        │
│     - Amount / Currency Immutability  │
│     - High-Value Cap (> ₹50,000)      │
│     - Customer Cooldown (Max 3 / 24h) │
│     - Single Active Link Limit        │
│     - C4 / C5 Category Restrictions   │
└──────────────────┬────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
    [ APPROVED ]        [ MODIFIED / BLOCKED ]
 (Authorized Policy) (ESCALATE or TERMINAL_NO_ACTION)
```

---

## 2. Model Context Protocol (MCP) Boundary

PaymentFlow integrates the **Model Context Protocol (MCP)** specification to formalize the boundary between the reasoning agent and host infrastructure:

- **MCP Server**: Implemented via `mcp.server.mcpserver.MCPServer` (`paymentflow-eval-mcp`).
- **MCP Client**: `RecoveryAgentClient` handles tool discovery, protocol transport, and typed invocation.

### Registered Tools

| Tool Name | Type | Description | Side Effects |
| :--- | :--- | :--- | :--- |
| `get_allowed_recovery_policies` | **Read** | Returns allowlisted recovery policies and descriptions | None |
| `get_payment_context` | **Read** | Retrieves sanitized payment diagnostics for a transaction | None |
| `get_recovery_case` | **Read** | Retrieves current recovery case state and classification | None |
| `get_recovery_status` | **Read** | Retrieves lifecycle state, terminal flags, and timestamps | None |
| `request_recovery_action` | **Action** | Submits proposed policy to `PolicyGuardrailEngine` | Bounded proposal validation only (zero gateway writes) |

### Why MCP Is Meaningful Rather Than Decorative
1. **Context Sanitization**: The agent receives structured, stripped payment context. Internal database schemas, connection strings, and credential secrets are strictly hidden behind the protocol boundary.
2. **Policy Enforcement Point**: Because action submission occurs over the `request_recovery_action` tool, every proposed action is intercepted and verified by the guardrail engine before any database record or gateway API can be touched.
3. **Model Interchangeability**: The application runtime can swap underlying models (Google Gemini, OpenAI, or local weights) without modifying recovery orchestration logic.

---

## 3. Deterministic Safety Invariants

The `PolicyGuardrailEngine` enforces five non-negotiable mathematical and operational invariants:

### Invariant 1: Amount Immutability
- **Rule**: $\text{Proposed Amount} \equiv \text{Verified Original Payment Amount}$.
- **Purpose**: Prevents adversarial prompt injection, hallucinated discounting (e.g., offering a 10% coupon to incentivize checkout), or accidental pricing inflation.
- **Enforcement**: If `proposed_amount != original_amount`, the proposal is immediately **REJECTED** and the case transitions to `TERMINAL_NO_ACTION`.

### Invariant 2: Currency Immutability
- **Rule**: $\text{Proposed Currency} \equiv \text{Original Currency} \equiv \text{"INR"}$.
- **Purpose**: Razorpay Payment Links in the recovery flow must strictly match the domestic settlement currency.
- **Enforcement**: Currency mutation attempts (e.g., proposing USD or EUR) are **REJECTED** and terminated.

### Invariant 3: High-Value Financial Escalation
- **Rule**: If $\text{Transaction Amount} > ₹50,000$ (5,000,000 paise), automated recovery is **PROHIBITED**.
- **Purpose**: Mitigates risk on large commercial transactions, VIP accounts, and high-ticket fraud.
- **Enforcement**: Regardless of the LLM's confidence or proposal, the action is deterministically downgraded to `P_ESCALATE_ONLY`, alerting human compliance and operations teams.

### Invariant 4: Customer Anti-Fatigue / Cooldown
- **Rule**: Maximum 3 recovery attempts per customer in any rolling 24-hour window.
- **Purpose**: Prevents spamming customers who have repeatedly abandoned or failed checkouts, protecting merchant brand reputation and avoiding regulatory scrutiny.
- **Enforcement**: Checked dynamically by querying recovery links issued to `customer_id` within `current_time - 24 hours`. Exceeding the threshold triggers `REJECT` $\rightarrow$ `TERMINAL_NO_ACTION`.

### Invariant 5: Single Active Link Limit
- **Rule**: Exactly 1 active (unpaid) Payment Link per failed transaction at any given moment.
- **Purpose**: Eliminates double-link confusion, multi-tab overcharges, and redundant webhook events.
- **Enforcement**: If a recovery link is already active, subsequent creation requests are suppressed.

---

## 4. Failure Category Stopping Rules

The engine enforces mandatory stopping rules mapped to the C1–C5 failure taxonomy:

| Failure Category | Permitted Policies | Forbidden Policies | Guardrail Enforcement |
| :--- | :--- | :--- | :--- |
| **C1 (User Friction / Timeout)** | `P_CREATE_LINK_IMMEDIATE`, `P_CREATE_LINK_DELAYED`, `P_ESCALATE_ONLY`, `P_NO_ACTION` | — | Evaluated against standard eligibility |
| **C2 (Network Timeout)** | `P_CREATE_LINK_DELAYED`, `P_CREATE_LINK_IMMEDIATE`, `P_ESCALATE_ONLY`, `P_NO_ACTION` | — | Delayed link preferred to allow network recovery |
| **C3 (Instrument Limits)** | `P_CREATE_LINK_DELAYED`, `P_ESCALATE_ONLY`, `P_NO_ACTION` | `P_CREATE_LINK_IMMEDIATE` | Immediate retry discouraged; cooldown window required |
| **C4 (Risk / AML Rejection)** | `P_ESCALATE_ONLY`, `P_NO_ACTION` | `P_CREATE_LINK_IMMEDIATE`, `P_CREATE_LINK_DELAYED` | **Mandatory Escalation**: AI cannot issue links to suspected fraud |
| **C5 (Technical Defects)** | `P_NO_ACTION` | All recovery links | **Terminal Stop**: Systemic defects cannot be recovered via customer links |

---

## 5. Ground-Truth Isolation & Zero Leakage Guarantee

A critical integrity requirement in evaluating AI agents is preventing ground-truth leakage:

1. **Schema Partitioning**: The evaluation framework strictly separates `DecisionContext` (decision-time diagnostics) from `SimulationGroundTruth` (latent customer intent, simulated response probabilities).
2. **Strict Pydantic Invariants**: `DecisionContext` enforces `extra="forbid"`. Any attempt to pass ground-truth variables into the context raises a schema validation exception.
3. **Automated Leakage Verification**: Unit test `test_llm_input_strictly_zero_ground_truth_leakage` programmatically validates that changing `SimulationGroundTruth` values produces zero change in serialized LLM prompts.

---

## 6. Fail-Closed Error Handling

Every failure mode in the AI interaction path fails closed:

- **Provider Timeout**: If the LLM API does not respond within the configured timeout (default 8,000 ms), the orchestrator falls back to `P_NO_ACTION` (or `P_ESCALATE_ONLY` if high-value).
- **HTTP 4xx/5xx Errors**: Logged with telemetry; triggers safe fallback without crashing the pipeline.
- **Schema Malformation**: Responses that fail JSON parsing or Pydantic validation fail closed to `P_NO_ACTION`.
- **Confidence Out of Range**: Scores $< 0.0$ or $> 1.0$ are rejected by schema validators.
- **Placeholder / Missing Keys**: If `LLM_API_KEY` is unset or contains placeholders, the system falls back safely without disrupting operational webhook ingestion.
