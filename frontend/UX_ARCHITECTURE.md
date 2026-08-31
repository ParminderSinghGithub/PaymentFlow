# PaymentFlow — UX Architecture v2.0

> **Specification only. Implementation has not started.**
> This document defines page layouts, information hierarchies, component composition,
> and interaction patterns for the full frontend rebuild.

---

## 1. Application Shell

### Navigation Model

Single-page application with hash-based routing (existing pattern, preserved).
Navigation state lives in `App.tsx`, passed down as props.

Routes:
```
#overview         Overview / Executive Summary
#cases            Cases Explorer
#investigation?id=CASE_ID   Case Investigation (Decision Story)
#architecture     MCP + Guardrail Architecture (static explainer)
#system           System Health
```

### Shell Layout

```
+--[SIDEBAR 220px]--+--[MAIN CONTENT AREA]--+
|                   |                       |
|  PaymentFlow      |  [PAGE HEADER]        |
|  Recovery Intel   |                       |
|                   |  [PAGE CONTENT]       |
|  > Overview       |                       |
|    Cases          |                       |
|    Investigation  |                       |
|    Architecture   |                       |
|    System         |                       |
|                   |                       |
|  [health dot]     |                       |
+-------------------+-----------------------+
```

Sidebar:
- Background: surface-void (same as page — no separate panel)
- Right border: 1px surface-border
- Collapsed breakpoint: < 1024px (show icon-only, 56px)
- Bottom of sidebar: small health indicator dot (green/amber/red) + last-refreshed timestamp

Page header (each page):
- Page title (heading-1)
- Page subtitle / description (body-sm, text-secondary)
- Right side: global refresh button + backend status indicator

Main content area:
- Left padding: 24px (sidebar gutter)
- Top padding: 24px
- Max-width: 1200px content column inside full-width area

---

## 2. Page: Overview

**Purpose**: Operational summary. What is the system doing right now?
A reviewer who knows nothing about the project should understand the value within 10 seconds.

### Information Hierarchy

```
[1] METRIC ROW — 4 KPI cards
[2] RECOVERY PIPELINE FUNNEL — horizontal stage-count visualization
[3] FAILURE TAXONOMY — C1-C5 intelligence breakdown
[4] LIVE CASES FEED — last 8 cases, clickable rows
```

### [1] Metric Row

4 cards in a row. Each has a 3px left zone-accent.

| Card | Zone | Left Accent | Data |
|------|------|-------------|------|
| Total Revenue Recovered | Emerald | success-base | total_recovered_amount_inr |
| Recovery Conversion Rate | Teal | guard-base | recovery_rate_pct + case counts |
| Active Recovery Links | Neutral | none | active_recovery_links |
| Guardrail Protected | Rose | halt-base | escalated + terminal_no_action |

Each card:
- Top: label (UPPERCASE 11px) left, icon right
- Middle: primary value (mono-lg, text-primary)
- Below value: one-line context (12px, zone-colored)
- Divider
- Bottom: secondary count (caption, text-tertiary)

### [2] Recovery Pipeline Funnel

Title: "Recovery Pipeline" + subtitle: "Deterministic state machine with AI advisory at stage 4"

6-stage horizontal layout:

```
[INGESTED]-->[CLASSIFY]-->[ELIGIBLE]--([AI TRIAGE])-->[GUARDRAIL]-->[EXECUTED]-->[RECOVERED]
   N cases     N cases     N cases     N cases          N cases       N cases     N cases
   amber dot   neutral     teal        VIOLET BOX        teal         teal        emerald
```

Stage 04 (AI TRIAGE) gets a distinct visual box treatment:
- Violet border, violet background muted
- "AI" label above the stage number

This is NOT a bar chart. It is a horizontal process diagram with case counts at each stage.
Implemented as a flex row of stage cards connected by arrow connectors.

### [3] Failure Taxonomy

Title: "Failure Intelligence" + subtitle: "C1-C5 normalized taxonomy — AI classifies, guardrails verify"

5 cards in a row (C1 through C5). Each card:
- Category badge (top)
- Category name (heading-3)
- One-sentence description (body-sm)
- Divider
- Default policy (policy badge, guard zone — deterministic)
- Recovery likelihood (text indicator)
- Case count from category_breakdown API field

### [4] Live Cases Feed

