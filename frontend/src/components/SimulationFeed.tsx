import type { PassSummary } from "../types"
import PassGrid from "./PassGrid"

interface SimulationFeedProps {
  passes: PassSummary[]
  selectedPassNumber: number | null
  setSelectedPassNumber: (num: number) => void
  simStatus: "idle" | "running" | "complete"
  newPassIds: number[]
}

export default function SimulationFeed({
  passes,
  selectedPassNumber,
  setSelectedPassNumber,
  simStatus,
  newPassIds,
}: SimulationFeedProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-secondary)" }}>
          Incoming Passes Feed
        </h3>
        {simStatus === "running" && (
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: "var(--severity-immediate)",
                display: "inline-block",
                animation: "pulse-immediate 1s ease-in-out infinite",
              }}
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
              Live Streaming
            </span>
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        <PassGrid
          passes={passes}
          selectedPassNumber={selectedPassNumber}
          setSelectedPassNumber={setSelectedPassNumber}
          newPassIds={newPassIds}
        />
      </div>
    </div>
  )
}
