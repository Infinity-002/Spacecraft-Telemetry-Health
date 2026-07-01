import { useState } from "react"
import type { Decision } from "../types"
import SeverityBadge from "./SeverityBadge"
import ConfidenceBar from "./ConfidenceBar"
import OverrideForm from "./OverrideForm"
import { postOverride } from "../api"

interface DecisionRowProps {
  decision: Decision
  onOverrideSuccess: (noteId: string, severity: string, comment: string) => void
}

export default function DecisionRow({ decision, onOverrideSuccess }: DecisionRowProps) {
  const [showOverride, setShowOverride] = useState(false)
  const [localOverride, setLocalOverride] = useState<{ severity: string; comment: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isRuleOverride = decision.is_rule_override || (decision.violated_rules && decision.violated_rules.length > 0)
  const hasLowConfidence = decision.uncertainty > 0.25

  // Format timestamp (HH:MM:SS UTC)
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString)
      return date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZone: "UTC",
      })
    } catch {
      return ""
    }
  }

  const handleOverrideSubmit = async (severity: string, comment: string) => {
    try {
      setError(null)
      await postOverride(decision.note_id, severity, comment)
      setLocalOverride({ severity, comment })
      onOverrideSuccess(decision.note_id, severity, comment)
      setShowOverride(false)
    } catch (err) {
      setError("Failed to submit override.")
    }
  }

  const timelineDotStyle = (sev: string) => {
    const s = sev.toLowerCase()
    if (s.includes("immediate")) return "dot-immediate"
    if (s.includes("investigate")) return "dot-investigate"
    if (s.includes("monitor")) return "dot-monitor"
    return "dot-nominal"
  }

  const severityToDisplay = localOverride ? localOverride.severity : decision.severity

  return (
    <div style={{ position: "relative", paddingBottom: "8px" }}>
      <div className={`timeline-dot ${timelineDotStyle(severityToDisplay)}`} />

      <div
        style={{
          borderLeft: isRuleOverride ? "3px solid var(--severity-immediate)" : "none",
          paddingLeft: isRuleOverride ? "12px" : "0px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className="mono" style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
              {formatTime(decision.timestamp)}
            </span>
            <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              {decision.note_id}
            </span>
            {hasLowConfidence && (
              <span
                style={{
                  fontSize: "10px",
                  color: "#f59e0b",
                  backgroundColor: "rgba(245, 158, 11, 0.1)",
                  padding: "1px 4px",
                  borderRadius: "3px",
                  animation: "pulse-immediate 1.5s ease-in-out infinite",
                }}
              >
                ⚠ Low Confidence
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
            <SeverityBadge severity={severityToDisplay} />
            <span className="mono" style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              {(decision.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <div style={{ fontSize: "14px", color: "var(--text-primary)", lineHeight: "1.4" }}>
          {decision.operator_note || "No operator note recorded."}
        </div>

        {isRuleOverride && decision.violated_rules && (
          <div style={{ display: "flex", flexDirection: "column", gap: "2px", margin: "4px 0" }}>
            {decision.violated_rules.map((rule, idx) => (
              <div
                key={idx}
                style={{ fontSize: "12px", color: "var(--severity-immediate)", fontWeight: 500 }}
              >
                ⚡ HARD LIMIT: {rule}
              </div>
            ))}
          </div>
        )}

        <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
          <strong style={{ color: "var(--text-primary)" }}>Action:</strong> {localOverride ? `Enter safe mode and prioritize subsystem stabilization (Override -> ${localOverride.severity})` : decision.action}
        </div>

        <div style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
          {decision.explanation}
        </div>

        <div 
          style={{ 
            display: "grid", 
            gridTemplateColumns: "repeat(4, 1fr)", 
            gap: "8px", 
            marginTop: "6px",
            padding: "8px",
            backgroundColor: "rgba(17, 24, 39, 0.4)",
            border: "1px solid var(--border)",
            borderRadius: "4px"
          }}
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase" }}>Telemetry Anomaly</span>
            <span className="mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{(decision.telemetry_score ?? 0).toFixed(2)}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase" }}>Conformal p-value</span>
            <span className="mono" style={{ fontSize: "11px", color: (decision.telemetry_pvalue ?? 1.0) < 0.01 ? "var(--severity-immediate)" : "var(--text-secondary)" }}>{(decision.telemetry_pvalue ?? 0).toFixed(3)}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase" }}>Operator Reliability</span>
            <span className="mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{(decision.note_weight ?? 0).toFixed(2)}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase" }}>Evidence Conflict (K)</span>
            <span className="mono" style={{ fontSize: "11px", color: (decision.conflict ?? 0) > 0.4 ? "var(--severity-investigate)" : "var(--text-secondary)" }}>{(decision.conflict ?? 0).toFixed(2)}</span>
          </div>
        </div>

        {localOverride && (
          <div
            style={{
              marginTop: "6px",
              padding: "6px 8px",
              backgroundColor: "rgba(59, 130, 246, 0.1)",
              border: "1px dashed var(--accent)",
              borderRadius: "4px",
              fontSize: "12px",
            }}
          >
            <span className="badge" style={{ backgroundColor: "rgba(59, 130, 246, 0.2)", color: "var(--accent)" }}>
              ✓ Operator Override → {localOverride.severity}
            </span>
            <div style={{ color: "var(--text-secondary)", marginTop: "4px" }}>
              <strong>Comment:</strong> {localOverride.comment}
            </div>
          </div>
        )}

        <ConfidenceBar confidence={decision.confidence} uncertainty={decision.uncertainty} />

        {!localOverride && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "4px" }}>
            {isRuleOverride ? (
              <button
                disabled
                title="Safety rule — cannot override"
                style={{
                  fontSize: "11px",
                  padding: "2px 8px",
                  backgroundColor: "transparent",
                  border: "1px solid var(--border)",
                  color: "var(--text-muted)",
                }}
              >
                Override
              </button>
            ) : (
              <button
                onClick={() => setShowOverride(!showOverride)}
                style={{
                  fontSize: "11px",
                  padding: "2px 8px",
                  backgroundColor: "transparent",
                  border: "1px solid var(--border)",
                  color: "var(--text-secondary)",
                }}
              >
                {showOverride ? "Cancel" : "Override"}
              </button>
            )}
          </div>
        )}

        {showOverride && (
          <OverrideForm
            onSubmit={handleOverrideSubmit}
            onCancel={() => setShowOverride(false)}
          />
        )}

        {error && (
          <div style={{ color: "var(--severity-immediate)", fontSize: "11px", marginTop: "4px" }}>
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