Title: "Pipeline Stream" + link to full Cases page.

Compact table, 8 rows max:
| Case ID | Amount | Category | State | Policy | Payment Link | Actions |
|---------|--------|----------|-------|--------|-------------|---------|

- Case ID: mono-sm, ai-text color, clickable
- Amount: mono-md, right-aligned
- Category: CategoryBadge
- State: StateBadge with dot
- Policy: PolicyBadge in guard zone (if validated)
- Payment Link: emerald text if present, dash if not
- Actions: "Triage" button (only if FAILED_INGESTED), "Inspect" text link

---

## 3. Page: Cases Explorer

**Purpose**: Full operational case list. Filterable. Every case visible.

### Layout

```
[TOOLBAR: filter bar + batch action button]
[TABLE: all cases, paginated]
```

### Toolbar

Left side:
- State filter: pill group (All / Ingested / Recovered / Escalated / No Action)
- Active state shows filled pill in that zone's color

Right side:
- "Process Delayed Cases" button (guard zone color — teal)
- "Refresh" button (secondary)
- Case count label

### Table

Columns:
| Column | Type | Notes |
|--------|------|-------|
| Case ID | mono-sm, ai-text | Clickable, opens investigation |
| Payment ID | mono-sm, text-tertiary | Truncated at 16 chars + ellipsis |
| Amount (INR) | mono-md, right-aligned | Full precision |
| Category | CategoryBadge | |
| State | StateBadge | |
| Authorized Policy | PolicyBadge (guard zone) | |
| Payment Link | mono-sm, emerald if present | Truncated |
| Created | caption | Relative time (e.g. "3 min ago") |
| Actions | | |

Action column:
- "Triage" button: only visible when state = FAILED_INGESTED. Violet zone, icon + label.
- Arrow icon: always visible, navigates to investigation

Row interaction:
- Full row click navigates to Case Investigation
- Triage button click does NOT navigate (stops event propagation)

Empty state:
- Icon: ListChecks
- Heading: "No cases match this filter"
- Description differs per active filter

---

## 4. Page: Case Investigation (The Crown Jewel)

**Purpose**: Tell the complete decision story for a single case.
A reviewer should understand every decision the system made, why it made it,
and how the AI boundary and guardrail boundary interact.

This is the most important page in the application.

### Layout

```
[CASE HEADER STRIP]
[4 METRIC CARDS]
[PIPELINE PROGRESS BAR — 8 stages]
[TAB BAR: Decision Story | Audit Trail | Raw Data]
[TAB CONTENT AREA]
```

### Case Header Strip

Full-width card spanning the content area.

Left side:
- Back button (← icon) returns to Cases
- Case ID (mono-lg, text-primary) + StateBadge + CategoryBadge
- Below: Payment ID, Customer ID (if present), Order ID — mono-sm, text-tertiary

Right side:
- "Execute Recovery Triage" button — violet zone, only if state = FAILED_INGESTED
- "Refresh" secondary button

### 4 Metric Cards (inline with header)

| Card | Value |
|------|-------|
| Transaction | amount_inr in mono-lg + currency |
| AI Proposed | ai_policy_id with AI prefix policy badge |
| Authorized | validated_policy_id with guard prefix policy badge |
| Recovered | recovered_amount_inr (emerald) or Rs 0.00 (tertiary) |

The juxtaposition of "AI Proposed" vs "Authorized" in two adjacent cards visually
demonstrates the advisory-to-guardrail handoff.

### Pipeline Progress Bar

Horizontal 8-stage sequence showing completion state for this specific case.

```
[01 INGESTED]--[02 CLASSIFY]--[03 ELIGIBLE]--[04 AI TRIAGE]--[05 GUARDRAIL]--[06 EXECUTED]--[07 VERIFY]--[08 ATTRIBUTED]
```

Stage states:
- Complete: filled circle, checkmark icon
- Current: pulsing outline circle
- Pending: empty outline circle, text-tertiary

Zone coloring:
- Stages 01-03: teal when complete
- Stage 04: violet when complete
- Stages 05-08: teal when complete

### Tab: Decision Story (default tab)

Two-column layout (2/3 + 1/3):

Left column — Vertical Timeline (8 stages):

