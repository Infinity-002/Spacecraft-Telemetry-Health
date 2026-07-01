interface ModeToggleProps {
  mode: "review" | "simulation"
  setMode: (mode: "review" | "simulation") => void
}

export default function ModeToggle({ mode, setMode }: ModeToggleProps) {
  const btnStyle = (active: boolean) => ({
    backgroundColor: active ? "var(--accent)" : "transparent",
    color: active ? "#ffffff" : "var(--text-secondary)",
    border: "1px solid var(--border)",
    padding: "6px 12px",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: 600,
    outline: "none",
  })

  return (
    <div style={{ display: "flex", gap: "2px", background: "var(--bg-surface)", padding: "2px", borderRadius: "6px", border: "1px solid var(--border)" }}>
      <button
        style={btnStyle(mode === "review")}
        onClick={() => setMode("review")}
      >
        Review Mode
      </button>
      <button
        style={btnStyle(mode === "simulation")}
        onClick={() => setMode("simulation")}
      >
        Simulation Mode
      </button>
    </div>
  )
}
