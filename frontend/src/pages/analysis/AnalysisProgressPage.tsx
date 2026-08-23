import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CheckCircle2, Loader2, ShieldCheck, Sparkles, UploadCloud, SearchCheck } from "lucide-react"
import { trackEvent } from "@/lib/analytics"

const stages = [
  { label: "Uploading project data", detail: "Workbook securely received and linked to the active project.", icon: UploadCloud },
  { label: "Validating data", detail: "Schema, required fields, data types and project relationships checked.", icon: ShieldCheck },
  { label: "Running deterministic checks", detail: "Control rules and cross-data consistency checks evaluated.", icon: SearchCheck },
  { label: "AI-assisted analysis", detail: "Findings are summarized with evidence context and recommended action.", icon: Sparkles },
]

export const AnalysisProgressPage: React.FC = () => {
  const navigate = useNavigate()
  const [activeStage, setActiveStage] = useState(0)
  const [ready, setReady] = useState(false)

  const summary = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("controlcheck_last_analysis_summary") || "{}")
    } catch {
      return {}
    }
  }, [])

  useEffect(() => {
    trackEvent("first_audit_progress_viewed", { run_id: summary.runId || "unknown" })

    const timers = [
      window.setTimeout(() => setActiveStage(1), 700),
      window.setTimeout(() => setActiveStage(2), 1500),
      window.setTimeout(() => setActiveStage(3), 2400),
      window.setTimeout(() => {
        setReady(true)
        trackEvent("first_audit_findings_ready", {
          run_id: summary.runId || "unknown",
          finding_count: summary.findingCount || 0,
        })
      }, 3400),
    ]

    return () => timers.forEach(window.clearTimeout)
  }, [summary.findingCount, summary.runId])

  const openFindings = () => {
    trackEvent("first_audit_findings_opened", {
      run_id: summary.runId || "unknown",
      finding_count: summary.findingCount || 0,
    })
    navigate("/findings")
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      <div>
        <div className="text-xs font-bold uppercase tracking-wider text-blue-600">First Project Check</div>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">ControlCheck is reviewing your project data</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Your upload has been accepted. ControlCheck is organizing the completed analysis into traceable findings for review.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="space-y-3">
          {stages.map((stage, index) => {
            const Icon = stage.icon
            const completed = ready || index < activeStage
            const active = !ready && index === activeStage

            return (
              <div key={stage.label} className={`flex gap-4 rounded-xl border p-4 transition-all ${active ? "border-blue-200 bg-blue-50/60" : completed ? "border-emerald-100 bg-emerald-50/40" : "border-slate-100 bg-slate-50/60"}`}>
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${completed ? "bg-emerald-100 text-emerald-700" : active ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-400"}`}>
                  {completed ? <CheckCircle2 className="h-5 w-5" /> : active ? <Loader2 className="h-5 w-5 animate-spin" /> : <Icon className="h-5 w-5" />}
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">{stage.label}</div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">{stage.detail}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {ready && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
            <div>
              <div className="flex items-center gap-2 text-sm font-bold text-emerald-800">
                <CheckCircle2 className="h-5 w-5" /> Findings ready for review
              </div>
              <p className="mt-2 text-sm text-emerald-900/70">
                {summary.ruleCount || 20} control checks evaluated{summary.findingCount ? ` and ${summary.findingCount} findings identified` : ""}. Open the findings workspace to review severity, evidence and recommended action.
              </p>
            </div>
            <button onClick={openFindings} className="shrink-0 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-700">
              Review Findings
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default AnalysisProgressPage