Each stage card:
```
+--[3px LEFT ACCENT]-------------------------------+
|  01 · RAZORPAY GATEWAY          [actor label]   |
|                                                  |
|  Payment Failed                                  |
|  Rs 2,500 — AUTHENTICATION_FAILED               |
|  error_code: BAD_REQUEST_ERROR                   |
+--------------------------------------------------+
```

Left accent color:
- Stage 04: ai-base (violet)
- Stage 05: guard-base (teal, brighter)
- Others: surface-border-med

Vertical connector line runs between cards. Color changes:
- teal → violet: between stage 03 and 04
- violet → teal: between stage 04 and 05

This color transition is the product centerpiece.

Stages:
1. Payment Failed (Razorpay Gateway) — failure_code, failure_description
2. Taxonomy Classification (Classifier) — failure_category, classification_evidence
3. Deterministic Eligibility (Eligibility Engine) — eligibility_status, eligibility_reason
4. **AI Advisory Proposal** (LLM Provider) — ai_policy_id, ai_explanation — VIOLET ACCENT
5. **Guardrail Authorization** (PolicyGuardrailEngine) — validated_policy_id — TEAL ACCENT
6. Recovery Execution (RecoveryExecutor) — payment_link_id, payment_link_short_url
7. Payment Verification (Verifier) — recovered_payment_id
8. Revenue Attribution (Attribution Service) — recovered_amount_inr

Right column — AI vs Guardrail comparison card:

```
+--[AI BOUNDARY]-------------------------------+
|  [BrainCircuit icon]  AI Advisory Proposal   |
|                                              |
|  Proposed policy: [AI badge] P_CREATE_LINK   |
|                                              |
|  "The failure appears to be an             |
|   authentication issue. Immediate link      |
|   creation may be appropriate."             |
+----------------------------------------------+

+--[GUARDRAIL]--------------------------------+
|  [ShieldCheck icon]  Guardrail Enforcement  |
|  [VERIFIED badge]                           |
|                                             |
|  Amount: Rs 2,500 (Immutable)              |
|  Currency: INR (Immutable)                  |
|  Cooldown: Satisfied                        |
|  Link limit: Max 1 per case                 |
|  ──────────────────────────────────────     |
|  Authorized: [guard badge] P_CREATE_LINK    |
+---------------------------------------------+
```

If AI proposed == guardrail authorized: show "Proposal Accepted" chip.
If AI proposed != guardrail authorized: show "Proposal Overridden" chip in amber.
This delta chip is a key explainability feature.

Below that, if payment_link_id exists:

```
+--[Payment Link Execution]-----------------+
|  Link ID: plink_ABC123                    |
|  URL: https://rzp.io/...  [open] [copy]  |
|  Status: created / paid / expired         |
+-------------------------------------------+
```

### Tab: Audit Trail

Full-width list of audit events, chronological ascending.

Each event:
```
+------------------------------------------------+
|  WEBHOOK_RECEIVED                              |
|  actor: webhook_service   12:34:56 2024-01-15 |
|                                                |
|  decision: ELIGIBLE  ·  policy: P_CREATE_LINK  |
|                                                |
|  [+ Details]  <- toggle to show JSON block    |
+------------------------------------------------+
```

Event type badge: uppercase mono-sm. Color based on event category:
- WEBHOOK_*: neutral
- ELIGIBILITY_*: guard zone
- AI_*: ai zone
- GUARDRAIL_*: guard zone
- RECOVERY_*: success zone
- ERROR_*: danger zone

### Tab: Raw Data

Two sections:
1. Case record: syntax-highlighted JSON of the full case payload
2. Endpoint reference: `GET /cases/{case_id}` label with copy button

JSON block: surface-overlay background, mono-sm font, max-height 480px, scrollable.

---

## 5. Page: Architecture

**Purpose**: Static explainer of the MCP boundary and safety invariants.
Educational — no live data. A reviewer should immediately understand the safety architecture.

### Layout

```
[INTRO: The Safety Boundary]
[SYSTEM FLOW DIAGRAM]
[MCP TOOLS TABLE]
[SAFETY INVARIANTS TABLE]
```

### Intro Section

Two-column:
- Left: heading "AI recommends. Deterministic policy authorizes." + 2-sentence description
- Right: the key constraint box:

