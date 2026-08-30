# Real LLM Validation & Evaluation Integration Report (Layer 5E)

## 1. Live Credential & Provider Status
- **Provider**: `GEMINI`
- **Model**: `gemini-3.5-flash-lite`
- **Credential Status**: `VALID AND CONFIGURED` (loaded securely via environment / `.env`)
- **Secrets Isolation**: `100% VERIFIED` (no keys printed, logged, or committed)

---

## 2. Real LLM Smoke Test Results (5 Representative Cases)
| Case ID | Ground-Truth Category | LLM Category | Proposed Policy | Authorized Policy | Guardrail Intervention | Confidence | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `eval_case_001` | **C1** | **C1** | `P_CREATE_LINK_DELAYED` | `P_CREATE_LINK_DELAYED` | NO (Approved) | 0.95 | 2472.67 |
| `eval_case_019` | **C2** | **C2** | `P_CREATE_LINK_IMMEDIATE` | `P_CREATE_LINK_IMMEDIATE` | NO (Approved) | 0.95 | 1933.43 |
| `eval_case_039` | **C3** | **C3** | `P_CREATE_LINK_DELAYED` | `P_CREATE_LINK_DELAYED` | NO (Approved) | 0.95 | 1830.92 |
| `eval_case_055` | **C4** | **C4** | `P_ESCALATE_ONLY` | `P_ESCALATE_ONLY` | NO (Approved) | 1.00 | 1590.37 |
| `eval_case_066` | **C5** | **C5** | `P_NO_ACTION` | `P_NO_ACTION` | NO (Approved) | 1.00 | 1682.72 |

---

## 3. Real MCP Protocol Boundary Verification
- **MCP Server Interface**: `mcp.server.mcpserver.MCPServer` (`paymentflow-eval-mcp`)
- **MCP Client**: `RecoveryAgentClient` executing tool discovery and protocol calls.
- **Read Tools Exercised**: `get_payment_context`, `get_recovery_case`, `get_recovery_status`, `get_allowed_recovery_policies`.
- **Action Tool Exercised**: `request_recovery_action` submitting advisory proposals into `PolicyGuardrailEngine`.
- **Financial Side Effects**: `ZERO` (no Razorpay write APIs invoked; offline safety verified).

---

## 4. Small Controlled LLM Evaluation (15 Cases)
- **Sample Size**: 15 cases (3 per C1-C5 category)
- **Schema Validity Rate**: 100.0%
- **Failure Category Accuracy**: 93.3%
- **Guardrail Intervention Rate**: 0.0% (0 cases)
- **Average LLM Latency**: 1802.52 ms
- **Total Tokens Consumed**: 18,666 tokens
- **Prompt Tokens**: 15,855
- **Completion Tokens**: 2,811
- **Fallback Rate**: 0 fallbacks across 20 calls (0.0%)

---

## 5. Full Evaluation Decision
### Status: `FULL EVALUATION JUSTIFIED VIA 75 DISTINCT DECISIONS x 50 CRN DRAWS`
**Rationale**: The model demonstrated 100% schema validity, zero fallback errors, stable sub-3s latency, and perfect compliance with deterministic guardrails. In accordance with sound statistical methodology, the 75 evaluation cases each receive a distinct LLM policy proposal, which is subsequently evaluated against 50 Common Random Number (CRN) customer response draws (3,750 simulated outcomes) rather than wastefully making 3,750 identical API calls.

---

## 6. Distinction of Evaluation Modes
1. **Offline Verification**: Unit and mock transport tests ensuring zero regressions and fail-closed error handling.
2. **Live Validation**: Real Google Gemini LLM calls producing structured JSON proposals through the MCP boundary.
3. **Synthetic Evaluation**: 75-case benchmark evaluated across 50 stochastic Common Random Number (CRN) customer response draws.
4. **What is NOT Demonstrated**: Production merchant uplift (requires live merchant traffic and Razorpay write execution in Layer 6+).
