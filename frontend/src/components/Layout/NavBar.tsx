/**
 * T073 — NavBar
 *
 * Navigation header with links to all pages.
 */

import { Link, useLocation } from "react-router-dom";
import { useAppStore } from "@/store";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useState, useEffect } from "react";

const NAV_ITEMS = [
  { path: "/map", label: "Map" },
  { path: "/coverage", label: "Coverage" },
  { path: "/route", label: "Routes" },
  { path: "/progress", label: "Progress" },
];

export default function NavBar() {
  const location = useLocation();
  const isMobile = useIsMobile();
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const displayName = useAppStore((s) => s.displayName);
  const logout = useAppStore((s) => s.logout);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Close menu on navigation
  useEffect(() => {
    setIsMenuOpen(false);
  }, [location.pathname]);

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
        position: "relative",
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

        {/* Desktop: inline links */}
        {!isMobile &&
          isAuthenticated &&
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
        {!isMobile && isAuthenticated && displayName && (
          <span style={{ color: "#9ca3af" }}>{displayName}</span>
        )}
        {!isMobile && isAuthenticated && (
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

        {/* Mobile: hamburger button */}
        {isMobile && isAuthenticated && (
          <button
            onClick={() => setIsMenuOpen((v) => !v)}
            aria-label="Menu"
            style={{
              background: "none",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              padding: "8px",
              minWidth: 44,
              minHeight: 44,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.5rem",
              lineHeight: 1,
            }}
          >
            {isMenuOpen ? "✕" : "☰"}
          </button>
        )}
      </div>

      {/* Mobile dropdown menu */}
      {isMobile && isMenuOpen && isAuthenticated && (
        <div
          style={{
            position: "absolute",
            top: "48px",
            left: 0,
            right: 0,
            backgroundColor: "#1f2937",
            zIndex: 2000,
            display: "flex",
            flexDirection: "column",
            padding: "0.5rem 0",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  color: isActive ? "#60a5fa" : "#d1d5db",
                  textDecoration: "none",
                  fontWeight: isActive ? 600 : 400,
                  padding: "0.625rem 1rem",
                  minHeight: 44,
                  display: "flex",
                  alignItems: "center",
                  borderBottom: "1px solid #374151",
                }}
              >
                {item.label}
              </Link>
            );
          })}
          {displayName && (
            <span style={{ color: "#9ca3af", padding: "0.5rem 1rem", fontSize: "0.8125rem", borderBottom: "1px solid #374151" }}>
              {displayName}
            </span>
          )}
          <button
            onClick={logout}
            style={{
              background: "none",
              border: "none",
              borderTop: "1px solid #374151",
              color: "#d1d5db",
              padding: "0.75rem 1rem",
              textAlign: "left",
              cursor: "pointer",
              fontSize: "0.875rem",
              minHeight: 44,
            }}
          >
            Logout
          </button>
        </div>
      )}
    </nav>
  );
}
