interface ConfidenceBarProps {
  confidence: number
  uncertainty: number
}

export default function ConfidenceBar({ confidence, uncertainty }: ConfidenceBarProps) {
  const confWidth = `${Math.min(100, confidence * 100)}%`
  const uncertWidth = `${Math.min(100 - confidence * 100, uncertainty * 100)}%`

  return (
    <div
      style={{
        width: "100%",
        height: "4px",
        backgroundColor: "var(--bg-elevated)",
        borderRadius: "2px",
        overflow: "hidden",
        display: "flex",
        marginTop: "8px",
      }}
    >
      <div
        style={{
          width: confWidth,
          height: "100%",
          backgroundColor: "var(--accent)",
        }}
        title={`Confidence: ${(confidence * 100).toFixed(0)}%`}
      />
      <div
        style={{
          width: uncertWidth,
          height: "100%",
          backgroundColor: "#f59e0b", // Amber fill for uncertainty
        }}
        title={`Uncertainty: ${(uncertainty * 100).toFixed(0)}%`}
      />
    </div>
  )
}
