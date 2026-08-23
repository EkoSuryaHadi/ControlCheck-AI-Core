import React, { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { api, ClosureReadiness } from "@/lib/api"
import { INITIAL_FINDINGS } from "./FindingsPage"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import { trackEvent } from "@/lib/analytics"
import { createAction, getActionsForFinding, FindingAction, ActionPriority } from "@/lib/actionStore"
import { ArrowLeft, CheckCircle2, FileSpreadsheet, Lightbulb, MapPin, ShieldCheck, Sparkles, Target, TriangleAlert, UserRound, CalendarDays, ClipboardCheck, LockKeyhole, Send, Clock3 } from "lucide-react"

const isUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)

export const FindingDetailV2Page: React.FC = () => {
  const { findingId } = useParams<{ findingId: string }>()
  const navigate = useNavigate()
  const { liveFindings } = useProject()
  const [evidence, setEvidence] = useState<any[]>([])
  const [status, setStatus] = useState("open")
  const [isResolving, setIsResolving] = useState(false)
  const [isRequestingApproval, setIsRequestingApproval] = useState(false)
  const [actions, setActions] = useState<FindingAction[]>([])
  const [closure, setClosure] = useState<ClosureReadiness | null>(null)
  const [closureError, setClosureError] = useState<string | null>(null)
  const [owner, setOwner] = useState("Project Control Lead")
  const [dueDate, setDueDate] = useState("")
  const [priority, setPriority] = useState<ActionPriority>("high")
  const [notes, setNotes] = useState("")

  const finding: any = useMemo(() => liveFindings.find((f: any) => f.id === findingId || f.rule_id === findingId) || INITIAL_FINDINGS.find((f: any) => f.id === findingId) || INITIAL_FINDINGS[0], [findingId, liveFindings])
  const canonicalFindingId = finding.id || finding.rule_id || findingId || "unknown"
  const serverGoverned = isUuid(canonicalFindingId)

  const refreshClosure = useCallback(async () => {
    if (!serverGoverned) return
    try {
      const readiness = await api.findings.closureReadiness(canonicalFindingId)
      setClosure(readiness)
      setClosureError(null)
    } catch {
      setClosure(null)
    }
  }, [canonicalFindingId, serverGoverned])

  useEffect(() => {
    setStatus(finding.status || "open")
    setActions(getActionsForFinding(canonicalFindingId))
    trackEvent("finding_detail_viewed", { finding_id: canonicalFindingId, severity: finding.severity })

    if (serverGoverned) {
      api.findings.getEvidence(canonicalFindingId).then((res) => {
        const items = Array.isArray(res) ? res : res?.items || []
        setEvidence(items)
      }).catch(() => {})
      void refreshClosure()
    }

    const syncLocal = () => {
      setActions(getActionsForFinding(canonicalFindingId))
      void refreshClosure()
    }
    window.addEventListener("controlcheck-actions-updated", syncLocal)
    return () => window.removeEventListener("controlcheck-actions-updated", syncLocal)
  }, [finding, canonicalFindingId, serverGoverned, refreshClosure])

  const fallbackEvidence = [
    { source_sheet: "Actual_Cost", source_rows: [142], fields: { WBS: finding.wbs || "03.02", Amount: finding.actual || "Rp 958,400,000", Source: "Actual Cost Register" } },
    { source_sheet: "Budget", source_rows: [12], fields: { WBS: finding.wbs || "03.02", BAC: finding.budget || "Rp 771,000,000", Source: "Approved Baseline" } },
    { source_sheet: "Commitment", source_rows: [37], fields: { WBS: finding.wbs || "03.02", PO: "PO-23017", Source: "PO Register" } },
  ]
  const evidenceItems = evidence.length ? evidence : (finding.evidence_records?.length ? finding.evidence_records : fallbackEvidence)
  const why = finding.ai_summary || finding.description || "This finding crossed the configured project-control threshold and requires review against its supporting records."
  const impact = finding.potential_impact || finding.business_impact || finding.impact || "Potential project impact requires review."
  const action = finding.recommendation || "Validate the source evidence, confirm the project impact, assign an owner, and agree the corrective action."
  const location = `${finding.wbs || finding.wbs_code || "Project"}${finding.wbs_name ? ` · ${finding.wbs_name}` : ""}`

  const evidenceCompleteness = useMemo(() => {
    const checks = [
      evidenceItems.length > 0,
      evidenceItems.some((e: any) => Boolean(e.source_sheet || e.table)),
      evidenceItems.some((e: any) => Boolean((e.source_rows?.length || e.row) || e.record_ids?.length)),
      evidenceItems.some((e: any) => Boolean(e.fields && Object.keys(e.fields).length)),
      Boolean(finding.wbs || finding.wbs_code),
      Boolean(finding.recommendation),
    ]
    return Math.round((checks.filter(Boolean).length / checks.length) * 100)
  }, [evidenceItems, finding])

  const localClosure = useMemo<ClosureReadiness>(() => {
    const activeActions = actions.filter((item) => !["completed", "cancelled"].includes(item.status))
    const evidenceReady = evidenceItems.length > 0
    const actionsReady = activeActions.length === 0
    return {
      can_close: evidenceReady && actionsReady,
      evidence_ready: evidenceReady,
      actions_ready: actionsReady,
      approval_required: false,
      approval_ready: true,
      approval_decision: null,
      approval_id: null,
      action_count: actions.length,
      open_action_count: activeActions.length,
      completed_action_count: actions.filter((item) => item.status === "completed").length,
      blockers: [
        ...(!evidenceReady ? ["At least one evidence record is required before closure."] : []),
        ...(!actionsReady ? ["All corrective actions must be completed or cancelled before closure."] : []),
      ],
    }
  }, [actions, evidenceItems])

  const closureState = closure || localClosure
  const approvalPending = closureState.approval_required && closureState.approval_decision === "pending"
  const approvalRejected = closureState.approval_required && closureState.approval_decision === "rejected"
  const preApprovalReady = closureState.evidence_ready && closureState.actions_ready

  const requestApproval = async () => {
    if (!serverGoverned || !closureState.approval_required) return
    setIsRequestingApproval(true)
    setClosureError(null)
    try {
      await api.findings.requestClosureApproval(canonicalFindingId, "Evidence and corrective actions reviewed; requesting governed closure approval.")
      trackEvent("finding_closure_approval_requested", { finding_id: canonicalFindingId })
      await refreshClosure()
    } catch (err: any) {
      setClosureError(err?.response?.data?.error?.message || "Closure approval request could not be created.")
    } finally {
      setIsRequestingApproval(false)
    }
  }

  const resolveFinding = async () => {
    setClosureError(null)
    if (!closureState.can_close) {
      setClosureError(closureState.blockers.join(" "))
      trackEvent("finding_closure_blocked", { finding_id: canonicalFindingId, blocker_count: closureState.blockers.length })
      return
    }

    setIsResolving(true)
    try {
      if (serverGoverned) await api.findings.closeGoverned(canonicalFindingId)
      setStatus("resolved")
      trackEvent("finding_closed_governed", { finding_id: canonicalFindingId, server_governed: serverGoverned })
    } catch (err: any) {
      if (err?.response?.status === 409) {
        await refreshClosure()
        setClosureError(err?.response?.data?.error?.message || "Closure blocked by governance.")
      } else if (err?.response?.status === 403) {
        setClosureError(err?.response?.data?.error?.message || "You do not have authority to close this governed finding.")
      } else {
        setClosureError("Finding could not be closed. Please verify the latest governance state.")
      }
    } finally {
      setIsResolving(false)
    }
  }

  const handleCreateAction = (e: React.FormEvent) => {
    e.preventDefault()
    const created = createAction({
      findingId: canonicalFindingId,
      findingTitle: finding.title,
      owner: owner.trim() || "Unassigned",
      dueDate: dueDate || new Date().toISOString().slice(0, 10),
      priority,
      status: "open",
      notes: notes.trim(),
    })
    setActions(getActionsForFinding(canonicalFindingId))
    setNotes("")
    setClosure((current) => current ? { ...current, can_close: false, actions_ready: false, action_count: current.action_count + 1, open_action_count: current.open_action_count + 1, blockers: Array.from(new Set([...current.blockers, "All corrective actions must be completed or cancelled before closure."])) } : current)
    trackEvent("finding_action_created", { finding_id: canonicalFindingId, action_id: created.id, priority })
    window.setTimeout(() => void refreshClosure(), 900)
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <button onClick={() => navigate("/findings")} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to Findings</button>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><SeverityBadge severity={finding.severity || "observation"} /><StatusBadge status={status} /><span className="font-mono text-xs text-slate-400">{canonicalFindingId}</span>{serverGoverned && <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase text-blue-700">Governed Closure</span>}</div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">{finding.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{finding.description || "Project-control exception detected and flagged for evidence-backed review."}</p>
          </div>
          {status !== "resolved" ? <button onClick={resolveFinding} disabled={isResolving || !closureState.can_close} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-700 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-45"><CheckCircle2 className="h-4 w-4" /> {isResolving ? "Closing..." : "Close Finding"}</button> : <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-700"><CheckCircle2 className="h-4 w-4" /> Resolved</div>}
        </div>
      </section>

      <section className={`rounded-2xl border p-5 ${closureState.can_close ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
        <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
          <div className="max-w-2xl">
            <div className={`flex items-center gap-2 text-xs font-bold uppercase tracking-wider ${closureState.can_close ? "text-emerald-700" : "text-amber-800"}`}><LockKeyhole className="h-4 w-4" /> Closure Readiness</div>
            <div className="mt-2 text-lg font-bold text-slate-900">{closureState.can_close ? "Ready for governed closure" : approvalPending ? "Waiting for independent approval" : "Closure requirements are not complete"}</div>
            {closureState.blockers.length > 0 && <div className="mt-2 space-y-1 text-xs text-amber-900">{closureState.blockers.map((blocker) => <div key={blocker}>• {blocker}</div>)}</div>}
            {closureError && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">{closureError}</div>}
            {serverGoverned && closureState.approval_required && !closureState.approval_ready && (
              <div className="mt-4 flex flex-wrap gap-2">
                {approvalPending ? (
                  <><span className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700"><Clock3 className="h-4 w-4" /> Approval Pending</span><button onClick={() => navigate("/governance")} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700">Open Governance Queue</button></>
                ) : (
                  <button onClick={requestApproval} disabled={!preApprovalReady || isRequestingApproval} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-45"><Send className="h-4 w-4" /> {isRequestingApproval ? "Requesting..." : approvalRejected ? "Request Approval Again" : "Request Closure Approval"}</button>
                )}
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-5">
            <ReadinessMetric label="Evidence" value={closureState.evidence_ready ? "Ready" : "Missing"} ready={closureState.evidence_ready} />
            <ReadinessMetric label="Actions" value={closureState.actions_ready ? "Ready" : `${closureState.open_action_count} Open`} ready={closureState.actions_ready} />
            <ReadinessMetric label="Approval" value={!closureState.approval_required ? "N/A" : closureState.approval_ready ? "Approved" : (closureState.approval_decision || "Required")} ready={closureState.approval_ready} />
            <ReadinessMetric label="Completed" value={String(closureState.completed_action_count)} ready />
            <ReadinessMetric label="Total Actions" value={String(closureState.action_count)} ready />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DecisionCard icon={TriangleAlert} label="WHAT" title="What was detected" text={finding.description || finding.title} tone="red" />
        <DecisionCard icon={MapPin} label="WHERE" title="Where it exists" text={location} />
        <DecisionCard icon={ShieldCheck} label="WHY" title="Why ControlCheck flagged it" text={why} />
        <DecisionCard icon={Target} label="IMPACT" title="Potential project impact" text={impact} tone="amber" />
        <DecisionCard icon={FileSpreadsheet} label="EVIDENCE" title={`Evidence Completeness ${evidenceCompleteness}%`} text={`${evidenceItems.length} linked evidence record${evidenceItems.length === 1 ? "" : "s"}. Completeness reflects source, row lineage, field context, WBS context and recommended action availability.`} tone="green" />
        <DecisionCard icon={Lightbulb} label="ACTION" title="Recommended next action" text={action} tone="blue" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-4"><div><div className="text-xs font-bold uppercase tracking-wider text-blue-600">Evidence Trace</div><h2 className="mt-1 text-lg font-bold text-slate-900">Source records behind this finding</h2></div><div className="text-right"><div className="text-2xl font-black text-emerald-600">{evidenceCompleteness}%</div><div className="text-[10px] font-bold uppercase text-slate-400">Completeness</div></div></div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${evidenceCompleteness}%` }} /></div>
          <div className="mt-5 space-y-3">{evidenceItems.map((item: any, index: number) => <div key={item.id || index} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-mono text-xs font-bold text-slate-800">{item.source_sheet || item.table || `Evidence ${index + 1}`}</div><div className="text-[11px] text-slate-400">Rows: {(item.source_rows || item.row || []).toString() || "linked"}</div></div><div className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(item.fields || item).filter(([key]) => !["id","source_sheet","source_rows","record_ids","aggregation"].includes(key)).slice(0, 6).map(([key, value]) => <div key={key} className="rounded-lg bg-white p-3"><div className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{key.replaceAll("_", " ")}</div><div className="mt-1 break-words text-xs font-semibold text-slate-700">{String(value)}</div></div>)}</div></div>)}</div>
        </div>

        <div className="space-y-5">
          <div className="rounded-2xl border border-purple-200 bg-purple-50 p-6"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-purple-700"><Sparkles className="h-4 w-4" /> AI-assisted interpretation</div><p className="mt-4 text-sm leading-6 text-slate-700">{why}</p><div className="mt-4 rounded-xl border border-purple-100 bg-white/70 p-4 text-xs leading-5 text-slate-600">AI interpretation is supporting context. The deterministic rule, calculations and source evidence remain the review basis.</div></div>

          <form onSubmit={handleCreateAction} className="rounded-2xl border border-blue-200 bg-blue-50 p-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-blue-700"><ClipboardCheck className="h-4 w-4" /> Corrective Action</div>
            <p className="mt-3 text-sm font-semibold leading-6 text-slate-800">{action}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <label><span className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase text-slate-500"><UserRound className="h-3 w-3" /> Owner</span><input value={owner} onChange={(e) => setOwner(e.target.value)} className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs" /></label>
              <label><span className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase text-slate-500"><CalendarDays className="h-3 w-3" /> Due Date</span><input required type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs" /></label>
              <label><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Priority</span><select value={priority} onChange={(e) => setPriority(e.target.value as ActionPriority)} className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs"><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
              <label><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Notes</span><input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional context" className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs" /></label>
            </div>
            <button className="mt-4 w-full rounded-xl bg-blue-600 px-4 py-3 text-xs font-bold text-white hover:bg-blue-700">Create Corrective Action</button>
            {actions.length > 0 && <button type="button" onClick={() => navigate("/actions")} className="mt-3 w-full rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-xs font-bold text-blue-700">View {actions.length} Action{actions.length === 1 ? "" : "s"} for this Finding</button>}
          </form>
        </div>
      </section>
    </div>
  )
}

const ReadinessMetric = ({ label, value, ready }: { label: string; value: string; ready: boolean }) => <div className="min-w-24 rounded-xl border border-white/70 bg-white/70 px-3 py-3"><div className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{label}</div><div className={`mt-1 text-xs font-black capitalize ${ready ? "text-emerald-700" : "text-amber-700"}`}>{value}</div></div>

const DecisionCard = ({ icon: Icon, label, title, text, tone = "slate" }: { icon: React.ElementType; label: string; title: string; text: string; tone?: "slate" | "red" | "amber" | "green" | "blue" }) => {
  const tones = { slate: "border-slate-200 bg-white text-slate-700", red: "border-red-200 bg-red-50/60 text-red-700", amber: "border-amber-200 bg-amber-50/60 text-amber-800", green: "border-emerald-200 bg-emerald-50/60 text-emerald-800", blue: "border-blue-200 bg-blue-50/60 text-blue-800" }
  return <div className={`rounded-xl border p-5 ${tones[tone]}`}><div className="flex items-center gap-2 text-[10px] font-black tracking-wider"><Icon className="h-4 w-4" /> {label}</div><div className="mt-3 text-sm font-bold text-slate-900">{title}</div><p className="mt-2 text-xs leading-5 text-slate-600">{text}</p></div>
}

export default FindingDetailV2Page
