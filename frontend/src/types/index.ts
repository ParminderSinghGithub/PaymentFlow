/**
 * PaymentFlow Recovery Intelligence Console — TypeScript Domain & API Types
 * Matched strictly to the frozen Layer 5G backend REST schema.
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
    name: 'Soft Infrastructure / Gateway',
    description: 'Bank switch down, gateway timeout, or temporary network failure.',
    defaultPolicy: 'P_CREATE_LINK_DELAYED',
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    recoveryLikelihood: 'High (50-70% after cooldown)',
  },
  C3: {
    code: 'C3',
    name: 'Hard Instrument / Card Limit',
    description: 'Card expired, insufficient balance, or credit limit exceeded.',
    defaultPolicy: 'P_CREATE_LINK_IMMEDIATE',
    badgeClass: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    recoveryLikelihood: 'Moderate (alternate payment instrument required)',
  },
  C4: {
    code: 'C4',
    name: 'Business / Risk / Compliance',
    description: 'Transaction flagged by fraud rules, velocity limit, or AML check.',
    defaultPolicy: 'P_ESCALATE_ONLY',
    badgeClass: 'bg-red-500/10 text-red-400 border-red-500/30',
    recoveryLikelihood: 'None (automated link creation strictly forbidden)',
  },
  C5: {
    code: 'C5',
    name: 'Technical / Integration Defect',
    description: 'Payload schema mismatch, bad parameter, or API contract violation.',
    defaultPolicy: 'P_NO_ACTION',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
    recoveryLikelihood: 'None (requires engineering fix)',
  },
  UNKNOWN: {
    code: 'UNKNOWN',
    name: 'Unclassified Failure',
    description: 'Uncategorized gateway error code; evaluated via fallback heuristics.',
    defaultPolicy: 'P_NO_ACTION',
    badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
    recoveryLikelihood: 'Low',
  },
};
