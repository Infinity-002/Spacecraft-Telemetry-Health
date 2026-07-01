import type { PassSummary } from "../types"
import SeverityBadge from "./SeverityBadge"

interface PassCardProps {
  passSummary: PassSummary
  selected: boolean
  onClick: () => void
  isNew?: boolean
}

export default function PassCard({ passSummary, selected, onClick, isNew }: PassCardProps) {
  const getSeverityColor = (sev: string) => {
    const s = sev.toLowerCase()
    if (s.includes("immediate")) return "var(--severity-immediate)"
    if (s.includes("investigate")) return "var(--severity-investigate)"
    if (s.includes("monitor")) return "var(--severity-monitor)"
    return "var(--severity-nominal)"
  }

  const getGlowClass = (sev: string) => {
    const s = sev.toLowerCase()
    if (s.includes("immediate")) return "glow-immediate"
    if (s.includes("investigate")) return "glow-investigate"
    if (s.includes("monitor")) return "glow-monitor"
    return "glow-nominal"
  }

  // Format time range (HH:MM–HH:MM UTC)
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString)
      return date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "UTC",
      })
    } catch {
      return ""
    }
  }

  const borderLeft = selected ? `3px solid ${getSeverityColor(passSummary.overall_severity)}` : "none"
  const isNominal = passSummary.overall_severity.toLowerCase() === "nominal"

  return (
    <div
      onClick={onClick}
      className={`card ${selected ? "selected" : ""} ${isNew ? "pass-card-new " + getGlowClass(passSummary.overall_severity) : ""}`}
      style={{
        borderLeft,
        opacity: isNominal && !selected ? 0.65 : 1,
        display: "flex",
        flexDirection: "column",
        gap: "10px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontWeight: 600, fontSize: "14px" }}>Pass {passSummary.pass_number}</span>
        <SeverityBadge severity={passSummary.overall_severity} />
      </div>

      <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        {formatTime(passSummary.start_time)} – {formatTime(passSummary.end_time)} UTC
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px" }}>
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          {passSummary.flagged_subsystems.map((sub) => (
            <span
              key={sub}
              style={{
                fontSize: "10px",
                backgroundColor: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "3px",
                padding: "1px 4px",
                color: "var(--text-secondary)",
              }}
            >
              {sub}
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", fontSize: "12px", color: "var(--text-muted)" }}>
          <span>{passSummary.num_notes} notes</span>
          {passSummary.num_rule_overrides > 0 && (
            <span style={{ color: "var(--severity-immediate)" }} title={`${passSummary.num_rule_overrides} rule overrides`}>
              ⚡ {passSummary.num_rule_overrides}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
