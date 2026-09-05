# PaymentFlow Recovery Agent — Local Development Guide

## 1. Prerequisites

Ensure your local development environment has the following installed:

- **Python**: Version `3.12.x` (required for modern typing and asyncio features)
- **Node.js**: Version `20.x` or `22.x` with `npm >= 10.x`
- **PostgreSQL**: Version `15+` running locally or via Docker
- **Docker & Docker Compose**: (Optional, for containerized services)

---

## 2. Environment Configuration

Copy the example environment template to create your active `.env`:

```bash
cp .env.example .env
```

### Essential Configuration Variables

```ini
# Application Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db
SYNC_DATABASE_URL=postgresql://paymentflow_user:paymentflow_password@localhost:5432/paymentflow_db

# Razorpay API Credentials (Test Mode)
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# AI & LLM Provider (Google Gemini)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key

# Service URLs
BACKEND_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
MERCHANT_DEMO_URL=http://localhost:8001
```

---

## 3. Database Initialization & Alembic Migrations

Start a local PostgreSQL container using Docker Compose:

```bash
docker-compose up -d postgres
```

Apply all 6 linear Alembic schema migrations:

```bash
# Windows PowerShell
.venv\Scripts\alembic upgrade head

# Linux / macOS
alembic upgrade head
```

Verify migration status:
```bash
alembic current
# Output: 20260903_0006_case_source_eval_runs (head)
```

### Optional: Seed Canonical Demonstration Batch
To pre-populate the database with the 15 canonical benchmark demonstration cases:

```bash
python scripts/seed_canonical_batch.py
```

---

## 4. Running Backend Services

### Python Virtual Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate environment
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### Launch FastAPI Backend
```bash
uvicorn paymentflow.main:app --reload --port 8000
```

Verify backend health at `http://localhost:8000/health` or open Swagger docs at `http://localhost:8000/docs`.

---

## 5. Running the Frontend Console

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser. The Vite dev server proxies API calls (`/health`, `/cases`) directly to `http://localhost:8000`.

---

## 6. Running the Merchant Demo Store

In a separate terminal:

```bash
cd apps/merchant-demo/server
python main.py --port 8001
```

Access the merchant storefront at `http://localhost:8001`.

---

## 7. Running Tests & Quality Checks

### Backend Test Suite (Pytest)
PaymentFlow includes **328 comprehensive backend unit, integration, and security tests**:

```bash
# Run full test suite
pytest

# Run tests with coverage report
pytest --cov=paymentflow --cov-report=term-missing

# Run specific domain or guardrail tests
pytest tests/test_canonical_benchmark.py -v
pytest tests/test_idempotency_concurrency.py -v
pytest tests/test_policy_engine.py -v
```

### Frontend Test Suite (Vitest)
PaymentFlow includes **15 frontend API client and UI tests**:

```bash
cd frontend
npm test -- --run
```

### Code Formatting & Static Analysis
```bash
# Backend linting with Ruff
ruff check src/ tests/

# Frontend type checking
cd frontend
npm run typecheck
```

---

## 8. Development Architecture Rules

1. **Maintain Invariant Separation**: The LLM proposal layer must never directly touch database models or Razorpay write APIs.
2. **Deterministic Pre-Write Validation**: Always route financial actions through `PolicyGuardrailEngine` and `RecoveryExecutor`.
3. **Pydantic extra="forbid"**: Any new schema representing agent decision context must enforce `extra="forbid"` to prevent accidental ground-truth leakage.
4. **Captured-Only Attribution**: Never credit revenue upon payment link creation or link dispatch.
