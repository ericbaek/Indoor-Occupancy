import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

export type LiveMlPrediction = {
  id: number;
  window_start: string;
  window_end: string;
  forecast_time: string;
  created_at: string;
  source: string;
  prediction: {
    predicted_occupancy: number;
    prediction_interval: { lower: number; upper: number };
    confidence: number;
    predicted_ventilation: "OFF" | "LOW" | "MEDIUM" | "HIGH";
    overcrowding: {
      overcrowding_risk: boolean;
      risk_probability: number;
      room_capacity: number;
    };
    empty_room: {
      empty_probability_30m: number;
      empty_probability: number;
      predicted_empty_duration_minutes: number;
      safety_validated: boolean;
    };
    ble_activity_side: "LEFT" | "RIGHT" | "BALANCED" | "NO_SIGNAL";
    input_quality: {
      feature_count_expected: number;
      feature_count_received: number;
      missing_feature_count: number;
      warnings: string[];
    };
  };
  recommendation: {
    recommended_actions: string[];
    warnings: string[];
    automatic_actions_allowed: boolean;
    dry_run: boolean;
    hardware_commands_sent: boolean;
  };
};

type MlPredictionState = {
  data: LiveMlPrediction | null;
  loading: boolean;
  error: string | null;
};

export function useMlPrediction(pollMs: number): MlPredictionState {
  const [state, setState] = useState<MlPredictionState>({
    data: null,
    loading: true,
    error: null,
  });
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;

    async function fetchLatest() {
      try {
        const response = await fetch(`${API_BASE}/ml/predictions/latest`);
        if (cancelled.current) return;
        if (response.status === 404) {
          setState({ data: null, loading: false, error: null });
          return;
        }
        if (!response.ok) {
          throw new Error(`ml/predictions/latest: ${response.status}`);
        }
        const data: LiveMlPrediction = await response.json();
        if (!cancelled.current) {
          setState({ data, loading: false, error: null });
        }
      } catch (error) {
        if (!cancelled.current) {
          setState((previous) => ({
            ...previous,
            loading: false,
            error: error instanceof Error ? error.message : "Prediction unavailable",
          }));
        }
      }
    }

    fetchLatest();
    const timer = window.setInterval(fetchLatest, Math.max(pollMs, 5000));
    return () => {
      cancelled.current = true;
      window.clearInterval(timer);
    };
  }, [pollMs]);

  return state;
}
