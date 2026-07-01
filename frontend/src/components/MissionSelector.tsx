interface MissionSelectorProps {
  missions: string[]
  selectedMission: string | null
  setSelectedMission: (mission: string) => void
}

export default function MissionSelector({
  missions,
  selectedMission,
  setSelectedMission,
}: MissionSelectorProps) {
  return (
    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
      <label htmlFor="mission-select" style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
        Mission:
      </label>
      <select
        id="mission-select"
        value={selectedMission || ""}
        onChange={(e) => setSelectedMission(e.target.value)}
        style={{ cursor: "pointer" }}
      >
        <option value="" disabled>Select Mission</option>
        {missions.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  )
}
