import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts"
import type { TelemetryData } from "../types"

interface TelemetryChartProps {
  telemetry: TelemetryData
  flaggedSubsystems: string[]
  startTime: string
  endTime: string
}

export default function TelemetryChart({
  telemetry,
  flaggedSubsystems,
  startTime,
  endTime,
}: TelemetryChartProps) {
  const getParametersToDraw = () => {
    const list: string[] = []
    const subs = flaggedSubsystems.map((s) => s.toUpperCase())

    if (subs.includes("EPS")) {
      list.push("batt_voltage", "batt_soc", "batt_current")
    }
    if (subs.includes("TCS")) {
      list.push("temp_batt", "temp_tx")
    }
    if (subs.includes("ADCS")) {
      list.push("rw_speed", "rw_current", "pointing_error")
    }

    if (list.length === 0) {
      list.push("batt_voltage", "temp_batt")
    }

    return list.slice(0, 5)
  }

  const parameters = getParametersToDraw()

  const startMs = new Date(startTime).getTime()
  const endMs = new Date(endTime).getTime()

  const paddingMs = 5 * 60 * 1000
  const paddedStart = startMs - paddingMs
  const paddedEnd = endMs + paddingMs

  const chartData: any[] = []
  telemetry.timestamps.forEach((timestampStr, idx) => {
    const timeMs = new Date(timestampStr).getTime()
    if (timeMs >= paddedStart && timeMs <= paddedEnd) {
      const dataPoint: any = {
        time: new Date(timestampStr).toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: "UTC",
        }),
        timestampVal: timeMs,
      }
      parameters.forEach((param) => {
        const val = telemetry.columns[param] ? telemetry.columns[param][idx] : null
        if (val !== undefined && val !== null && !isNaN(val)) {
          dataPoint[param] = parseFloat(val.toFixed(3))
        }
      })
      chartData.push(dataPoint)
    }
  })

  const COLORS = {
    batt_voltage: "var(--accent)",
    batt_soc: "var(--severity-nominal)",
    batt_current: "var(--severity-monitor)",
    temp_batt: "var(--severity-investigate)",
    temp_tx: "var(--severity-immediate)",
    rw_speed: "var(--accent)",
    rw_current: "var(--severity-monitor)",
    pointing_error: "var(--severity-immediate)",
  }

  const getColor = (param: string) => {
    return (COLORS as any)[param] || "var(--text-secondary)"
  }

  const getLimits = (param: string) => {
    if (param === "batt_voltage") return { warn: [26.5, 31.5], crit: [22.0, 34.0] }
    if (param === "temp_batt") return { warn: [0.0, 25.0], crit: [-20.0, 45.0] }
    if (param === "temp_tx") return { warn: [0.0, 50.0], crit: [-20.0, 80.0] }
    if (param === "pointing_error") return { warn: [0.1, 0.5], crit: [1.0] }
    if (param === "batt_soc") return { warn: [40.0], crit: [15.0] }
    if (param === "rw_speed") return { warn: [-3000.0, 3000.0], crit: [-6000.0, 6000.0] }
    if (param === "rw_current") return { warn: [1.2, 1.8], crit: [2.5] }
    return null
  }

  const hasValidData = chartData.some((dp) =>
    Object.keys(dp).some(
      (key) => key !== "time" && key !== "timestampVal" && dp[key] !== undefined && dp[key] !== null
    )
  )

  if (!hasValidData) {
    return (
      <div
        style={{
          minHeight: "200px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          color: "var(--severity-immediate)",
          fontSize: "12px",
          backgroundColor: "#1a1213",
          border: "1px dashed var(--severity-immediate)",
          borderRadius: "var(--radius-card)",
          padding: "24px",
          textAlign: "center",
        }}
      >
        <span style={{ fontSize: "20px" }}>⚠️</span>
        <span style={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Telemetry Packet Loss (Signal Dropout)
        </span>
        <span style={{ color: "var(--text-secondary)", fontSize: "11px", maxWidth: "420px", lineHeight: "1.4" }}>
          No downlinked telemetry frames were decoded during this pass. Subsystem sensors are offline.
        </span>
      </div>
    )
  }

  return (
    <div
      style={{
        height: "240px",
        position: "relative",
        width: "100%",
      }}
    >
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "8px" }}>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          {parameters.map((param) => (
            <div key={param} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: getColor(param) }} />
              <span className="mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                {param}
              </span>
            </div>
          ))}
        </div>
      </div>

      {chartData.length === 0 ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "180px", color: "var(--text-muted)", fontSize: "12px" }}>
          No telemetry points in time-slice.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={chartData} margin={{ left: -20, right: 10, top: 5, bottom: 5 }}>
            <CartesianGrid stroke="var(--border)" strokeOpacity={0.3} strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
            <YAxis stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border)" }}
              itemStyle={{ fontSize: 11, color: "var(--text-primary)" }}
              labelStyle={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" }}
            />
            {parameters.map((param) => (
              <Line
                key={param}
                type="monotone"
                dataKey={param}
                stroke={getColor(param)}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}

            {parameters.length > 0 && getLimits(parameters[0]) && (
              <>
                {getLimits(parameters[0])?.warn.map((val, idx) => (
                  <ReferenceLine
                    key={`w-${idx}`}
                    y={val}
                    stroke="var(--severity-monitor)"
                    strokeDasharray="3 3"
                    label={{ value: "Caution", fill: "var(--severity-monitor)", position: "right", fontSize: 9 }}
                  />
                ))}
                {getLimits(parameters[0])?.crit.map((val, idx) => (
                  <ReferenceLine
                    key={`c-${idx}`}
                    y={val}
                    stroke="var(--severity-immediate)"
                    strokeDasharray="3 3"
                    label={{ value: "Critical", fill: "var(--severity-immediate)", position: "right", fontSize: 9 }}
                  />
                ))}
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
