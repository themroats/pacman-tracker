/**
 * T077 — LoadingSpinner
 *
 * A simple CSS-only loading spinner component.
 */

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
}

export default function LoadingSpinner({
  size = 32,
  message = "Loading...",
}: LoadingSpinnerProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "0.75rem",
      }}
    >
      <div
        style={{
          width: size,
          height: size,
          border: "3px solid #e5e7eb",
          borderTopColor: "#3b82f6",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      {message && (
        <span style={{ color: "#6b7280", fontSize: "0.875rem" }}>{message}</span>
      )}
      <style>
        {`@keyframes spin { to { transform: rotate(360deg); } }`}
      </style>
    </div>
  );
}
