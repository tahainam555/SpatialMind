import React from 'react';
import type { TraceStep } from '../types';

interface TraceTimelineProps {
  trace: TraceStep[];
  totalMs: number;
  refined: boolean;
  faultInjected?: string | null;
}

const STAGE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  understand: { label: 'Agent 1: Understand', icon: '🧠', color: '#818cf8' },
  plan: { label: 'Agent 2: Spatial Plan', icon: '📐', color: '#38bdf8' },
  inject_fault: { label: 'Fault Injected (Demo)', icon: '⚠️', color: '#f59e0b' },
  construct: { label: 'Agent 3: Construction', icon: '🏗️', color: '#a855f7' },
  verify: { label: 'Agent 4: Verification', icon: '🛡️', color: '#10b981' },
  replan: { label: 'Loop: Memory Re-plan', icon: '🔄', color: '#f97316' },
  done: { label: 'Final Validated Scene', icon: '✨', color: '#22c55e' },
};

export const TraceTimeline: React.FC<TraceTimelineProps> = ({
  trace,
  totalMs,
  refined,
  faultInjected,
}) => {
  return (
    <div className="trace-card">
      <div className="trace-header">
        <h4 className="card-heading">State-Machine Execution Trace</h4>
        <div className="trace-meta">
          {faultInjected && <span className="pill pill-fault">Fault Injected</span>}
          {refined && <span className="pill pill-refined">Self-Repaired via Loop</span>}
          <span className="pill pill-time">⚡ {totalMs.toFixed(1)} ms</span>
        </div>
      </div>

      <div className="timeline-steps">
        {trace.map((step, idx) => {
          const info = STAGE_LABELS[step.stage] || {
            label: step.stage,
            icon: '⚙️',
            color: '#94a3b8',
          };
          const isFail = step.passed === false;
          const isSuccess = step.passed === true;

          return (
            <div key={`step-${idx}`} className={`timeline-item ${isFail ? 'step-fail' : ''}`}>
              <div className="timeline-marker" style={{ borderColor: info.color }}>
                <span className="step-icon">{info.icon}</span>
              </div>
              <div className="timeline-content">
                <div className="step-row">
                  <span className="step-title" style={{ color: info.color }}>
                    {info.label}
                  </span>
                  {step.iteration > 0 && (
                    <span className="iter-badge">Iter #{step.iteration}</span>
                  )}
                  <span className="step-duration">{step.duration_ms.toFixed(1)} ms</span>
                </div>
                <div className="step-summary">
                  {step.summary}
                  {isSuccess && <span className="step-badge-pass"> ✓ PASSED</span>}
                  {isFail && <span className="step-badge-fail"> ✗ VIOLATIONS</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
