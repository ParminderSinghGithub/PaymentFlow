# PaymentFlow Recovery Intelligence Console (Frontend)

Autonomous Revenue Recovery Operations Console for Razorpay Failed Payments.

---

## 1. Overview

The **PaymentFlow Recovery Intelligence Console** is a flagship frontend operations interface for financial recovery teams. It communicates exclusively via HTTPS/REST with the headless PaymentFlow FastAPI backend (`http://localhost:8000`).

Key capabilities:
- **Executive Overview**: Real-time revenue recovery metrics (INR), conversion rates, and lifecycle funnel progression.
- **C1–C5 Failure Intelligence**: Category distribution connected to automated recovery policies.
- **Case Decision Story Mode**: 8-stage step-by-step walkthrough explaining *why* transactions were recovered or halted.
- **AI vs. Guardrail Gate**: Visual side-by-side contrast proving that advisory LLM proposals are bounded by deterministic invariants.
- **Immutable Audit Trail**: Chronological event logs for complete auditability.
- **System Health Diagnostics**: Live `/health` diagnostic probe.

---

## 2. Quickstart & Development

### Prerequisites
- Node.js `>= 20.x`
- npm `>= 10.x`
- PaymentFlow Backend running on `http://localhost:8000`

### Local Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 3. Scripts

- `npm run dev`: Launch Vite development server with local proxy to `http://localhost:8000`.
- `npm run build`: Typecheck and compile production bundle into `dist/`.
- `npm run typecheck`: Run TypeScript static analysis without emitting files.
- `npm run test`: Run unit and API client test suite via Vitest.

---

## 4. Docker Deployment

```bash
docker build -t paymentflow-frontend:latest .
docker run -d -p 3000:80 --name paymentflow-console paymentflow-frontend:latest
```

The multi-stage Docker build compiles the TypeScript/React application using Node 22 and serves the production bundle using high-performance Nginx Alpine with gzip compression and SPA fallback routing.

---

## 5. Security & Isolation

- **Zero Secrets Shipped**: No database connection strings, Razorpay API secrets, or LLM keys exist in the frontend code or build bundle.
- **Headless Decoupling**: The console connects only to frozen public REST endpoints over HTTP/HTTPS.
