import { cleanup, fireEvent, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OCCUPANCY_REFRESH_EVENT } from "../lib/occupancyCalibration";
import { useOccupancyKeyboardCalibration } from "./useOccupancyKeyboardCalibration";

function successfulResponse(): Response {
  return { ok: true, status: 200 } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useOccupancyKeyboardCalibration", () => {
  it("increases occupancy and requests an immediate refresh", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse());
    const refreshHandler = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    window.addEventListener(OCCUPANCY_REFRESH_EVENT, refreshHandler);
    renderHook(() => useOccupancyKeyboardCalibration(true));

    fireEvent.keyDown(window, { key: "+" });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:5000/api/occupancy/calibrate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ delta: 1 }),
      }),
    );
    await waitFor(() => expect(refreshHandler).toHaveBeenCalledOnce());
    window.removeEventListener(OCCUPANCY_REFRESH_EVENT, refreshHandler);
  });

  it("decreases occupancy with the down arrow", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderHook(() => useOccupancyKeyboardCalibration(true));

    fireEvent.keyDown(window, { key: "ArrowDown" });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ body: JSON.stringify({ delta: -1 }) }),
    );
  });

  it("does not run while typing or outside the Dashboard", () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse());
    vi.stubGlobal("fetch", fetchMock);
    const input = document.createElement("input");
    document.body.appendChild(input);
    const { rerender } = renderHook(
      ({ enabled }) => useOccupancyKeyboardCalibration(enabled),
      { initialProps: { enabled: true } },
    );

    fireEvent.keyDown(input, { key: "+" });
    rerender({ enabled: false });
    fireEvent.keyDown(window, { key: "+" });

    expect(fetchMock).not.toHaveBeenCalled();
    input.remove();
  });
});
