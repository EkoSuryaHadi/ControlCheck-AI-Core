import React, { useEffect, useState } from "react"
import { Calendar, Loader2 } from "lucide-react"
import { api, AnalysisSummary } from "@/lib/api"
import { useProject } from "@/context/ProjectContext"

export const SchedulePage: React.FC = () => {
  const { currentProject, currentRun } = useProject()
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  useEffect(() => { if (currentProject?.id && currentRun?.id) void api.runs.getSummary(currentProject.id, currentRun.id).then(setSummary).catch(() => setSummary(null)) }, [currentProject?.id, currentRun?.id])
  if (!currentProject || !currentRun) return <Empty text="Select a project with a completed analysis run to review schedule data." />
  if (!summary) return <div className="flex justify-center p-12"><Loader2 className="animate-spin" /></div>
  if (!summary.schedule.activity_count) return <Empty text="No schedule activities were included in this import." />
  return <div className="mx-auto max-w-7xl space-y-6 pb-12"><div><h1 className="text-xl font-bold text-slate-900">Schedule Health</h1><p className="mt-1 text-xs text-slate-500">Activities imported from the selected MPP analysis run.</p></div><div className="grid gap-4 sm:grid-cols-4"><Metric label="Activities" value={summary.schedule.activity_count} /><Metric label="Critical" value={summary.schedule.critical_count} /><Metric label="Negative float" value={summary.schedule.negative_float_count} /><Metric label="High float" value={summary.schedule.high_float_count} /></div><div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase text-slate-500"><tr><th className="p-3">Activity</th><th>WBS</th><th>Finish</th><th className="text-right">Plan</th><th className="text-right">Actual</th><th className="p-3 text-right">Float</th></tr></thead><tbody className="divide-y divide-slate-100">{summary.schedule.activities.map(item => <tr key={item.activity_id}><td className="p-3"><b>{item.activity_id}</b><div className="mt-1 text-slate-500">{item.activity_name}</div></td><td>{item.wbs_code || "—"}</td><td>{item.baseline_finish}</td><td className="text-right">{(item.planned_progress * 100).toFixed(0)}%</td><td className="text-right">{(item.actual_progress * 100).toFixed(0)}%</td><td className="p-3 text-right font-semibold">{item.total_float_days}d</td></tr>)}</tbody></table></div></div>
}
const Metric = ({ label, value }: { label: string; value: number }) => <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="text-[10px] font-bold uppercase text-slate-400">{label}</div><div className="mt-1 text-2xl font-bold">{value}</div></div>
const Empty = ({ text }: { text: string }) => <div className="mx-auto max-w-3xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900"><Calendar className="mb-3 h-5 w-5" />{text}</div>
