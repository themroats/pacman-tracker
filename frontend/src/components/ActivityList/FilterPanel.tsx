/**
 * FilterPanel — activity filter controls (sport type, date range, distance).
 */

import { useState } from "react";
import type { ActivityFilters } from "@/types/api";

const SPORT_TYPES = ["All", "Run", "Walk", "Ride", "Hike"];

interface FilterPanelProps {
  filters: ActivityFilters;
  onFiltersChange: (filters: Partial<ActivityFilters>) => void;
}

export default function FilterPanel({ filters, onFiltersChange }: FilterPanelProps) {
  const [localStartDate, setLocalStartDate] = useState(filters.start_date || "");
  const [localEndDate, setLocalEndDate] = useState(filters.end_date || "");

  return (
    <div
      style={{
        padding: "1rem",
        background: "#fff",
        borderRadius: "8px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
        display: "flex",
        flexWrap: "wrap",
        gap: "1rem",
        alignItems: "flex-end",
      }}
    >
      {/* Sport Type */}
      <div>
        <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", color: "#666" }}>
          Sport Type
        </label>
        <select
          value={filters.sport_type || "All"}
          onChange={(e) => {
            const val = e.target.value === "All" ? undefined : e.target.value;
            onFiltersChange({ sport_type: val });
          }}
          style={selectStyle}
        >
          {SPORT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Start Date */}
      <div>
        <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", color: "#666" }}>
          From
        </label>
        <input
          type="date"
          value={localStartDate}
          onChange={(e) => {
            setLocalStartDate(e.target.value);
            onFiltersChange({ start_date: e.target.value || undefined });
          }}
          style={inputStyle}
        />
      </div>

      {/* End Date */}
      <div>
        <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", color: "#666" }}>
          To
        </label>
        <input
          type="date"
          value={localEndDate}
          onChange={(e) => {
            setLocalEndDate(e.target.value);
            onFiltersChange({ end_date: e.target.value || undefined });
          }}
          style={inputStyle}
        />
      </div>

      {/* Clear Filters */}
      <button
        onClick={() => {
          setLocalStartDate("");
          setLocalEndDate("");
          onFiltersChange({ sport_type: undefined, start_date: undefined, end_date: undefined });
        }}
        style={{
          padding: "0.4rem 1rem",
          background: "#eee",
          border: "1px solid #ccc",
          borderRadius: "4px",
          cursor: "pointer",
          fontSize: "0.85rem",
        }}
      >
        Clear
      </button>
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "0.4rem 0.5rem",
  border: "1px solid #ccc",
  borderRadius: "4px",
  fontSize: "0.9rem",
};

const inputStyle: React.CSSProperties = {
  padding: "0.4rem 0.5rem",
  border: "1px solid #ccc",
  borderRadius: "4px",
  fontSize: "0.9rem",
};
