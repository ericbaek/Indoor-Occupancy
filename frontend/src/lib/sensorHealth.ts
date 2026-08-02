/**
 * Shared "is this device actually sending data right now" check.
 *
 * A device counts as online if its last reading arrived within
 * `staleAfterMs` of now; otherwise offline. Thresholds are set per sensor
 * type in Sensors.tsx based on how that sensor actually reports:
 *   - radar / CO2: continuous polling, so a short window (~15-30s) means
 *     "genuinely offline" rather than just a slow network tick.
 *   - PIR: event-driven (only reports on entry/exit), so a short window
 *     would flag it "offline" any time nobody's walked through the door
 *     for a minute \u2014 misleading. Uses a much longer window instead.
 */
export function isRecentlySeen(receivedAtIso: string | null | undefined, staleAfterMs: number): boolean {
  if (!receivedAtIso) return false;
  const receivedAt = new Date(receivedAtIso).getTime();
  if (Number.isNaN(receivedAt)) return false;
  return Date.now() - receivedAt <= staleAfterMs;
}

export function timeAgoLabel(receivedAtIso: string | null | undefined): string {
  if (!receivedAtIso) return "Never";
  const receivedAt = new Date(receivedAtIso).getTime();
  if (Number.isNaN(receivedAt)) return "Never";
  const diffSec = Math.max(0, Math.round((Date.now() - receivedAt) / 1000));
  if (diffSec < 5) return "Just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  return `${diffHr}h ago`;
}