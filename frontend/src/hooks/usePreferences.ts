import { useEffect, useState } from "react";

/**
 * App-wide user preferences — all genuinely functional, frontend-only
 * settings (no backend dependency). Persisted to localStorage so they
 * survive a refresh.
 *
 * Deliberately excludes anything that would need backend support to
 * actually do something (per-room capacity limits, PIR/mmWave sensor
 * thresholds, BLE zone boundaries) — those are still hardcoded server-side
 * in ble_config.py / routes.py and aren't exposed via any API yet.
 */
export type Theme = "light" | "dark";
export type Units = "metric" | "imperial";

export type Preferences = {
  theme: Theme;
  /** metric = \u00b0C + metres, imperial = \u00b0F + feet */
  units: Units;
  /** How often the dashboard polls the backend, in ms. */
  pollMs: number;
  /**
   * Client-side-only CO2 reference line (ppm), shown as the dashed
   * threshold on the CO2 trend chart. Does NOT change the backend's
   * actual normal/elevated/high classification (_co2_level() in
   * routes.py) — that stays the source of truth for the StatCard tone.
   * This just lets the viewer pick what "elevated" means to *them*
   * visually on the chart.
   */
  co2AlertThreshold: number;
};

export const POLL_RATE_OPTIONS = [1000, 2000, 5000, 10000] as const;

const DEFAULT_PREFERENCES: Preferences = {
  theme: "light",
  units: "metric",
  pollMs: 1000,
  co2AlertThreshold: 800,
};

const STORAGE_KEY = "indoor-occupancy-preferences";

function loadPreferences(): Preferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_PREFERENCES, ...parsed };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function usePreferences() {
  const [preferences, setPreferences] = useState<Preferences>(loadPreferences);

  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      // Preferences still apply for this session even if storage is unavailable.
    }
  }, [preferences]);

  function update<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    setPreferences((prev) => ({ ...prev, [key]: value }));
  }

  return { preferences, update };
}

// ---------------------------------------------------------------------------
// Unit conversion helpers
// ---------------------------------------------------------------------------

export function formatTemperature(celsius: number, units: Units): string {
  if (units === "imperial") {
    return `${(celsius * 9 / 5 + 32).toFixed(1)}\u00b0F`;
  }
  return `${celsius.toFixed(1)}\u00b0C`;
}

export function formatDistanceMetres(metres: number, units: Units): string {
  if (units === "imperial") {
    return `${(metres * 3.28084).toFixed(1)}ft`;
  }
  return `${metres.toFixed(1)}m`;
}
