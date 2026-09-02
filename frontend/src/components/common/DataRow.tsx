/**
 * DataRow — consistent labeled metadata item for PaymentFlow.
 *
 * Used across case details, telemetry viewers, and diagnostic cards.
 * Enforces tabular, high-contrast display with monospace values for technical identifiers.
 */

import React from 'react';

interface DataRowProps {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  copyable?: boolean;
  hint?: string;
  className?: string;
}

export const DataRow: React.FC<DataRowProps> = ({
  label,
  value,
  mono = false,
  hint,
  className = '',
}) => {
  return (
    <div className={`data-row ${className}`}>
      <span className="data-row__label" title={hint}>
        {label}
      </span>
      <span className={`data-row__value ${mono ? 'font-mono text-[11px]' : ''}`}>
        {value ?? <span className="text-[#4B5563]">—</span>}
      </span>
    </div>
  );
};
