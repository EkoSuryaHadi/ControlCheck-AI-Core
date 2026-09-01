import React, { useEffect, useState } from "react"
import { DollarSign, Loader2 } from "lucide-react"
import { api, AnalysisSummary } from "@/lib/api"
import { availabilityMessage } from "@/lib/analysis-summary.js"
import { useProject } from "@/context/ProjectContext"

const money = (value: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(value || 0)

export const CostPage: React.FC = () => {
  const { currentProject, currentRun } = useProject()
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  useEffect(() => { if (currentProject?.id && currentRun?.id) void api.runs.getSummary(currentProject.id, currentRun.id).then(setSummary).catch(() => setSummary(null)) }, [currentProject?.id, currentRun?.id])
  if (!currentProject || !currentRun) return <Empty text="Select a project with a completed analysis run to review cost data." />
  if (!summary) return <div className="flex justify-center p-12 text-slate-500"><Loader2 className="animate-spin" /></div>
  if (!summary.cost.available) return <Empty text={availabilityMessage(summary.cost, "cost")} />
  return <div className="mx-auto max-w-5xl space-y-6 pb-12"><div><h1 className="text-xl font-bold text-slate-900">Cost Performance</h1><p className="mt-1 text-xs text-slate-500">Actual values from the selected analysis run.</p></div><div className="grid gap-4 sm:grid-cols-3"><Metric label="Budget" value={money(summary.cost.budget_total)} /><Metric label="Actual cost" value={money(summary.cost.actual_total)} /><Metric label="Commitments" value={money(summary.cost.commitment_total)} /></div></div>
}
const Metric = ({ label, value }: { label: string; value: string }) => <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="text-[10px] font-bold uppercase text-slate-400">{label}</div><div className="mt-2 text-xl font-bold text-slate-900">{value}</div></div>
const Empty = ({ text }: { text: string }) => <div className="mx-auto max-w-3xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900"><DollarSign className="mb-3 h-5 w-5" />{text}</div>
