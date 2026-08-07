import type { ReactNode } from "react";
import { Moon, Sun, Ruler, RefreshCw, Wind } from "lucide-react";
import type { Preferences, Theme, Units } from "../hooks/usePreferences";
import { POLL_RATE_OPTIONS } from "../hooks/usePreferences";
import "./Settings.css";

/**
 * Settings page — deliberately scoped to preferences that are fully
 * functional today with no backend changes:
 *   - theme (was previously a Topbar toggle, moved here)
 *   - units (metric/imperial — affects temperature + BLE distance display)
 *   - dashboard poll rate (actually feeds useOccupancyData's interval)
 *   - CO2 chart reference line (client-side display only)
 *
 * Deliberately NOT here: per-room capacity limits, PIR/mmWave thresholds,
 * BLE zone boundaries, account/notification prefs — those either need new
 * backend endpoints (capacity, thresholds, zones are hardcoded server-side
 * today) or would just be mock, and this page only holds settings that
 * really do something when you change them.
 */
export default function Settings({
  preferences,
  onUpdate,
}: {
  preferences: Preferences;
  onUpdate: <K extends keyof Preferences>(key: K, value: Preferences[K]) => void;
}) {
  return (
    <div className="settings-page">
      <div className="settings-section">
        <div className="settings-section-info">
          <div className="settings-section-title">Appearance</div>
          <div className="settings-section-sub">Light or dark theme for the whole dashboard.</div>
        </div>
        <div className="settings-control">
          <div className="segmented">
            <SegmentedButton
              active={preferences.theme === "light"}
              onClick={() => onUpdate("theme", "light" as Theme)}
              icon={<Sun size={13} strokeWidth={2.25} />}
              label="Light"
            />
            <SegmentedButton
              active={preferences.theme === "dark"}
              onClick={() => onUpdate("theme", "dark" as Theme)}
              icon={<Moon size={13} strokeWidth={2.25} />}
              label="Dark"
            />
          </div>
        </div>
      </div>

      <div className="settings-section">
        <div className="settings-section-info">
          <div className="settings-section-title">Units</div>
          <div className="settings-section-sub">
            Temperature (&deg;C / &deg;F) and BLE tag distance (metres / feet) across the dashboard.
          </div>
        </div>
        <div className="settings-control">
          <div className="segmented">
            <SegmentedButton
              active={preferences.units === "metric"}
              onClick={() => onUpdate("units", "metric" as Units)}
              icon={<Ruler size={13} strokeWidth={2.25} />}
              label="Metric"
            />
            <SegmentedButton
              active={preferences.units === "imperial"}
              onClick={() => onUpdate("units", "imperial" as Units)}
              icon={<Ruler size={13} strokeWidth={2.25} />}
              label="Imperial"
            />
          </div>
        </div>
      </div>

      <div className="settings-section">
        <div className="settings-section-info">
          <div className="settings-section-title">Data refresh rate</div>
          <div className="settings-section-sub">
            How often the dashboard polls the backend for new readings. Lower = more live, more requests.
          </div>
        </div>
        <div className="settings-control">
          <div className="segmented">
            {POLL_RATE_OPTIONS.map((ms) => (
              <SegmentedButton
                key={ms}
                active={preferences.pollMs === ms}
                onClick={() => onUpdate("pollMs", ms)}
                label={`${ms / 1000}s`}
                icon={<RefreshCw size={13} strokeWidth={2.25} />}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="settings-section">
        <div className="settings-section-info">
          <div className="settings-section-title">CO2 chart reference line</div>
          <div className="settings-section-sub">
            <Wind size={12} strokeWidth={2.25} style={{ verticalAlign: "-2px", marginRight: 4 }} />
            Sets the dashed threshold shown on the CO2 trend chart. This is a display preference only &mdash; the
            backend's actual normal / elevated / high classification on the CO2 stat card is unaffected.
          </div>
        </div>
        <div className="settings-control">
          <input
            className="settings-number-input"
            type="number"
            min={200}
            max={5000}
            step={50}
            value={preferences.co2AlertThreshold}
            onChange={(e) => {
              const value = Number(e.target.value);
              if (!Number.isNaN(value)) onUpdate("co2AlertThreshold", value);
            }}
          />
          <span className="settings-unit-suffix">ppm</span>
        </div>
      </div>
    </div>
  );
}

function SegmentedButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      className={`segmented-option${active ? " is-active" : ""}`}
      onClick={onClick}
      aria-pressed={active}
    >
      {icon}
      {label}
    </button>
  );
}