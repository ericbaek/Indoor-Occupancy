import type { OccupancyPoint, OccupancyRange, OccupancyStatus } from "../data";

export const OCCUPANCY_RANGE_MS: Record<OccupancyRange, number> = {
  "5m": 5 * 60 * 1000,
  "10m": 10 * 60 * 1000,
  "30m": 30 * 60 * 1000,
  "1H": 60 * 60 * 1000,
  "2H": 2 * 60 * 60 * 1000,
};

export const MAX_OCCUPANCY_HISTORY_MS = OCCUPANCY_RANGE_MS["2H"];

function parseTimestamp(value: string | number | null | undefined): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  if (typeof value !== "string" || value.trim() === "") return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Prefer a true API snapshot timestamp; otherwise use the local receipt time. */
export function resolveOccupancyTimestamp(
  reading: Pick<OccupancyStatus, "timestamp" | "received_at" | "reading_at">,
  receivedAt: number,
): number {
  for (const candidate of [reading.timestamp, reading.received_at, reading.reading_at]) {
    const timestamp = parseTimestamp(candidate);
    if (timestamp !== null) return timestamp;
  }

  return receivedAt;
}

/** Append one authoritative reading while deduplicating, ordering, and pruning to 2h. */
export function appendOccupancyPoint(
  history: OccupancyPoint[],
  point: OccupancyPoint,
  now: number = Date.now(),
): OccupancyPoint[] {
  const cutoff = now - MAX_OCCUPANCY_HISTORY_MS;
  const next = history.filter(
    (existing) =>
      Number.isFinite(existing.timestamp) &&
      Number.isFinite(existing.count) &&
      existing.timestamp >= cutoff &&
      existing.timestamp !== point.timestamp,
  );

  if (
    Number.isFinite(point.timestamp) &&
    Number.isFinite(point.count) &&
    point.timestamp >= cutoff
  ) {
    next.push(point);
  }

  return next.sort((a, b) => a.timestamp - b.timestamp);
}

export function filterOccupancyPoints(
  history: OccupancyPoint[],
  range: OccupancyRange,
  now: number = Date.now(),
): OccupancyPoint[] {
  const cutoff = now - OCCUPANCY_RANGE_MS[range];
  return history
    .filter((point) => point.timestamp >= cutoff)
    .sort((a, b) => a.timestamp - b.timestamp);
}