```
+--[ai-muted border]-----------+
|  LLM CAN:                    |
|  · Classify failure (C1-C5)  |
|  · Propose policy ID         |
|  · Provide explanation       |
+------------------------------+

+--[guard-muted border]--------+
|  LLM CANNOT:                 |
|  · Set amounts               |
|  · Create payment links      |
|  · Override guardrails       |
|  · Access PAN/bank data      |
+------------------------------+
```

### System Flow Diagram

A horizontal flow with visual zone separation:

```
[payment.failed]
      |
      v
[Webhook + Idempotency]  <- deterministic, teal
      |
      v
[Recovery Case + Context]  <- deterministic, teal
      |
      v
[Eligibility Engine]  <- deterministic, teal
      |
+-----v-----+
|  MCP      |    <- dotted violet border
|  Client   |
|    |      |
|  LLM      |    <- violet zone
|  Agent    |
|    |      |
|  MCP      |
|  Server   |
+-----v-----+
      |
[PolicyGuardrailEngine]  <- deterministic, teal — WALL between zones
      |
      v
[RecoveryExecutor]  <- deterministic, teal
      |
      v
[Razorpay Payment Link]  <- external, neutral
```

The MCP/LLM block has a distinct visual box (violet zone: dashed border ai-border, muted background).
The guardrail below it is described as "The Wall" — teal zone, solid border.

### MCP Tools Table

| Tool | Access | Input | Capability |
|------|--------|-------|------------|
| get_payment_context | READ ONLY | case_id | Returns sanitized context |
| get_recovery_case | READ ONLY | case_id | Returns case state |
| get_recovery_status | READ ONLY | case_id | Real-time payment link status |
| request_recovery_action | PROPOSAL (GUARDED) | case_id, policy_id, amount, currency | Submits to PolicyGuardrailEngine |

Access type badge:
- READ ONLY: teal zone
- PROPOSAL (GUARDED): amber zone

### Safety Invariants Table

| Invariant | Rule | What It Prevents | Enforcement |
|-----------|------|-----------------|-------------|
| Amount Immutability | proposed_amount == original_amount | LLM discounts | Hard rejection |
| Currency Immutability | currency == INR | Currency manipulation | Hard rejection |
| Customer Cooldown | attempts <= 2 per 24h | Spam | Eligibility EXHAUSTED |
| High-Value Escalation | amount > Rs 50,000 | Automated large writes | Override to ESCALATE |
| Single Active Link | link_id == null | Double charging | DB lock + guardrail |
| Captured-Only Attribution | verified_status == captured | Phantom revenue | API barrier |

Invariant rows: teal-zone styling. The table reads like a formal contract.

---

## 6. Page: System Health

**Purpose**: Backend connectivity, environment, version, and layer status.

### Layout

```
[HEALTH STATUS CARD — prominent]
[LAYER STATUS GRID]
[ENDPOINT REFERENCE TABLE]
```

### Health Status Card

Full-width card. Center-aligned.

If healthy:
- Large green dot + "System Operational" heading
- Environment: test, version, database: connected
- Last checked timestamp

If degraded/offline:
- Large amber/red dot + "System Degraded" heading
- Which component failed
- Retry button

### Layer Status Grid

Static information about what was implemented in each layer:

| Layer | Status | Description |
|-------|--------|-------------|
| 5A-5C Evaluation | Complete | Synthetic evaluation, baseline, agent evaluator |
| 5D LLM Provider | Complete | Gemini with structured output |
| 5E MCP Boundary | Complete | MCP client/server tools |
| 5F Runtime Hardening | Complete | Guardrail engine, executor |
| 5G API Contract | Complete | Frozen REST endpoints |
| Layer 6 Frontend | Active | This interface |

### Endpoint Reference Table

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | System health check |
| GET | /cases | List recovery cases |
| GET | /cases/{id} | Case detail + audit trail |
| GET | /cases/metrics/summary | Aggregate metrics |
| POST | /cases/{id}/triage | Execute recovery orchestration |
| POST | /cases/delayed/process | Process due delayed cases |

---

## 7. Interaction Patterns

### Navigation

- All navigation is client-side hash routing
- Clicking a Case ID from any page navigates to #investigation?id=CASE_ID
- Browser back button works correctly via hashchange listener
- Sidebar active state updates on navigation

### Triage Action Flow

