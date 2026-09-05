# PaymentFlow Recovery Agent — System Architecture

## 1. System Overview & Philosophy

**PaymentFlow** is an autonomous AI-driven revenue recovery agent designed for Razorpay's payment infrastructure (Track 03 — AI for Revenue Recovery). It recovers revenue lost to dropouts, network timeouts, and soft card friction while strictly enforcing deterministic safety boundaries.

The core architectural tenet of PaymentFlow is:

> **"AI Recommends. Deterministic Policy Authorizes. The Gateway Verifies."**

Large Language Models (LLMs) excel at reasoning over unstructured data, interpreting ambiguous gateway error messages, and choosing nuanced recovery strategies. However, in financial systems, non-deterministic models must never hold unmediated execution authority over money movement. PaymentFlow enforces absolute separation between the **probabilistic advisory layer** (LLM + MCP) and the **authoritative deterministic gatekeeper** (`PolicyGuardrailEngine`).

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PaymentFlow Runtime Architecture                   │
└─────────────────────────────────────────────────────────────────────────────┘
  Incoming Webhook (payment.failed)
            │
            ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 1: Ingestion & Idempotency (HMAC-SHA256, deduplication)             │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 2: Context Enrichment, C1–C5 Classification & Eligibility          │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 3: Advisory AI & MCP Protocol Boundary (gemini-3.5-flash-lite)     │
 │          - Receives sanitized DecisionContext (no ground-truth leakage)  │
 │          - Emits structured AgentDecision proposal via MCP tool          │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 4: Deterministic PolicyGuardrailEngine (Defense-in-Depth)           │
 │          - Amount & Currency Immutability                                │
 │          - High-Value Escalation Threshold (> ₹50,000)                   │
 │          - 24-Hour Cooldown Limits (Max 3 attempts)                      │
 │          - Single Active Link Invariant                                  │
 │          - Category Restrictions (C4 Escalate, C5 Terminal Halt)         │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 5: Bounded Recovery Execution (RecoveryExecutor)                   │
 │          - Row-level database locking (SELECT ... FOR UPDATE)            │
 │          - Immediate Link Dispatch or Restart-Safe Delayed Scheduling    │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Layer 6: Verification & Attribution (Webhook payment_link.paid)          │
 │          - 100% Captured-Only Revenue Verification                       │
 │          - Immutable Append-Only Audit Logging                           │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End Pipeline Layers

### Layer 1: Ingestion & Idempotency
- **Signature Verification**: Validates `X-Razorpay-Signature` via HMAC-SHA256 against `RAZORPAY_WEBHOOK_SECRET`. Rejects unauthorized payloads immediately.
- **Idempotency Guard**: Extracts `event_id` and checks against `webhook_events` table. Duplicate events are acknowledged with HTTP 200 and logged without re-triggering triage.
- **Case Initialization**: Creates a `RecoveryCaseModel` record in state `FAILED_INGESTED`.

### Layer 2: Enrichment, Classification & Deterministic Eligibility
- **Context Enrichment**: Enriches the case with payment context (amount in paise, currency, customer metadata, error code, error description, failure step). In live production, pulls from Razorpay Gateway API; in offline benchmark, loads synthetic event payloads.
- **C1–C5 Failure Taxonomy**:
  - **C1 (Customer Dropout / Authentication Friction)**: OTP timeout, user cancelled, checkout abandonment.
  - **C2 (Network & Gateway Degradation)**: Acquiring bank timeout, PSP downtime, connection drop.
  - **C3 (Instrument & Balance Limits)**: Insufficient funds, temporary card balance limit.
  - **C4 (Business & Risk Rejection)**: AML trigger, card risk blacklist, fraud score threshold.
  - **C5 (Technical & Integration Defects)**: Invalid merchant key, malformed request, unsupported currency.
- **Eligibility Engine**: Deterministically validates prerequisites (currency == `INR`, age < 72 hours, state freshness, not already paid).

### Layer 3: Advisory AI & MCP Boundary
- **Model**: Google Gemini `gemini-3.5-flash-lite` (supports OpenAI protocol fallback).
- **Protocol**: Model Context Protocol (MCP standard).
- **Context Isolation**: The model receives strictly sanitized `DecisionContext` containing only public payment diagnostics. It has zero visibility into customer intent scores or ground-truth simulation variables.
- **Advisory Role**: Proposes one of four allowed policies:
  - `P_CREATE_LINK_IMMEDIATE`
  - `P_CREATE_LINK_DELAYED`
  - `P_ESCALATE_ONLY`
  - `P_NO_ACTION`
- **Output Schema**: Validated against Pydantic `AgentDecision` schema (`extra="forbid"`). Any schema breach or network timeout triggers fail-closed fallback to `P_NO_ACTION` (or `P_ESCALATE_ONLY` if high-value).

### Layer 4: Authoritative PolicyGuardrailEngine
Every proposal must pass through the deterministic guardrail gate before any action can occur:
1. **Amount Immutability**: Recovery amount must exactly match the original failed transaction amount.
2. **Currency Immutability**: Recovery currency must match original currency (strictly INR).
3. **High-Value Cap**: Any transaction $> ₹50,000$ (5,000,000 paise) is deterministically downgraded to `P_ESCALATE_ONLY`.
4. **Anti-Spam / Cooldown**: Maximum 3 recovery attempts per customer in any rolling 24-hour window.
5. **Single Active Link**: Exactly one unpaid recovery link allowed per failed transaction.
6. **Category Constraints**: C4 Risk failures are forced to `P_ESCALATE_ONLY`; C5 Technical failures are forced to `P_NO_ACTION`.

