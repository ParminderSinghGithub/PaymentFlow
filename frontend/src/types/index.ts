/**
 * PaymentFlow Recovery Intelligence Console — TypeScript Domain & API Types
 * Strictly aligned to the frozen FastAPI backend REST schema and Product Spec v2.0.
 */

export type CaseState =
  | 'FAILED_INGESTED'
  | 'CONTEXT_RETRIEVED'
  | 'ELIGIBILITY_CHECKED'
  | 'ACTION_APPROVED'
  | 'ACTION_EXECUTED'
  | 'RECOVERED'
  | 'ESCALATED'
  | 'TERMINAL_NO_ACTION';

export type RecoveryPolicy =
  | 'P_CREATE_LINK_IMMEDIATE'
  | 'P_CREATE_LINK_DELAYED'
  | 'P_ESCALATE_ONLY'
  | 'P_NO_ACTION';

export type FailureCategory = 'C1' | 'C2' | 'C3' | 'C4' | 'C5' | 'UNKNOWN';

export interface CaseSummaryItem {
  case_id: string;
  failed_payment_id: string;
  order_id: string | null;
  customer_id: string | null;
  amount_paise: number;
  amount_inr: number;
  currency: string;
  payment_method: string | null;
  failure_category: FailureCategory | string | null;
  state: CaseState | string;
  validated_policy_id: RecoveryPolicy | string | null;
  payment_link_id: string | null;
  payment_link_short_url: string | null;
  recovered_amount_paise: number | null;
  recovered_amount_inr: number;
  case_source?: string | null;
  eval_run_id?: string | null;
  created_at: string | null;
  scheduled_at: string | null;
}

export interface AuditEvent {
  id: number;
  event_type: string;
  actor: string;
  decision: string | null;
  policy: string | null;
  action: string | null;
  outcome: string | null;
  timestamp: string | null;
  details: Record<string, unknown> | null;
  guardrail_result: Record<string, unknown> | null;
}

