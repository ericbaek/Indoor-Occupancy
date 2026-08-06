import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

// Health barely changes — poll far less often than the 1s occupancy loop.
const POLL_MS = 5000;

export type HealthState = {
  status: "ok" | "error" | "checking";
  database: string | null;
  error: string | null;
};

const initialState: HealthState = {
  status: "checking",
  database: null,
  error: null,
};

/** Polls GET /api/health for a lightweight backend/database connectivity signal. */
export function useHealthCheck(): HealthState {
  const [state, setState] = useState<HealthState>(initialState);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function check() {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) throw new Error(`health: ${res.status}`);
        const json: { status?: string; database?: string } = await res.json();
        if (cancelledRef.current) return;
        setState({
          status: json.status === "ok" ? "ok" : "error",
          database: json.database ?? null,
          error: null,
        });
      } catch (err) {
        if (cancelledRef.current) return;
        setState({
          status: "error",
          database: null,
          error: err instanceof Error ? err.message : "Health check failed",
        });
      }
    }

    check();
    const id = setInterval(check, POLL_MS);
    return () => {
      cancelledRef.current = true;
      clearInterval(id);
    };
  }, []);

  return state;
}