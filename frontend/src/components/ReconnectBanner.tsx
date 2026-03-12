/**
 * T098 — ReconnectBanner
 *
 * Shows a banner prompting the user to reconnect Strava when their token has been revoked.
 */

import { useAppStore } from "@/store";
import { authApi } from "@/api/client";

const STRAVA_ORANGE = "#fc4c02";

export default function ReconnectBanner() {
  const syncStatus = useAppStore((s) => s.syncStatus);

  // Only show when sync status indicates revoked
  if (syncStatus?.status !== "revoked") {
    return null;
  }

  return (
    <div
      style={{
        backgroundColor: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: "8px",
        padding: "0.75rem 1rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        margin: "0.5rem 1rem",
      }}
    >
      <div>
        <strong style={{ color: "#dc2626" }}>Strava disconnected</strong>
        <p style={{ color: "#6b7280", fontSize: "0.8125rem", margin: "0.25rem 0 0" }}>
          Your Strava access has been revoked. Reconnect to continue syncing activities.
        </p>
      </div>
      <a
        href={authApi.getLoginUrl()}
        style={{
          backgroundColor: STRAVA_ORANGE,
          color: "#fff",
          padding: "8px 16px",
          borderRadius: "6px",
          textDecoration: "none",
          fontWeight: 600,
          fontSize: "0.875rem",
          whiteSpace: "nowrap",
        }}
      >
        Reconnect Strava
      </a>
    </div>
  );
}
