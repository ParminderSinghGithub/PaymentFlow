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

export interface LaunchScenarioRequest {
  scenario_id?: string;
  amount_paise?: number;
  customer_email?: string;
  customer_contact?: string;
  reset_previous?: boolean;
}

export interface LaunchScenarioResponse {
  status: 'success' | 'error' | string;
  case_id: string;
  scenario_id: string;
  state: string;
  failure_category: string;
  amount_paise: number;
  amount_inr: number;
  ai_policy?: string | null;
  validated_policy?: string | null;
  action_status?: string | null;
  payment_link_id?: string | null;
  payment_link_url?: string | null;
  audit_trail_count: number;
  orchestrator_result?: Record<string, unknown>;
}

export interface InteractiveStatusResponse {
  case_id: string;
  exists: boolean;
  state?: string | null;
  failure_category?: string | null;
  failure_code?: string | null;
  failure_description?: string | null;
  amount_paise?: number;
  amount_inr?: number;
  currency?: string;
  payment_link_id?: string | null;
  payment_link_url?: string | null;
  payment_link_status?: string | null;
  recovered_payment_id?: string | null;
  recovered_amount_paise?: number | null;
  recovered_amount_inr?: number;
  ai_policy?: string | null;
  ai_explanation?: string | null;
  validated_policy?: string | null;
  scheduled_at?: string | null;
  audit_trail?: AuditEvent[];
  created_at?: string | null;
  updated_at?: string | null;
  message?: string;
}

export interface InteractiveVerifyResponse {
  case_id: string;
  verified: boolean;
  already_recovered?: boolean;
  state?: string;
  payment_status?: string;
  payment_link_id?: string;
  payment_link_status?: string;
  recovered_payment_id?: string;
  recovered_amount_inr?: number;
  audit_trail_count?: number;
  message?: string;
  error?: string;
}

export interface InteractiveResetResponse {
  status: string;
  message: string;
  case_id?: string;
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
    name: 'Transient Customer Action',
    description: 'User dropped off, OTP timeout, or momentary app cancellation.',
    defaultPolicy: 'P_CREATE_LINK_IMMEDIATE',
    badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    recoveryLikelihood: 'Very High (70-85%)',
  },
  C2: {
    code: 'C2',
    name: 'Network / User Dropout',
    description: 'PSP gateway timeout, interrupted network connectivity, app switch dropout.',
    defaultPolicy: 'P_CREATE_LINK_IMMEDIATE',
    badgeClass: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
    recoveryLikelihood: 'High (60-75%)',
  },
  C3: {
    code: 'C3',
    name: 'Soft Infrastructure / Balance Limit',
    description: 'Card limit exceeded, balance friction; benefits from delayed retry scheduling.',
    defaultPolicy: 'P_CREATE_LINK_DELAYED',
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    recoveryLikelihood: 'Moderate (35-50%)',
  },
  C4: {
    code: 'C4',
    name: 'Risk / Compliance Rejection',
    description: 'Card risk filter, AML blacklist, card stolen; automated retry strictly forbidden.',
    defaultPolicy: 'P_ESCALATE_ONLY',
    badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    recoveryLikelihood: 'Zero (Escalate Only)',
  },
  C5: {
    code: 'C5',
    name: 'Technical / Gateway Defect',
    description: 'Malformed payload, 500 internal gateway defect; customer retry unrecoverable.',
    defaultPolicy: 'P_NO_ACTION',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
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
