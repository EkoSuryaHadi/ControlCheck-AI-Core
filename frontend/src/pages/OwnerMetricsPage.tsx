import React from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, AlertTriangle, BarChart3, CheckCircle2, FolderKanban, MessageSquare, Users } from "lucide-react"
import { api } from "@/lib/api"

const MetricCard: React.FC<{ label: string; value: string | number; icon: React.ElementType; tone: string }> = ({ label, value, icon: Icon, tone }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><div className={`rounded-lg p-2 ${tone}`}><Icon className="h-4 w-4" /></div></div><div className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{value}</div></div>
)

export const OwnerMetricsPage: React.FC = () => {
  const metrics = useQuery({ queryKey: ["owner-metrics"], queryFn: api.owner.metrics, staleTime: 30_000 })
  if (metrics.isLoading) return <div className="py-16 text-center text-sm text-slate-500">Loading beta usage metrics…</div>
  if (metrics.isError) return <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">Metrics are only available to an authorized owner account.</div>
  const data = metrics.data!
  return <div className="mx-auto max-w-6xl space-y-6 pb-12"><div><h1 className="text-xl font-bold tracking-tight text-slate-900">Beta Usage Metrics</h1><p className="mt-1 text-xs text-slate-500">First-party product analytics. Workbook contents are never included in telemetry.</p></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><MetricCard label="Registrations" value={data.registrations} icon={Users} tone="bg-blue-50 text-blue-600" /><MetricCard label="Active users" value={data.active_users} icon={Activity} tone="bg-indigo-50 text-indigo-600" /><MetricCard label="Projects" value={data.projects} icon={FolderKanban} tone="bg-emerald-50 text-emerald-600" /><MetricCard label="Feedback" value={data.feedback_count} icon={MessageSquare} tone="bg-purple-50 text-purple-600" /><MetricCard label="Accepted uploads" value={data.uploads_accepted} icon={CheckCircle2} tone="bg-cyan-50 text-cyan-600" /><MetricCard label="Completed analyses" value={data.analyses_completed} icon={BarChart3} tone="bg-violet-50 text-violet-600" /><MetricCard label="Result-use rate" value={`${Math.round(data.result_use_rate * 100)}%`} icon={BarChart3} tone="bg-amber-50 text-amber-600" /><MetricCard label="Error rate" value={`${Math.round(data.error_rate * 100)}%`} icon={AlertTriangle} tone="bg-rose-50 text-rose-600" /></div><div className="rounded-xl border border-slate-200 bg-white p-5 text-xs text-slate-500 shadow-sm">Useful feedback rate: <span className="font-semibold text-slate-900">{Math.round(data.useful_feedback_rate * 100)}%</span> · Result-use events: <span className="font-semibold text-slate-900">{data.result_use_events}</span></div></div>
}
