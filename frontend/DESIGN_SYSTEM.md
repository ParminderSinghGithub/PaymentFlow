# PaymentFlow — Design System v2.0

> **AI recommends. Deterministic policy authorizes.**
> This sentence is the design system north star. Every visual decision follows from it.

---

## 1. Design Philosophy

PaymentFlow is not a dashboard. It is an **operations console** for an AI-augmented financial
recovery system. The interface must communicate:

- Precision and trustworthiness (financial data at stake)
- System depth (distributed pipeline, state machine, LLM + guardrails)
- Operational clarity (what happened, why, what is next)

**Three anti-patterns to avoid:**
1. Decorative gradients / glassmorphism that obscure rather than clarify
2. Generic "SaaS dashboard" visual patterns (big numbers in colored cards, nothing else)
3. Visual clutter that competes with financial and decision data

---

## 2. Core Color Language

The single most important design decision: **two-zone color identity**.

The interface must make immediately legible where a human is reading about an AI action
versus a deterministic policy enforcement. These are architecturally different and must look
architecturally different.

### Zone A — AI Advisory (Violet)

Used for anything originating from the LLM: proposals, explanations, failure classifications,
MCP boundary visualization.

```
ai-base:   #7C3AED
ai-dim:    #4C1D95
ai-muted:  rgba(124, 58, 237, 0.12)
ai-border: rgba(124, 58, 237, 0.25)
ai-text:   #C4B5FD
```

### Zone B — Deterministic / Guardrail (Teal)

Used for anything enforced by the PolicyGuardrailEngine, eligibility engine,
state machine transitions, and verified financial outcomes.

```
guard-base:   #0D9488
guard-dim:    #134E4A
guard-muted:  rgba(13, 148, 136, 0.12)
guard-border: rgba(13, 148, 136, 0.25)
guard-text:   #5EEAD4
```

### Zone C — Recovered / Success (Emerald)

Used only for verified, captured, attributed revenue outcomes.

```
success-base:   #059669
success-muted:  rgba(5, 150, 105, 0.12)
success-text:   #6EE7B7
```

### Zone D — Escalation / Risk (Amber)

Used for ESCALATED state, high-value overrides, guardrail rejections.

```
risk-base:   #D97706
risk-muted:  rgba(217, 119, 6, 0.12)
risk-text:   #FCD34D
```

### Zone E — Hard Failure / No-Action (Rose)

Used for TERMINAL_NO_ACTION, C4/C5 categories, critical system errors.

```
danger-base:   #E11D48
danger-muted:  rgba(225, 29, 72, 0.10)
danger-text:   #FDA4AF
```

### Surface / Neutral Scale

```
surface-void:       #07090C   page background
surface-base:       #0D1017   primary cards
surface-raised:     #131820   elevated elements
surface-overlay:    #1A2030   modals, dropdowns
surface-border:     rgba(255, 255, 255, 0.06)
surface-border-med: rgba(255, 255, 255, 0.10)
surface-border-str: rgba(255, 255, 255, 0.18)

text-primary:       #F0F2F5   headings, critical values
text-secondary:     #9CA3AF   labels, descriptions
text-tertiary:      #4B5563   timestamps, IDs, metadata
text-mono:          #E2E8F0   monospace data
```

---

## 3. Typography

Typefaces:
- UI Font: Inter (400, 500, 600, 700) — all labels, body, descriptions
- Data Font: JetBrains Mono (400, 500, 600) — IDs, amounts, policy codes, states, JSON

Type Scale:

| Role | Font | Size | Weight | Usage |
|------|------|------|--------|-------|
| display | Inter | 28px | 700 | Page-level KPIs |
| heading-1 | Inter | 20px | 700 | Section headers |
| heading-2 | Inter | 15px | 600 | Card titles |
| heading-3 | Inter | 13px | 600 | Sub-section titles |
| body | Inter | 13px | 400 | All body text |
| body-sm | Inter | 12px | 400 | Secondary descriptors |
| label | Inter | 11px | 500 | Uppercase labels |
| caption | Inter | 11px | 400 | Timestamps, metadata |
| mono-lg | JetBrains Mono | 14px | 600 | KPI amounts |
| mono-md | JetBrains Mono | 12px | 500 | Policy IDs, state names |
| mono-sm | JetBrains Mono | 11px | 400 | Long IDs, audit data |

Rule: UPPERCASE MONO for system-generated codes. No title-case italics.

---

## 4. Spacing and Layout Grid

```
space-1:   4px
space-2:   8px
space-3:   12px
space-4:   16px
space-5:   20px
space-6:   24px
space-8:   32px
space-10:  40px
space-12:  48px
```

- Content max-width: 1440px, centered
- Sidebar: 220px expanded / 56px collapsed
- Main content padding: 24px desktop, 16px mobile
- Card padding: 20px standard, 16px compact
- Border radius: cards 8px, badges 4px, buttons 6px, modals 12px

---

## 5. Component Patterns

### 5.1 KPI Metric Card

Left accent strip (3px) in zone color — NOT a full colored border or glow.

- Recovery metric: success-base left accent
- Guardrail metric: guard-base left accent
- AI metric: ai-base left accent

No shadows. No gradients. The accent communicates the zone.
Hover: border to surface-border-str, background to surface-raised.

### 5.2 State Badge

States visual mapping:

