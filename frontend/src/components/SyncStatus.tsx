/**
 * SyncStatus — sync status indicator component.
 */

import { useEffect } from "react";
import { syncApi } from "@/api/client";
import { useAppStore } from "@/store";

export default function SyncStatus() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const storeSyncStatus = useAppStore((s) => s.syncStatus);
  const setSyncStatus = useAppStore((s) => s.setSyncStatus);

  useEffect(() => {
    if (!isAuthenticated) return;

    let timer: ReturnType<typeof setInterval>;

    const fetchStatus = async () => {
      const status = await syncApi.status();
      setSyncStatus(status);

      if (status.status === "complete") {
        // Show success toast via store
        useAppStore.getState().addToast("Sync completed successfully!", "success");
      }
    };

    fetchStatus();

    // Poll during active sync or "complete" (one more cycle to observe idle transition)
    if (
      storeSyncStatus?.status === "importing" ||
      storeSyncStatus?.status === "syncing" ||
      storeSyncStatus?.status === "complete"
    ) {
      timer = setInterval(fetchStatus, 5000);
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isAuthenticated, storeSyncStatus?.status, setSyncStatus]);

  if (!isAuthenticated || !storeSyncStatus) return null;

  const { status, total_activities, imported_activities, matched_activities } = storeSyncStatus;

  const statusColor =
    status === "idle"
      ? "#44cc44"
      : status === "importing" || status === "syncing"
        ? "#ff9900"
        : status === "error"
          ? "#ff4444"
          : "#888";

  return (
    <div
      style={{
        padding: "0.5rem 1rem",
        background: "#fff",
        borderRadius: "6px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.1)",
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        fontSize: "0.85rem",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: statusColor,
          display: "inline-block",
        }}
      />
      <span style={{ textTransform: "capitalize" }}>{status}</span>
      <span style={{ color: "#888" }}>
        {imported_activities}/{total_activities} imported
        {matched_activities > 0 && ` • ${matched_activities} matched`}
      </span>
    </div>
  );
}
