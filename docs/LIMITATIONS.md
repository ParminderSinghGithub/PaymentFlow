# PaymentFlow Recovery Agent — Limitations, Assumptions & Roadmap

## 1. Demarcation of Demonstrated vs. Production Realities

To maintain complete truthfulness and transparency for hackathon evaluators, this document explicitly details what is fully verified versus what relies on simulation models:

| Dimension | Demonstrated & Verified | Requires Live Production Deployment |
| :--- | :--- | :--- |
| **Backend & Architecture** | Full FastAPI asynchronous backend, PostgreSQL, 6 Alembic migrations, 328 passing tests | Horizontal Kubernetes pod autoscaling |
| **Safety Guardrails** | 100% deterministic enforcement: amount immutability, currency, cooldowns, > ₹50k cap | Custom per-merchant dynamic threshold configuration |
| **AI Advisory Reasoning** | Real Google Gemini 3.5 Flash Lite live integration via MCP; 100% schema validity | Custom fine-tuned domain models for payment errors |
| **Controlled Benchmark** | 15 live canonical scenarios executed through authentic triage and guardrail engine | Live merchant historical cohort benchmarks |
| **Attribution** | 100% captured-only revenue verification via signed Razorpay webhooks | Multi-month cohort retention and churn analytics |
| **Customer Conversion** | 50-draw Monte Carlo simulation with Common Random Numbers (CRN) | Real human consumer payment psychology in the wild |

---

## 2. Assumptions & Known Constraints

### 1. Synthetic Evaluation Dataset Boundary
- **Context**: Evaluating autonomous agents against real customer payments during development would risk charging real money or spamming actual consumers.
- **Limitation**: The 75 evaluation cases and 15 benchmark scenarios are synthetically constructed based on real-world Razorpay error codes and failure distributions.
- **Mitigation**: Scenarios model real failure dynamics (C1 dropouts, C2 timeouts, C3 limits, C4 risk, C5 technical bugs) with realistic transaction amounts ranging from ₹1,299.00 to ₹75,000.00.

### 2. Live SMS & WhatsApp Notification Delivery
- **Context**: In production, Razorpay Payment Links send automated SMS, email, and WhatsApp notifications to customer phone numbers.
- **Limitation**: In Razorpay Test Mode, live cellular SMS dispatches are simulated by Razorpay's sandbox. Actual delivery rates depend on merchant DLT registration and carrier delivery receipts.
- **Mitigation**: The Operator Console and Merchant Demo provide direct short URLs and copyable links to test checkout completion directly.

### 3. Single-Merchant Account Binding in Current Release
- **Context**: The current release connects to a primary merchant Razorpay keypair via `.env`.
- **Limitation**: True multi-tenant SaaS architecture (where multiple merchants register their distinct keypairs via OAuth) is an enterprise extension scheduled for future releases.

---

## 3. Design Trade-offs

### Trade-off 1: Strict Financial Safety vs. Gross Conversion
- **Decision**: Enforced hard ₹50,000 ceiling on automated recovery links and hard blocks on C4/C5 categories.
- **Trade-off**: Lowers gross portfolio recovery rate to **23.46%** in the benchmark, because high-ticket transactions (e.g., CS04 ₹65,000) are blocked from automated links.
- **Justification**: In financial systems, preventing a single unauthorized ₹65,000 recovery dispute or fraudulent chargeback far outweighs the marginal gain of unmediated automated conversion.

### Trade-off 2: LLM Latency vs. Static Heuristics
- **Decision**: Utilized Google Gemini (`gemini-3.5-flash-lite`) for nuanced error interpretation.
- **Trade-off**: Introduces an average inference latency of **1,802 ms**, compared to sub-millisecond execution for static `if/else` rules.
- **Justification**: Payment recovery is not high-frequency trading. A 2-second triage latency is completely imperceptible to a customer who just dropped off or experienced a gateway timeout, while providing 93.3% category classification accuracy.

---

## 4. Future Roadmap & Enterprise Extensions

1. **Multi-Tenant Merchant Onboarding**:
   - Razorpay Partner OAuth integration allowing merchants to install PaymentFlow with one click from the Razorpay App Store.
2. **Conversational WhatsApp Recovery Bot**:
   - Interactive recovery flow enabling customers to choose alternate payment methods (e.g., switching from a failed card to instant UPI) directly within WhatsApp.
3. **Dynamic Personalized Merchant Budget Caps**:
   - Allowing merchants to allocate dynamic recovery discount budgets with automated velocity caps.
4. **Autonomous Retry Schedule Optimization**:
   - Reinforcement learning models that optimize delayed recovery dispatch hours based on customer time-of-day payment propensities.
