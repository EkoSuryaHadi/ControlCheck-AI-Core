import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { api, ClosureApproval, GovernanceEscalation, GovernancePolicy } from "@/lib/api"
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldCheck, SlidersHorizontal, XCircle } from "lucide-react"

const defaultPolicy: GovernancePolicy = {
  project_id: "",
  critical_sla_days: 3,
  warning_sla_days: 7,
  observation_sla_days: 14,
  require_critical_closure_approval: true,
  require_warning_closure_approval: false,
}

export const GovernancePage: React.FC = () => {
  const { currentProject } = useProject()
  const navigate = useNavigate()
  const [policy, setPolicy] = useState<GovernancePolicy>(defaultPolicy)
  const [approvals, setApprovals] = useState<ClosureApproval[]>([])
  const [escalations, setEscalations] = useState<GovernanceEscalation[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    if (!currentProject?.id) return
    setLoading(true)
    setMessage(null)
    try {
      const [policyRes, approvalRes, escalationRes] = await Promise.all([
        api.governance.getPolicy(currentProject.id),
        api.governance.listApprovals(currentProject.id, "pending"),
        api.governance.listEscalations(currentProject.id),
      ])
      setPolicy(policyRes)
      setApprovals(approvalRes.items || [])
      setEscalations(escalationRes.items || [])
    } catch (error: any) {
      setMessage(error?.response?.data?.error?.message || "Governance data is not available yet for this workspace.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [currentProject?.id])

  const openEscalations = useMemo(() => escalations.filter((item) => item.status === "open"), [escalations])
  const criticalEscalations = useMemo(() => escalations.filter((item) => item.severity === "critical" && item.status !== "resolved"), [escalations])

  const savePolicy = async () => {
    if (!currentProject?.id) return
    setSaving(true)
    setMessage(null)
    try {
      const updated = await api.governance.updatePolicy(currentProject.id, {
        critical_sla_days: policy.critical_sla_days,
        warning_sla_days: policy.warning_sla_days,
        observation_sla_days: policy.observation_sla_days,
        require_critical_closure_approval: policy.require_critical_closure_approval,
        require_warning_closure_approval: policy.require_warning_closure_approval,
      })
      setPolicy(updated)
      setMessage("Governance policy saved.")
    } catch (error: any) {
      setMessage(error?.response?.data?.error?.message || "You do not have authority to update governance policy.")
    } finally {
      setSaving(false)
    }
  }

  const scan = async () => {
    if (!currentProject?.id) return
    setLoading(true)
    setMessage(null)
    try {
      const created = await api.governance.scanEscalations(currentProject.id)
      setMessage(created.items.length ? `${created.items.length} new escalation${created.items.length === 1 ? "" : "s"} created.` : "No new SLA breach detected.")
      await load()
    } catch (error: any) {
      setMessage(error?.response?.data?.error?.message || "Escalation scan requires manager authority.")
      setLoading(false)
    }
  }

  const decide = async (approval: ClosureApproval, decision: "approved" | "rejected") => {
    setMessage(null)
    try {
      await api.governance.decideApproval(approval.id, decision)
      setMessage(`Closure request ${decision}.`)
      await load()
    } catch (error: any) {
      setMessage(error?.response?.data?.error?.message || "Approval decision was blocked by governance policy.")
    }
  }

  const acknowledge = async (item: GovernanceEscalation) => {
    try {
      await api.governance.acknowledgeEscalation(item.id)
      await load()
    } catch (error: any) {
      setMessage(error?.response?.data?.error?.message || "Escalation acknowledgement requires manager authority.")
    }
  }

  if (!currentProject) {
    return <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">Select a project to open Governance.</div>
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-indigo-600">Assurance Governance</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Approval & Escalation Governance</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Maker-checker closure approval, severity-based SLA, overdue escalation and management authority for {currentProject.name}.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</button>
          <button onClick={scan} disabled={loading} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50"><AlertTriangle className="h-4 w-4" /> Scan SLA Breaches</button>
        </div>
      </div>

      {message && <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-xs font-semibold text-indigo-800">{message}</div>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Pending Approvals" value={approvals.length} icon={ShieldCheck} />
        <Metric label="Open Escalations" value={openEscalations.length} icon={AlertTriangle} />
        <Metric label="Critical Escalations" value={criticalEscalations.length} icon={Clock3} />
        <Metric label="Critical SLA" value={`${policy.critical_sla_days}d`} icon={SlidersHorizontal} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[.9fr_1.1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500"><SlidersHorizontal className="h-4 w-4" /> Project Governance Policy</div>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <SlaInput label="Critical" value={policy.critical_sla_days} onChange={(value) => setPolicy({ ...policy, critical_sla_days: value })} />
            <SlaInput label="Warning" value={policy.warning_sla_days} onChange={(value) => setPolicy({ ...policy, warning_sla_days: value })} />
            <SlaInput label="Observation" value={policy.observation_sla_days} onChange={(value) => setPolicy({ ...policy, observation_sla_days: value })} />
          </div>
          <div className="mt-5 space-y-3">
            <Toggle label="Critical finding requires closure approval" checked={policy.require_critical_closure_approval} onChange={(checked) => setPolicy({ ...policy, require_critical_closure_approval: checked })} />
            <Toggle label="Warning finding requires closure approval" checked={policy.require_warning_closure_approval} onChange={(checked) => setPolicy({ ...policy, require_warning_closure_approval: checked })} />
          </div>
          <button onClick={savePolicy} disabled={saving} className="mt-5 w-full rounded-xl bg-slate-900 px-4 py-3 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50">{saving ? "Saving..." : "Save Governance Policy"}</button>
          <p className="mt-3 text-[11px] leading-5 text-slate-400">Only organization admins and project managers can change policy. Critical approval uses maker-checker separation.</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3"><div><div className="text-xs font-bold uppercase tracking-wider text-indigo-600">Decision Queue</div><h2 className="mt-1 text-lg font-bold text-slate-900">Pending Closure Approvals</h2></div><span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">{approvals.length} pending</span></div>
          <div className="mt-5 space-y-3">
            {approvals.length === 0 ? <Empty text="No closure approval is waiting for a decision." /> : approvals.map((approval) => (
              <article key={approval.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                <button onClick={() => navigate(`/findings/${approval.finding_id}`)} className="font-mono text-xs font-bold text-blue-600 hover:underline">{approval.finding_id}</button>
                <div className="mt-1 text-xs text-slate-500">Requested {new Date(approval.requested_at).toLocaleString()}</div>
                {approval.decision_note && <p className="mt-2 text-xs leading-5 text-slate-600">{approval.decision_note}</p>}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button onClick={() => decide(approval, "approved")} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700"><CheckCircle2 className="h-4 w-4" /> Approve</button>
                  <button onClick={() => decide(approval, "rejected")} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-700 hover:bg-red-100"><XCircle className="h-4 w-4" /> Reject</button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4"><div><div className="text-xs font-bold uppercase tracking-wider text-amber-600">Escalation Inbox</div><h2 className="mt-1 text-lg font-bold text-slate-900">SLA and Corrective Action Breaches</h2></div><span className="text-xs font-semibold text-slate-400">Finding SLA + Action Overdue</span></div>
        <div className="mt-5 space-y-3">
          {escalations.length === 0 ? <Empty text="No governance escalation has been recorded for this project." /> : escalations.map((item) => (
            <article key={item.id} className="grid gap-4 rounded-xl border border-slate-200 p-4 lg:grid-cols-[1.2fr_.5fr_.5fr_auto] lg:items-center">
              <div><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-1 text-[10px] font-black uppercase ${item.severity === "critical" ? "bg-red-100 text-red-700" : item.severity === "warning" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"}`}>{item.severity}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-600">{item.escalation_type.replaceAll("_", " ")}</span></div><p className="mt-2 text-sm font-semibold text-slate-800">{item.reason}</p><button onClick={() => navigate(`/findings/${item.finding_id}`)} className="mt-1 font-mono text-[11px] font-bold text-blue-600 hover:underline">Finding {item.finding_id}</button></div>
              <div><div className="text-[10px] font-bold uppercase text-slate-400">Triggered</div><div className="mt-1 text-xs font-semibold text-slate-700">{new Date(item.triggered_at).toLocaleDateString()}</div></div>
              <div><div className="text-[10px] font-bold uppercase text-slate-400">Status</div><div className="mt-1 text-xs font-bold capitalize text-slate-700">{item.status}</div></div>
              {item.status === "open" ? <button onClick={() => acknowledge(item)} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800 hover:bg-amber-100">Acknowledge</button> : <span className="text-xs font-semibold text-slate-400">Acknowledged</span>}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

const Metric = ({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ElementType }) => <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div><Icon className="h-4 w-4 text-slate-400" /></div><div className="mt-2 text-3xl font-black text-slate-900">{value}</div></div>
const SlaInput = ({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) => <label><span className="text-[10px] font-bold uppercase text-slate-500">{label} SLA</span><div className="mt-1 flex items-center rounded-lg border border-slate-200 bg-slate-50"><input type="number" min={1} max={365} value={value} onChange={(e) => onChange(Math.max(1, Number(e.target.value) || 1))} className="w-full bg-transparent px-3 py-2 text-sm font-bold outline-none" /><span className="pr-3 text-xs text-slate-400">days</span></div></label>
const Toggle = ({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) => <label className="flex cursor-pointer items-center justify-between rounded-xl border border-slate-200 p-3"><span className="text-xs font-semibold text-slate-700">{label}</span><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-indigo-600" /></label>
const Empty = ({ text }: { text: string }) => <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-xs text-slate-500">{text}</div>

export default GovernancePage
