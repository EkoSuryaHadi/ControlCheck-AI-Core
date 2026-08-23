import React, { useEffect, useMemo, useState } from "react"
import { getActions, updateAction, deleteAction, FindingAction, ActionStatus } from "@/lib/actionStore"
import { trackEvent } from "@/lib/analytics"
import { CalendarDays, CheckCircle2, ClipboardCheck, Trash2, UserRound } from "lucide-react"

export const ActionsPage: React.FC = () => {
  const [actions, setActions] = useState<FindingAction[]>(() => getActions())
  const [statusFilter, setStatusFilter] = useState("all")

  const refresh = () => setActions(getActions())

  useEffect(() => {
    trackEvent("actions_workspace_viewed", { action_count: actions.length })
    window.addEventListener("controlcheck-actions-updated", refresh)
    return () => window.removeEventListener("controlcheck-actions-updated", refresh)
  }, [])

  const filtered = useMemo(() => actions.filter((a) => statusFilter === "all" || a.status === statusFilter), [actions, statusFilter])
  const openCount = actions.filter((a) => a.status !== "completed").length
  const completedCount = actions.filter((a) => a.status === "completed").length

  const changeStatus = (action: FindingAction, status: ActionStatus) => {
    updateAction(action.id, { status })
    refresh()
    trackEvent("finding_action_status_changed", { action_id: action.id, finding_id: action.findingId, status })
  }

  const remove = (action: FindingAction) => {
    deleteAction(action.id)
    refresh()
    trackEvent("finding_action_deleted", { action_id: action.id, finding_id: action.findingId })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Corrective Action Management</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Actions</h1>
          <p className="mt-2 text-sm text-slate-500">Track owners, due dates and closure status for finding-level corrective actions.</p>
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
          <option value="all">All statuses</option><option value="open">Open</option><option value="in_review">In review</option><option value="completed">Completed</option>
        </select>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Total Actions" value={actions.length} />
        <Metric label="Open / In Review" value={openCount} />
        <Metric label="Completed" value={completedCount} />
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <ClipboardCheck className="mx-auto h-8 w-8 text-slate-400" />
          <h2 className="mt-4 font-bold text-slate-900">No actions in this view</h2>
          <p className="mt-2 text-sm text-slate-500">Create an action from any finding detail page.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((action) => (
            <article key={action.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-5 lg:grid-cols-[1.4fr_.8fr_.8fr_.8fr_auto] lg:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[11px] font-bold text-blue-600">{action.id}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-600">{action.priority}</span></div>
                  <div className="mt-2 font-bold text-slate-900">{action.findingTitle}</div>
                  <div className="mt-1 text-xs text-slate-500">Finding {action.findingId}{action.notes ? ` · ${action.notes}` : ""}</div>
                </div>
                <div><div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><UserRound className="h-3.5 w-3.5" /> Owner</div><div className="mt-1 text-sm font-semibold">{action.owner}</div></div>
                <div><div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><CalendarDays className="h-3.5 w-3.5" /> Due</div><div className="mt-1 text-sm font-semibold">{action.dueDate}</div></div>
                <div>
                  <div className="text-[10px] font-bold uppercase text-slate-400">Status</div>
                  <select value={action.status} onChange={(e) => changeStatus(action, e.target.value as ActionStatus)} className="mt-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs font-semibold">
                    <option value="open">Open</option><option value="in_review">In review</option><option value="completed">Completed</option>
                  </select>
                </div>
                <button onClick={() => remove(action)} title="Delete action" className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
        <strong>v0.4 persistence scope:</strong> actions are persisted in the current browser workspace. Server-side action persistence and multi-user synchronization require a dedicated backend Action API and database model.
      </div>
    </div>
  )
}

const Metric = ({ label, value }: { label: string; value: number }) => <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div><div className="mt-2 text-3xl font-black text-slate-900">{value}</div></div>

export default ActionsPage
