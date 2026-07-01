import type { Decision } from "../types"
import DecisionRow from "./DecisionRow"

interface DecisionTimelineProps {
  decisions: Decision[]
  onOverrideSuccess: (noteId: string, severity: string, comment: string) => void
}

export default function DecisionTimeline({ decisions, onOverrideSuccess }: DecisionTimelineProps) {
  if (!decisions || decisions.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "14px", textAlign: "center", padding: "24px 0" }}>
        No operator decisions available for this pass.
      </div>
    )
  }

  const sortedDecisions = [...decisions].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px" }}>
      <h3 style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
        Operator Notes & Decision Fusions
      </h3>
      <div className="timeline-container">
        {sortedDecisions.map((dec) => (
          <DecisionRow
            key={dec.note_id}
            decision={dec}
            onOverrideSuccess={onOverrideSuccess}
          />
        ))}
      </div>
    </div>
  )
}
