import React from "react"
import { cn } from "@/lib/utils"
import { DollarSign, Calendar, TrendingUp, ShieldCheck, ArrowUpRight, ArrowDownRight } from "lucide-react"

interface DomainHealthItemProps {
  title: string
  score: number
  weight?: string
  icon: "cost" | "schedule" | "progress" | "quality"
  onClick?: () => void
}

export const DomainHealthBar: React.FC<DomainHealthItemProps> = ({
  title,
  score,
  weight,
  icon,
  onClick,
}) => {
  const iconConfig = {
    cost: { icon: DollarSign, color: "text-red-600", bg: "bg-red-50" },
    schedule: { icon: Calendar, color: "text-amber-600", bg: "bg-amber-50" },
    progress: { icon: TrendingUp, color: "text-yellow-600", bg: "bg-yellow-50" },
    quality: { icon: ShieldCheck, color: "text-emerald-600", bg: "bg-emerald-50" },
  }[icon]

  const Icon = iconConfig.icon

  // Color progress bar
  let barColor = "bg-red-500"
  if (score >= 80) barColor = "bg-emerald-500"
  else if (score >= 60) barColor = "bg-amber-500"
  else if (score >= 40) barColor = "bg-yellow-500"

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex-1 p-3.5 bg-white rounded-xl border border-slate-200 shadow-sm transition-all hover:border-slate-300",
        onClick && "cursor-pointer hover:shadow-md"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={cn("p-1.5 rounded-lg", iconConfig.bg)}>
            <Icon className={cn("w-4 h-4", iconConfig.color)} />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-800 tracking-wider uppercase">{title}</div>
            {weight && <div className="text-[10px] text-slate-400">Weight {weight}</div>}
          </div>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold text-slate-900 tabular-nums">{score}</span>
          <span className="text-xs text-slate-400 font-medium">/100</span>
        </div>
      </div>

      {/* Progress track */}
      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700 ease-out", barColor)}
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
    </div>
  )
}

interface MetricCardProps {
  title: string
  value: string | number
  delta?: {
    value: string | number
    label: string
    isPositive?: boolean
  }
  variant?: "critical" | "warning" | "observation" | "default" | "success"
  icon?: React.ReactNode
  className?: string
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  delta,
  variant = "default",
  icon,
  className,
}) => {
  const variantStyles = {
    critical: "border-red-200 bg-red-50/40 text-red-700",
    warning: "border-amber-200 bg-amber-50/40 text-amber-800",
    observation: "border-yellow-200 bg-yellow-50/40 text-yellow-800",
    success: "border-emerald-200 bg-emerald-50/40 text-emerald-800",
    default: "border-slate-200 bg-white text-slate-900",
  }[variant]

  const titleStyles = {
    critical: "text-red-700",
    warning: "text-amber-800",
    observation: "text-yellow-800",
    success: "text-emerald-800",
    default: "text-slate-500",
  }[variant]

  return (
    <div
      className={cn(
        "p-4 rounded-xl border shadow-sm flex flex-col justify-between transition-all hover:shadow-md",
        variantStyles,
        className
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className={cn("text-xs font-bold uppercase tracking-wider", titleStyles)}>
          {title}
        </span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>

      <div className="my-1">
        <span className="text-3xl font-bold tracking-tight tabular-nums">{value}</span>
      </div>

      {delta && (
        <div className="flex items-center gap-1 text-xs text-slate-500 mt-1">
          <span>{delta.label}</span>
          <span
            className={cn(
              "inline-flex items-center font-semibold",
              delta.isPositive ? "text-emerald-600" : "text-red-600"
            )}
          >
            {delta.isPositive ? (
              <ArrowUpRight className="w-3.5 h-3.5" />
            ) : (
              <ArrowDownRight className="w-3.5 h-3.5" />
            )}
            {delta.value}
          </span>
        </div>
      )}
    </div>
  )
}
