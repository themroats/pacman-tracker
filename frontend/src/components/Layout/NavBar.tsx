/**
 * T073 — NavBar
 *
 * Navigation header with links to all pages.
 */

import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useAppStore } from "@/store";

const NAV_ITEMS = [
  { path: "/map", label: "Map" },
  { path: "/coverage", label: "Coverage" },
  { path: "/route", label: "Routes" },
  { path: "/progress", label: "Progress" },
];

export default function NavBar() {
  const location = useLocation();
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const displayName = useAppStore((s) => s.displayName);
  const logout = useAppStore((s) => s.logout);

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 1rem",
        height: "48px",
        backgroundColor: "#1f2937",
        color: "#fff",
        fontSize: "0.875rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
        <Link
          to="/"
          style={{
            color: "#fff",
            textDecoration: "none",
            fontWeight: 700,
            fontSize: "1rem",
          }}
        >
          Street Mapper
        </Link>

        {isAuthenticated &&
          NAV_ITEMS.map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  color: isActive ? "#60a5fa" : "#d1d5db",
                  textDecoration: "none",
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {item.label}
              </Link>
            );
          })}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        {isAuthenticated && displayName && (
          <span style={{ color: "#9ca3af" }}>{displayName}</span>
        )}
        {isAuthenticated && (
          <button
            onClick={logout}
            style={{
              background: "none",
              border: "1px solid #4b5563",
              color: "#d1d5db",
              padding: "4px 12px",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "0.8125rem",
            }}
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