| State | Zone | Display Label |
|-------|------|---------------|
| FAILED_INGESTED | Amber | INGESTED |
| CONTEXT_RETRIEVED | Neutral | CONTEXT |
| ELIGIBILITY_CHECKED | Neutral | ELIGIBLE |
| AI_TRIAGE_COMPLETE | AI Violet | AI ADVISED |
| ACTION_APPROVED | Guard Teal | APPROVED |
| ACTION_EXECUTED | Guard Teal | LINK SENT |
| RECOVERED | Emerald | RECOVERED |
| ESCALATED | Amber | ESCALATED |
| TERMINAL_NO_ACTION | Rose | NO ACTION |
| ERROR | Rose | ERROR |

Badge anatomy: 6px filled dot (zone color) + UPPERCASE mono-sm label.

### 5.3 Category Badge (C1-C5)

| Category | Color | Label |
|----------|-------|-------|
| C1 | Amber | C1 CUSTOMER |
| C2 | Blue | C2 GATEWAY |
| C3 | Orange | C3 INSTRUMENT |
| C4 | Rose | C4 RISK |
| C5 | Zinc | C5 TECHNICAL |

These use categorical colors independent of the AI/Guard zone system.

### 5.4 Policy Badge

Two rendering contexts — same data, different zone = safety boundary made visible:

```
AI  P_CREATE_LINK_IMMEDIATE    <- violet background, AI prefix
 v  P_CREATE_LINK_IMMEDIATE    <- teal background, checkmark prefix
```

### 5.5 Pipeline Step Indicator

Horizontal sequence. Stages 01-03 and 05-08 = teal. Stage 04 = violet.

Stage 04 visually separates from the deterministic pipeline — the advisory boundary.

### 5.6 Decision Story Timeline

Vertical card sequence in Case Investigation.

Each stage card has a 3px left accent:
- Stage 04 (AI Advisory): ai-base accent, AI ADVISORY label in header
- Stage 05 (Guardrail): guard-base accent, GUARDRAIL label in header
- All other stages: surface-border-med accent

Vertical connector line between cards changes from teal to violet at stage 04,
back to teal at stage 05. This color transition IS the product central story.

### 5.7 Audit Trail Event

Compact record with monospace event type, right-aligned timestamp, and collapsible JSON
details block. JSON block: surface-overlay background, collapsed by default.

### 5.8 Data Table

- No outer border on the table
- Column headers: label type, text-tertiary, uppercase
- Row hover: background surface-raised
- Full-row click for navigation
- No zebra striping — clean rows
- Amounts: right-aligned, mono-md, text-primary

### 5.9 Buttons

Primary action (violet, AI zone):
- background rgba(124, 58, 237, 0.15), border rgba(124, 58, 237, 0.40), text #C4B5FD

Secondary action (neutral):
- background transparent, border surface-border-med, text text-secondary

Batch/guardrail action (teal, guard zone):
- background rgba(13, 148, 136, 0.15), border rgba(13, 148, 136, 0.35), text #5EEAD4

No filled solid-color buttons. No button shadows.

### 5.10 Navigation Sidebar

- Background: surface-void (same as page — no distinct panel)
- Right edge: 1px solid surface-border
- Active nav: background surface-raised, 2px solid ai-base left accent
- Wordmark: "PaymentFlow" Inter 700, 15px — no logo emblem
- Subtext: "Recovery Intelligence" text-tertiary 11px

---

## 6. Motion and Animation

Motion communicates state change — not decoration.

| Event | Animation |
|-------|-----------|
| Page transition | opacity 0 to 1, 150ms ease-out |
| Triage loading | Spinner on action button only |
| Skeleton loading | Shimmer pulse, 1.5s loop |
| Toast notification | Slide in from bottom-right, 200ms |
| Row hover | background-color transition, 100ms |
| Tab switch | Underline slide, 150ms |
| Live ingested badge | 2s opacity pulse on INGESTED dot |

No parallax. No floating. No scroll-triggered animations.

---

## 7. Tailwind Configuration Extension

```js
extend: {
  colors: {
    void: '#07090C',
    surface: { base: '#0D1017', raised: '#131820', overlay: '#1A2030' },
    ai:    { base: '#7C3AED', dim: '#4C1D95', text: '#C4B5FD' },
    guard: { base: '#0D9488', dim: '#134E4A', text: '#5EEAD4' },
    recover: { base: '#059669', text: '#6EE7B7' },
    risk:    { base: '#D97706', text: '#FCD34D' },
    halt:    { base: '#E11D48', text: '#FDA4AF' },
  },
  fontFamily: {
    sans: ['Inter', 'system-ui', 'sans-serif'],
    mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
  },
}
```

---

## 8. Icon Map (lucide-react)

| Context | Icon |
|---------|------|
| AI / LLM | BrainCircuit, Bot, Sparkles |
| Guardrail / Policy | ShieldCheck, Lock, BadgeCheck |
| Payment Link | Link2, ExternalLink |
| Revenue / Recovery | IndianRupee, TrendingUp |
| Cases / Workflow | GitBranch, ListChecks |
| System / Health | Activity, Server |
| MCP Architecture | Network, Cpu |
| Audit / Log | ClipboardList, History |
| Error / No-action | XCircle, AlertTriangle |

Icons: 16px standard, 14px inline dense text.

---

## 9. Accessibility Baseline

- Minimum contrast 4.5:1 for body text, 3:1 for large text and UI elements
- focus-visible ring: 2px ai-text color on all interactive elements
- Color is never the sole differentiator — always paired with label, icon, or shape
- aria-label on all icon-only buttons
