import React from "react"
import { cn } from "@/lib/utils"

export type SeverityType = "critical" | "warning" | "observation"
export type StatusType = "open" | "in_review" | "resolved" | "dismissed"

interface SeverityBadgeProps {
  severity: SeverityType | string
  className?: string
  showDot?: boolean
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  className,
  showDot = true,
}) => {
  const norm = severity.toLowerCase()

  const config = {
    critical: {
      bg: "bg-red-50 text-red-700 border-red-200",
      dot: "bg-red-500",
      label: "Critical",
    },
    warning: {
      bg: "bg-amber-50 text-amber-800 border-amber-200",
      dot: "bg-amber-500",
      label: "Warning",
    },
    observation: {
      bg: "bg-yellow-50 text-yellow-800 border-yellow-200",
      dot: "bg-yellow-500",
      label: "Observation",
    },
  }[norm] || {
    bg: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
    label: severity,
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border",
        config.bg,
        className
      )}
    >
      {showDot && <span className={cn("w-1.5 h-1.5 rounded-full", config.dot)} />}
      {config.label}
    </span>
  )
}

interface StatusBadgeProps {
  status: StatusType | string
  className?: string
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  const norm = status.toLowerCase().replace(/_/g, " ")

  const config = {
    open: "bg-blue-50 text-blue-700 border-blue-200",
    "in review": "bg-purple-50 text-purple-700 border-purple-200",
    resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dismissed: "bg-slate-100 text-slate-600 border-slate-200",
  }[norm] || "bg-slate-100 text-slate-700 border-slate-200"

  const label = norm.charAt(0).toUpperCase() + norm.slice(1)

  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border", config, className)}>
      {label}
    </span>
  )
}
