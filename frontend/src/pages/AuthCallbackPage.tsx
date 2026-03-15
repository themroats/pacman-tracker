/**
 * AuthCallbackPage — processes OAuth code from Strava, stores session, redirects to map.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "@/api/client";
import { useAppStore } from "@/store";

export default function AuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const login = useAppStore((s) => s.login);
  const [error, setError] = useState<string | null>(null);
  const hasStartedRef = useRef(false);

  useEffect(() => {
    if (hasStartedRef.current) {
      return;
    }

    const code = searchParams.get("code");
    const scope = searchParams.get("scope");
    const state = searchParams.get("state");

    if (!code || !scope || !state) {
      setError("Missing OAuth parameters");
      return;
    }

    const callbackKey = `strava-callback:${state}:${code}`;
    if (sessionStorage.getItem(callbackKey) === "done") {
      return;
    }

    hasStartedRef.current = true;
    sessionStorage.setItem(callbackKey, "done");

    authApi
      .callback(code, scope, state)
      .then((res) => {
        login(res.user_id, res.display_name, res.access_token);
        navigate("/map", { replace: true });
      })
      .catch((err) => {
        sessionStorage.removeItem(callbackKey);
        hasStartedRef.current = false;
        setError(err.message || "Authentication failed");
      });
  }, [searchParams, login, navigate]);

  if (error) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <h2>Authentication Error</h2>
        <p style={{ color: "red" }}>{error}</p>
        <a href="/">Go Home</a>
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h2>Connecting to Strava...</h2>
      <p>Please wait while we set up your account.</p>
    </div>
  );
}
