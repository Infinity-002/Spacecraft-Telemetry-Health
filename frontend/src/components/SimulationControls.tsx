interface SimulationControlsProps {
  simStatus: "idle" | "running" | "complete"
  simSpeed: number
  setSimSpeed: (speed: number) => void
  onStart: () => void
  onStop: () => void
  passesReceived: number
  totalPasses: number
}

export default function SimulationControls({
  simStatus,
  simSpeed,
  setSimSpeed,
  onStart,
  onStop,
  passesReceived,
  totalPasses,
}: SimulationControlsProps) {
  const speeds = [1, 5, 10]

  const pct = Math.min(100, (passesReceived / totalPasses) * 100)

  return (
    <div
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "14px", fontWeight: 600 }}>Simulation Controls</span>
        {simStatus === "running" && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "var(--severity-immediate)", fontSize: "12px" }}>●</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Live</span>
          </div>
        )}
      </div>

      {/* Speed Selector */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Simulation Speed:</span>
        <div style={{ display: "flex", gap: "4px" }}>
          {speeds.map((s) => (
            <label
              key={s}
              style={{
                fontSize: "11px",
                display: "flex",
                alignItems: "center",
                gap: "2px",
                cursor: simStatus === "running" ? "not-allowed" : "pointer",
                padding: "2px 6px",
                border: "1px solid var(--border)",
                borderRadius: "3px",
                backgroundColor: simSpeed === s ? "var(--bg-elevated)" : "transparent",
                color: simSpeed === s ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              <input
                type="radio"
                name="speed"
                value={s}
                checked={simSpeed === s}
                disabled={simStatus === "running"}
                onChange={() => setSimSpeed(s)}
                style={{ display: "none" }}
              />
              {s}x
            </label>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: "8px" }}>
        {simStatus === "running" ? (
          <button
            onClick={onStop}
            style={{
              backgroundColor: "var(--severity-immediate)",
              flex: 1,
            }}
          >
            Stop Simulation
          </button>
        ) : (
          <button
            onClick={onStart}
            style={{
              backgroundColor: "var(--severity-nominal)",
              color: "#ffffff",
              flex: 1,
            }}
          >
            Start Simulation
          </button>
        )}
      </div>

      {/* Status Indicators */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "4px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-secondary)" }}>
          <span>
            {simStatus === "idle" && "Status: Idle"}
            {simStatus === "running" && `Running — Pass ${passesReceived}/${totalPasses} received`}
            {simStatus === "complete" && `Complete — ${passesReceived} passes`}
          </span>
          <span>{pct.toFixed(0)}%</span>
        </div>

        {/* Progress Bar */}
        <div
          style={{
            width: "100%",
            height: "6px",
            backgroundColor: "var(--bg-elevated)",
            borderRadius: "3px",
            overflow: "hidden",
            marginTop: "2px",
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              backgroundColor: simStatus === "complete" ? "var(--severity-nominal)" : "var(--accent)",
              transition: "width 0.3s ease",
            }}
          />
        </div>
      </div>
    </div>
  )
}
