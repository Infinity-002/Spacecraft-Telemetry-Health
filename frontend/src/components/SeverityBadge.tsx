interface SeverityBadgeProps {
  severity: string
}

export default function SeverityBadge({ severity }: SeverityBadgeProps) {
  const normClass = () => {
    const s = severity.toLowerCase()
    if (s.includes("immediate")) return "badge-immediate"
    if (s.includes("investigate")) return "badge-investigate"
    if (s.includes("monitor")) return "badge-monitor"
    return "badge-nominal"
  }

  return (
    <span className={`badge ${normClass()}`}>
      {severity}
    </span>
  )
}
