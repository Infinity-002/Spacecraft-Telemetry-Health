import type { PassSummary, TelemetryData } from "../types"
import TrendBanner from "./TrendBanner"
import TelemetryChart from "./TelemetryChart"
import DecisionTimeline from "./DecisionTimeline"
import SeverityBadge from "./SeverityBadge"

interface PassDetailProps {
  passSummary: PassSummary | null
  telemetry: TelemetryData | null
  onOverrideSuccess: (noteId: string, severity: string, comment: string) => void
}

export default function PassDetail({
  passSummary,
  telemetry,
  onOverrideSuccess,
}: PassDetailProps) {
  if (!passSummary) {
    return (
      <div
        style={{
          display: "flex",
          height: "100%",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: "14px",
        }}
      >
        Awaiting live downlink packets...
      </div>
    )
  }

  // Calculate worst D-S metrics across decisions in this pass
  const avgConfidence = passSummary.overall_confidence;
  const maxUncertainty = passSummary.overall_uncertainty;
  const maxConflict = passSummary.decisions.reduce((max, d) => Math.max(max, d.conflict ?? 0), 0);
  const avgNoteWeight = passSummary.decisions.reduce((sum, d) => sum + (d.note_weight ?? 0), 0) / (passSummary.decisions.length || 1);

  // List of subsystems we want to display status cards for
  const subsystemsList = ["EPS", "TCS", "ADCS", "TT&C", "System"]

  const getSubsystemStatus = (sub: string) => {
    const subDecisions = passSummary.decisions.filter(
      (d) => d.subsystem.toUpperCase() === sub.toUpperCase()
    )
    if (subDecisions.length === 0) return "Nominal"

    const SEVERITY_ORDER: Record<string, number> = {
      "Nominal": 0,
      "Monitor": 1,
      "Investigate": 2,
      "Immediate Action": 3,
    }
    
    return subDecisions.reduce((worst, curr) => {
      const wIdx = SEVERITY_ORDER[worst] || 0
      const cIdx = SEVERITY_ORDER[curr.severity] || 0
      return cIdx > wIdx ? curr.severity : worst
    }, "Nominal")
  }

  const getStatusColorClass = (status: string) => {
    const s = status.toLowerCase()
    if (s.includes("immediate")) return "var(--severity-immediate)"
    if (s.includes("investigate")) return "var(--severity-investigate)"
    if (s.includes("monitor")) return "var(--severity-monitor)"
    return "var(--severity-nominal)"
  }

  const getStatusBgColor = (status: string) => {
    const s = status.toLowerCase()
    if (s.includes("immediate")) return "rgba(239, 68, 68, 0.1)"
    if (s.includes("investigate")) return "rgba(249, 115, 22, 0.1)"
    if (s.includes("monitor")) return "rgba(245, 158, 11, 0.1)"
    return "rgba(16, 185, 129, 0.1)"
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      
      {/* Spacecraft Health HUD */}
      <div
        style={{
          background: getStatusBgColor(passSummary.overall_severity),
          border: `1px solid ${getStatusColorClass(passSummary.overall_severity)}`,
          borderRadius: "var(--radius-card)",
          padding: "16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px", color: "var(--text-secondary)" }}>
              Spacecraft Status
            </span>
            {passSummary.num_rule_overrides > 0 && (
              <span className="badge" style={{ backgroundColor: "rgba(239, 68, 68, 0.2)", color: "var(--severity-immediate)" }}>
                ⚡ FSW Rule Override Active
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
            <h2 style={{ fontSize: "22px", fontWeight: 700, color: "#ffffff" }}>
              {passSummary.overall_severity === "Immediate Action" ? "CRITICAL ALERT" : passSummary.overall_severity.toUpperCase()}
            </h2>
            <SeverityBadge severity={passSummary.overall_severity} />
          </div>
        </div>

        {/* Dempster-Shafer Metrics */}
        <div style={{ display: "flex", gap: "24px" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "uppercase" }}>Belief (Conf)</span>
            <span className="mono" style={{ fontSize: "16px", fontWeight: 600, color: "#ffffff" }}>
              {(avgConfidence * 100).toFixed(0)}%
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "uppercase" }}>Uncertainty</span>
            <span className="mono" style={{ fontSize: "16px", fontWeight: 600, color: maxUncertainty > 0.25 ? "var(--severity-monitor)" : "#ffffff" }}>
              {(maxUncertainty * 100).toFixed(0)}%
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "uppercase" }}>Conflict (K)</span>
            <span className="mono" style={{ fontSize: "16px", fontWeight: 600, color: maxConflict > 0.4 ? "var(--severity-investigate)" : "#ffffff" }}>
              {maxConflict.toFixed(2)}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "uppercase" }}>Note Reliability</span>
            <span className="mono" style={{ fontSize: "16px", fontWeight: 600, color: "#ffffff" }}>
              {avgNoteWeight.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Subsystem Health Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "12px" }}>
        {subsystemsList.map((sub) => {
          const status = getSubsystemStatus(sub)
          const color = getStatusColorClass(status)
          const bg = getStatusBgColor(status)
          return (
            <div
              key={sub}
              style={{
                backgroundColor: "var(--bg-surface)",
                border: `1px solid ${status === "Nominal" ? "var(--border)" : color}`,
                borderRadius: "var(--radius-card)",
                padding: "12px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                alignItems: "center",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary)" }}>{sub}</span>
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  color: color,
                  backgroundColor: bg,
                  padding: "2px 6px",
                  borderRadius: "4px",
                  border: `1px solid ${color}33`,
                }}
              >
                {status.replace(" Action", "")}
              </span>
            </div>
          )
        })}
      </div>

      {/* Active Trend Alerts */}
      <TrendBanner trends={passSummary.trend_alerts || []} />

      {/* Live Telemetry Plots */}
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
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-secondary)" }}>
            Physical Telemetry Timeline
          </span>
          <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            26 parameters monitored
          </span>
        </div>

        {telemetry ? (
          <TelemetryChart
            telemetry={telemetry}
            flaggedSubsystems={passSummary.flagged_subsystems}
            startTime={passSummary.start_time}
            endTime={passSummary.end_time}
          />
        ) : (
          <div
            style={{
              height: "260px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-muted)",
              fontSize: "12px",
            }}
          >
            Awaiting telemetry cache synchronization...
          </div>
        )}
      </div>

      {/* Decision timeline showing Dempster-Shafer reasoning */}
      <div
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: "16px",
        }}
      >
        <h3 style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "16px" }}>
          Dempster-Shafer Evidence Timeline
        </h3>
        <DecisionTimeline
          decisions={passSummary.decisions}
          onOverrideSuccess={onOverrideSuccess}
        />
      </div>
    </div>
  )
}
