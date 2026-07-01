import { useState } from "react"
import type { TrendAlert } from "../types"

interface TrendBannerProps {
  trends: TrendAlert[]
}

export default function TrendBanner({ trends }: TrendBannerProps) {
  const [expanded, setExpanded] = useState(false)

  if (!trends || trends.length === 0) return null

  const firstTrend = trends[0]
  const restTrends = trends.slice(1)

  const formatHours = (h: number | null) => {
    if (h === null) return ""
    return ` → warning in ${h.toFixed(1)} hours`
  }

  return (
    <div
      style={{
        borderLeft: "4px solid var(--severity-monitor)",
        backgroundColor: "rgba(245, 158, 11, 0.05)",
        border: "1px solid var(--border)",
        borderLeftColor: "var(--severity-monitor)",
        borderRadius: "var(--radius-card)",
        padding: "12px 16px",
        marginBottom: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "6px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", color: "var(--severity-monitor)" }}>
          <span style={{ fontSize: "16px" }}>⚠</span>
          <span style={{ fontWeight: 600, fontSize: "13px" }}>Active Telemetry Trends</span>
        </div>
        {restTrends.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              backgroundColor: "transparent",
              color: "var(--text-secondary)",
              padding: "2px 8px",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              fontSize: "11px",
            }}
          >
            {expanded ? "Collapse" : `+${restTrends.length} more`}
          </button>
        )}
      </div>

      {/* First trend */}
      <div style={{ fontSize: "13px", color: "var(--text-primary)" }}>
        {firstTrend.message}
        {firstTrend.hours_to_warning !== null && (
          <strong style={{ color: "var(--severity-monitor)", marginLeft: "4px" }}>
            {formatHours(firstTrend.hours_to_warning)}
          </strong>
        )}
        <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "8px" }}>
          (confidence: {firstTrend.confidence.toFixed(2)})
        </span>
      </div>

      {/* Expanded rest trends */}
      {expanded && restTrends.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "4px", borderTop: "1px solid var(--border)", paddingTop: "6px" }}>
          {restTrends.map((t, idx) => (
            <div key={idx} style={{ fontSize: "13px", color: "var(--text-primary)" }}>
              {t.message}
              {t.hours_to_warning !== null && (
                <strong style={{ color: "var(--severity-monitor)", marginLeft: "4px" }}>
                  {formatHours(t.hours_to_warning)}
                </strong>
              )}
              <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "8px" }}>
                (confidence: {t.confidence.toFixed(2)})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
