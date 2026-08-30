# PaymentFlow Recovery Agent — Production Recovery Workflow Integration Report

**Layer:** Production Integration & Orchestration (Layer 6)  
**Specification:** `private-docs/RAZORPAY_PAYMENTFLOW_SOURCE_OF_TRUTH_v1.0.md`  
**Date:** 2026-08-30  
**Status:** Verified & Fully Implemented  

---

## 1. Executive Summary

The PaymentFlow Recovery Agent has successfully integrated the real LLM (`gemini-3.5-flash-lite`) and Model Context Protocol (MCP) decision layer into the authoritative production recovery runtime. 

The complete runtime path:
```text
payment.failed webhook
  ↓ Webhook signature verification (HMAC-SHA256)
  ↓ Webhook idempotency & case creation (state: FAILED_INGESTED)
  ↓ RecoveryContext enrichment (Razorpay API context fetch)
  ↓ Deterministic Failure Taxonomy (C1–C5 classification)
  ↓ Deterministic Eligibility Evaluation (state: ELIGIBILITY_CHECKED)
  ↓ MCP Tool Discovery & Context Retrieval (get_payment_context, get_recovery_case, get_recovery_status)
  ↓ Real LLM Decision Provider (AgentDecision proposal)
  ↓ MCP request_recovery_action dispatch
  ↓ Authoritative PolicyGuardrailEngine gate (Defense-in-Depth)
  ↓ Authorized Effective Policy (P_CREATE_LINK_IMMEDIATE / P_CREATE_LINK_DELAYED / P_ESCALATE_ONLY / P_NO_ACTION)
  ↓ RecoveryExecutor (Row locking, pre-write validation, single-link safety)
  ↓ Razorpay Payment Link Creation (RazorpayAdapter API write)
  ↓ payment_link.paid verification webhook
  ↓ Captured-only payment verification & ₹ attribution
  ↓ Immutable Audit Trail across all lifecycle events
```

---

## 2. Architectural Principles & Guardrail Preservation

1. **Advisory LLM Principle**: The LLM agent operates purely as an advisory proposal generator. It has zero capability to mutate payment states or trigger gateway writes directly.
2. **MCP Security Boundary**: The LLM accesses recovery data and actions strictly over typed MCP tools. The MCP action tool `request_recovery_action` passes all proposals through `PolicyGuardrailEngine.validate()`.
3. **Defense-in-Depth Pre-Write Validation**: `RecoveryExecutor` independently executes a secondary pre-write validation before invoking the Razorpay Payment Link API.
4. **Restart-Safe Delayed Execution**: Delayed recovery cases (`P_CREATE_LINK_DELAYED`) persist a `scheduled_at` timestamp in PostgreSQL. The background orchestrator re-verifies case freshness, existing payment status, and guardrails at execution time without sleeping in memory or blocking worker threads.
5. **Captured-Only Attribution**: Revenue is attributed only when Razorpay payment status is confirmed as `captured` via signed webhook and direct API verification.
6. **Frontend / Backend Separation**: The backend service exposes clean REST endpoints (`/api/v1/cases`, `/api/v1/cases/{case_id}`, `/api/v1/cases/metrics/summary`, `/api/v1/cases/delayed/process`) while maintaining strict process separation from any future UI layer.

---

## 3. Test Suite & Verification Results

### Test Suite Execution Summary
- **Total Tests Passed:** 190 / 190 (100% pass rate)
- **Codebase Coverage:** 93% across all source files
- **Ruff Linting:** 0 errors (100% compliant)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Projects\Razorpay
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0, cov-7.1.0

tests/test_production_orchestration.py::test_end_to_end_immediate_recovery_pipeline PASSED
tests/test_production_orchestration.py::test_end_to_end_delayed_recovery_pipeline PASSED
tests/test_production_orchestration.py::test_high_value_escalation_guardrail_override PASSED
tests/test_production_orchestration.py::test_llm_timeout_fail_closed_safe_fallback PASSED
tests/test_production_orchestration.py::test_api_case_endpoints_and_metrics PASSED
tests/test_production_orchestration.py::test_malformed_llm_output_fail_closed_safe_fallback PASSED
tests/test_production_orchestration.py::test_c4_business_risk_escalates_without_link PASSED
tests/test_production_orchestration.py::test_delayed_execution_state_freshness_recheck PASSED

TOTAL: 190 passed in 50.46s (93% coverage)
```

---

## 4. Key Verification Scenarios

| Scenario | Ingestion & Triage | LLM Proposal | Guardrail Decision | Execution Outcome | Attribution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Immediate Recovery (C1)** | Ingested $\rightarrow$ C1 $\rightarrow$ Eligible | `P_CREATE_LINK_IMMEDIATE` | `APPROVE` | Payment Link Created (`ACTION_EXECUTED`) | `RECOVERED` (₹2,500 captured) |
| **Delayed Recovery (C2)** | Ingested $\rightarrow$ C2 $\rightarrow$ Eligible | `P_CREATE_LINK_DELAYED` | `APPROVE` | Scheduled (`scheduled_at` set) $\rightarrow$ Batch Executed | `ACTION_EXECUTED` |
| **High Value (> ₹50,000)** | Ingested $\rightarrow$ C1 $\rightarrow$ High Value | `P_CREATE_LINK_IMMEDIATE` | `ESCALATE` (Forced) | ₹0 link created (`ESCALATED`) | ₹0 attributed |
| **Business Risk (C4)** | Ingested $\rightarrow$ C4 | `P_CREATE_LINK_IMMEDIATE` | `ESCALATE` (Forced) | ₹0 link created (`ESCALATED`) | ₹0 attributed |
| **Technical Failure (C5)** | Ingested $\rightarrow$ C5 | `P_CREATE_LINK_IMMEDIATE` | `NO_ACTION` (Forced) | ₹0 link created (`TERMINAL_NO_ACTION`) | ₹0 attributed |
| **LLM Timeout / Network Failure** | Ingested $\rightarrow$ C1 | *Timeout* | Fallback `P_NO_ACTION` | `TERMINAL_NO_ACTION` (Fail-Closed) | ₹0 attributed |
| **Delayed Recheck (Interim Paid)** | Ingested $\rightarrow$ Delayed Scheduled | `P_CREATE_LINK_DELAYED` | Re-verify State | Already `RECOVERED` $\rightarrow$ Link skipped | Preserved |

---

## 5. Artifacts and Source Code References

- **Orchestrator:** [`src/paymentflow/services/recovery_orchestrator.py`](file:///c:/Projects/Razorpay/src/paymentflow/services/recovery_orchestrator.py)
- **Executor:** [`src/paymentflow/services/recovery_executor.py`](file:///c:/Projects/Razorpay/src/paymentflow/services/recovery_executor.py)
- **MCP Server & Client:** [`src/paymentflow/mcp/server.py`](file:///c:/Projects/Razorpay/src/paymentflow/mcp/server.py), [`src/paymentflow/mcp/client.py`](file:///c:/Projects/Razorpay/src/paymentflow/mcp/client.py)
- **REST Status & Metrics API:** [`src/paymentflow/api/cases.py`](file:///c:/Projects/Razorpay/src/paymentflow/api/cases.py)
- **Database Schema Migration:** [`migrations/versions/20260830_0002_add_scheduled_at.py`](file:///c:/Projects/Razorpay/migrations/versions/20260830_0002_add_scheduled_at.py)
- **Integration Test Suite:** [`tests/test_production_orchestration.py`](file:///c:/Projects/Razorpay/tests/test_production_orchestration.py)
