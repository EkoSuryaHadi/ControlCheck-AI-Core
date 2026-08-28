import React, { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { api, ClosureReadiness } from "@/lib/api"
import { resolveFindingEvidence, resolveServerFinding } from "@/lib/finding-source.js"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import { trackEvent } from "@/lib/analytics"
import { createAction, getActionsForFinding, FindingAction, ActionPriority } from "@/lib/actionStore"
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  FileSpreadsheet,
  Lightbulb,
  MapPin,
  ShieldCheck,
  Sparkles,
  Target,
  TriangleAlert,
  UserRound,
  CalendarDays,
  ClipboardCheck,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"

const isUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
type ResolutionStep = "review" | "action" | "evidence" | "closed"

export const FindingDetailV2Page: React.FC = () => {
  const { findingId } = useParams<{ findingId: string }>()
  const navigate = useNavigate()
  const { liveFindings } = useProject()
  const [evidence, setEvidence] = useState<any[]>([])
  const [evidenceLoaded, setEvidenceLoaded] = useState(false)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)
  const [status, setStatus] = useState("open")
  const [isResolving, setIsResolving] = useState(false)
  const [actions, setActions] = useState<FindingAction[]>([])
  const [closure, setClosure] = useState<ClosureReadiness | null>(null)
  const [resolutionError, setResolutionError] = useState<string | null>(null)
  const [owner, setOwner] = useState("Project Control Lead")
  const [dueDate, setDueDate] = useState("")
  const [priority, setPriority] = useState<ActionPriority>("high")
  const [notes, setNotes] = useState("")
  const [feedbackRating, setFeedbackRating] = useState<"useful" | "not_useful" | null>(null)
  const [feedbackComment, setFeedbackComment] = useState("")
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)

  const finding: any = useMemo(
    () => resolveServerFinding(liveFindings, findingId) || {
        id: findingId || "unknown",
        title: "Finding details",
        severity: "observation",
        status: "open",
        description: "Loading the server-backed finding details.",
      },
    [findingId, liveFindings],
  )

  const canonicalFindingId = finding.id || finding.rule_id || findingId || "unknown"
  const serverBacked = isUuid(canonicalFindingId)

  const refreshClosure = useCallback(async () => {
    if (!serverBacked) return
    try {
      const readiness = await api.findings.closureReadiness(canonicalFindingId)
      setClosure(readiness)
      setResolutionError(null)
    } catch {
      setClosure(null)
    }
  }, [canonicalFindingId, serverBacked])

  useEffect(() => {
    setStatus(finding.status || "open")
    setActions(getActionsForFinding(canonicalFindingId))
    setEvidence([])
    setEvidenceLoaded(!serverBacked)
    setEvidenceError(null)
    setFeedbackRating(null)
    setFeedbackComment("")
    setFeedbackSubmitted(false)
    setFeedbackError(null)
    trackEvent("finding_detail_viewed", { finding_id: canonicalFindingId, severity: finding.severity })
    if (serverBacked) void api.telemetry.event("finding_viewed", { finding_id: canonicalFindingId }).catch(() => undefined)

    if (serverBacked) {
      api.findings.getEvidence(canonicalFindingId).then((res) => {
        const items = Array.isArray(res) ? res : res?.items || []
        setEvidence(items)
        setEvidenceLoaded(true)
        void api.telemetry.event("evidence_viewed", { finding_id: canonicalFindingId }).catch(() => undefined)
      }).catch(() => {
        setEvidence([])
        setEvidenceLoaded(true)
        setEvidenceError("Server evidence could not be loaded. Refresh before closing this finding.")
      })
      void refreshClosure()
    }

    const syncLocal = () => {
      setActions(getActionsForFinding(canonicalFindingId))
      void refreshClosure()
    }
    window.addEventListener("controlcheck-actions-updated", syncLocal)
    return () => window.removeEventListener("controlcheck-actions-updated", syncLocal)
  }, [finding, canonicalFindingId, serverBacked, refreshClosure])

  const evidenceItems = resolveFindingEvidence(finding, evidence, serverBacked)
  const why = finding.ai_summary || finding.description || "This finding crossed the configured project-control threshold and requires review against its supporting records."
  const impact = finding.potential_impact || finding.business_impact || finding.impact || "Potential project impact requires review."
  const action = finding.recommendation || "Validate the source evidence, confirm the project impact, assign an owner, and agree the corrective action."
  const location = `${finding.wbs || finding.wbs_code || "Project"}${finding.wbs_name ? ` · ${finding.wbs_name}` : ""}`

  const evidenceCompleteness = useMemo(() => {
    if (serverBacked && (!evidenceLoaded || evidenceError)) return 0
    const checks = [
      evidenceItems.length > 0,
      evidenceItems.some((e: any) => Boolean(e.source_sheet || e.table)),
      evidenceItems.some((e: any) => Boolean((e.source_rows?.length || e.row) || e.record_ids?.length)),
      evidenceItems.some((e: any) => Boolean(e.fields && Object.keys(e.fields).length)),
      Boolean(finding.wbs || finding.wbs_code),
      Boolean(finding.recommendation),
    ]
    return Math.round((checks.filter(Boolean).length / checks.length) * 100)
  }, [evidenceItems, evidenceError, evidenceLoaded, finding, serverBacked])

  const localClosure = useMemo<ClosureReadiness>(() => {
    const activeActions = actions.filter((item) => !["completed", "cancelled"].includes(item.status))
    const evidenceReady = evidenceItems.length > 0 && (!serverBacked || (evidenceLoaded && !evidenceError))
    const actionsReady = actions.length > 0 && activeActions.length === 0
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
        ...(actions.length === 0 ? ["Create at least one corrective action."] : []),
        ...(!evidenceReady ? ["Supporting evidence is required."] : []),
        ...(actions.length > 0 && !actionsReady ? ["Complete or cancel all open corrective actions."] : []),
      ],
    }
  }, [actions, evidenceError, evidenceItems, evidenceLoaded, serverBacked])

  const closureState = closure || localClosure
  const hasAction = closureState.action_count > 0
  const isClosed = status === "resolved" || status === "closed"

  const currentStep = useMemo<ResolutionStep>(() => {
    if (isClosed) return "closed"
    if (!hasAction || !closureState.actions_ready) return "action"
    if (!closureState.evidence_ready) return "evidence"
    return "closed"
  }, [isClosed, hasAction, closureState.actions_ready, closureState.evidence_ready])

  const steps = [
    { key: "review" as const, label: "Review", done: true },
    { key: "action" as const, label: "Action", done: hasAction && closureState.actions_ready },
    { key: "evidence" as const, label: "Evidence", done: closureState.evidence_ready },
    { key: "closed" as const, label: "Closed", done: isClosed },
  ]

  const remainingItems = useMemo(() => {
    const items: string[] = []
    if (!hasAction) items.push("Create a corrective action")
    else if (!closureState.actions_ready) items.push(`Complete ${closureState.open_action_count} open corrective action${closureState.open_action_count === 1 ? "" : "s"}`)
    if (!closureState.evidence_ready) items.push(serverBacked ? "Verify server-backed supporting evidence" : "Attach or link supporting evidence")
    return items
  }, [hasAction, closureState.actions_ready, closureState.open_action_count, closureState.evidence_ready, serverBacked])

  const resolveFinding = async () => {
    setResolutionError(null)
    if (!closureState.can_close) {
      setResolutionError(remainingItems.length ? remainingItems.join(" · ") : closureState.blockers.join(" "))
      trackEvent("finding_closure_blocked", { finding_id: canonicalFindingId, blocker_count: closureState.blockers.length })
      return
    }

    setIsResolving(true)
    try {
      if (serverBacked) await api.findings.closeGoverned(canonicalFindingId)
      setStatus("resolved")
      trackEvent("finding_closed", { finding_id: canonicalFindingId, server_backed: serverBacked })
    } catch (err: any) {
      if (err?.response?.status === 409) {
        await refreshClosure()
        setResolutionError(err?.response?.data?.error?.message || "Finding is not ready to close yet.")
      } else if (err?.response?.status === 403) {
        setResolutionError(err?.response?.data?.error?.message || "You do not have authority to close this finding.")
      } else {
        setResolutionError("Finding could not be closed. Refresh the page and verify the latest status.")
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
    setClosure((current) => current ? {
      ...current,
      can_close: false,
      actions_ready: false,
      action_count: current.action_count + 1,
      open_action_count: current.open_action_count + 1,
      blockers: Array.from(new Set([...current.blockers, "Complete or cancel all open corrective actions."])),
    } : current)
    trackEvent("finding_action_created", { finding_id: canonicalFindingId, action_id: created.id, priority })
    window.setTimeout(() => void refreshClosure(), 900)
  }

  const submitFeedback = async () => {
    if (!serverBacked || !feedbackRating) return
    setIsSubmittingFeedback(true)
    setFeedbackError(null)
    try {
      await api.findings.feedback(canonicalFindingId, feedbackRating, feedbackComment.trim() || undefined)
      setFeedbackSubmitted(true)
      trackEvent("finding_feedback_submitted", { finding_id: canonicalFindingId, rating: feedbackRating })
    } catch {
      setFeedbackError("Feedback belum tersimpan. Coba kirim ulang.")
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  const primaryAction = () => {
    if (isClosed) return null
    if (!hasAction) return { label: "Create Action", onClick: () => document.getElementById("resolution-action-form")?.scrollIntoView({ behavior: "smooth" }), disabled: false }
    if (!closureState.actions_ready) return { label: "Update Action", onClick: () => navigate("/actions"), disabled: false }
    if (!closureState.evidence_ready) return { label: "Review Evidence", onClick: () => document.getElementById("evidence-trace")?.scrollIntoView({ behavior: "smooth" }), disabled: false }
    return { label: isResolving ? "Closing..." : "Close Finding", onClick: resolveFinding, disabled: isResolving }
  }

  const cta = primaryAction()

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <button onClick={() => navigate("/findings")} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Findings
      </button>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={finding.severity || "observation"} />
              <StatusBadge status={status} />
              <span className="font-mono text-xs text-slate-400">{canonicalFindingId}</span>
            </div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">{finding.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{finding.description || "Project-control exception detected and flagged for evidence-backed review."}</p>
          </div>
          {isClosed && <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-700"><CheckCircle2 className="h-4 w-4" /> Closed</div>}
        </div>
      </section>

      <section className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl flex-1">
            <div className="text-xs font-black uppercase tracking-wider text-blue-700">Resolution</div>
            <h2 className="mt-1 text-xl font-bold text-slate-900">Resolve this finding step by step</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">Review the finding, complete the corrective action, verify the supporting evidence, then close the finding.</p>

            <div className="mt-5 grid grid-cols-4 gap-2">
              {steps.map((step, index) => {
                const active = step.key === currentStep && !step.done
                return (
                  <div key={step.key} className="relative">
                    <div className={`flex min-h-20 flex-col items-center justify-center rounded-xl border px-2 text-center ${step.done ? "border-emerald-200 bg-emerald-50" : active ? "border-blue-300 bg-blue-100" : "border-slate-200 bg-white"}`}>
                      {step.done ? <Check className="h-4 w-4 text-emerald-700" /> : active ? <Clock3 className="h-4 w-4 text-blue-700" /> : <Circle className="h-4 w-4 text-slate-300" />}
                      <span className={`mt-2 text-[10px] font-black uppercase tracking-wide ${step.done ? "text-emerald-700" : active ? "text-blue-700" : "text-slate-400"}`}>{step.label}</span>
                    </div>
                    {index < steps.length - 1 && <div className="pointer-events-none absolute left-[calc(100%-2px)] top-10 hidden h-px w-2 bg-slate-200 sm:block" />}
                  </div>
                )
              })}
            </div>

            <div className="mt-5 rounded-xl border border-white bg-white/80 p-4">
              {isClosed ? (
                <div className="flex items-center gap-2 text-sm font-bold text-emerald-700"><CheckCircle2 className="h-5 w-5" /> Finding closed. Resolution requirements are complete.</div>
              ) : remainingItems.length === 0 ? (
                <div><div className="flex items-center gap-2 text-sm font-bold text-emerald-700"><CheckCircle2 className="h-5 w-5" /> Ready to close</div><p className="mt-1 text-xs text-slate-500">All required actions and evidence are complete.</p></div>
              ) : (
                <div><div className="text-sm font-bold text-slate-900">{remainingItems.length} item{remainingItems.length === 1 ? "" : "s"} remaining</div><div className="mt-2 space-y-1">{remainingItems.map((item) => <div key={item} className="flex items-center gap-2 text-xs text-slate-600"><Circle className="h-3 w-3 text-slate-300" /> {item}</div>)}</div></div>
              )}
              {resolutionError && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">{resolutionError}</div>}
            </div>
          </div>

          <div className="w-full rounded-2xl border border-slate-200 bg-white p-5 xl:w-72">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">Next step</div>
            <div className="mt-2 text-base font-bold text-slate-900">
              {isClosed ? "Completed" : !hasAction ? "Create corrective action" : !closureState.actions_ready ? "Complete corrective action" : !closureState.evidence_ready ? "Complete evidence" : "Close finding"}
            </div>
            {cta && <button onClick={cta.onClick} disabled={cta.disabled} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-xs font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"><CheckCircle2 className="h-4 w-4" /> {cta.label}</button>}
            {hasAction && !isClosed && <button onClick={() => navigate("/actions")} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50">Open Actions</button>}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DecisionCard icon={TriangleAlert} label="WHAT" title="What was detected" text={finding.description || finding.title} tone="red" />
        <DecisionCard icon={MapPin} label="WHERE" title="Where it exists" text={location} />
        <DecisionCard icon={ShieldCheck} label="WHY" title="Why ControlCheck flagged it" text={why} />
        <DecisionCard icon={Target} label="IMPACT" title="Potential project impact" text={impact} tone="amber" />
        <DecisionCard icon={FileSpreadsheet} label="EVIDENCE" title={`Evidence Completeness ${evidenceCompleteness}%`} text={evidenceItems.length ? `${evidenceItems.length} linked evidence record${evidenceItems.length === 1 ? "" : "s"}. Completeness reflects source, row lineage, field context, WBS context and recommended action availability.` : serverBacked ? "No server-backed evidence is currently linked. Closure remains blocked until traceable evidence is available." : "No linked evidence records."} tone="green" />
        <DecisionCard icon={Lightbulb} label="ACTION" title="Recommended next action" text={action} tone="blue" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
        <div id="evidence-trace" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div><div className="text-xs font-bold uppercase tracking-wider text-blue-600">Evidence</div><h2 className="mt-1 text-lg font-bold text-slate-900">Source records behind this finding</h2></div>
            <div className="text-right"><div className="text-2xl font-black text-emerald-600">{evidenceCompleteness}%</div><div className="text-[10px] font-bold uppercase text-slate-400">Completeness</div></div>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${evidenceCompleteness}%` }} /></div>
          <div className="mt-5 space-y-3">
            {serverBacked && !evidenceLoaded ? (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs font-semibold text-blue-800">Loading server-backed evidence…</div>
            ) : evidenceError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">{evidenceError}</div>
            ) : evidenceItems.length === 0 ? (
              <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-amber-800"><TriangleAlert className="h-4 w-4" /> No server evidence available</div>
                <p className="mt-2 text-xs leading-5 text-amber-800/80">This is a live finding, so ControlCheck will not substitute demo evidence. Link or regenerate traceable evidence before closure.</p>
              </div>
            ) : evidenceItems.map((item: any, index: number) => (
              <div key={item.id || index} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2"><div className="font-mono text-xs font-bold text-slate-800">{item.source_sheet || item.table || `Evidence ${index + 1}`}</div><div className="text-[11px] text-slate-400">Rows: {(item.source_rows || item.row || []).toString() || "linked"}</div></div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(item.fields || item).filter(([key]) => !["id", "source_sheet", "source_rows", "record_ids", "aggregation"].includes(key)).slice(0, 6).map(([key, value]) => <div key={key} className="rounded-lg bg-white p-3"><div className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{key.replaceAll("_", " ")}</div><div className="mt-1 break-words text-xs font-semibold text-slate-700">{String(value)}</div></div>)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-5">
          {serverBacked && <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Finding feedback</div>
            {feedbackSubmitted ? (
              <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">Terima kasih. Feedback tersimpan untuk review beta.</div>
            ) : (
              <>
                <p className="mt-2 text-sm leading-6 text-slate-600">Apakah finding ini berguna untuk review project Anda?</p>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setFeedbackRating("useful")} className={`inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-bold ${feedbackRating === "useful" ? "border-emerald-400 bg-emerald-50 text-emerald-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}><ThumbsUp className="h-4 w-4" /> Useful</button>
                  <button type="button" onClick={() => setFeedbackRating("not_useful")} className={`inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-bold ${feedbackRating === "not_useful" ? "border-amber-400 bg-amber-50 text-amber-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}><ThumbsDown className="h-4 w-4" /> Not useful</button>
                </div>
                <textarea value={feedbackComment} onChange={(e) => setFeedbackComment(e.target.value)} maxLength={1000} rows={3} placeholder="Optional context (maks. 1.000 karakter)" className="mt-3 w-full resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
                <button type="button" disabled={!feedbackRating || isSubmittingFeedback} onClick={() => void submitFeedback()} className="mt-3 w-full rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300">{isSubmittingFeedback ? "Saving…" : "Send feedback"}</button>
                {feedbackError && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">{feedbackError}</div>}
              </>
            )}
          </section>}

          <div className="rounded-2xl border border-purple-200 bg-purple-50 p-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-purple-700"><Sparkles className="h-4 w-4" /> AI-assisted interpretation</div>
            <p className="mt-4 text-sm leading-6 text-slate-700">{why}</p>
            <div className="mt-4 rounded-xl border border-purple-100 bg-white/70 p-4 text-xs leading-5 text-slate-600">AI interpretation is supporting context. The deterministic rule, calculations and source evidence remain the review basis.</div>
          </div>

          <form id="resolution-action-form" onSubmit={handleCreateAction} className="rounded-2xl border border-blue-200 bg-blue-50 p-6">
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

const DecisionCard = ({ icon: Icon, label, title, text, tone = "slate" }: { icon: React.ElementType; label: string; title: string; text: string; tone?: "slate" | "red" | "amber" | "green" | "blue" }) => {
  const tones = {
    slate: "border-slate-200 bg-white text-slate-700",
    red: "border-red-200 bg-red-50/60 text-red-700",
    amber: "border-amber-200 bg-amber-50/60 text-amber-800",
    green: "border-emerald-200 bg-emerald-50/60 text-emerald-800",
    blue: "border-blue-200 bg-blue-50/60 text-blue-800",
  }
  return <div className={`rounded-xl border p-5 ${tones[tone]}`}><div className="flex items-center gap-2 text-[10px] font-black tracking-wider"><Icon className="h-4 w-4" /> {label}</div><div className="mt-3 text-sm font-bold text-slate-900">{title}</div><p className="mt-2 text-xs leading-5 text-slate-600">{text}</p></div>
}

export default FindingDetailV2Page
