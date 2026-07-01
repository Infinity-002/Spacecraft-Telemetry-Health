export interface Decision {
  mission_id: string
  timestamp: string
  note_id: string
  subsystem: string
  fault_type: string
  urgency: string
  telemetry_score: number
  telemetry_pvalue: number
  note_weight: number
  severity: "Nominal" | "Monitor" | "Investigate" | "Immediate Action"
  confidence: number
  uncertainty: number
  conflict: number
  action: string
  explanation: string
  is_rule_override?: boolean
  violated_rules?: string[]
  operator_note?: string
}

export interface PassSummary {
  mission_id: string
  pass_number: number
  start_time: string
  end_time: string
  overall_severity: string
  overall_confidence: number
  overall_uncertainty: number
  flagged_subsystems: string[]
  num_notes: number
  num_rule_overrides: number
  summary_text: string
  decisions: Decision[]
  trend_alerts?: TrendAlert[]
}

export interface TrendAlert {
  mission_id?: string
  parameter: string
  direction: string
  slope_per_hour: number
  hours_to_warning: number | null
  confidence: number
  message: string
}

export interface TelemetryData {
  timestamps: string[]
  columns: Record<string, number[]>
}
