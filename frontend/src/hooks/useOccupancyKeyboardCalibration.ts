import { useEffect, useRef } from "react";
import { adjustOccupancy } from "../lib/occupancyCalibration";

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

export function useOccupancyKeyboardCalibration(enabled: boolean): void {
  const pendingRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;

    async function handleKeyDown(event: KeyboardEvent) {
      if (
        event.repeat ||
        event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        isEditableTarget(event.target)
      ) {
        return;
      }

      const delta =
        event.key === "+" || event.key === "ArrowUp"
          ? 1
          : event.key === "-" || event.key === "ArrowDown"
            ? -1
            : null;
      if (delta === null) return;

      event.preventDefault();
      if (pendingRef.current) return;
      pendingRef.current = true;

      try {
        await adjustOccupancy(delta);
      } catch (error) {
        console.error("Occupancy keyboard calibration failed", error);
      } finally {
        pendingRef.current = false;
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled]);
}
