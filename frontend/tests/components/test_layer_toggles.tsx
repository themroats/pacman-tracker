/**
 * LayerToggles interaction tests.
 *
 * Tests:
 * - Renders all layer labels with correct colors
 * - Checkboxes reflect enabled state
 * - Clicking a toggle fires onToggle with the correct key
 * - Toggling off changes label style
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LayerToggles from "@/components/Map/LayerToggles";
import type { LayerToggle } from "@/components/Map/LayerToggles";

const sampleLayers: LayerToggle[] = [
  { key: "activities", label: "Activities", color: "#3b82f6", enabled: true },
  { key: "traveled", label: "Covered streets", color: "#22c55e", enabled: true },
  { key: "untraveled", label: "Missing streets", color: "#ef4444", enabled: false },
];

describe("LayerToggles", () => {
  it("renders all layer labels", () => {
    const onToggle = vi.fn();
    render(<LayerToggles layers={sampleLayers} onToggle={onToggle} />);

    expect(screen.getByText("Activities")).toBeDefined();
    expect(screen.getByText("Covered streets")).toBeDefined();
    expect(screen.getByText("Missing streets")).toBeDefined();
  });

  it("checkboxes reflect enabled state", () => {
    const onToggle = vi.fn();
    render(<LayerToggles layers={sampleLayers} onToggle={onToggle} />);

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
    expect(checkboxes[0]).toBeChecked();     // activities = true
    expect(checkboxes[1]).toBeChecked();     // traveled = true
    expect(checkboxes[2]).not.toBeChecked(); // untraveled = false
  });

  it("fires onToggle with correct key on click", () => {
    const onToggle = vi.fn();
    render(<LayerToggles layers={sampleLayers} onToggle={onToggle} />);

    const checkboxes = screen.getAllByRole("checkbox");

    fireEvent.click(checkboxes[0]);
    expect(onToggle).toHaveBeenCalledWith("activities");

    fireEvent.click(checkboxes[2]);
    expect(onToggle).toHaveBeenCalledWith("untraveled");

    expect(onToggle).toHaveBeenCalledTimes(2);
  });

  it("disabled layer label is dimmed", () => {
    const onToggle = vi.fn();
    render(<LayerToggles layers={sampleLayers} onToggle={onToggle} />);

    const missingLabel = screen.getByText("Missing streets");
    // Disabled layers get color: #9ca3af (jsdom returns rgb form)
    expect(missingLabel.style.color).toBe("rgb(156, 163, 175)");
  });

  it("renders nothing for empty layers", () => {
    const onToggle = vi.fn();
    const { container } = render(<LayerToggles layers={[]} onToggle={onToggle} />);
    // Panel still renders but with no checkboxes
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});
