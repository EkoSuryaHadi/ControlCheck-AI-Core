import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CheckCircle2, Loader2, AlertTriangle, RefreshCw, ServerCog, SearchCheck, FileCheck2 } from "lucide-react"
import { api, AnalysisRun } from "@/lib/api"
import { useProject } from "@/context/ProjectContext"
import { trackEvent } from "@/lib/analytics"

const POLL_INTERVAL_MS = 2500
const isSuccessfulStatus = (status: unknown) => ["succeeded", "completed"].includes(String(status || "").toLowerCase())

export const AnalysisProgressPage: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, currentRun, refreshHealthAndFindings } = useProject()
  const [run, setRun] = useState<AnalysisRun | null>(currentRun)
  const [pollError, setPollError] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const storedSummary = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("controlcheck_last_analysis_summary") || "{}")
    } catch {
      return {}
    }
  }, [])

  const targetRunId = run?.id || currentRun?.id || storedSummary.runId || null
  const normalizedStatus = String(run?.status || "running").toLowerCase()
  const completed = isSuccessfulStatus(normalizedStatus)
  const failed = normalizedStatus === "failed"
  const running = !completed && !failed

  const fetchRun = async () => {
    if (!currentProject?.id || !targetRunId) return
    setIsRefreshing(true)
    try {
      const response = await api.runs.list(currentProject.id)
      const items: AnalysisRun[] = Array.isArray(response) ? response : response?.items || []
      const latest = items.find((item) => item.id === targetRunId)
      if (!latest) throw new Error("The analysis run is not present in the current project run list.")
      setRun(latest)
      setPollError(null)
      if (isSuccessfulStatus(latest.status)) await refreshHealthAndFindings()
    } catch (err: any) {
      setPollError(err?.response?.data?.error?.message || err?.message || "Could not refresh analysis status.")
    } finally {
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    trackEvent("analysis_progress_viewed", { run_id: targetRunId || "unknown" })
    if (!currentProject?.id || !targetRunId) return

    void fetchRun()
    if (completed || failed) return
    const interval = window.setInterval(() => void fetchRun(), POLL_INTERVAL_MS)
    return () => window.clearInterval(interval)
  }, [currentProject?.id, targetRunId, completed, failed])

  useEffect(() => {
    if (!completed || !run?.id) return
    trackEvent("analysis_completed_confirmed", { run_id: run.id, finding_count: run.finding_count ?? 0 })
  }, [completed, run?.id, run?.finding_count])

  if (!targetRunId) {
    return <div className="mx-auto max-w-3xl rounded-2xl border border-amber-200 bg-amber-50 p-6"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" /><div><h1 className="font-bold text-amber-900">No analysis run selected</h1><p className="mt-2 text-sm leading-6 text-amber-800">Upload a project-control workbook first. ControlCheck will only show progress for a real server-created run.</p><button onClick={() => navigate("/data")} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white">Go to Data Import</button></div></div></div>
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><div className="text-xs font-bold uppercase tracking-wider text-blue-600">Analysis Run</div><h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Server analysis status</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">This page polls the real project analysis-run record. It does not advance using timers or simulated progress.</p></div>
        <button onClick={() => void fetchRun()} disabled={isRefreshing} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} /> Refresh</button>
      </div>

      <section className={`rounded-2xl border p-6 shadow-sm ${completed ? "border-emerald-200 bg-emerald-50" : failed ? "border-red-200 bg-red-50" : "border-blue-200 bg-blue-50"}`}>
        <div className="flex items-start gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${completed ? "bg-emerald-100 text-emerald-700" : failed ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"}`}>{completed ? <CheckCircle2 className="h-6 w-6" /> : failed ? <AlertTriangle className="h-6 w-6" /> : <Loader2 className="h-6 w-6 animate-spin" />}</div>
          <div className="min-w-0 flex-1"><div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Run {targetRunId}</div><h2 className="mt-1 text-lg font-bold text-slate-900">{completed ? "Analysis completed" : failed ? "Analysis failed" : "Analysis in progress"}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{completed ? "The server confirmed this analysis run is complete. Findings and health results can now be reviewed." : failed ? "The server marked this analysis run as failed. Review the source file or backend error before retrying." : "ControlCheck is waiting for the server to mark this run completed or failed."}</p></div>
        </div>
      </section>

      {pollError && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">{pollError}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div><div className="text-xs font-bold uppercase tracking-wider text-slate-400">Pipeline reference</div><h2 className="mt-1 text-base font-bold">What the analysis run performs</h2><p className="mt-1 text-xs leading-5 text-slate-500">The current API does not expose a granular stage field, so these are explanatory pipeline stages—not a simulated progress meter.</p></div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <PipelineCard icon={FileCheck2} title="Validate input" detail="Workbook structure, canonical data and quality checks." />
          <PipelineCard icon={SearchCheck} title="Run controls" detail="Deterministic project-control rules and consistency checks." />
          <PipelineCard icon={ServerCog} title="Persist results" detail="Analysis run, evidence-backed findings and health outputs." />
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Server Status" value={normalizedStatus} />
        <Metric label="Rules" value={run?.rule_count != null ? String(run.rule_count) : "—"} />
        <Metric label="Findings" value={run?.finding_count != null ? String(run.finding_count) : "—"} />
        <Metric label="Duration" value={run?.duration_ms != null ? `${run.duration_ms} ms` : "—"} />
      </section>

      {completed && <div className="flex flex-wrap gap-3"><button onClick={() => navigate("/findings")} className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white">Review Findings</button><button onClick={() => navigate("/dashboard")} className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700">Open Dashboard</button></div>}
      {failed && <button onClick={() => navigate("/data")} className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white">Return to Data Import</button>}
    </div>
  )
}

const PipelineCard = ({ icon: Icon, title, detail }: { icon: React.ElementType; title: string; detail: string }) => <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"><Icon className="h-5 w-5 text-blue-600" /><div className="mt-3 text-sm font-bold text-slate-900">{title}</div><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p></div>
const Metric = ({ label, value }: { label: string; value: string }) => <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div><div className="mt-2 break-all text-sm font-black capitalize text-slate-900">{value}</div></div>

export default AnalysisProgressPage

