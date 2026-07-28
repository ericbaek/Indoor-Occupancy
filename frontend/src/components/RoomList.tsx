import type { RoomState } from "../data";
import "./RoomList.css";

const LEVEL_LABEL: Record<RoomState["level"], string> = {
  safe: "Safe",
  "near-limit": "Near limit",
  over: "Overcapacity",
};

export default function RoomList({ rooms }: { rooms: RoomState[] }) {
  return (
    <div className="room-card">
      <div className="room-head">
        <div className="chart-title">Occupancy by room</div>
        <button className="link-btn">View all &rarr;</button>
      </div>
      <div className="room-rows">
        {rooms.map((r) => {
          const pct = Math.min(100, (r.occupancy / r.capacity) * 100);
          return (
            <div key={r.room} className="room-row">
              <span className={`room-pill room-pill-${r.level}`}>{r.room}</span>
              <span className="room-count">
                {r.occupancy}/{r.capacity}
              </span>
              <div className="room-bar-track">
                <div className={`room-bar-fill room-bar-${r.level}`} style={{ width: `${pct}%` }} />
              </div>
              <span className={`room-status room-status-${r.level}`}>{LEVEL_LABEL[r.level]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
