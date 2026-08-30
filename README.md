# PaymentFlow Recovery Agent

Autonomous Revenue Recovery for Razorpay Failed Payments (Track 03 — AI Revenue Recovery).

## Overview
PaymentFlow Recovery Agent is a policy-first agentic revenue-recovery system for failed one-time Razorpay payments. It combines constrained LLM reasoning and Model Context Protocol (MCP) with deterministic financial guardrails and verifiable attribution.

## Quickstart (Development)

### 1. Environment Setup
```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Run Database & Migrations
```bash
docker compose up -d db
alembic upgrade head
```

### 3. Start Application
```bash
uvicorn paymentflow.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Run Tests
```bash
pytest -v --cov=paymentflow
```
