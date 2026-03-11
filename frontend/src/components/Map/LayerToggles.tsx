/**
 * LayerToggles — floating toggle panel for showing/hiding map layers.
 */

import { type CSSProperties } from "react";

export interface LayerToggle {
  key: string;
  label: string;
  color: string;
  enabled: boolean;
}

interface LayerTogglesProps {
  layers: LayerToggle[];
  onToggle: (key: string) => void;
}

const panelStyle: CSSProperties = {
  position: "absolute",
  bottom: 24,
  left: 12,
  zIndex: 1000,
  background: "#fff",
  borderRadius: "8px",
  padding: "8px 12px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
  display: "flex",
  flexDirection: "column",
  gap: "4px",
  fontSize: "0.8125rem",
};

const rowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  cursor: "pointer",
  userSelect: "none",
};

export default function LayerToggles({ layers, onToggle }: LayerTogglesProps) {
  return (
    <div style={panelStyle}>
      {layers.map((l) => (
        <label key={l.key} style={rowStyle}>
          <input
            type="checkbox"
            checked={l.enabled}
            onChange={() => onToggle(l.key)}
            style={{ accentColor: l.color }}
          />
          <span
            style={{
              width: 12,
              height: 3,
              backgroundColor: l.color,
              borderRadius: 2,
              display: "inline-block",
            }}
          />
          <span style={{ color: l.enabled ? "#111" : "#9ca3af" }}>{l.label}</span>
        </label>
      ))}
    </div>
  );
}
