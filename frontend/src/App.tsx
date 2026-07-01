import { useState, useEffect, useRef } from "react"
import "./styles/global.css"
import type { PassSummary, TelemetryData } from "./types"
import { connectSimulation } from "./api"
import Header from "./components/Header"
import SimulationControls from "./components/SimulationControls"
import SimulationFeed from "./components/SimulationFeed"
import PassDetail from "./components/PassDetail"

export default function App() {
  const [passes, setPasses] = useState<PassSummary[]>([])
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null)
  const [selectedPassNumber, setSelectedPassNumber] = useState<number | null>(null)

  // Simulation states
  const [simStatus, setSimStatus] = useState<"idle" | "running" | "complete">("idle")
  const [simSpeed, setSimSpeed] = useState<number>(5)
  const [newPassIds, setNewPassIds] = useState<number[]>([])
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const simEventSourceRef = useRef<EventSource | null>(null)
  const telemetryCacheRef = useRef<Record<number, TelemetryData>>({})

  // Auto-start simulation on first load to immediately show data coming in
  useEffect(() => {
    handleStartSimulation()
    return () => {
      if (simEventSourceRef.current) {
        simEventSourceRef.current.close()
      }
    }
  }, [])

  const handleStartSimulation = () => {
    if (simEventSourceRef.current) {
      simEventSourceRef.current.close()
    }
    setPasses([])
    setTelemetry(null)
    setSelectedPassNumber(null)
    setNewPassIds([])
    setSimStatus("running")
    setErrorMsg(null)
    telemetryCacheRef.current = {}

    const source = connectSimulation(
      simSpeed,
      (pass) => {
        setPasses((prev) => {
          const updated = [...prev, pass]
          setSelectedPassNumber(pass.pass_number)
          return updated
        })
        setNewPassIds((prev) => [...prev, pass.pass_number])
        setTimeout(() => {
          setNewPassIds((prev) => prev.filter((id) => id !== pass.pass_number))
        }, 1000)
      },
      (tel) => {
        setPasses((currentPasses) => {
          if (currentPasses.length > 0) {
            const latestPass = currentPasses[currentPasses.length - 1]
            telemetryCacheRef.current[latestPass.pass_number] = tel
            setSelectedPassNumber((activeNum) => {
              if (activeNum === latestPass.pass_number || activeNum === null) {
                setTelemetry(tel)
              }
              return activeNum
            })
          }
          return currentPasses
        })
      },
      () => {
        setSimStatus("complete")
        if (simEventSourceRef.current) {
          simEventSourceRef.current.close()
          simEventSourceRef.current = null
        }
      }
    )

    source.onerror = () => {
      setErrorMsg("Connection to live telemetry feed lost.")
      setSimStatus("idle")
      if (simEventSourceRef.current) {
        simEventSourceRef.current.close()
        simEventSourceRef.current = null
      }
    }

    simEventSourceRef.current = source
  }

  const handleStopSimulation = () => {
    if (simEventSourceRef.current) {
      simEventSourceRef.current.close()
      simEventSourceRef.current = null
    }
    setSimStatus("idle")
  }

  // Handle active telemetry selection in simulation mode (from cache)
  useEffect(() => {
    if (!selectedPassNumber) return
    const tel = telemetryCacheRef.current[selectedPassNumber]
    if (tel) {
      setTelemetry(tel)
    } else {
      setTelemetry(null)
    }
  }, [selectedPassNumber])

  // In-line override update handler to keep UI state consistent
  const handleOverrideSuccess = (noteId: string, severity: string, comment: string) => {
    setPasses((prev) =>
      prev.map((p) => {
        const hasNote = p.decisions.some((d) => d.note_id === noteId)
        if (!hasNote) return p

        const updatedDecisions = p.decisions.map((d) => {
          if (d.note_id === noteId) {
            return {
              ...d,
              severity: severity as any,
              explanation: `${d.explanation} | Operator Override: ${comment}`,
            }
          }
          return d
        })

        const SEVERITY_ORDER: Record<string, number> = {
          "Nominal": 0,
          "Monitor": 1,
          "Investigate": 2,
          "Immediate Action": 3,
        }
        const overall_severity = updatedDecisions.reduce((worst, curr) => {
          const wIdx = SEVERITY_ORDER[worst] || 0
          const cIdx = SEVERITY_ORDER[curr.severity] || 0
          return cIdx > wIdx ? curr.severity : worst
        }, "Nominal")

        return {
          ...p,
          overall_severity,
          decisions: updatedDecisions,
        }
      })
    )
  }

  const selectedPass = passes.find((p) => p.pass_number === selectedPassNumber) || null

  return (
    <div className="app-shell">
      <Header />

      {errorMsg && (
        <div
          style={{
            backgroundColor: "var(--severity-immediate)",
            color: "#ffffff",
            padding: "10px 24px",
            fontSize: "13px",
            fontWeight: 500,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>{errorMsg}</span>
          <button
            onClick={handleStartSimulation}
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              color: "#ffffff",
              border: "1px solid rgba(255, 255, 255, 0.4)",
              padding: "4px 12px",
              fontSize: "11px",
            }}
          >
            Reconnect Downlink
          </button>
        </div>
      )}

      <main className="main-container">
        {/* Left Panel */}
        <section className="left-panel">
          <SimulationControls
            simStatus={simStatus}
            simSpeed={simSpeed}
            setSimSpeed={setSimSpeed}
            onStart={handleStartSimulation}
            onStop={handleStopSimulation}
            passesReceived={passes.length}
            totalPasses={8}
          />
          <SimulationFeed
            passes={passes}
            selectedPassNumber={selectedPassNumber}
            setSelectedPassNumber={setSelectedPassNumber}
            simStatus={simStatus}
            newPassIds={newPassIds}
          />
        </section>

        {/* Right Panel */}
        <section className="right-panel">
          {simStatus === "complete" && (
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.1)",
                border: "1px solid var(--severity-nominal)",
                borderRadius: "var(--radius-card)",
                padding: "12px 16px",
                marginBottom: "16px",
                fontSize: "13px",
                color: "var(--severity-nominal)",
                fontWeight: 500,
              }}
            >
              ✓ Live simulation completed. Total orbits streamed: 8.
            </div>
          )}

          {passes.length === 0 ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                fontSize: "14px",
                gap: "12px",
              }}
            >
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  backgroundColor: "var(--severity-immediate)",
                  animation: "pulse-immediate 1s ease-in-out infinite",
                }}
              />
              Awaiting Live Telemetry Connection... Click 'Start Simulation' to establish the satellite downlink.
            </div>
          ) : (
            <PassDetail
              passSummary={selectedPass}
              telemetry={telemetry}
              onOverrideSuccess={handleOverrideSuccess}
            />
          )}
        </section>
      </main>
    </div>
  )
}