1. User clicks "Execute Recovery Triage" button on a FAILED_INGESTED case
2. Button shows spinner, is disabled
3. API call to POST /cases/{id}/triage
4. On success: toast notification "AI Triage Complete" with policy + state
5. On non-recoverable: toast notification "Outcome Non-Recoverable" in warning style
6. Metrics, cases list, and case detail all refresh automatically after action

### Delayed Cases Processing

1. User clicks "Process Delayed Cases" on Cases page
2. Button shows spinner
3. API call to POST /cases/delayed/process
4. Toast shows count of processed cases
5. Metrics and cases list refresh

### Global Refresh

- Header refresh button triggers parallel fetch of health + metrics + cases
- If on investigation page, also refreshes case detail
- Toast confirms "Data Synchronized"
- Refresh button shows spinner while in flight

### Toast System

Position: bottom-right
Types: success (emerald), warning (amber), error (rose), info (violet)
Duration: 4 seconds auto-dismiss
Stack: max 3 toasts visible simultaneously

---

## 8. Responsive Behavior

| Breakpoint | Sidebar | Content | Tables |
|------------|---------|---------|--------|
| < 768px | Hidden (hamburger) | Full width | Horizontal scroll |
| 768-1023px | Icon-only (56px) | 56px offset | Horizontal scroll |
| >= 1024px | Full (220px) | 220px offset | Normal |

Mobile is secondary — the system is an operations console, not a mobile app.
Minimum viable mobile: sidebar hidden, content readable, tables scrollable.

---

## 9. Data Fetching Strategy

All data lives in App.tsx as the single source of truth.
Props flow downward to pages and components.
No local state for API data in child components.

Fetch functions (existing pattern preserved):
- `fetchHealth()` → health state
- `fetchMetricsSummary()` → metrics state
- `fetchCases()` → cases list state
- `fetchCaseDetail(id)` → case detail state

Refresh triggers:
- Initial mount: all four in parallel
- Global refresh button: all four in parallel
- After triage action: metrics + cases + case detail
- After delayed processing: metrics + cases

Error handling:
- API errors → toast notification with error type and message
- Health fetch failure → health set to degraded/offline state object
- Case detail fetch failure → error banner in case investigation area

---

## 10. File Structure After Rebuild

```
frontend/src/
  App.tsx                    routing + data orchestration (preserved, refactored)
  main.tsx                   entry point (preserved)
  index.css                  global tokens + resets
  vite-env.d.ts
  api/
    client.ts                API client functions (preserved)
  types/
    index.ts                 TypeScript types (preserved, extended)
  components/
    layout/
      AppShell.tsx           shell with sidebar + content area
      Sidebar.tsx            nav sidebar component
      Header.tsx             page header component
    common/
      StateBadge.tsx         state badge (replaces StatusBadge)
      CategoryBadge.tsx      C1-C5 badge (preserved, restyled)
      PolicyBadge.tsx        AI vs guardrail context-aware badge
      KpiCard.tsx            metric card with zone accent
      PipelineStep.tsx       stage indicator for pipeline views
      Skeleton.tsx           loading skeleton (preserved)
      Toast.tsx              toast notification system (preserved)
      EmptyState.tsx         empty state component (preserved)
      ErrorBanner.tsx        error display (preserved)
      DataTable.tsx          shared table component (new)
  pages/
    OverviewPage.tsx
    CasesPage.tsx
    CaseInvestigationPage.tsx    (replaces CaseDetailPage)
    ArchitecturePage.tsx         (replaces McpArchitecturePage)
    SystemHealthPage.tsx
```

---

## 11. Open Questions (For Review)

1. **Chart library**: The Overview funnel is described as a horizontal process diagram
   with case counts per stage. No bar charts are planned. Confirm no charting library needed.

2. **Mobile sidebar**: Collapse to icon-only (current approach) or add hamburger overlay?
   Current plan: icon-only at 768-1023px, hamburger hidden at <768px.

3. **AI explanation in timeline**: The LLM explanation can be long (several sentences).
   Implement as collapsible or always-visible with text-clamp?
   Current plan: always visible for RECOVERED/complete cases, collapsed for pending stages.

4. **Guardrail override display**: When AI proposed != authorized policy, show an explicit
   "Override" indicator. Proposed design: amber chip "PROPOSAL OVERRIDDEN" between the
   AI and guardrail cards. Confirm this is the correct behavior to highlight.
