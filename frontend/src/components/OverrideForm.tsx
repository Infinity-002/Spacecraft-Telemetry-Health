import { useState } from "react"

interface OverrideFormProps {
  onSubmit: (severity: string, comment: string) => void
  onCancel: () => void
}

export default function OverrideForm({ onSubmit, onCancel }: OverrideFormProps) {
  const [severity, setSeverity] = useState("Nominal")
  const [comment, setComment] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!comment.trim()) return
    onSubmit(severity, comment)
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginTop: "12px",
        backgroundColor: "var(--bg-elevated)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        padding: "12px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
      }}
    >
      <div style={{ display: "flex", gap: "8px", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
          Override Severity
        </span>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          style={{ padding: "4px 8px", fontSize: "12px" }}
        >
          <option value="Nominal">Nominal</option>
          <option value="Monitor">Monitor</option>
          <option value="Investigate">Investigate</option>
          <option value="Immediate Action">Immediate Action</option>
        </select>
      </div>

      <textarea
        rows={2}
        placeholder="Reason for override..."
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        required
        style={{
          width: "100%",
          padding: "6px",
          fontSize: "12px",
          resize: "none",
        }}
      />

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
        <button
          type="button"
          onClick={onCancel}
          style={{
            backgroundColor: "transparent",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
            padding: "4px 10px",
            fontSize: "12px",
          }}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!comment.trim()}
          style={{
            padding: "4px 10px",
            fontSize: "12px",
          }}
        >
          Submit Override
        </button>
      </div>
    </form>
  )
}
