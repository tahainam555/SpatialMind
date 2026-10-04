import React, { useState } from 'react';
import type { PlacedObject, Room, Violation } from '../types';

interface SceneViewerProps {
  room: Room;
  objects: PlacedObject[];
  violations?: Violation[];
}

const CATEGORY_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  bed: { fill: 'rgba(99, 102, 241, 0.25)', stroke: '#818cf8', label: '🛏️ Bed' },
  nightstand: { fill: 'rgba(168, 85, 247, 0.25)', stroke: '#c084fc', label: '🪵 Nightstand' },
  desk: { fill: 'rgba(16, 185, 129, 0.25)', stroke: '#34d399', label: '🖥️ Desk' },
  chair: { fill: 'rgba(245, 158, 11, 0.25)', stroke: '#fbbf24', label: '🪑 Chair' },
  wardrobe: { fill: 'rgba(139, 92, 246, 0.25)', stroke: '#a78bfa', label: '🚪 Wardrobe' },
  dresser: { fill: 'rgba(236, 72, 153, 0.25)', stroke: '#f472b6', label: '🗄️ Dresser' },
  bookshelf: { fill: 'rgba(20, 184, 166, 0.25)', stroke: '#2dd4bf', label: '📚 Bookshelf' },
  sofa: { fill: 'rgba(56, 189, 248, 0.25)', stroke: '#38bdf8', label: '🛋️ Sofa' },
  armchair: { fill: 'rgba(14, 165, 233, 0.25)', stroke: '#0284c7', label: '🪑 Armchair' },
  coffee_table: { fill: 'rgba(217, 119, 6, 0.25)', stroke: '#f59e0b', label: '☕ Coffee Table' },
  tv_stand: { fill: 'rgba(244, 63, 94, 0.25)', stroke: '#fb7185', label: '📺 TV Stand' },
  filing_cabinet: { fill: 'rgba(100, 116, 139, 0.25)', stroke: '#94a3b8', label: '📁 Filing Cab' },
};

