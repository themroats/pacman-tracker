/**
 * HomePage — landing page with "Connect with Strava" button and OAuth redirect.
 */

import { useAppStore } from "@/store";
import { authApi } from "@/api/client";
import { useNavigate } from "react-router-dom";

export default function HomePage() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const displayName = useAppStore((s) => s.displayName);
  const navigate = useNavigate();

  if (isAuthenticated) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <h1>Strava Street Mapper</h1>
        <p>Welcome back{displayName ? `, ${displayName}` : ""}!</p>
        <div style={{ marginTop: "1.5rem", display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button onClick={() => navigate("/map")} style={btnStyle}>
            View Map
          </button>
          <button onClick={() => navigate("/coverage")} style={btnStyle}>
            Coverage Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h1>Strava Street Mapper</h1>
      <p>Track your runs and map every street in the city.</p>
      <a
        href={authApi.getLoginUrl()}
        style={{
          display: "inline-block",
          marginTop: "2rem",
          padding: "0.75rem 2rem",
          background: "#fc4c02",
          color: "#fff",
          borderRadius: "6px",
          textDecoration: "none",
          fontWeight: "bold",
          fontSize: "1.1rem",
        }}
      >
        Connect with Strava
      </a>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "0.5rem 1.5rem",
  background: "#333",
  color: "#fff",
  border: "none",
  borderRadius: "4px",
  cursor: "pointer",
  fontSize: "1rem",
};