export interface CaseDetail {
  case_id: string;
  failed_payment_id: string;
  order_id: string | null;
  customer_id: string | null;
  amount_paise: number;
  amount_inr: number;
  currency: string;
  payment_method: string | null;
  failure_category: FailureCategory | string | null;
  failure_code: string | null;
  failure_description: string | null;
  failure_context: Record<string, unknown> | null;
  eligibility_status: string | null;
  eligibility_reason: string | null;
  classification_evidence: Record<string, unknown> | null;
  ai_policy_id: string | null;
  ai_explanation: string | null;
  validated_policy_id: RecoveryPolicy | string | null;
  action_status: string | null;
  case_source?: string | null;
  eval_run_id?: string | null;
  payment_link_id: string | null;
  payment_link_reference_id: string | null;
  payment_link_short_url: string | null;
  payment_link_status: string | null;
  recovered_payment_id: string | null;
  recovered_amount_paise: number | null;
  recovered_amount_inr: number;
  state: CaseState | string;
  scheduled_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CaseDetailResponse {
  case: CaseDetail;
  audit_trail: AuditEvent[];
}

export interface MetricsSummary {
  total_cases: number;
  recovered_cases: number;
  total_recovered_amount_inr: number;
  recovery_rate_pct: number;
  active_recovery_links: number;
  escalated_cases: number;
  terminal_no_action_cases: number;
  category_breakdown: Record<string, number>;
  policy_breakdown: Record<string, number>;
  eval_run_id?: string | null;
  case_source?: string | null;
  total_at_risk_amount_inr?: number;
  eligible_cases?: number;
  eligible_opportunity_amount_inr?: number;
  evaluation_recovered_cases?: number;
  evaluation_recovered_amount_inr?: number;
  escalated_amount_inr?: number;
  terminal_amount_inr?: number;
  overall_case_recovery_rate_pct?: number;
  eligible_case_recovery_rate_pct?: number;
  portfolio_revenue_recovery_rate_pct?: number;
  eligible_opportunity_recovery_rate_pct?: number;
}

export interface BenchmarkLatestResponse {
  eval_run_id: string;
  case_source: string;
  status: string;
  total_cases: number;
  total_at_risk_amount_inr: number;
  eligible_cases: number;
  eligible_opportunity_amount_inr: number;
  recovery_actions_executed: number;
  recovery_actions_blocked: number;
  evaluation_recovered_cases: number;
  evaluation_recovered_amount_inr: number;
  escalated_cases: number;
  escalated_amount_inr: number;
  terminal_cases: number;
  terminal_amount_inr: number;
  overall_case_recovery_rate_pct: number;
  eligible_case_recovery_rate_pct: number;
  portfolio_revenue_recovery_rate_pct: number;
  eligible_opportunity_recovery_rate_pct: number;
  category_breakdown: Record<string, number>;
  policy_breakdown: Record<string, number>;
  created_at: string | null;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | string;
  environment: string;
  database: 'connected' | 'disconnected' | string;
  version: string;
}

export interface TriageResult {
  success: boolean;
  case_id: string;
  stage?: string;
  state?: string;
  policy?: string;
  payment_link_id?: string;
  payment_link_url?: string;
  error?: string;
  action_executed?: boolean;
}

export interface DelayedProcessResult {
  processed_count: number;
  results: Array<Record<string, unknown>>;
}

export interface DemoSeedResponse {
  status: string;
  seeded_cases_count: number;
  total_revenue_at_risk_inr: number;
  total_recovered_inr: number;
  recovery_rate_pct: number;
  cases: string[];
}

export interface BenchmarkRunResponse {
  eval_run_id: string;
  case_source: string;
  status: string;
  total_cases: number;
  total_at_risk_amount_inr: number;
  eligible_cases: number;
  eligible_opportunity_amount_inr: number;
  recovery_actions_executed: number;
  recovery_actions_blocked: number;
  evaluation_recovered_cases: number;
  evaluation_recovered_amount_inr: number;
  escalated_cases: number;
  escalated_amount_inr: number;
  terminal_cases: number;
  terminal_amount_inr: number;
  overall_case_recovery_rate_pct: number;
  eligible_case_recovery_rate_pct: number;
  portfolio_revenue_recovery_rate_pct: number;
  eligible_opportunity_recovery_rate_pct: number;
  cases: Array<Record<string, unknown>>;
}


export interface CategoryMetadata {
  code: FailureCategory;
  name: string;
  description: string;
  defaultPolicy: RecoveryPolicy;
  badgeClass: string;
  recoveryLikelihood: string;
}

export const CATEGORY_INFO: Record<FailureCategory, CategoryMetadata> = {
  C1: {
    code: 'C1',
    name: 'Customer Dropoff',
    description: 'Transient customer action (OTP cancellation, delayed entry, session expiry).',
    defaultPolicy: 'P_CREATE_LINK_IMMEDIATE',
    badgeClass: 'bg-[rgba(217,119,6,0.12)] text-[#FCD34D] border-[rgba(217,119,6,0.30)]',
    recoveryLikelihood: 'High (70–85%)',
  },
  C2: {
    code: 'C2',
    name: 'Soft Infrastructure',
    description: 'Acquirer network glitch, bank downtime, or gateway processing timeout.',
    defaultPolicy: 'P_CREATE_LINK_DELAYED',
    badgeClass: 'bg-[rgba(37,99,235,0.12)] text-[#93C5FD] border-[rgba(37,99,235,0.30)]',
    recoveryLikelihood: 'High (60–75%)',
  },
  C3: {
    code: 'C3',
    name: 'Instrument Defect',
    description: 'Card or account failure (insufficient funds, expired card, bank limit exceeded).',
    defaultPolicy: 'P_CREATE_LINK_DELAYED',
    badgeClass: 'bg-[rgba(234,88,12,0.12)] text-[#FDBA74] border-[rgba(234,88,12,0.30)]',
    recoveryLikelihood: 'Moderate (35–50%)',
  },
  C4: {
    code: 'C4',
    name: 'Risk & Fraud Gate',
    description: 'High-risk velocity breach, stolen card detection, or AML/compliance flag.',
    defaultPolicy: 'P_ESCALATE_ONLY',
    badgeClass: 'bg-[rgba(225,29,72,0.10)] text-[#FDA4AF] border-[rgba(225,29,72,0.30)]',
    recoveryLikelihood: 'Zero (Escalate Only)',
  },
  C5: {
    code: 'C5',
    name: 'Technical / Bug',
    description: 'Non-recoverable technical bug (malformed payload, invalid schema, gateway 500).',
    defaultPolicy: 'P_NO_ACTION',
    badgeClass: 'bg-[rgba(82,82,91,0.15)] text-[#A1A1AA] border-[rgba(82,82,91,0.30)]',
    recoveryLikelihood: 'Zero (Halt)',
  },
  UNKNOWN: {
    code: 'UNKNOWN',
    name: 'Unclassified',
    description: 'Unclassified failure mode.',
    defaultPolicy: 'P_NO_ACTION',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
    recoveryLikelihood: 'Unknown',
  },
};

