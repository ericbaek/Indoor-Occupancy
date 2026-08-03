/// <reference types="node" />

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RadarTarget } from "../data";
import RadarScope from "./RadarScope";

const radarStyles = readFileSync(resolve(process.cwd(), "src/components/RadarScope.css"), "utf8");

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const targets: RadarTarget[] = [
  { id: 1, angle: -20, distance: 2_000, speed: 4.2 },
  { id: 2, angle: 0, distance: 3_000, speed: -1.5 },
  { id: 3, angle: 25, distance: 4_000, speed: 0.8 },
];

describe("RadarScope", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders no target marker without backend target data", () => {
    const { container } = render(<RadarScope targets={[]} />);

    expect(screen.getByText("scanning")).toBeTruthy();
    expect(screen.getByText("NO TARGET DATA")).toBeTruthy();
    expect(container.querySelectorAll(".radar-blip")).toHaveLength(0);
    expect(container.querySelectorAll(".radar-blip-halo")).toHaveLength(0);
    expect(container.querySelector(".radar-sweep-group")).toBeTruthy();
  });

  it("keeps T1, T2 and T3 positions fixed until backend coordinates change", () => {
    const { container, rerender } = render(<RadarScope targets={targets} />);
    const coordinatesBefore = [...container.querySelectorAll(".radar-blip")].map((dot) => [
      dot.getAttribute("cx"),
      dot.getAttribute("cy"),
    ]);

    expect(container.querySelectorAll(".radar-blip")).toHaveLength(3);
    expect(container.querySelectorAll(".radar-blip-halo")).toHaveLength(3);
    expect(screen.getByText("T1")).toBeTruthy();
    expect(screen.getByText("T2")).toBeTruthy();
    expect(screen.getByText("T3")).toBeTruthy();

    rerender(
      <RadarScope
        targets={targets.map((target) => ({ ...target, speed: 0 }))}
      />,
    );

    const coordinatesAfter = [...container.querySelectorAll(".radar-blip")].map((dot) => [
      dot.getAttribute("cx"),
      dot.getAttribute("cy"),
    ]);
    expect(coordinatesAfter).toEqual(coordinatesBefore);
  });

  it("uses a radar-specific opacity pulse so another component cannot move the halo", () => {
    expect(radarStyles).toContain("animation: radar-pulse 1.4s ease-in-out infinite");
    expect(radarStyles).toContain("@keyframes radar-pulse");
    expect(radarStyles).not.toContain("animation: pulse");
  });
});
