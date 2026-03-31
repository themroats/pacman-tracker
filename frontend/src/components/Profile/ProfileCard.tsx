/**
 * ProfileCard — collapsible summary card for the Profile page.
 *
 * Shows a compact summary line; click to expand full content.
 */

import { useState } from "react";

interface ProfileCardProps {
  title: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function ProfileCard({ title, summary, defaultOpen = false, children }: ProfileCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: "10px",
        overflow: "hidden",
        backgroundColor: "#fff",
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          padding: "1rem 1.25rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: "1rem", color: "#111827" }}>
            {title}
          </div>
          <div style={{ fontSize: "0.8125rem", color: "#6b7280", marginTop: "2px" }}>
            {summary}
          </div>
        </div>
        <span
          style={{
            fontSize: "1.25rem",
            color: "#9ca3af",
            transition: "transform 0.2s ease",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            flexShrink: 0,
            marginLeft: "1rem",
          }}
        >
          ▾
        </span>
      </button>

      {open && (
        <div
          style={{
            borderTop: "1px solid #f3f4f6",
            padding: "1rem 1.25rem",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
