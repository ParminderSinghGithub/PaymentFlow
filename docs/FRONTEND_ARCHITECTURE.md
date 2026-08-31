# PaymentFlow Recovery Agent — Frontend Architecture (Layer 6)

## 1. System Overview & Boundaries

The **PaymentFlow Recovery Intelligence Console** is an independently deployable Single-Page Application (SPA) built with React 18, TypeScript, Vite, and Tailwind CSS. It serves as an AI/fintech operations console for monitoring, explaining, and executing autonomous payment recovery workflows.

```text
┌────────────────────────────────────────────────────────────┐
│         PaymentFlow Recovery Intelligence Console          │
│            (React + TypeScript + Vite + Tailwind)          │
└──────────────────────────────┬─────────────────────────────┘
                               │ HTTPS / REST (CORS enabled)
                               ▼
┌────────────────────────────────────────────────────────────┐
│                    PaymentFlow Backend                     │
│               (FastAPI @ http://localhost:8000)            │
├──────────────────────────────┬─────────────────────────────┤
│  /health                     │  /cases                     │
│  /cases/metrics/summary      │  /cases/{case_id}           │
│  /cases/{case_id}/triage     │  /cases/delayed/process     │
└──────────────────────────────┴─────────────────────────────┘
```

---

## 2. Information Architecture & Navigation

The application shell provides 5 primary operational surfaces:

1. **Executive Overview (`/ #overview`)**:
   - Top-level operational KPIs (Total Recovered Revenue in ₹, Recovery Conversion Rate %, Processed Cases, Active Payment Links).
   - Interactive 6-stage lifecycle funnel (`FAILED_INGESTED` $\rightarrow$ `CONTEXT_RETRIEVED` $\rightarrow$ `ELIGIBILITY_CHECKED` $\rightarrow$ `ACTION_APPROVED` $\rightarrow$ `ACTION_EXECUTED` $\rightarrow$ `RECOVERED`).
   - C1–C5 Failure Intelligence Matrix.
   - Live cases stream with one-click AI triage execution.

2. **Cases Explorer (`/ #cases`)**:
   - Multi-state filtering (`ALL`, `RECOVERED`, `ACTION_EXECUTED`, `ACTION_APPROVED`, `ESCALATED`, `TERMINAL_NO_ACTION`, `FAILED_INGESTED`).
   - Full-text search across Case ID, Payment ID, Order ID, Customer ID.
   - Batch delayed execution trigger (`POST /cases/delayed/process`).
   - Precise financial grid displaying both exact integer paise and formatted INR values.

3. **Case Decision Story & Investigation (`/ #investigation?id=...`)**:
   - **Decision Story Mode**: Sequential 8-stage narrative explaining *why* the transaction was recovered, delayed, escalated, or halted.
   - **AI Proposal vs. Guardrail Gate**: Visual side-by-side card contrasting the advisory LLM proposal against the authoritative `PolicyGuardrailEngine` validation.
   - **Immutable Chronological Audit Trail**: Complete event history (`CONTEXT_ENRICHED`, `FAILURE_CLASSIFIED`, `ELIGIBILITY_EVALUATED`, `POLICY_GUARDRAIL_VALIDATED`, `RAZORPAY_PAYMENT_LINK_CREATED`, `RECOVERED`).
   - **Live Triage Action Trigger**: Execute `/cases/{case_id}/triage` with immediate real-time state synchronization.

4. **MCP Boundary & Safety Architecture (`/ #mcp`)**:
   - Interactive visual map of the Model Context Protocol boundary.
   - Tool isolation documentation: Read tools (`get_payment_context`, `get_recovery_case`, `get_recovery_status`) vs guarded Action tool (`request_recovery_action`).
   - Deterministic Guardrail Safety Invariants table (Amount Immutability, Currency Immutability, Single Active Link, Customer Cooldown, High-Value Escalation > ₹50,000, Captured-Only Attribution).

5. **System Operational Diagnostics (`/ #health`)**:
   - Real-time `/health` diagnostics probe.
   - Service health status (FastAPI Backend, asyncpg PostgreSQL connection, Gemini AI provider, Alembic migration head).
   - Architectural milestone verification across Layers 0 to 6.

---

## 3. Design System & Aesthetics

- **Theme**: Fintech Dark Mode (`#090B0E` background, `#161B22` surface, `#21262D` elevated cards).
- **Typography**: `Inter` for primary text; `JetBrains Mono` for IDs, amounts, hashes, error codes, and audit telemetry.
- **Color Semantics**:
  - `Emerald (#10B981)`: Captured payments, verified attribution, successful executions.
  - `Sky / Brand (#38BDF8)`: Action executed, active links, interactive elements.
  - `Blue (#3B82F6)`: Action approved, delayed recovery scheduling.
  - `Amber (#F59E0B)`: Ingestion, soft infrastructure timeouts, warnings.
  - `Rose (#EF4444)`: Risk escalation (C4), fraud checks, guardrail rejections.
  - `Zinc (#71717A)`: Technical defects (C5), terminal no-action outcomes.
- **Motion**: Subtle CSS keyframe animations (`animate-fade-in`, `animate-slide-up`, `animate-live-dot`) with `prefers-reduced-motion` compliance.

---

## 4. Production Deployment & Security

- **Zero Secrets Shipped**: No API keys, database credentials, or private webhook secrets are bundled into the client build.
- **Containerization**: Multi-stage `frontend/Dockerfile` building with Node 22 and serving via Nginx Alpine with gzip compression and SPA fallback routing (`try_files $uri $uri/ /index.html`).
- **CORS Handling**: Backend FastAPI service enables CORS requests from the frontend origin via configured `CORSMiddleware`.
