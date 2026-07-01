import type { PassSummary, TelemetryData, TrendAlert } from "./types"

export async function fetchMissions(): Promise<string[]> {
  const res = await fetch("/api/missions")
  if (!res.ok) throw new Error("Failed to fetch missions")
  return res.json()
}

export async function fetchPasses(missionId?: string): Promise<PassSummary[]> {
  const url = missionId ? `/api/passes?mission_id=${missionId}` : "/api/passes"
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch passes")
  return res.json()
}

export async function fetchTelemetry(missionId: string): Promise<TelemetryData> {
  const res = await fetch(`/api/telemetry/${missionId}`)
  if (!res.ok) throw new Error("Failed to fetch telemetry")
  return res.json()
}

export async function fetchTrends(missionId: string): Promise<TrendAlert[]> {
  const res = await fetch(`/api/trends/${missionId}`)
  if (!res.ok) throw new Error("Failed to fetch trends")
  return res.json()
}

export async function postOverride(
  noteId: string,
  severity: string,
  comment: string
): Promise<void> {
  const res = await fetch("/api/override", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      note_id: noteId,
      operator_severity: severity,
      operator_comment: comment,
    }),
  })
  if (!res.ok) throw new Error("Failed to post override")
}

export function connectSimulation(
  speed: number,
  onPass: (pass: PassSummary) => void,
  onTelemetry: (tel: TelemetryData) => void,
  onComplete: () => void
): EventSource {
  const source = new EventSource(`/api/simulate/start?speed=${speed}`)

  source.addEventListener("pass", (e) => {
    const data = JSON.parse(e.data)
    onPass(data)
  })

  source.addEventListener("telemetry", (e) => {
    const data = JSON.parse(e.data)
    onTelemetry(data)
  })

  source.addEventListener("complete", () => {
    onComplete()
  })

  return source
}
