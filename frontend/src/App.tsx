import { useEffect, useState } from 'react';
import './App.css';
import { SceneViewer } from './components/SceneViewer';
import { TraceTimeline } from './components/TraceTimeline';
import { VerificationPanel } from './components/VerificationPanel';
import type { GenerationResult, HealthInfo } from './types';

export function App() {
  const [prompt, setPrompt] = useState<string>(
    'Create a bedroom with a bed, desk and wardrobe, with the desk near the window and enough space for movement.'
  );
  const [examples, setExamples] = useState<string[]>([]);
  const [roomWidth, setRoomWidth] = useState<number | undefined>(undefined);
  const [roomDepth, setRoomDepth] = useState<number | undefined>(undefined);
  const [injectFault, setInjectFault] = useState<boolean>(false);
  const [maxIterations, setMaxIterations] = useState<number>(3);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [activeTab, setActiveTab] = useState<'visual' | 'spec' | 'memory' | 'payload'>('visual');

  // Load initial health info and examples from API
  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data: HealthInfo) => setHealth(data))
      .catch(() => setHealth({ status: 'offline', version: 'unknown', provider: 'mock' }));

    fetch('/api/examples')
      .then((res) => res.json())
      .then((data: string[]) => setExamples(data))
      .catch(() => {});
  }, []);

  const handleGenerate = async (customPrompt?: string) => {
    const textToRun = (customPrompt || prompt).trim();
    if (!textToRun) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: textToRun,
          room_width: roomWidth,
          room_depth: roomDepth,
          max_iterations: maxIterations,
          inject_fault: injectFault,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(errData.detail || `Server error (${res.status})`);
      }

      const data: GenerationResult = await res.json();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown generation error');
    } finally {
      setLoading(false);
    }
  };

  // Convert memory objects dictionary to list for the visualizer
  const placedObjects = result ? Object.values(result.memory.objects) : [];

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <header className="navbar">
        <div className="nav-brand">
          <div className="brand-logo">📐</div>
          <div>
            <h1 className="brand-title">SpatialMind</h1>
            <p className="brand-subtitle">
              Agentic Indoor 3D Scene Generation with Persistent Spatial Memory
            </p>
          </div>
        </div>

        <div className="nav-badges">
          <span className="badge badge-fyp">FYP-1 Mid Evaluation</span>
          <span className={`badge ${health?.status === 'ok' ? 'badge-online' : 'badge-offline'}`}>
            ● {health?.status === 'ok' ? 'API Online' : 'API Connecting...'}
          </span>
          {health?.provider && (
            <span className="badge badge-provider">
              LLM: {health.provider.toUpperCase()}
            </span>
          )}
        </div>
      </header>

      {/* Main Grid Layout */}
      <main className="main-layout">
        {/* Left Column: Interactive Inputs & Controls */}
        <section className="controls-panel">
          <div className="panel-card">
            <h2 className="panel-heading">1. Natural Language Requirements</h2>

            {/* Quick Example Presets */}
            {examples.length > 0 && (
              <div className="examples-wrapper">
                <span className="examples-label">Proposal Presets:</span>
                <div className="example-chips">
                  {examples.map((ex, i) => (
                    <button
                      key={`ex-${i}`}
                      type="button"
                      className="chip-btn"
                      onClick={() => {
                        setPrompt(ex);
                        handleGenerate(ex);
                      }}
                    >
                      Preset {i + 1}: {ex.slice(0, 32)}...
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Prompt Textarea */}
            <div className="textarea-container">
              <textarea
                className="prompt-textarea"
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe your room layout, furniture, and spatial constraints..."
              />
            </div>

            {/* Room Dimension Overrides */}
            <div className="dimension-controls">
              <div className="dim-row">
                <label className="dim-label">
                  Room Width: <strong>{roomWidth ? `${roomWidth.toFixed(1)}m` : 'Default'}</strong>
                </label>
                <input
                  type="range"
                  min="3.0"
                  max="7.0"
                  step="0.5"
                  value={roomWidth || 4.0}
                  onChange={(e) => setRoomWidth(parseFloat(e.target.value))}
                />
              </div>

              <div className="dim-row">
                <label className="dim-label">
                  Room Depth: <strong>{roomDepth ? `${roomDepth.toFixed(1)}m` : 'Default'}</strong>
                </label>
                <input
                  type="range"
                  min="3.0"
                  max="7.0"
                  step="0.5"
                  value={roomDepth || 4.0}
                  onChange={(e) => setRoomDepth(parseFloat(e.target.value))}
                />
              </div>

              {(roomWidth || roomDepth) && (
                <button
                  type="button"
                  className="reset-btn"
                  onClick={() => {
                    setRoomWidth(undefined);
                    setRoomDepth(undefined);
                  }}
                >
                  Reset to Auto Room Dimensions
                </button>
              )}
            </div>

            {/* Refinement & Evaluation Controls */}
            <div className="eval-options">
              <label className="checkbox-label fault-highlight">
                <input
                  type="checkbox"
                  checked={injectFault}
                  onChange={(e) => setInjectFault(e.target.checked)}
                />
                <span>
                  <strong>Inject Fault (Evaluation Mode):</strong> Deliberately creates a collision to demonstrate Agent 4 verification and automatic repair.
                </span>
              </label>

              <div className="iter-row">
                <label className="dim-label">Max Refinement Loops:</label>
                <select
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(parseInt(e.target.value, 10))}
                  className="select-dropdown"
                >
                  <option value={0}>0 (Single pass baseline — no loop)</option>
                  <option value={1}>1 loop</option>
                  <option value={2}>2 loops</option>
                  <option value={3}>3 loops (Standard)</option>
                  <option value={5}>5 loops</option>
                </select>
              </div>
            </div>

            {/* Primary Action Button */}
            <button
              type="button"
              className={`primary-cta ${loading ? 'cta-loading' : ''}`}
              disabled={loading || !prompt.trim()}
              onClick={() => handleGenerate()}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Reasoning & Planning Layout...
                </>
              ) : (
                '🚀 Generate & Verify 3D Scene'
              )}
            </button>

            {error && <div className="error-banner">⚠️ {error}</div>}
          </div>

          {/* Architecture Pipeline Summary Widget */}
          <div className="pipeline-info-card">
            <h3 className="card-subheading">Closed-Loop Agentic Pipeline</h3>
            <ul className="pipeline-steps-list">
              <li>
                <span className="step-num">1</span>
                <strong>Agent 1 (VLM/LLM):</strong> Parses English to structured constraints
              </li>
              <li>
                <span className="step-num">2</span>
                <strong>Agent 2 (Planner):</strong> Deterministic spatial memory & candidate scoring
              </li>
              <li>
                <span className="step-num">3</span>
                <strong>Agent 3 (Blender):</strong> 3D-FUTURE construction contract payload
              </li>
              <li>
                <span className="step-num">4</span>
                <strong>Agent 4 (Verifier):</strong> Geometric collision & clearance verification
              </li>
              <li>
                <span className="step-num">🔄</span>
                <strong>Refinement Loop:</strong> Updates rejected poses & re-plans
              </li>
            </ul>
          </div>
        </section>

        {/* Right Column: Visualization & Agent Metrics */}
        <section className="results-panel">
          {result ? (
            <div className="results-flow">
              {/* Tab Selector */}
              <div className="tab-bar">
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'visual' ? 'active' : ''}`}
                  onClick={() => setActiveTab('visual')}
                >
                  🗺️ 2D Spatial Plan & Verification
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'spec' ? 'active' : ''}`}
                  onClick={() => setActiveTab('spec')}
                >
                  📋 Scene Spec (Agent 1)
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'memory' ? 'active' : ''}`}
                  onClick={() => setActiveTab('memory')}
                >
                  🧠 Spatial Memory (Agent 2)
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'payload' ? 'active' : ''}`}
                  onClick={() => setActiveTab('payload')}
                >
                  🏗️ 3D Scene Payload (Agent 3)
                </button>
              </div>

              {/* Tab 1: Visual Plan & Verifier */}
              {activeTab === 'visual' && (
                <div className="visual-tab-grid">
                  <SceneViewer
                    room={result.spec.room || result.memory.room}
                    objects={placedObjects}
                    violations={result.final_report.violations}
                  />

                  <div className="metrics-and-trace-col">
                    <VerificationPanel
                      initialReport={result.initial_report}
                      finalReport={result.final_report}
                      refined={result.refined}
                      iterations={result.iterations}
                    />

                    <TraceTimeline
                      trace={result.trace}
                      totalMs={result.total_ms}
                      refined={result.refined}
                      faultInjected={result.fault_injected}
                    />
                  </div>
                </div>
              )}

              {/* Tab 2: Scene Spec JSON */}
              {activeTab === 'spec' && (
                <div className="json-card">
                  <div className="json-header">
                    <h4>Structured Scene Specification (Contract from Agent 1)</h4>
                    <span className="badge badge-provider">Pydantic Validated</span>
                  </div>
                  <pre className="json-block">{JSON.stringify(result.spec, null, 2)}</pre>
                </div>
              )}

              {/* Tab 3: Spatial Memory JSON & Event Log */}
              {activeTab === 'memory' && (
                <div className="json-card">
                  <div className="json-header">
                    <h4>Persistent Spatial Memory (Agent 2 State & Event History)</h4>
                    <span className="badge badge-provider">
                      Iteration #{result.memory.iteration}
                    </span>
                  </div>
                  <div className="events-strip">
                    <strong>Event Log ({result.memory.events.length} events):</strong>
                    <ul className="events-list">
                      {result.memory.events.map((e, idx) => (
                        <li key={`ev-${idx}`} className="event-item">
                          <span className="ev-iter">[Iter {e.iteration}]</span>
                          <span className="ev-act">{e.action.toUpperCase()}:</span>
                          <span className="ev-det">{e.detail}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <pre className="json-block">{JSON.stringify(result.memory, null, 2)}</pre>
                </div>
              )}

              {/* Tab 4: 3D Scene Payload (Blender Contract) */}
              {activeTab === 'payload' && (
                <div className="json-card">
                  <div className="json-header">
                    <h4>Blender / bpy Construction Payload (Contract for Agent 3)</h4>
                    <span className="badge badge-provider">spatialmind.scene/v1</span>
                  </div>
                  <p className="payload-note">
                    This payload is the clean contract consumed by the Blender execution agent:
                    all transforms are in standard metres with base-footprint centres and Z-up rotations.
                  </p>
                  <pre className="json-block">{JSON.stringify(result.scene, null, 2)}</pre>
                </div>
              )}
            </div>
          ) : (
            /* Welcome / Onboarding Card when no generation has run yet */
            <div className="welcome-card">
              <div className="welcome-icon">🏢</div>
              <h2 className="welcome-title">Ready for Spatial Reasoning</h2>
              <p className="welcome-desc">
                Select one of the proposal presets on the left or type your own indoor room description.
                SpatialMind will extract structured constraints, compute collision-free layouts,
                verify all spatial relations, and iteratively refine any detected errors.
              </p>
              <div className="welcome-actions">
                <button
                  type="button"
                  className="preset-starter-btn"
                  onClick={() => handleGenerate(examples[0] || prompt)}
                >
                  Run Proposal Example Bedroom →
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
