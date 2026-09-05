# PaymentFlow — AI Revenue Recovery
### Razorpay Buildathon · Track 03: AI Revenue Recovery

[![Tests](https://img.shields.io/badge/tests-328%20passing-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.12-blue)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](src/paymentflow/main.py)
[![React](https://img.shields.io/badge/React-18-61dafb)](frontend/package.json)

> **"AI recommends. Deterministic policy authorizes. Razorpay executes. System verifies."**

PaymentFlow is a policy-first agentic revenue-recovery system for failed one-time Razorpay payments. It uses constrained LLM reasoning (Google Gemini via MCP) behind a deterministic guardrail engine to identify recoverable payment failures, dispatch Razorpay Payment Links, and attribute recovered revenue only after gateway capture is confirmed.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture Overview](#architecture-overview)
3. [Services](#services)
4. [The AI Safety Model](#the-ai-safety-model)
5. [Recovery Flow](#recovery-flow)
6. [Demo: End-to-End Walkthrough](#demo-end-to-end-walkthrough)
7. [Quickstart (Local Development)](#quickstart-local-development)
8. [Environment Variables](#environment-variables)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [API Reference](#api-reference)
12. [Benchmark & Evaluation](#benchmark--evaluation)
13. [Design Decisions & Limitations](#design-decisions--limitations)
14. [Project Structure](#project-structure)

---

## What It Does

When a customer's Razorpay checkout fails, merchants typically lose the revenue with no intelligent follow-up. PaymentFlow solves this by:

1. **Ingesting** `payment.failed` webhooks from Razorpay with HMAC-SHA256 signature verification
2. **Diagnosing** the failure using an empirical C1–C5 taxonomy (soft/transient vs. hard/terminal)
3. **Advising** via Gemini LLM through a sanitized MCP data contract — the LLM never touches the database or gateway credentials
4. **Authorizing** only through a deterministic `PolicyGuardrailEngine` that enforces 8 financial invariants
5. **Executing** a bounded Razorpay Payment Link dispatch (new payment opportunity — never retrying the original failed payment)
6. **Verifying** revenue attribution only after authoritative gateway capture confirmation
7. **Surfacing** results in a real-time Operator Console and the customer-facing Merchant Storefront

### What PaymentFlow Does NOT Do

- It does **not** retry, resurrect, or force-capture the original failed payment
- It does **not** grant the LLM write access to the database or gateway
- It does **not** claim revenue recovered until `payment.captured` is confirmed by Razorpay
- It does **not** handle subscriptions, mandates, recurring payments, or fraud scoring

---

## Architecture Overview

```
Customer Checkout (Apex Gear Co. Storefront)
       |
       v  (intentional failure in Razorpay Test Mode)
Razorpay Gateway ---- payment.failed webhook --------------------------+
       |                                                               v
       |                                              PaymentFlow Backend (FastAPI)
       |                                              +--------------------------+
       |                                              | 1. Webhook Ingestion     |
       |                                              |    HMAC-SHA256 Verify    |
       |                                              | 2. C1-C5 Diagnosis       |
       |                                              | 3. Gemini AI Advisory    |
       |                                              |    (MCP / read-only)     |
       |                                              | 4. Guardrail Engine      |
       |                                              |    (8 invariants)        |
       |                                              | 5. Payment Link Create   |
       |                                              +--------------------------+
       |                                                          |
       +<--- Recovery Link surfaced in Storefront ----------------+
       |
Customer pays recovery link
       |
       v  (payment_link.paid webhook -> payment.captured)
Revenue Attribution (row-level lock, single attribution guarantee)
       |
       v
Operator Console: RECOVERED | Rs.X,XXX.XX | Gateway Verified
```

---

## Services

| Service | Tech | Source | Deployed |
|---|---|---|---|
| **PaymentFlow Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, asyncpg | `src/paymentflow/` | Railway |
| **Merchant Demo** | Python 3.12, FastAPI (server) + Vanilla JS (UI) | `apps/merchant-demo/` | Railway |
| **Operator Console** | React 18, Vite, TypeScript, Tailwind CSS | `frontend/` | Vercel |
| **Database** | PostgreSQL 16 (Neon in production) | Alembic migrations | Neon |

### Service Boundaries

- **Backend → Razorpay**: Razorpay API HTTP calls (test mode keys)
- **Backend → Gemini**: `httpx` HTTP client via MCP tool protocol
- **Merchant Demo → Backend**: HTTP REST with `X-PaymentFlow-Key` API key authentication
- **Operator Console → Backend**: HTTP REST (`VITE_API_BASE_URL`)
- **Razorpay → Backend**: Webhook `POST /webhooks/razorpay` (HMAC-SHA256 verified)

---

## The AI Safety Model

PaymentFlow enforces a hard boundary between LLM advisory and transactional execution:

```
+----------------------------------+-----------------------------------+
| LLM Reasoning (Advisory Only)    | PolicyGuardrailEngine (Gate)      |
+----------------------------------+-----------------------------------+
| - Consumes sanitized MCP data    | - Sole write-authorization gate   |
| - Diagnoses failure root cause   | - Amount immutability (paise)     |
| - Proposes policy and timing     | - Currency allowlist (INR only)   |
| - Suggests customer message      | - High-value threshold Rs.50,000  |
| - No gateway credentials         | - Single-link limit per case      |
| - No database write access       | - 24h customer cooldown           |
| - No payment authorization       | - Hard C4/C5 escalation block     |
+----------------------------------+-----------------------------------+
```

The LLM is **never** granted authority to create payment links, modify amounts, capture payments, or declare revenue recovered.

---

## Recovery Flow

### Failure Classification (C1–C5 Taxonomy)

| Class | Description | Recovery Policy |
|---|---|---|
| **C1** | Customer dropoff (soft) | `P_CREATE_LINK_IMMEDIATE` — link within minutes |
| **C2** | Gateway/bank downtime (transient) | `P_CREATE_LINK_DELAYED` — link after cooling-off |
| **C3** | Insufficient funds / method limit (soft) | Alternative method recommendation |
| **C4** | Fraud, risk, AML flags (hard) | `P_ESCALATE_ONLY` — unconditional human escalation |
| **C5** | Terminal / invalid card / closed account (hard) | `P_NO_ACTION` — no link dispatched |

### Guardrail Invariants (8 Rules)

1. Amount must be positive and match original failure exactly (paise precision)
2. Currency must be INR
3. Amount must not exceed Rs.50,000
4. Case must not already have an active payment link
5. Customer must not be in 24-hour cooldown
6. C4 (fraud/risk) cases must always escalate — no exceptions
7. C5 (terminal) cases receive no link
8. Recovery opportunity bounded to single link per case

---

## Demo: End-to-End Walkthrough

### Live Test Mode Demo (Two-Tab Flow)

**Prerequisites:** Backend, Merchant Demo, and Operator Console all running (locally or deployed).

**Tab 1 — Merchant Storefront** (`http://localhost:8002` or deployed URL):

1. Browse the Apex Gear Co. product catalog
2. Add a product to cart and proceed to checkout
3. Enter your phone number (required for recovery), name and email are optional
4. In Razorpay Test Mode checkout:
   - **To trigger failure:** UPI -> VPA: `failure@razorpay`
   - **Or card path:** Card `4111 1111 1111 1111`, any future expiry, CVV `123` -> click **"Failure"** on OTP screen
5. Payment fails -> webhook fires -> PaymentFlow creates recovery link
6. Storefront polls `/api/recovery-status` and surfaces the recovery link
7. Click the recovery link -> complete payment:
   - **UPI success:** VPA `success@razorpay`
   - **Card success:** Same card -> click **"Success"** on OTP screen

**Tab 2 — Operator Console** (`http://localhost:5173` or Vercel URL):

- Watch the case move through: `INGESTED -> DIAGNOSED -> AI_ADVISORY -> GUARDRAIL_APPROVED -> ACTION_EXECUTED -> RECOVERED`
- Each stage shows: AI reasoning, guardrail invariant checks, gateway payment ID, attributed cash

### Synthetic Benchmark Demo

From the Operator Console:

1. Click **"Run Benchmark"** to execute the 15-case synthetic evaluation harness
2. View: Diagnosis Accuracy, Action Match Rate, Guardrail Compliance, Eligible Recovery Rate
3. All metrics are labeled **"Synthetic Evaluation"** — no real money moves

---

## Quickstart (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (or Docker)
- Razorpay Test Mode account (free)
- Google Gemini API key (free tier available)

### 1. Clone & Configure

```bash
git clone <repo-url>
cd Razorpay
cp .env.example .env
# Edit .env with your Razorpay test keys and Gemini API key
```

### 2. Start Database

```bash
# Option A: Docker
docker compose up -d db

# Option B: Local PostgreSQL — create DB: paymentflow_db, user: paymentflow_user
```

### 3. Install Backend & Run Migrations

```bash
# Using uv (recommended)
pip install uv
uv sync
uv run alembic upgrade head
uv run uvicorn paymentflow.main:app --host 0.0.0.0 --port 8001 --reload

# Or pip
pip install -e ".[dev]"
alembic upgrade head
uvicorn paymentflow.main:app --host 0.0.0.0 --port 8001 --reload
```

Backend: `http://localhost:8001` · API docs: `http://localhost:8001/docs`

### 4. Start Merchant Demo

```bash
cd apps/merchant-demo
pip install fastapi uvicorn pydantic pydantic-settings httpx
RAZORPAY_KEY_ID=rzp_test_xxx RAZORPAY_KEY_SECRET=xxx \
  PAYMENTFLOW_API_KEY=pf_live_test_merchant_key_2026 \
  PAYMENTFLOW_API_URL=http://localhost:8001 \
  uvicorn server.main:app --host 0.0.0.0 --port 8002
```

Merchant Storefront: `http://localhost:8002`

### 5. Start Operator Console

```bash
cd frontend
npm install
# Edit .env: VITE_API_BASE_URL=http://localhost:8001
npm run dev
```

Operator Console: `http://localhost:5173`

### 6. Full Stack via Docker Compose

```bash
cp .env.example .env
# Fill in real keys in .env
docker compose up --build
```

Services: Backend `:8001`, Merchant `:8002`

---

## Environment Variables

### Backend (`src/paymentflow/config.py`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` — async DB connection (asyncpg driver) |
| `RAZORPAY_KEY_ID` | Yes | Razorpay Test Mode Key ID (`rzp_test_...`) |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay API Key Secret |
| `RAZORPAY_WEBHOOK_SECRET` | Yes | Dedicated webhook signing secret (from Razorpay Dashboard) |
| `LLM_API_KEY` / `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `PAYMENTFLOW_API_KEY` | Yes | Server-to-server merchant API key (shared with Merchant Demo) |
| `CORS_ORIGINS` | Yes (prod) | Comma-separated or JSON array of allowed frontend origins |
| `ENVIRONMENT` | No | `development` / `production` (default: `development`) |
| `LLM_MODEL` | No | Gemini model name (default: `gemini-1.5-flash`) |
| `LLM_PROVIDER_TYPE` | No | `gemini` / `mock` (default: `gemini`) |
| `PORT` / `APP_PORT` | No | Server port (Railway injects `PORT`, default: `8000`) |
| `PUBLIC_BASE_URL` | No | Public HTTPS URL (for webhook URL construction) |

### Merchant Demo (`apps/merchant-demo/server/config.py`)

| Variable | Required | Description |
|---|---|---|
| `RAZORPAY_KEY_ID` | Yes | Razorpay Test Mode Key ID |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay API Key Secret |
| `PAYMENTFLOW_API_KEY` | Yes | Must match backend `PAYMENTFLOW_API_KEY` |
| `PAYMENTFLOW_API_URL` | Yes | Backend base URL (e.g. `https://paymentflow-backend-*.railway.app`) |
| `PORT` | No | Server port (default: `8002`) |

### Operator Console (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Backend URL (e.g. `https://paymentflow-backend-*.railway.app`) |
| `VITE_MERCHANT_STOREFRONT_URL` | No | Merchant demo URL (auto-derived from backend URL if on Railway) |

---

## Testing

### Backend (328 tests)

```bash
# Run all tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=paymentflow --cov-report=term-missing

# Lint + format check
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

**Test coverage includes:**

- Webhook ingestion, HMAC signature verification, idempotency deduplication
- C1–C5 failure classification accuracy across all error codes
- PolicyGuardrailEngine — all 8 invariants, including edge cases
- RecoveryOrchestrator state machine transitions
- Revenue attribution with row-level lock semantics
- LLM provider mock harness (gemini/openai/mock protocol)
- Benchmark evaluation harness (15 canonical synthetic cases)
- Merchant API boundary: authentication, tenant isolation, cross-tenant rejection

### Frontend (15 tests)

```bash
cd frontend
npm test
```

Frontend tests cover: API client URL resolution, merchant storefront domain derivation, environment variable handling.

---

## Deployment

### Deployed Architecture (Production)

| Service | Host | URL |
|---|---|---|
| PaymentFlow Backend | Railway | `https://paymentflow-backend-production.up.railway.app` |
| Merchant Demo | Railway | `https://merchant-demo-production.up.railway.app` |
| Operator Console | Vercel | Your Vercel deployment URL |
| Database | Neon (PostgreSQL) | Connection via `DATABASE_URL` env var |

### Razorpay Webhook Configuration

Configure in Razorpay Dashboard -> Settings -> Webhooks:

- **URL:** `https://paymentflow-backend-production.up.railway.app/webhooks/razorpay`
- **Active Events:** `payment.failed`, `payment.captured`, `payment_link.paid`
- **Secret:** Set as `RAZORPAY_WEBHOOK_SECRET` in Railway backend environment

### Database Migrations (Neon)

```bash
railway run --service paymentflow-backend uv run alembic upgrade head
```

---

## API Reference

Full interactive API docs: `https://paymentflow-backend-production.up.railway.app/docs`

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health + DB connectivity check |
| `POST` | `/webhooks/razorpay` | Razorpay webhook ingestion (HMAC-SHA256 verified) |
| `GET` | `/cases` | List recovery cases (filterable by state, source) |
| `GET` | `/cases/{case_id}` | Case detail with chronological audit trail |
| `GET` | `/cases/metrics/summary` | Aggregated recovery KPIs |
| `POST` | `/cases/{case_id}/triage` | Manually trigger AI recovery orchestration |
| `POST` | `/cases/delayed/process` | Execute due delayed recovery cases |
| `GET` | `/cases/benchmark/latest` | Latest synthetic benchmark results |
| `POST` | `/cases/benchmark/run` | Execute 15-case synthetic benchmark |

### Merchant API (authenticated with `X-PaymentFlow-Key`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/merchant/checkout/context` | Register checkout context pre-gateway |
| `GET` | `/api/v1/merchant/orders/{order_id}/recovery` | Poll recovery link availability |
| `GET` | `/api/v1/merchant/cases/{case_id}/status` | Poll case recovery status |

---

## Benchmark & Evaluation

PaymentFlow includes a versioned synthetic evaluation harness that measures AI agent decision quality against a deterministic baseline.

> **Important:** The benchmark uses fully synthetic data. No real money moves during evaluation.

### Metrics (15 canonical cases across C1–C5)

| Metric | Formula |
|---|---|
| Eligible Recovery Rate | Recovered soft cases / Total eligible soft cases |
| Gross Recovery Rate | Total recovered / Total ingested cases |
| Diagnosis Accuracy | Correct C1–C5 classification / Total cases |
| Action Match Rate | Agent policy matches ground truth / Total cases |
| Guardrail Compliance | 1 - (Guardrail overrides / Total AI proposals) |
| Unnecessary Action Rate | Actions on hard cases (C4/C5) / Total hard cases |

Run the benchmark from the Operator Console UI or via API: `POST /cases/benchmark/run`

---

## Design Decisions & Limitations

### Deliberate Design Choices

**LLM via MCP (not direct DB access):** The Gemini LLM receives a sanitized read-only data contract via MCP. This is the core trust architecture — AI advises, policy authorizes.

**Paise-precision amount handling:** All amounts stored and compared in paise (1 INR = 100 paise). No floating-point arithmetic on financial values.

**Row-level locking for attribution:** `SELECT ... FOR UPDATE` in the attribution path prevents double-attribution even under concurrent webhook delivery.

**Webhook idempotency:** `webhook_events` table deduplicates on `gateway_event_id`. Replayed events return HTTP 200 without re-processing.

**Separate sync/async DB URLs:** `asyncpg` (FastAPI/SQLAlchemy) requires `?ssl=require`. Alembic uses `psycopg2` which requires `?sslmode=require`. The `reconcile_database_urls` validator in `config.py` handles conversion automatically at startup.

### Scope & Limitations (Buildathon Context)

- **Test Mode only:** All Razorpay integration uses Test Mode keys. Payment captures are simulated in Razorpay's sandbox.
- **INR only:** The guardrail engine allowlists only Indian Rupees.
- **Single tenant demo:** Merchant isolation is implemented but the demo uses one primary merchant (`merchant_apex_gear`).
- **No SMS/WhatsApp delivery:** Recovery links are surfaced in the storefront UI and Operator Console. SMS delivery is not available in Razorpay Test Mode.
- **LLM fallback:** If Gemini is unavailable, `LLM_PROVIDER_TYPE=mock` applies deterministic fallback policies without LLM calls.

---

## Project Structure

```
Razorpay/
├── src/paymentflow/           # Backend Python package
│   ├── adapters/              # Razorpay API adapter (test mode)
│   ├── api/                   # FastAPI routes: cases, webhooks, health, merchant, interactive
│   ├── config.py              # Settings (pydantic-settings, DB URL dialect reconciliation)
│   ├── db/                    # SQLAlchemy async session, models
│   ├── domain/                # Entities, C1-C5 taxonomy, policy engine, state machine
│   ├── eval/                  # Synthetic benchmark harness, canonical dataset, LLM evaluator
│   ├── mcp/                   # MCP protocol data contracts for LLM advisory
│   ├── merchant/              # Tenant model, API key authentication
│   ├── services/              # RecoveryOrchestrator, PolicyGuardrailEngine, WebhookService
│   └── main.py                # FastAPI app factory, lifespan, CORS
├── apps/merchant-demo/        # Merchant Reference Application
│   ├── server/                # FastAPI server (Python): orders, recovery polling
│   └── frontend/              # Merchant storefront UI (Vanilla JS / HTML)
├── frontend/                  # Operator Console (React + TypeScript + Vite + Tailwind)
├── migrations/                # Alembic database migrations
├── tests/                     # pytest test suite (328 tests)
├── docker-compose.yml         # Local multi-service stack
├── Dockerfile                 # Backend container (python:3.12-slim, non-root)
└── pyproject.toml             # Python dependencies + tool config
```

---

## Built With

**Backend:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Alembic · pydantic-settings · httpx · MCP SDK

**Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · Vitest

**Merchant Demo:** FastAPI · Vanilla JS

**Database:** PostgreSQL 16 (Neon in production)

**AI:** Google Gemini via MCP tool protocol

**Deployment:** Railway (backend + merchant) · Vercel (frontend) · Neon (database)

---

*Razorpay Buildathon · Track 03 — AI Revenue Recovery*
