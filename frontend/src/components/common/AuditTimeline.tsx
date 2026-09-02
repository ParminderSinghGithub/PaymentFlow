/**
 * AuditTimeline — immutable, chronological event stream primitive for PaymentFlow.
 *
 * Visual semantics:
 *   - Violet marker: AI Advisory events (proposals, suggestions, LLM triage)
 *   - Teal marker: Guardrail events (rule evaluations, policy authorizations)
 *   - Emerald marker: Revenue capture / recovery attribution
 *   - Amber marker: Escalations / human review
 *   - Rose marker: Hard halts / terminal blocks
 *   - Neutral marker: System ingestion, webhooks, context retrieval
 */

import React from 'react';
import type { AuditEvent } from '../../types';
import { PolicyBadge } from './PolicyBadge';

interface AuditTimelineProps {
  events: AuditEvent[];
  loading?: boolean;
  className?: string;
  emptyMessage?: string;
}

const getEventZone = (
  eventType: string,
  actor: string,
  decision: string | null
): 'ai' | 'guard' | 'recover' | 'risk' | 'halt' | 'neutral' => {
  const t = eventType.toLowerCase();
  const a = actor.toLowerCase();
  const d = (decision ?? '').toLowerCase();

  if (t.includes('recovered') || t.includes('captured') || d.includes('captured')) {
    return 'recover';
  }
  if (t.includes('escalat') || d.includes('escalat')) {
    return 'risk';
  }
  if (t.includes('halt') || t.includes('block') || d.includes('block') || t.includes('terminal')) {
    return 'halt';
  }
  if (a.includes('guardrail') || a.includes('policy') || t.includes('guardrail') || t.includes('authoriz')) {
    return 'guard';
  }
  if (a.includes('ai') || a.includes('llm') || a.includes('agent') || t.includes('triage') || t.includes('propos')) {
    return 'ai';
  }
  return 'neutral';
};

const ZONE_STYLES = {
  ai: {
    dot: 'bg-ai-base ring-4 ring-ai-muted border-ai-border',
    text: 'text-ai-text',
    badge: 'bg-ai-muted border-ai-border text-ai-text',
  },
  guard: {
    dot: 'bg-guard-base ring-4 ring-guard-muted border-guard-border',
    text: 'text-guard-text',
    badge: 'bg-guard-muted border-guard-border text-guard-text',
  },
  recover: {
    dot: 'bg-recover-base ring-4 ring-recover-muted border-recover-border',
    text: 'text-recover-text',
    badge: 'bg-recover-muted border-recover-border text-recover-text',
  },
  risk: {
    dot: 'bg-risk-base ring-4 ring-risk-muted border-risk-border',
    text: 'text-risk-text',
    badge: 'bg-risk-muted border-risk-border text-risk-text',
  },
  halt: {
    dot: 'bg-halt-base ring-4 ring-halt-muted border-halt-border',
    text: 'text-halt-text',
    badge: 'bg-halt-muted border-halt-border text-halt-text',
  },
  neutral: {
    dot: 'bg-[#4B5563] ring-4 ring-white/[0.04] border-white/[0.12]',
    text: 'text-[#9CA3AF]',
    badge: 'bg-white/[0.04] border-white/[0.08] text-[#9CA3AF]',
  },
};

export const AuditTimeline: React.FC<AuditTimelineProps> = ({
  events,
  loading = false,
  className = '',
  emptyMessage = 'No audit records in the event log.',
}) => {
  if (loading) {
    return (
      <div className={`space-y-4 py-3 ${className}`}>
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-4">
            <div className="w-3 h-3 rounded-full skeleton-shimmer mt-1 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-40 skeleton-shimmer rounded" />
              <div className="h-3 w-64 skeleton-shimmer rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className={`py-6 text-center text-[12px] text-[#4B5563] font-mono ${className}`}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`relative pl-3 space-y-6 before:absolute before:left-[17px] before:top-2 before:bottom-2 before:w-[1px] before:bg-white/[0.08] ${className}`}>
      {events.map((evt, idx) => {
        const zone = getEventZone(evt.event_type, evt.actor, evt.decision);
        const style = ZONE_STYLES[zone];
        const formattedTime = evt.timestamp
          ? new Date(evt.timestamp).toLocaleTimeString('en-US', {
              hour12: false,
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })
          : '—';

        return (
          <div key={evt.id ?? idx} className="relative flex items-start gap-3.5 group">
            {/* Timeline Dot */}
            <div
              className={`w-2.5 h-2.5 rounded-full border shrink-0 mt-1.5 transition-transform group-hover:scale-110 ${style.dot}`}
              title={`${evt.actor} · ${evt.event_type}`}
            />

            {/* Event Content */}
            <div className="flex-1 min-w-0 bg-surface-raised border border-white/[0.06] rounded-md p-3 hover:border-white/[0.12] transition-colors">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`text-[10px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${style.badge}`}>
                    {evt.actor}
                  </span>
                  <span className="text-[12px] font-medium text-[#F0F2F5] truncate">
                    {evt.event_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[#4B5563] shrink-0">
                  {formattedTime}
                </span>
              </div>

              {/* Decision / Action / Policy Row */}
              <div className="flex flex-wrap items-center gap-2 mt-2 pt-2 border-t border-white/[0.04] text-[11px]">
                {evt.decision && (
                  <span className="text-[#9CA3AF]">
                    Decision: <strong className={style.text}>{evt.decision}</strong>
                  </span>
                )}
                {evt.policy && (
                  <PolicyBadge
                    policy={evt.policy}
                    context={zone === 'ai' ? 'ai' : zone === 'guard' ? 'guard' : 'auto'}
                  />
                )}
                {evt.outcome && (
                  <span className="text-[#6B7280] font-mono text-[10px]">
                    Outcome: {evt.outcome}
                  </span>
                )}
              </div>

              {/* Event Details JSON (if present and non-empty) */}
              {evt.details && Object.keys(evt.details).length > 0 && (
                <details className="mt-2 text-[10px]">
                  <summary className="text-[#4B5563] hover:text-[#9CA3AF] cursor-pointer font-mono select-none">
                    View payload metadata
                  </summary>
                  <pre className="mt-1.5 p-2 rounded bg-black/40 border border-white/[0.04] text-[#9CA3AF] font-mono overflow-x-auto max-h-32 text-[10px]">
                    {JSON.stringify(evt.details, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
