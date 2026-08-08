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