### Layer 5: Bounded Recovery Execution (`RecoveryExecutor`)
- **Concurrency Safety**: Uses PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) to prevent race conditions during parallel webhook deliveries.
- **Immediate Recovery (`P_CREATE_LINK_IMMEDIATE`)**: Invokes Razorpay Payment Link API, attaches metadata, records short URL, transitions case to `ACTION_EXECUTED`.
- **Restart-Safe Delayed Recovery (`P_CREATE_LINK_DELAYED`)**: Computes backoff maturity window and persists `scheduled_at` timestamp in PostgreSQL. The background recovery worker polls matured cases, re-verifies case freshness (ensuring order wasn't paid in the interim), and dispatches the link.

### Layer 6: Verification, Attribution & Audit Trail
- **Captured-Only Attribution**: Revenue is never attributed upon link creation or customer click. Only when Razorpay delivers a signed `payment_link.paid` webhook and the transaction status is verified as `captured` is revenue credited.
- **Immutable Audit Trail**: Every decision, classification, guardrail validation, link creation, and attribution event is appended to `audit_events` with timestamp, actor, decision, and details payload.

---

## 3. Backend Architecture

- **Runtime**: Python 3.12 + FastAPI asynchronous REST framework.
- **Database Layer**: PostgreSQL accessed via SQLAlchemy 2.0 async engine (`asyncpg`).
- **Migrations**: Alembic with 6 version-controlled linear migrations (`0001_initial_schema` to `0006_case_source_eval_runs`).
- **Configuration**: Pydantic `BaseSettings` reading environment variables with zero in-code secrets.
- **Service Layer**:
  - `WebhookService`: Signature validation and idempotency.
  - `RecoveryTriageService`: Context enrichment, classification, and deterministic eligibility.
  - `RecoveryOrchestrator`: Full pipeline execution coordinating MCP, AI advisory, guardrails, and execution.
  - `RecoveryExecutor`: Razorpay API client with row-level database locking.
  - `BenchmarkRunner`: Controlled benchmark batch runner for evaluation.

---

## 4. Frontend Architecture (Operator Console)

The **PaymentFlow Recovery Intelligence Console** is an independently deployable Single-Page Application (SPA) built with React 18, TypeScript, Vite, and Tailwind CSS.

### Operational Surfaces
1. **Executive Overview (`/#overview`)**:
   - Primary KPI Ribbon: Revenue at Risk, Recovered Revenue, Recovery Rate, Active Links, Gated Operations.
   - 6-Stage Recovery Funnel: `FAILED_INGESTED` $\rightarrow$ `CONTEXT_RETRIEVED` $\rightarrow$ `ELIGIBILITY_CHECKED` $\rightarrow$ `ACTION_APPROVED` $\rightarrow$ `ACTION_EXECUTED` $\rightarrow$ `RECOVERED`.
   - C1–C5 Failure Intelligence breakdown.
   - Live cases stream with instant triage triggers.
2. **Cases Explorer (`/#cases`)**:
   - Multi-state filtering, search by IDs, pagination.
   - Batch delayed execution worker trigger (`POST /cases/delayed/process`).
   - Exact integer paise and formatted INR display.
3. **Case Decision Story (`/#investigation?id=...`)**:
   - 8-stage chronological narrative explaining *why* a case was recovered, delayed, escalated, or halted.
   - AI Advisory vs Guardrail Gate comparison.
   - Immutable audit trail.
4. **MCP & Safety Architecture (`/#mcp`)**:
   - Visual boundary map separating LLM tools from deterministic execution.
   - Guardrail invariant definitions.
5. **System Health Diagnostics (`/#health`)**:
   - Live `/health` diagnostic probe verifying DB connection, Gemini provider, and migration status.

### Design System & Theme
- **Fintech Dark Mode**: `#090B0E` background, `#161B22` surface, `#21262D` cards.
- **Typography**: Inter for UI text; JetBrains Mono for monetary amounts, IDs, and telemetry.
- **Two-Zone Semantics**: Violet (`#7C3AED`) for AI advisory elements; Teal (`#0D9488`) for deterministic guardrail enforcement.

---

## 5. State Machine Invariants

```text
               ┌─────────────────┐
               │ FAILED_INGESTED │
               └────────┬────────┘
                        │ Context Enriched & Classified
                        ▼
               ┌─────────────────┐
               │ CONTEXT_RETRIEVED│
               └────────┬────────┘
                        │ Eligibility Evaluated
                        ▼
               ┌─────────────────────┐
               │ ELIGIBILITY_CHECKED │
               └────────┬────────────┘
                        │ Guardrails Authorized
        ┌───────────────┼───────────────┬────────────────┐
        ▼               ▼               ▼                ▼
┌───────────────┐ ┌───────────┐ ┌───────────────┐ ┌─────────────┐
│ACTION_APPROVED│ │ ESCALATED │ │TERMINAL_NO_ACT│ │ (Ineligible)│
└───────┬───────┘ └───────────┘ └───────────────┘ └─────────────┘
        │ Razorpay Link Dispatched
        ▼
┌────────────────┐
│ ACTION_EXECUTED│
└───────┬────────┘
        │ payment_link.paid verified captured
        ▼
┌────────────────┐
│   RECOVERED    │
└────────────────┘
```

1. **Forward-Only Transitions**: Cases cannot transition backward (e.g., from `RECOVERED` to `FAILED_INGESTED`).
2. **Terminal States**: `RECOVERED`, `ESCALATED`, and `TERMINAL_NO_ACTION` are terminal.
3. **Attribution Guard**: A case can only enter `RECOVERED` if a verified Razorpay payment ID exists with status `captured`.
