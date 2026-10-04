import React from 'react';
import type { VerificationReport } from '../types';

interface VerificationPanelProps {
  initialReport: VerificationReport;
  finalReport: VerificationReport;
  refined: boolean;
  iterations: number;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({
  initialReport,
  finalReport,
  refined,
  iterations,
}) => {
  const scorePercent = Math.round(finalReport.score * 100);
  const m = finalReport.metrics;

  return (
    <div className="verification-card">
      <div className="verif-header">
        <h4 className="card-heading">Agent 4: Verification & Metrics</h4>
        <div className="verif-score-badge" style={{ backgroundColor: finalReport.passed ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: finalReport.passed ? '#4ade80' : '#f87171' }}>
          {finalReport.passed ? '✓ Valid Scene' : '✗ Issues Found'} • {scorePercent}% Score
        </div>
      </div>

      {refined && (
        <div className="refinement-alert">
          <span className="alert-icon">🔄</span>
          <div className="alert-body">
            <strong>Verification Feedback Triggered Re-plan:</strong>
            <p>
              The initial layout had {initialReport.violations.length} violation(s).
              Spatial memory updated with rejected poses, and the planner successfully re-arranged objects in {iterations} iteration(s).
            </p>
          </div>
        </div>
      )}

      {/* Numerical Metrics Grid */}
      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-val" style={{ color: (m.collisions || 0) === 0 ? '#4ade80' : '#f87171' }}>
            {m.collisions || 0}
          </span>
          <span className="metric-lbl">Collisions</span>
        </div>
        <div className="metric-box">
          <span className="metric-val" style={{ color: (m.boundary_violations || 0) === 0 ? '#4ade80' : '#f87171' }}>
            {m.boundary_violations || 0}
          </span>
          <span className="metric-lbl">Out of Bounds</span>
        </div>
        <div className="metric-box">
          <span className="metric-val" style={{ color: (m.opening_blocks || 0) === 0 ? '#4ade80' : '#f87171' }}>
            {m.opening_blocks || 0}
          </span>
          <span className="metric-lbl">Door/Win Blocks</span>
        </div>
        <div className="metric-box">
          <span className="metric-val" style={{ color: (m.clearance_violations || 0) === 0 ? '#4ade80' : '#f87171' }}>
            {m.clearance_violations || 0}
          </span>
          <span className="metric-lbl">Clearance Clashes</span>
        </div>
        <div className="metric-box">
          <span className="metric-val" style={{ color: '#38bdf8' }}>
            {m.constraints_satisfied || 0}/{m.constraints_total || 0}
          </span>
          <span className="metric-lbl">Constraints Met</span>
        </div>
      </div>

      {/* Constraints Breakdown */}
      {finalReport.constraint_results.length > 0 && (
        <div className="constraints-section">
          <h5 className="sub-heading">Spatial Requirements & Relations:</h5>
          <div className="constraint-list">
            {finalReport.constraint_results.map((c, i) => (
              <div key={`cr-${i}`} className={`constraint-item ${c.satisfied ? 'c-pass' : 'c-fail'}`}>
                <span className="c-status">{c.satisfied ? '✓' : '✗'}</span>
                <span className="c-code">{c.constraint}</span>
                <span className="c-detail">{c.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Violations List (if any remain) */}
      {finalReport.violations.length > 0 && (
        <div className="violations-section">
          <h5 className="sub-heading" style={{ color: '#f87171' }}>Active Violations:</h5>
          <ul className="violations-list">
            {finalReport.violations.map((v, i) => (
              <li key={`v-${i}`} className="violation-item">
                <span className="v-kind">[{v.kind}]</span> {v.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
