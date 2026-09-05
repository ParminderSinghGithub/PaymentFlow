# PaymentFlow Recovery Agent — Deployment & Operations

## 1. Production Architecture Overview

PaymentFlow is architected as an independently deployable microservices topology running across high-availability cloud platforms:

```text
┌─────────────────────────────────────────────────────────────┐
│                      Vercel Edge CDN                        │
│         PaymentFlow Operator Console (React 18 SPA)         │
│          https://paymentflow-recovery-agent.vercel.app      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / REST (CORS enabled)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Railway Cloud Platform                   │
│                                                             │
│  ┌────────────────────────┐      ┌───────────────────────┐  │
│  │  PaymentFlow Backend   │◄────►│ Managed PostgreSQL 15 │  │
│  │    (FastAPI / Python)  │      │     (asyncpg pool)    │  │
│  └───────────▲────────────┘      └───────────────────────┘  │
│              │                                              │
│              │ Internal / External Webhooks (HMAC-SHA256)   │
│              ▼                                              │
│  ┌────────────────────────┐                                 │
│  │  Merchant Demo Store   │                                 │
│  │   (FastAPI / Python)   │                                 │
│  └────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Live Service Endpoints

| Service Name | Cloud Provider | Domain / URL | Deployment Type |
| :--- | :--- | :--- | :--- |
| **Operator Console** | Vercel | `https://paymentflow-recovery-agent.vercel.app` | Static SPA + Edge CDN |
| **Backend API** | Railway | `https://paymentflow-backend-production.up.railway.app` | Docker Container |
| **Merchant Store** | Railway | `https://merchant-demo-production.up.railway.app` | Docker Container |
| **Database** | Railway | Managed Internal Connection | PostgreSQL 15 |

---

## 3. Containerization Strategy

### Backend Service (`Dockerfile`)
The backend uses a security-hardened, multi-stage Python 3.12 Debian slim image:

- **Non-Root Execution**: Runs under an unprivileged `appuser` (UID 10001).
- **Layer Caching**: Dependencies are installed in a separate builder stage to optimize rebuild times.
- **Production Server**: Runs via `uvicorn` with configurable worker threads.

### Frontend Console (`frontend/Dockerfile`)
The frontend uses a two-stage container build:

1. **Build Stage**: Node 22 Alpine builds and minifies the Vite TypeScript bundle (`npm run build`).
2. **Serving Stage**: Nginx Alpine serves static assets with gzip compression, security headers, and SPA fallback routing (`try_files $uri $uri/ /index.html`).

---

## 4. Production Database Migrations

Database schema migrations are executed automatically during deployment via Railway release commands:

```bash
# Railway Release Command
alembic upgrade head && uvicorn paymentflow.main:app --host 0.0.0.0 --port $PORT
```

- **Linear Migration Path**: Guarantees zero migration drift across environments.
- **Transactional DDL**: PostgreSQL ensures schema modifications are applied atomically.
- **Rollback Safety**: Migrations include bidirectional `upgrade()` and `downgrade()` methods.

---

## 5. Production Environment Configuration

### Backend Environment Variables

```ini
ENVIRONMENT=production
LOG_LEVEL=INFO
PORT=8000

# Managed Database URL (Supplied by Railway)
DATABASE_URL=postgresql+asyncpg://postgres:secret@postgres.railway.internal:5432/railway
SYNC_DATABASE_URL=postgresql://postgres:secret@postgres.railway.internal:5432/railway

# Razorpay Production / Test Credentials
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...

# AI Provider Credentials
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=...

# Security & CORS
ALLOWED_ORIGINS=https://paymentflow-recovery-agent.vercel.app,http://localhost:3000
```

### Frontend Environment Variables (Vercel)

```ini
VITE_API_BASE_URL=https://paymentflow-backend-production.up.railway.app
```

> [!IMPORTANT]
> **Zero Secrets in Frontend**: `VITE_API_BASE_URL` is the only environment variable provided to Vercel. Database credentials, Razorpay secret keys, and Gemini API keys are strictly forbidden from frontend bundles.

---

## 6. Health Probes & Monitoring

The backend exposes an unauthenticated health probe at `/health`:

- **Railway Healthcheck Path**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Restart Threshold**: 3 consecutive failures

When probed, the endpoint dynamically verifies:
1. Database read/write connectivity (`SELECT 1`).
2. Gemini API client initialization status.
3. Current Alembic schema head match (`0006_case_source_eval_runs`).
