import type { PassSummary } from "../types"
import PassCard from "./PassCard"

interface PassGridProps {
  passes: PassSummary[]
  selectedPassNumber: number | null
  setSelectedPassNumber: (num: number) => void
  newPassIds?: number[]
}

const SEVERITY_ORDER: Record<string, number> = {
  "Nominal": 0,
  "Monitor": 1,
  "Investigate": 2,
  "Immediate Action": 3,
  "Immediate": 3,
}

export default function PassGrid({
  passes,
  selectedPassNumber,
  setSelectedPassNumber,
  newPassIds = [],
}: PassGridProps) {
  const sortedPasses = [...passes].sort((a, b) => {
    const sevA = SEVERITY_ORDER[a.overall_severity] || 0
    const sevB = SEVERITY_ORDER[b.overall_severity] || 0
    if (sevB !== sevA) {
      return sevB - sevA
    }
    return a.pass_number - b.pass_number
  })

  if (passes.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "14px", textAlign: "center", marginTop: "32px" }}>
        No passes received yet.
      </div>
    )
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {sortedPasses.map((p) => (
        <PassCard
          key={p.pass_number}
          passSummary={p}
          selected={selectedPassNumber === p.pass_number}
          onClick={() => setSelectedPassNumber(p.pass_number)}
          isNew={newPassIds.includes(p.pass_number)}
        />
      ))}
    </div>
  )
}
