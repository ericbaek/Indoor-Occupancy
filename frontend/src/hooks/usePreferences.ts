import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
export type Units = "metric" | "imperial";

export type Preferences = {
  theme: Theme;
  units: Units;
  pollMs: number;
  co2AlertThreshold: number;
};

export const POLL_RATE_OPTIONS = [500, 1000, 3000, 5000] as const;

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
