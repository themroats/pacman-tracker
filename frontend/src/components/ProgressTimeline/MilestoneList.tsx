/**
 * MilestoneList
 *
 * Achievement badges showing coverage milestones (25%, 50%, 75%, 100%)
 * with dates for each neighborhood.
 */

import type { Milestone } from "@/types/api";
import { useIsMobile } from "@/hooks/useIsMobile";

interface MilestoneListProps {
  milestones: Milestone[];
}

const BADGE_COLORS: Record<string, string> = {
  "25%": "#f59e0b",  // amber
  "50%": "#3b82f6",  // blue
  "75%": "#8b5cf6",  // purple
  "100%": "#22c55e", // green
};

export default function MilestoneList({ milestones }: MilestoneListProps) {
  const isMobile = useIsMobile();
  if (milestones.length === 0) {
    return (
      <div style={{ padding: "1rem", color: "#9ca3af", fontSize: "0.875rem" }}>
        No milestones yet.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: isMobile ? "0.5rem" : "0.75rem", padding: "0.5rem 0" }}>
      {milestones.map((m) => {
        const color = BADGE_COLORS[m.label] ?? "#6b7280";
        const opacity = m.reached ? 1 : 0.35;

        return (
          <div
            key={m.label + m.neighborhood_name}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              padding: isMobile ? "0.5rem" : "0.75rem",
              borderRadius: "8px",
              border: `2px solid ${color}`,
              opacity,
              minWidth: isMobile ? "80px" : "100px",
            }}
          >
            <div
              style={{
                width: isMobile ? "32px" : "40px",
                height: isMobile ? "32px" : "40px",
                borderRadius: "50%",
                backgroundColor: color,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontWeight: 700,
                fontSize: "0.75rem",
                marginBottom: "0.5rem",
              }}
            >
              {m.label}
            </div>
            {m.neighborhood_name && (
              <div style={{ fontSize: "0.75rem", fontWeight: 500, textAlign: "center" }}>
                {m.neighborhood_name}
              </div>
            )}
            <div style={{ fontSize: "0.6875rem", color: "#6b7280", marginTop: "0.25rem" }}>
              {m.reached && m.date ? m.date : "Not reached"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
