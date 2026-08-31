import React, { useEffect, useState } from "react"
import { TrendingUp, Loader2 } from "lucide-react"
import { api, AnalysisSummary } from "@/lib/api"
import { availabilityMessage } from "@/lib/analysis-summary.js"
import { useProject } from "@/context/ProjectContext"

export const ProgressPage: React.FC = () => {
  const { currentProject, currentRun } = useProject()
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  useEffect(() => { if (currentProject?.id && currentRun?.id) void api.runs.getSummary(currentProject.id, currentRun.id).then(setSummary).catch(() => setSummary(null)) }, [currentProject?.id, currentRun?.id])
  if (!currentProject || !currentRun) return <Empty text="Select a project with a completed analysis run to review progress." />
  if (!summary) return <div className="flex justify-center p-12"><Loader2 className="animate-spin" /></div>
  if (!summary.progress.available) return <Empty text="No progress data was included in this import." />
  return <div className="mx-auto max-w-5xl space-y-6 pb-12"><div><h1 className="text-xl font-bold text-slate-900">Progress</h1><p className="mt-1 text-xs text-slate-500">{availabilityMessage(summary.progress, "progress")}</p></div><div className="grid gap-4 sm:grid-cols-3"><Metric label="Planned" value={summary.progress.planned_progress} /><Metric label="Actual" value={summary.progress.actual_progress} /><Metric label="Variance" value={summary.progress.variance} /></div></div>
}
const Metric = ({ label, value }: { label: string; value: number }) => <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="text-[10px] font-bold uppercase text-slate-400">{label}</div><div className="mt-2 text-2xl font-bold">{(value * 100).toFixed(1)}%</div></div>
const Empty = ({ text }: { text: string }) => <div className="mx-auto max-w-3xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900"><TrendingUp className="mb-3 h-5 w-5" />{text}</div>
