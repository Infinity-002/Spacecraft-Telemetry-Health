export default function Header() {
  return (
    <header className="header">
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span
          style={{
            display: "inline-block",
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            backgroundColor: "var(--severity-nominal)",
            boxShadow: "0 0 8px var(--severity-nominal)",
          }}
        />
        <h1>Spacecraft DSS — Live Health Assessment Console</h1>
      </div>
      <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
        <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Active Mission:</span>
        <span
          className="mono"
          style={{
            fontWeight: 600,
            color: "var(--accent)",
            backgroundColor: "rgba(59, 130, 246, 0.15)",
            border: "1px solid rgba(59, 130, 246, 0.3)",
            padding: "2px 8px",
            borderRadius: "4px",
            fontSize: "12px",
          }}
        >
          M06 — LIVE DOWNLINK
        </span>
      </div>
    </header>
  )
}
