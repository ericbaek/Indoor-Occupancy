const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

export const OCCUPANCY_REFRESH_EVENT = "occupancy:refresh";

export async function adjustOccupancy(delta: 1 | -1): Promise<void> {
  const response = await fetch(`${API_BASE}/occupancy/calibrate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ delta }),
  });

  if (!response.ok) {
    throw new Error(`occupancy/calibrate: ${response.status}`);
  }

  window.dispatchEvent(new Event(OCCUPANCY_REFRESH_EVENT));
}
