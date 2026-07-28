import type { RadarTarget } from "../data";
import "./RadarScope.css";

const SIZE = 200;
const CENTER = SIZE / 2;
const MAX_RANGE = 600; // mm-ish scale for the RD-03D field of view

function toXY(angleDeg: number, distance: number) {
  // RD-03D reports angle relative to boresight; 0deg = straight ahead (up).
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  const r = (Math.min(distance, MAX_RANGE) / MAX_RANGE) * (CENTER - 14);
  return {
    x: CENTER + r * Math.cos(rad),
    y: CENTER + r * Math.sin(rad),
  };
}

export default function RadarScope({ targets }: { targets: RadarTarget[] }) {
  const live = targets.filter((t) => t.distance > 0);

  return (
    <div className="radar-panel">
      <div className="radar-panel-head">
        <div>
          <div className="radar-title">mmWave scope</div>
          <div className="radar-sub">RD-03D &middot; up to 3 simultaneous targets</div>
        </div>
        <div className="radar-live">
          <span className="radar-live-dot" />
          tracking
        </div>
      </div>

      <div className="radar-body">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="radar-svg" role="img" aria-label="mmWave radar scope">
          {[1, 2, 3].map((i) => (
            <circle
              key={i}
              cx={CENTER}
              cy={CENTER}
              r={((CENTER - 14) / 3) * i}
              className="radar-ring"
            />
          ))}
          <line x1={CENTER} y1={14} x2={CENTER} y2={SIZE - 14} className="radar-cross" />
          <line x1={14} y1={CENTER} x2={SIZE - 14} y2={CENTER} className="radar-cross" />

          <g className="radar-sweep-group">
            <path
              d={`M ${CENTER} ${CENTER} L ${CENTER} 14 A ${CENTER - 14} ${CENTER - 14} 0 0 1 ${
                CENTER + (CENTER - 14) * Math.sin((40 * Math.PI) / 180)
              } ${CENTER - (CENTER - 14) * Math.cos((40 * Math.PI) / 180)} Z`}
              className="radar-sweep"
            />
          </g>

          {live.map((t) => {
            const { x, y } = toXY(t.angle, t.distance);
            return (
              <g key={t.id}>
                <circle cx={x} cy={y} r={9} className="radar-blip-halo" />
                <circle cx={x} cy={y} r={4} className="radar-blip" />
              </g>
            );
          })}
        </svg>
      </div>

      <div className="radar-readout">
        {targets.map((t) => (
          <div key={t.id} className={`radar-readout-row${t.distance > 0 ? " is-live" : ""}`}>
            <span className="radar-readout-id">T{t.id}</span>
            <span className="radar-readout-field">
              <span className="radar-readout-k">angle</span>
              {t.angle.toFixed(1)}&deg;
            </span>
            <span className="radar-readout-field">
              <span className="radar-readout-k">dist</span>
              {t.distance.toFixed(0)}mm
            </span>
            <span className="radar-readout-field">
              <span className="radar-readout-k">spd</span>
              {t.speed.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
