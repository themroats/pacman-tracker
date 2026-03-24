/**
 * Toast notification container — renders active toasts from the Zustand store.
 * Fixed position bottom-right, auto-dismiss after 5s with manual close.
 */

import { useAppStore } from "@/store";
import type { Toast } from "@/store";
import { useIsMobile } from "@/hooks/useIsMobile";

const typeColors: Record<Toast["type"], { bg: string; border: string; text: string }> = {
  error: { bg: "#fef2f2", border: "#fca5a5", text: "#dc2626" },
  warning: { bg: "#fffbeb", border: "#fcd34d", text: "#d97706" },
  success: { bg: "#f0fdf4", border: "#86efac", text: "#16a34a" },
  info: { bg: "#eff6ff", border: "#93c5fd", text: "#2563eb" },
};

export default function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const removeToast = useAppStore((s) => s.removeToast);
  const isMobile = useIsMobile();

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: isMobile ? "0.5rem" : "1rem",
        right: isMobile ? "0.5rem" : "1rem",
        left: isMobile ? "0.5rem" : undefined,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        maxWidth: isMobile ? undefined : "24rem",
      }}
    >
      {toasts.map((toast) => {
        const colors = typeColors[toast.type];
        return (
          <div
            key={toast.id}
            role="alert"
            style={{
              backgroundColor: colors.bg,
              border: `1px solid ${colors.border}`,
              borderRadius: "0.5rem",
              padding: "0.75rem 1rem",
              display: "flex",
              alignItems: "flex-start",
              gap: "0.5rem",
              boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            <span style={{ flex: 1, color: colors.text, fontSize: "0.875rem" }}>
              {toast.message}
            </span>
            <button
              onClick={() => removeToast(toast.id)}
              aria-label="Dismiss notification"
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: colors.text,
                fontSize: "1rem",
                lineHeight: 1,
                padding: 0,
              }}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