export const SceneViewer: React.FC<SceneViewerProps> = ({ room, objects, violations = [] }) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showClearance, setShowClearance] = useState<boolean>(true);

  // SVG coordinate transformation:
  // Math coordinates: (0,0) is South-West corner; x grows East (right), y grows North (up).
  // SVG coordinates: (0,0) is Top-Left; x grows right, y grows DOWN.
  // We flip y: svg_y = (room.depth - y) * scale.
  const padding = 50;
  const targetSvgWidth = 600;
  const targetSvgHeight = 520;

  const scaleX = (targetSvgWidth - padding * 2) / room.width;
  const scaleY = (targetSvgHeight - padding * 2) / room.depth;
  const scale = Math.min(scaleX, scaleY);

  const roomSvgW = room.width * scale;
  const roomSvgH = room.depth * scale;
  const offsetX = (targetSvgWidth - roomSvgW) / 2;
  const offsetY = (targetSvgHeight - roomSvgH) / 2;

  const toSvgX = (x: number) => offsetX + x * scale;
  const toSvgY = (y: number) => offsetY + (room.depth - y) * scale;

  // Set of violating object IDs
  const violatingIds = new Set<string>();
  violations.forEach((v) => {
    v.objects.forEach((id) => violatingIds.add(id));
  });

  return (
    <div className="scene-viewer-card">
      <div className="scene-viewer-header">
        <div className="scene-title-group">
          <span className="live-dot" />
          <h3 className="scene-title">2D Top-Down Spatial Layout</h3>
          <span className="room-dim-pill">
            {room.width.toFixed(1)}m × {room.depth.toFixed(1)}m ({room.height.toFixed(1)}m H)
          </span>
        </div>
        <div className="scene-controls">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={showClearance}
              onChange={(e) => setShowClearance(e.target.checked)}
            />
            Show Clearance Zones
          </label>
        </div>
      </div>

      <div className="canvas-wrapper">
        <svg
          viewBox={`0 0 ${targetSvgWidth} ${targetSvgHeight}`}
          className="room-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Grid background */}
            <pattern id="grid-pattern" width={scale * 0.5} height={scale * 0.5} patternUnits="userSpaceOnUse">
              <path
                d={`M ${scale * 0.5} 0 L 0 0 0 ${scale * 0.5}`}
                fill="none"
                stroke="rgba(255, 255, 255, 0.04)"
                strokeWidth="1"
              />
            </pattern>
            {/* 1m Major Grid pattern */}
            <pattern id="major-grid" width={scale} height={scale} patternUnits="userSpaceOnUse">
              <path
                d={`M ${scale} 0 L 0 0 0 ${scale}`}
                fill="none"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth="1.2"
              />
            </pattern>
            {/* Front facing arrow marker */}
            <marker
              id="arrow-front"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
            </marker>
          </defs>

          {/* Canvas background */}
          <rect width={targetSvgWidth} height={targetSvgHeight} fill="#0d1117" />

          {/* Room Interior */}
          <g>
            <rect
              x={offsetX}
              y={offsetY}
              width={roomSvgW}
              height={roomSvgH}
              fill="#161b22"
              stroke="#30363d"
              strokeWidth="2"
            />
            <rect
              x={offsetX}
              y={offsetY}
              width={roomSvgW}
              height={roomSvgH}
              fill="url(#grid-pattern)"
            />
            <rect
              x={offsetX}
              y={offsetY}
              width={roomSvgW}
              height={roomSvgH}
              fill="url(#major-grid)"
            />
          </g>

          {/* Wall Cardinal Labels */}
          <text x={offsetX + roomSvgW / 2} y={offsetY - 12} className="cardinal-label" textAnchor="middle">
            NORTH (Window Wall)
          </text>
          <text x={offsetX + roomSvgW / 2} y={offsetY + roomSvgH + 24} className="cardinal-label" textAnchor="middle">
            SOUTH (Entrance)
          </text>
          <text
            x={offsetX - 14}
            y={offsetY + roomSvgH / 2}
            className="cardinal-label"
            textAnchor="middle"
            transform={`rotate(-90 ${offsetX - 14} ${offsetY + roomSvgH / 2})`}
          >
            WEST
          </text>
          <text
            x={offsetX + roomSvgW + 16}
            y={offsetY + roomSvgH / 2}
            className="cardinal-label"
            textAnchor="middle"
            transform={`rotate(90 ${offsetX + roomSvgW + 16} ${offsetY + roomSvgH / 2})`}
          >
            EAST
          </text>

          {/* Openings (Doors & Windows) */}
          {room.openings.map((op, idx) => {
            const halfW = op.width / 2;
            let x1 = 0, y1 = 0, x2 = 0, y2 = 0;
            let swingPath = '';

            if (op.wall === 'north') {
              x1 = toSvgX(op.offset - halfW);
              x2 = toSvgX(op.offset + halfW);
              y1 = y2 = offsetY;
              if (op.kind === 'door') {
                const reach = op.width * scale;
                swingPath = `M ${x1} ${y1} A ${reach} ${reach} 0 0 0 ${x1} ${y1 + reach}`;
              }
            } else if (op.wall === 'south') {
              x1 = toSvgX(op.offset - halfW);
              x2 = toSvgX(op.offset + halfW);
              y1 = y2 = offsetY + roomSvgH;
              if (op.kind === 'door') {
                const reach = op.width * scale;
                swingPath = `M ${x1} ${y1} A ${reach} ${reach} 0 0 1 ${x1} ${y1 - reach}`;
              }
            } else if (op.wall === 'east') {
              x1 = x2 = offsetX + roomSvgW;
              y1 = toSvgY(op.offset - halfW);
              y2 = toSvgY(op.offset + halfW);
            } else if (op.wall === 'west') {
              x1 = x2 = offsetX;
              y1 = toSvgY(op.offset - halfW);
              y2 = toSvgY(op.offset + halfW);
            }

            const isWindow = op.kind === 'window';

            return (
              <g key={`opening-${idx}`}>
                {/* Door swing arc if door */}
                {swingPath && (
                  <path
                    d={swingPath}
                    fill="none"
                    stroke="rgba(245, 158, 11, 0.4)"
                    strokeWidth="1.5"
                    strokeDasharray="4 3"
                  />
                )}
                {/* Wall cut opening indicator */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={isWindow ? '#38bdf8' : '#f59e0b'}
                  strokeWidth="6"
                  strokeLinecap="round"
                />
                <text
                  x={(x1 + x2) / 2}
                  y={(y1 + y2) / 2 + (op.wall === 'north' ? -8 : 16)}
                  className="opening-tag"
                  textAnchor="middle"
                  fill={isWindow ? '#38bdf8' : '#f59e0b'}
                >
                  {isWindow ? `🪟 Window (${op.width.toFixed(1)}m)` : `🚪 Door (${op.width.toFixed(1)}m)`}
                </text>
              </g>
            );
          })}

          {/* Placed Objects */}
          {objects.map((obj) => {
            const isHovered = hoveredId === obj.id;
            const isViolating = violatingIds.has(obj.id);
            const styleInfo = CATEGORY_COLORS[obj.category] || {
              fill: 'rgba(148, 163, 184, 0.25)',
              stroke: '#94a3b8',
              label: obj.category,
            };

            // Calculate unrotated footprint dimensions
            // Rotation is in degrees CCW: 0: width on x, depth on y.
            // 90: width on y, depth on x.
            const isRotatedQuarter = obj.rotation === 90 || obj.rotation === 270;
            const effectiveW = (isRotatedQuarter ? obj.depth : obj.width) * scale;
            const effectiveH = (isRotatedQuarter ? obj.width : obj.depth) * scale;

            const cx = toSvgX(obj.x);
            const cy = toSvgY(obj.y);
            const topLeftX = cx - effectiveW / 2;
            const topLeftY = cy - effectiveH / 2;

            // Front direction arrow vector:
            // rotation 0: front is South (-y math, +y SVG)
            // rotation 90: front is East (+x math, +x SVG)
            // rotation 180: front is North (+y math, -y SVG)
            // rotation 270: front is West (-x math, -x SVG)
            let arrowDx = 0;
            let arrowDy = 0;
            if (obj.rotation === 0) arrowDy = effectiveH / 2 + 14;
            else if (obj.rotation === 90) arrowDx = effectiveW / 2 + 14;
            else if (obj.rotation === 180) arrowDy = -(effectiveH / 2 + 14);
            else if (obj.rotation === 270) arrowDx = -(effectiveW / 2 + 14);

            return (
              <g
                key={obj.id}
                onMouseEnter={() => setHoveredId(obj.id)}
                onMouseLeave={() => setHoveredId(null)}
                className="furniture-group"
                style={{ cursor: 'pointer' }}
              >
                {/* Front clearance preview on hover or toggle */}
                {showClearance && isHovered && (
                  <rect
                    x={
                      obj.rotation === 90
                        ? cx + effectiveW / 2
                        : obj.rotation === 270
                        ? cx - effectiveW / 2 - 0.6 * scale
                        : topLeftX
                    }
                    y={
                      obj.rotation === 0
                        ? cy + effectiveH / 2
                        : obj.rotation === 180
                        ? cy - effectiveH / 2 - 0.6 * scale
                        : topLeftY
                    }
                    width={isRotatedQuarter ? 0.6 * scale : effectiveW}
                    height={isRotatedQuarter ? effectiveH : 0.6 * scale}
                    fill="rgba(56, 189, 248, 0.12)"
                    stroke="rgba(56, 189, 248, 0.4)"
                    strokeDasharray="3 3"
                    rx="3"
                  />
                )}

                {/* Furniture Box */}
                <rect
                  x={topLeftX}
                  y={topLeftY}
                  width={effectiveW}
                  height={effectiveH}
                  fill={isViolating ? 'rgba(239, 68, 68, 0.35)' : styleInfo.fill}
                  stroke={isViolating ? '#ef4444' : isHovered ? '#60a5fa' : styleInfo.stroke}
                  strokeWidth={isViolating || isHovered ? 2.5 : 1.5}
                  rx="4"
                  className="furniture-box"
                />

                {/* Front Direction Indicator */}
                <line
                  x1={cx}
                  y1={cy}
                  x2={cx + arrowDx * 0.75}
                  y2={cy + arrowDy * 0.75}
                  stroke={isViolating ? '#ef4444' : '#38bdf8'}
                  strokeWidth="2"
                  markerEnd="url(#arrow-front)"
                />

                {/* Label inside box */}
                <text
                  x={cx}
                  y={cy}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="furniture-label"
                  fill="#f1f5f9"
                >
                  {obj.category.replace('_', ' ')}
                </text>

                {/* Sub-label with dimensions */}
                {effectiveH > 35 && (
                  <text
                    x={cx}
                    y={cy + 13}
                    textAnchor="middle"
                    className="furniture-sublabel"
                    fill="rgba(255, 255, 255, 0.55)"
                  >
                    {obj.width.toFixed(1)}×{obj.depth.toFixed(1)}m
                  </text>
                )}
              </g>
            );
          })}

          {/* Scale Legend */}
          <g transform={`translate(${targetSvgWidth - 110}, ${targetSvgHeight - 24})`}>
            <line x1="0" y1="0" x2={scale} y2="0" stroke="#94a3b8" strokeWidth="2.5" />
            <line x1="0" y1="-4" x2="0" y2="4" stroke="#94a3b8" strokeWidth="1.5" />
            <line x1={scale} y1="-4" x2={scale} y2="4" stroke="#94a3b8" strokeWidth="1.5" />
            <text x={scale / 2} y="-6" textAnchor="middle" fill="#94a3b8" fontSize="10">
              1.0 metre
            </text>
          </g>
        </svg>
      </div>

      {/* Selected Object Detail Strip */}
      {hoveredId && (() => {
        const obj = objects.find((o) => o.id === hoveredId);
        if (!obj) return null;
        return (
          <div className="hover-inspector">
            <span className="inspector-id">📦 {obj.id}</span>
            <span className="inspector-badge">Pos: ({obj.x.toFixed(2)}m, {obj.y.toFixed(2)}m)</span>
            <span className="inspector-badge">Dim: {obj.width}m W × {obj.depth}m D × {obj.height}m H</span>
            <span className="inspector-badge">Rot: {obj.rotation}° CCW</span>
          </div>
        );
      })()}
    </div>
  );
};
