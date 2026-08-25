import React from "react"
import { cn } from "@/lib/utils"

interface HealthGaugeProps {
  score: number | null
  label?: string
  lastUpdated?: string
  size?: number
  className?: string
}

export const HealthGauge: React.FC<HealthGaugeProps> = ({
  score,
  label = "MODERATE",
  lastUpdated = "Last update: 2 minutes ago",
  size = 180,
  className,
}) => {
  const strokeWidth = 14
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const isComputed = score !== null
  const normalizedScore = isComputed ? Math.max(0, Math.min(100, score)) : 0
  const strokeDashoffset = circumference - (normalizedScore / 100) * circumference

  // Color mapping based on score
  let strokeColor = "#EF4444" // Critical (<40)
  let statusText = label || "CRITICAL RISK"

  if (!isComputed) {
    strokeColor = "#94A3B8"
  } else if (normalizedScore >= 80) {
    strokeColor = "#2E8B57" // Good
    statusText = label || "HEALTHY"
  } else if (normalizedScore >= 60) {
    strokeColor = "#F59E0B" // Moderate / Needs Attention
    statusText = label || "MODERATE"
  } else if (normalizedScore >= 40) {
    strokeColor = "#EAB308" // At Risk
    statusText = label || "AT RISK"
  }

  return (
    <div className={cn("flex flex-col items-center justify-center p-4 bg-white rounded-xl border border-slate-200 shadow-sm", className)}>
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#F1F5F9"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-4xl font-bold tracking-tight text-slate-900 tabular-nums">
            {isComputed ? normalizedScore : "—"}
          </span>
          <span className="text-xs font-semibold tracking-wider text-slate-600 uppercase mt-0.5">
            {statusText}
          </span>
        </div>
      </div>

      {lastUpdated && (
        <span className="text-xs text-slate-400 mt-3">{lastUpdated}</span>
      )}
    </div>
  )
}
