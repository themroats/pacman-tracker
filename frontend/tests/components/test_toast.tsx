/**
 * Tests for toast notification system.
 *
 * Covers:
 * - T010: addToast/removeToast in Zustand store
 * - T011: ToastContainer renders toasts
 * - T012: ToastContainer is mounted in App
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("Toast Store (T010)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("addToast adds a toast to the store", async () => {
    const { useAppStore } = await import("@/store");

    act(() => {
      useAppStore.getState().addToast("Test error", "error");
    });

    const toasts = useAppStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Test error");
    expect(toasts[0].type).toBe("error");
  });

  it("addToast generates unique IDs", async () => {
    const { useAppStore } = await import("@/store");

    act(() => {
      useAppStore.getState().addToast("First", "error");
      useAppStore.getState().addToast("Second", "warning");
    });

    const toasts = useAppStore.getState().toasts;
    expect(toasts).toHaveLength(2);
    expect(toasts[0].id).not.toBe(toasts[1].id);
  });

  it("removeToast removes a specific toast", async () => {
    const { useAppStore } = await import("@/store");

    act(() => {
      useAppStore.getState().addToast("To remove", "info");
    });

    const id = useAppStore.getState().toasts[0].id;

    act(() => {
      useAppStore.getState().removeToast(id);
    });

    expect(useAppStore.getState().toasts).toHaveLength(0);
  });

  it("toast auto-dismisses after 5 seconds", async () => {
    const { useAppStore } = await import("@/store");

    act(() => {
      useAppStore.getState().addToast("Temporary", "success");
    });

    expect(useAppStore.getState().toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(useAppStore.getState().toasts).toHaveLength(0);
  });

  it("addToast defaults to error type", async () => {
    const { useAppStore } = await import("@/store");

    act(() => {
      useAppStore.getState().addToast("Default type");
    });

    expect(useAppStore.getState().toasts[0].type).toBe("error");
  });
});

describe("ToastContainer (T011 + T012)", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when no toasts", async () => {
    const { default: ToastContainer } = await import(
      "@/components/common/ToastContainer"
    );

    const { container } = render(<ToastContainer />);
    expect(container.innerHTML).toBe("");
  });

  it("renders toast messages", async () => {
    const { useAppStore } = await import("@/store");
    const { default: ToastContainer } = await import(
      "@/components/common/ToastContainer"
    );

    act(() => {
      useAppStore.getState().addToast("Visible error", "error");
    });

    render(<ToastContainer />);

    expect(screen.getByText("Visible error")).toBeDefined();
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("dismiss button removes toast", async () => {
    const user = userEvent.setup();
    const { useAppStore } = await import("@/store");
    const { default: ToastContainer } = await import(
      "@/components/common/ToastContainer"
    );

    act(() => {
      useAppStore.getState().addToast("Dismissible", "warning");
    });

    render(<ToastContainer />);

    const dismissBtn = screen.getByLabelText("Dismiss notification");
    await user.click(dismissBtn);

    expect(useAppStore.getState().toasts).toHaveLength(0);
  });
});

describe("App mounts ToastContainer (T012)", () => {
  it("App.tsx imports ToastContainer", async () => {
    // Verify by checking the import exists in the source
    const fs = await import("fs");
    const path = await import("path");
    const appSource = fs.readFileSync(
      path.resolve(__dirname, "../../src/App.tsx"),
      "utf-8"
    );
    expect(appSource).toContain("ToastContainer");
    expect(appSource).toContain("ErrorBoundary");
  });
});
