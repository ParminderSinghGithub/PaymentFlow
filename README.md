# PaymentFlow — AI Revenue Recovery

> **Razorpay Buildathon · Track 03 — AI Revenue Recovery**

[![Tests](https://img.shields.io/badge/backend%20tests-328%20passing-brightgreen)](#engineering-validation)
[![Frontend](https://img.shields.io/badge/frontend%20tests-15%20passing-brightgreen)](#engineering-validation)
[![Python](https://img.shields.io/badge/python-3.12-3776ab)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)](src/paymentflow/main.py)
[![React](https://img.shields.io/badge/React-18-61dafb)](frontend/package.json)
[![License](https://img.shields.io/badge/license-MIT-informational)](LICENSE)

> **"AI recommends. Deterministic policy authorizes. Razorpay executes. System verifies."**

PaymentFlow is an autonomous, policy-first revenue recovery system for failed Razorpay payments. It combines constrained LLM reasoning (Google Gemini `gemini-3.5-flash-lite` via the Model Context Protocol) with an authoritative deterministic guardrail engine to recover lost revenue from dropouts, network timeouts, and soft card friction. It dispatches official Razorpay Payment Links and attributes recovered revenue if and only if gateway capture is verified.

---

## 🔴 Live Interactive Deployments

| Service | Live URL | Purpose |
|---|---|---|
| **Operator Intelligence Console** | [paymentflow-recovery-agent.vercel.app](https://paymentflow-recovery-agent.vercel.app/) | Operations dashboard — live case monitoring, decision stories & one-click benchmark |
| **Merchant Storefront Demo** | [merchant-demo-production.up.railway.app](https://merchant-demo-production.up.railway.app/) | Apex Gear Co. merchant storefront — simulate checkouts and live failures |
| **Merchant Checkout Page** | [merchant-demo-production.up.railway.app/checkout](https://merchant-demo-production.up.railway.app/checkout) | Direct checkout page with failure simulation triggers |
| **Backend REST API** | [paymentflow-backend-production.up.railway.app](https://paymentflow-backend-production.up.railway.app/) | Asynchronous FastAPI service running on Railway |
| **Interactive Swagger Docs** | [paymentflow-backend-production.up.railway.app/docs](https://paymentflow-backend-production.up.railway.app/docs) | Interactive OpenAPI documentation — inspect & test all endpoints |
| **Health Diagnostics Probe** | [paymentflow-backend-production.up.railway.app/health](https://paymentflow-backend-production.up.railway.app/health) | Live health status: backend, database, Gemini AI provider, and migration status |

---

## The Problem & Opportunity

Approximately 15–20% of Indian e-commerce checkouts fail. A failed transaction is rarely a lost customer—most dropoffs are transient (interrupted network pipes, OTP timeouts, momentary card limit holds). Without an intelligent recovery system, merchants permanently forfeit this revenue and incur high re-acquisition costs.

---

## The PaymentFlow Solution

PaymentFlow ingests `payment.failed` webhooks from Razorpay, enriches diagnostics, classifies the root cause using a normalized **C1–C5 failure taxonomy**, consults a constrained Google Gemini advisory layer via **MCP**, and passes every proposal through the deterministic **PolicyGuardrailEngine**. When safe and compliant, it dispatches an immediate or restart-safe delayed Razorpay Payment Link. Revenue is credited **only after a signed webhook confirms funds are captured**.

---

## Why PaymentFlow Is Different

| Dimension | PaymentFlow Architecture | Typical Industry Approach |
|---|---|---|
| **AI Role** | Advisory only — zero direct DB or write permissions | Unbounded LLM writes directly to gateway |
| **Authorization Gate** | Authoritative deterministic `PolicyGuardrailEngine` | Model prompt instructions / trust-based |
| **Revenue Attribution** | 100% captured-only verification via signed webhooks | Optimistic attribution on link creation |
| **Financial Guardrail** | Mandatory human escalation for transactions $> ₹50,000$ | Automated retries on high-ticket fraud risk |
| **Anti-Tampering** | Mathematical immutability on amount and currency | Prompt-vulnerable discounting or mutation |
| **Anti-Spam / Cooldown** | Max 3 attempts per rolling 24 hours per customer | Repeated customer spamming |
| **Delayed Execution** | Restart-safe DB persistence (`scheduled_at`) | Fragile in-memory `asyncio.sleep()` loops |
| **Audit Trail** | Append-only immutable PostgreSQL ledger | Fragmented application logs |

---

## Architecture

```text
Customer Checkout  (Apex Gear Co. Merchant Demo)
        │
        │  Payment fails (UPI failure@razorpay / Card OTP timeout)
        ▼
Razorpay Gateway ──── payment.failed webhook ──────────────────────────┐
        │                                                               │
        │                                          PaymentFlow Backend (FastAPI)
        │                                          ┌──────────────────────────────┐
        │                                          │ 1. Ingestion & Idempotency   │
        │                                          │    HMAC-SHA256 Signature     │
        │                                          │    event_id Deduplication    │
        │                                          │                              │
        │                                          │ 2. C1–C5 Failure Diagnosis   │
        │                                          │    Deterministic Taxonomy    │
        │                                          │                              │
        │                                          │ 3. Gemini LLM Advisory       │
        │                                          │    ← MCP Tool Boundary →     │
        │                                          │    get_payment_context       │
        │                                          │    request_recovery_action   │
        │                                          │                              │
        │                                          │ 4. PolicyGuardrailEngine     │
        │                                          │    5 Mathematical Invariants │
        │                                          │    APPROVE / ESCALATE / BLOCK│
        │                                          │                              │
        │                                          │ 5. RecoveryExecutor          │
        │                                          │    SELECT ... FOR UPDATE     │
        │                                          │    Payment Link Creation     │
        │                                          └──────────────────────────────┘
        │                                                      │
        │◀── Recovery Link surfaced in Merchant Storefront ───┘
        │
Customer pays the recovery link
        │
        ▼  payment_link.paid → payment.captured (signed webhook)
PaymentFlow attributes revenue (row-level lock, captured-only guarantee)
        │
        ▼
Operator Console: RECOVERED │ ₹X,XXX.XX │ Gateway Verified
```

→ Full technical design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## ⭐ Controlled Dashboard Benchmark (Panel Showcase)

PaymentFlow includes an interactive **Controlled Demonstration Benchmark** built directly into the Operator Console dashboard. Evaluators can trigger the authentic production triage, diagnosis, and guardrail layers live with a single click.

### Key Metrics from the Controlled 15-Scenario Batch

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 Controlled Benchmark Panel Scorecard (15 Scenarios)         │
├─────────────────────────────────────────┬───────────────────────────────────┤
│ Metric                                  │ Verified Value                    │
├─────────────────────────────────────────┼───────────────────────────────────┤
│ Total Scenarios Evaluated               │ 15 Scenarios (CS01–CS15)          │
│ Total Volume at Risk                    │ ₹1,22,117.00 (12,211,700 paise)   │
│ Policy-Eligible Opportunities           │ 7 Cases                           │
│ Eligible Opportunity Revenue            │ ₹31,538.00 (3,153,800 paise)      │
│ Evaluation Recovered Cases              │ 6 Cases (CS01, CS02, CS03, 11,14,15)│
│ Evaluation Recovered Revenue            │ ₹28,648.00 (2,864,800 paise)      │
│ In-Flight / Unrecovered Eligible Cases  │ 1 Case (CS12, ₹2,890.00)          │
│ High-Value / Compliance Escalated Cases │ 2 Cases (CS04, CS05, ₹69,750.00)  │
│ Terminal Safe Halts                     │ 6 Cases (CS06,07,08,09,10,13)     │
│ Total Protected / Safeguarded Volume    │ ₹90,579.00                        │
├─────────────────────────────────────────┼───────────────────────────────────┤
│ ★ Primary: Eligible Opportunity Rate    │ 90.84% (₹28,648 / ₹31,538)        │
│ Eligible Case Recovery Rate             │ 85.71% (6 / 7 eligible cases)     │
│ Overall Case Recovery Rate              │ 40.00% (6 / 15 total cases)       │
│ Gross Portfolio Revenue Recovery Rate   │ 23.46% (₹28,648 / ₹1,22,117)      │
└─────────────────────────────────────────┴───────────────────────────────────┘
```

### Why Eligible Opportunity vs. Gross Portfolio Matters
- **90.84% Eligible Opportunity Rate**: Demonstrates that where recovery is safe and compliant, PaymentFlow converts over 90% of lost revenue into cash.
- **23.46% Gross Portfolio Rate**: Reflects strict financial safety controls. High-value transactions (such as **CS04 for ₹65,000**) and AML risks (**CS05**) are **rightfully halted from automated links**, successfully safeguarding **₹90,579.00** from unmediated risk.

→ Complete scenario breakdown and measurement semantics: [docs/CONTROLLED_BENCHMARK.md](docs/CONTROLLED_BENCHMARK.md)

---

## AI Safety & Deterministic Guardrails

PaymentFlow enforces a hard architectural boundary between AI reasoning and financial execution:

```text
DecisionContext (sanitized payment facts)
        │
        ▼
Gemini LLM (via MCP)         ← ADVISORY ONLY
  – Diagnoses failure root cause
  – Proposes recovery policy + timing
  – Supplies confidence score + reasoning
  – Has zero access to DB or gateway credentials
        │
        ▼  AgentDecision (structured proposal)
PolicyGuardrailEngine        ← SOLE AUTHORIZATION GATE
  – Validates every proposal deterministically
  – Enforces 5 mathematical invariants
  – Can APPROVE / DOWNGRADE / ESCALATE / REJECT
  – Cannot be bypassed by the LLM
        │
        ▼  Authorized Policy
RecoveryExecutor             ← ONLY SYSTEM THAT WRITES
  – Creates Razorpay Payment Link
  – Executes pre-write secondary validation
  – Maintains single-link-per-case guarantee
```

### Deterministic Safety Invariants

| Invariant | Mathematical Rule | Purpose |
|---|---|---|
| **Amount Immutability** | $\text{Proposed Amount} \equiv \text{Original Amount}$ | Rejects adversarial discount tampering (e.g., CS07 10% discount blocked) |
| **Currency Immutability** | $\text{Proposed Currency} \equiv \text{Original Currency} \equiv \text{"INR"}$ | Rejects unauthorized foreign currency switching (e.g., CS08 USD blocked) |
| **High-Value Cap** | $\text{Amount} > ₹50,000 \implies \text{P\_ESCALATE\_ONLY}$ | Prevents automated recovery on high-ticket VIP purchases (e.g., CS04 ₹65,000) |
| **Anti-Spam Cooldown** | $\text{Attempts in 24h} \le 3$ | Prevents customer spamming and brand fatigue (e.g., CS09 4th attempt blocked) |
| **Single Active Link** | $\text{Active Links per Case} \le 1$ | Eliminates duplicate links and multi-tab overcharges |

→ Full safety architecture & MCP protocol specs: [docs/AI_SAFETY.md](docs/AI_SAFETY.md)

---

## Comprehensive Evaluation Results

All quantitative figures below have been **100% verified against raw evaluation result artifacts** (`baseline_results.json`, `mock_agent_results.json`, and database test records):

### 1. Synthetic Dataset Evaluation (75 Cases $\times$ 50 CRN Draws = 3,750 Simulations)

| Metric | Deterministic Baseline (L5B) | Agentic Recovery (L5C) | Net Uplift |
|---|---:|---:|---:|
| Dataset Size | 75 cases | 75 cases | — |
| Monte Carlo Draws | 3,750 simulations | 3,750 simulations | Identical CRN Seeds |
| **Overall Recovery Rate** | **31.73%** (1,190 / 3,750) | **61.71%** (2,314 / 3,750) | **+29.98% absolute** |
| Total Opportunity Value | ₹11,96,623.00 | ₹11,96,623.00 | — |
| **Expected Recovered Revenue**| **₹1,67,699.16** | **₹8,43,619.04** | **+₹6,75,919.88 (+403%)** |
| Opportunity Share Recovered | **14.01%** | **70.50%** | **+56.49% absolute** |
| Guardrail Interventions | 0 (Static Rules) | 4 (Safe Halts Enforced) | Defense-in-Depth |

### 2. Real Google Gemini LLM Validation (Layer 5E — 15 Cases)

| Metric | Result | Verification Standard |
|---|---|---|
| **Schema Validity Rate** | **100.0%** (15 / 15) | Validated against Pydantic `AgentDecision` |
| **Failure Category Accuracy** | **93.3%** (14 / 15) | Ground-truth benchmark alignment |
| **Guardrail Compliance Rate** | **100.0%** (0 interventions) | Perfect policy adherence |
| **Average Model Latency** | **1,802.52 ms** | Production-acceptable for async triage |
| **Total Tokens Consumed** | **18,666 tokens** | Prompt: 15,855 · Completion: 2,811 |

→ Detailed statistical analysis & category tables: [docs/EVALUATION_RESULTS.md](docs/EVALUATION_RESULTS.md)  
→ Evaluation methodology & CRN variance reduction: [docs/EVALUATION_METHODOLOGY.md](docs/EVALUATION_METHODOLOGY.md)

---

## Engineering Validation & Test Suite

PaymentFlow maintains a rigorous automated testing and static analysis regime:

| Verification Target | Result | Command |
|---|---|---|
| **Backend Test Suite** | **328 / 328 passing (100%)** | `pytest` |
| **Frontend Test Suite** | **15 / 15 passing (100%)** | `npm test -- --run` |
| **Code Coverage** | **93% across core domain** | `pytest --cov=paymentflow` |
| **Ruff Linter** | **0 errors / clean** | `ruff check src/ tests/` |
| **TypeScript Typecheck** | **0 errors / clean** | `npm run typecheck` |
| **Alembic Database Migrations** | **6 linear migrations (head: 0006)**| `alembic current` |
| **Docker Build (Backend)** | Multi-stage, non-root `appuser` | `docker build -t backend .` |
| **Docker Build (Frontend)** | Node 22 + Nginx Alpine SPA | `docker build -t frontend frontend/` |

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.12+ · Node.js 20+ · PostgreSQL 15+ (or Docker)

### 2. Configure Environment
```bash
cp .env.example .env
# Fill in DATABASE_URL, GEMINI_API_KEY, and RAZORPAY test credentials
```

### 3. Backend Setup & Migrations
```bash
# Setup virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows (.venv/bin/activate on Unix)
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start backend server
uvicorn paymentflow.main:app --reload --port 8000
# → API: http://localhost:8000 · Swagger: http://localhost:8000/docs
```

### 4. Frontend Console Setup
```bash
cd frontend
npm install
npm run dev
# → Console: http://localhost:3000
```

### 5. Merchant Demo Store Setup
```bash
cd apps/merchant-demo/server
python main.py --port 8001
# → Store: http://localhost:8001
```

→ Complete setup & Docker instructions: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

---

## Documentation Index

The repository maintains an authoritative, fully updated, all-caps documentation suite in `docs/`:

| Document | Focus Area | Contents |
|---|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture | Complete 6-layer pipeline, frontend & backend design, state machine, data models |
| [docs/CONTROLLED_BENCHMARK.md](docs/CONTROLLED_BENCHMARK.md) | **Panel Showcase** | Detailed breakdown of the 15-scenario dashboard benchmark, metrics, and demo flow |
| [docs/AI_SAFETY.md](docs/AI_SAFETY.md) | Safety & Guardrails | Gemini LLM advisory model, MCP protocol boundary, 5 mathematical invariants |
| [docs/RECOVERY_ENGINE.md](docs/RECOVERY_ENGINE.md) | Core Engine | C1–C5 failure taxonomy, eligibility rules, restart-safe delayed recovery, attribution |
| [docs/EVALUATION_RESULTS.md](docs/EVALUATION_RESULTS.md) | Results | Verified results for Baseline (31.73%), Mock Agent (61.71%), Real LLM & Benchmark |
| [docs/EVALUATION_METHODOLOGY.md](docs/EVALUATION_METHODOLOGY.md) | Methodology | 75-case dataset design, CustomerResponseSimulator, SHA-256 CRN seeds, zero-leakage |
| [docs/MERCHANT_INTEGRATION.md](docs/MERCHANT_INTEGRATION.md) | Merchant Integration | Standalone demo store, webhook HMAC verification, API key binding, checkout simulator |
| [docs/EXTERNAL_TESTING.md](docs/EXTERNAL_TESTING.md) | Evaluator Guide | Step-by-step testing instructions, live endpoints, and guardrail observation guide |
| [docs/API.md](docs/API.md) | API Reference | Complete REST API endpoint reference, schemas, query parameters, and responses |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local Development | Local installation, database setup, migrations, tests, and environment variables |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deployment | Railway and Vercel production topology, containerization, and health probes |
| [docs/SECURITY.md](docs/SECURITY.md) | Security & Privacy | Threat modeling, PCI-DSS scope exemption, PII masking, append-only audit trail |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Constraints | Honest demarcation of demonstrated vs production realities, trade-offs, and roadmap |

---

## Project Structure

```text
Razorpay/
├── src/paymentflow/           # Backend Python package (FastAPI)
│   ├── adapters/              # Razorpay API client adapter
│   ├── api/                   # REST routes: /cases, /webhooks, /health, /merchant
│   ├── config.py              # Pydantic Settings & dialect normalization
│   ├── db/                    # SQLAlchemy 2.0 models & async sessionmaker
│   ├── domain/                # C1–C5 taxonomy, PolicyGuardrailEngine, eligibility, state machine
│   ├── eval/                  # Benchmark runner, canonical scenarios, synthetic simulator
│   ├── mcp/                   # Model Context Protocol server, client & tool registry
│   ├── merchant/              # Merchant key binding & schemas
│   └── services/              # RecoveryOrchestrator, RecoveryExecutor, WebhookService
├── apps/merchant-demo/        # Autonomous Merchant Demo Application (FastAPI + JS)
├── frontend/                  # Operator Intelligence Console (React 18 + TypeScript + Vite)
├── migrations/                # Alembic database migrations (6 versions)
├── tests/                     # Automated test suite (328 backend tests)
├── docs/                      # Authoritative project documentation (13 ALL-CAPS files)
├── docker-compose.yml         # Multi-service local container stack
├── Dockerfile                 # Multi-stage production backend container
└── pyproject.toml             # Python configuration, dependencies, ruff & pytest settings
```

---

*Built for Razorpay Buildathon · Track 03 — AI Revenue Recovery*
