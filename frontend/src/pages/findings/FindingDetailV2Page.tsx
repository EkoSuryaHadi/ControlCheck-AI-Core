import React, { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { api } from "@/lib/api"
import { INITIAL_FINDINGS } from "./FindingsPage"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import { trackEvent } from "@/lib/analytics"
import { createAction, getActionsForFinding, FindingAction, ActionPriority } from "@/lib/actionStore"
import { ArrowLeft, CheckCircle2, FileSpreadsheet, Lightbulb, MapPin, ShieldCheck, Sparkles, Target, TriangleAlert, UserRound, CalendarDays, ClipboardCheck } from "lucide-react"

export const FindingDetailV2Page: React.FC = () => {
  const { findingId } = useParams<{ findingId: string }>()
  const navigate = useNavigate()
  const { liveFindings } = useProject()
  const [evidence, setEvidence] = useState<any[]>([])
  const [status, setStatus] = useState("open")
  const [isResolving, setIsResolving] = useState(false)
  const [actions, setActions] = useState<FindingAction[]>([])
  const [owner, setOwner] = useState("Project Control Lead")
  const [dueDate, setDueDate] = useState("")
  const [priority, setPriority] = useState<ActionPriority>("high")
  const [notes, setNotes] = useState("")

  const finding: any = useMemo(() => liveFindings.find((f: any) => f.id === findingId || f.rule_id === findingId) || INITIAL_FINDINGS.find((f: any) => f.id === findingId) || INITIAL_FINDINGS[0], [findingId, liveFindings])
  const canonicalFindingId = finding.id || finding.rule_id || findingId || "unknown"

  useEffect(() => {
    setStatus(finding.status || "open")
    setActions(getActionsForFinding(canonicalFindingId))
    trackEvent("finding_detail_viewed", { finding_id: canonicalFindingId, severity: finding.severity })
    if (finding.id) {
      api.findings.getEvidence(finding.id).then((res) => {
        const items = Array.isArray(res) ? res : res?.items || []
        if (items.length) setEvidence(items)
      }).catch(() => {})
    }
  }, [finding, canonicalFindingId])

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

  const resolveFinding = async () => {
    setIsResolving(true)
    try {
      if (finding.id) await api.findings.updateStatus(finding.id, "resolved")
      setStatus("resolved")
      trackEvent("finding_resolved", { finding_id: canonicalFindingId })
    } catch {
      setStatus("resolved")
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
      dueDate: dueDate || "Not set",
      priority,
      status: "open",
      notes: notes.trim(),
    })
    setActions(getActionsForFinding(canonicalFindingId))
    setNotes("")
    trackEvent("finding_action_created", { finding_id: canonicalFindingId, action_id: created.id, priority })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <button onClick={() => navigate("/findings")} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to Findings</button>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><SeverityBadge severity={finding.severity || "observation"} /><StatusBadge status={status} /><span className="font-mono text-xs text-slate-400">{canonicalFindingId}</span></div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">{finding.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{finding.description || "Project-control exception detected and flagged for evidence-backed review."}</p>
          </div>
          {status !== "resolved" ? <button onClick={resolveFinding} disabled={isResolving} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"><CheckCircle2 className="h-4 w-4" /> {isResolving ? "Updating..." : "Mark Reviewed / Resolved"}</button> : <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-700"><CheckCircle2 className="h-4 w-4" /> Resolved</div>}
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
              <label><span className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase text-slate-500"><CalendarDays className="h-3 w-3" /> Due Date</span><input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs" /></label>
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
  const tones = { slate: "border-slate-200 bg-white text-slate-700", red: "border-red-200 bg-red-50/60 text-red-700", amber: "border-amber-200 bg-amber-50/60 text-amber-800", green: "border-emerald-200 bg-emerald-50/60 text-emerald-800", blue: "border-blue-200 bg-blue-50/60 text-blue-800" }
  return <div className={`rounded-xl border p-5 ${tones[tone]}`}><div className="flex items-center gap-2 text-[10px] font-black tracking-wider"><Icon className="h-4 w-4" /> {label}</div><div className="mt-3 text-sm font-bold text-slate-900">{title}</div><p className="mt-2 text-xs leading-5 text-slate-600">{text}</p></div>
}

export default FindingDetailV2Page
