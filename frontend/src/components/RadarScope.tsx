import { useLayoutEffect, useRef, useState } from "react";
import type { RadarTarget } from "../data";
import "./RadarScope.css";

const MAX_RANGE_MM = 8_000; // RD-03D specified maximum sensing distance.
const MAX_TARGETS = 3;
const FOV_HALF_ANGLE = 70;
const SWEEP_HALF_ANGLE = 22;
const TOP_INSET = 12;
const SIDE_INSET = 12;
const ORIGIN_BOTTOM_INSET = 4;
const FALLBACK_SIZE = { width: 320, height: 220 };

const DOT_RANGE_SCALE = 2;

type RadarGeometry = {
  width: number;
  height: number;
  cx: number;
  cy: number;
  radius: number;
};

function getRadarGeometry(width: number, height: number): RadarGeometry {
  const cx = width / 2;
  const cy = height - ORIGIN_BOTTOM_INSET;
  const halfFovRad = (FOV_HALF_ANGLE * Math.PI) / 180;

  // Grow until the fan reaches either the top inset or both side insets.
  const radiusFromHeight = Math.max(0, cy - TOP_INSET);
  const radiusFromWidth = Math.max(0, (cx - SIDE_INSET) / Math.sin(halfFovRad));

  return {
    width,
    height,
    cx,
    cy,
    radius: Math.min(radiusFromHeight, radiusFromWidth),
  };
}

function toXY(
  angleDeg: number,
  distance: number,
  { cx, cy, radius }: RadarGeometry,
) {
  // RD-03D reports 0deg straight ahead, with positive angles to the right.
  const angleRad = (angleDeg * Math.PI) / 180;
  const rawNormalized = Math.min(Math.max(distance / MAX_RANGE_MM, 0), 1);
  const normalizedDistance = Math.min(rawNormalized * DOT_RANGE_SCALE, 1);
  const targetRadius = radius * normalizedDistance;

  return {
    x: cx + targetRadius * Math.sin(angleRad),
    y: cy - targetRadius * Math.cos(angleRad),
  };
}

function polarPoint(angleDeg: number, radius: number, cx: number, cy: number) {
  const angleRad = (angleDeg * Math.PI) / 180;
  return {
    x: cx + radius * Math.sin(angleRad),
    y: cy - radius * Math.cos(angleRad),
  };
}

function arcPath(radius: number, cx: number, cy: number) {
  const start = polarPoint(-FOV_HALF_ANGLE, radius, cx, cy);
  const end = polarPoint(FOV_HALF_ANGLE, radius, cx, cy);
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 0 1 ${end.x} ${end.y}`;
}

function sweepPath(radius: number, cx: number, cy: number) {
  const start = polarPoint(-SWEEP_HALF_ANGLE, radius, cx, cy);
  const end = polarPoint(SWEEP_HALF_ANGLE, radius, cx, cy);
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 0 1 ${end.x} ${end.y} Z`;
}

export default function RadarScope({ targets }: { targets: RadarTarget[] }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [scopeSize, setScopeSize] = useState(FALLBACK_SIZE);

  useLayoutEffect(() => {
    const body = bodyRef.current;
    if (!body) return;

    const updateSize = (width: number, height: number) => {
      if (width <= 0 || height <= 0) return;

      setScopeSize((previous) => {
        if (previous.width === width && previous.height === height) return previous;
        return { width, height };
      });
    };

    const initialRect = body.getBoundingClientRect();
    updateSize(initialRect.width, initialRect.height);

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      updateSize(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(body);
    return () => observer.disconnect();
  }, []);

  const geometry = getRadarGeometry(scopeSize.width, scopeSize.height);
  const { width, height, cx, cy, radius } = geometry;
  const visibleTargets = targets
    .filter(
      (target) =>
        Number.isFinite(target.angle) &&
        Number.isFinite(target.distance) &&
        Number.isFinite(target.speed) &&
        target.distance > 0,
    )
    .slice(0, MAX_TARGETS);

  return (
    <div className="radar-panel">
      <div className="radar-panel-head">
        <div>
          <div className="radar-title">mmWave scope</div>
          <div className="radar-sub">RD-03D &middot; up to 3 simultaneous targets</div>
        </div>
        <div
          className={`radar-live ${visibleTargets.length > 0 ? "is-tracking" : "is-scanning"}`}
          aria-live="polite"
        >
          <span className="radar-live-dot" />
          {visibleTargets.length > 0 ? "tracking" : "scanning"}
        </div>
      </div>

      <div className="radar-body" ref={bodyRef}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="radar-svg"
          role="img"
          aria-label="mmWave radar scope"
        >
          {[1, 2, 3, 4, 5].map((i) => (
            <path
              key={i}
              d={arcPath((radius / 5) * i, cx, cy)}
              className="radar-ring"
            />
          ))}
          {[-70, -55, -40, -25, -10, 0, 10, 25, 40, 55, 70].map((angle) => {
            const point = polarPoint(angle, radius, cx, cy);
            return (
              <line
                key={angle}
                x1={cx}
                y1={cy}
                x2={point.x}
                y2={point.y}
                className="radar-cross"
              />
            );
          })}

          <g
            className="radar-sweep-group"
            style={{ transformOrigin: `${cx}px ${cy}px` }}
          >
            <path d={sweepPath(radius, cx, cy)} className="radar-sweep" />
          </g>

          {visibleTargets.map((t, index) => {
            const { x, y } = toXY(t.angle, t.distance, geometry);
            return (
              <g key={`${t.id}-${index}`}>
                <circle cx={x} cy={y} r={9} className="radar-blip-halo" />
                <circle cx={x} cy={y} r={4} className="radar-blip" />
              </g>
            );
          })}
        </svg>
      </div>

      <div className="radar-readout" aria-label="Live radar target telemetry">
        {visibleTargets.length > 0 ? (
          visibleTargets.map((target, index) => (
            <div key={`${target.id}-${index}`} className="radar-readout-row is-live">
              <span className="radar-readout-id">T{target.id}</span>
              <span className="radar-readout-field">
                <span className="radar-readout-k">ANGLE</span>
                {target.angle.toFixed(1)}&deg;
              </span>
              <span className="radar-readout-field">
                <span className="radar-readout-k">DIST</span>
                {target.distance.toFixed(0)}mm
              </span>
              <span className="radar-readout-field">
                <span className="radar-readout-k">SPD</span>
                {target.speed.toFixed(1)}
              </span>
            </div>
          ))
        ) : (
          <div className="radar-readout-empty">NO TARGET DATA</div>
        )}
      </div>
    </div>
  );
}