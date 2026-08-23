import React, { useEffect, useMemo, useState } from "react"
import { useProject } from "@/context/ProjectContext"
import { getActions, syncProjectActions, updateAction, deleteAction, FindingAction, ActionStatus } from "@/lib/actionStore"
import { trackEvent } from "@/lib/analytics"
import { CalendarDays, ClipboardCheck, TriangleAlert, UserRound, XCircle } from "lucide-react"

export const ActionsPage: React.FC = () => {
  const { currentProject } = useProject()
  const [actions, setActions] = useState<FindingAction[]>(() => getActions())
  const [statusFilter, setStatusFilter] = useState("all")
  const [isSyncing, setIsSyncing] = useState(false)

  const refresh = () => setActions(getActions())

  useEffect(() => {
    let active = true
    const runSync = async () => {
      if (!currentProject?.id) return
      setIsSyncing(true)
      const synced = await syncProjectActions(currentProject.id)
      if (active) {
        setActions(synced)
        setIsSyncing(false)
      }
    }
    void runSync()
    trackEvent("actions_workspace_viewed", { action_count: actions.length, project_id: currentProject?.id })
    window.addEventListener("controlcheck-actions-updated", refresh)
    return () => {
      active = false
      window.removeEventListener("controlcheck-actions-updated", refresh)
    }
  }, [currentProject?.id])

  const isOverdue = (action: FindingAction) => {
    if (["completed", "cancelled"].includes(action.status)) return false
    const due = new Date(`${action.dueDate}T23:59:59`)
    return !Number.isNaN(due.getTime()) && due.getTime() < Date.now()
  }

  const filtered = useMemo(() => actions.filter((a) => statusFilter === "all" || a.status === statusFilter), [actions, statusFilter])
  const activeCount = actions.filter((a) => ["open", "in_review"].includes(a.status)).length
  const overdueCount = actions.filter(isOverdue).length
  const completedCount = actions.filter((a) => a.status === "completed").length

  const changeStatus = (action: FindingAction, status: ActionStatus) => {
    updateAction(action.id, { status })
    refresh()
    trackEvent("finding_action_status_changed", { action_id: action.serverId || action.id, finding_id: action.findingId, status })
  }

  const cancel = (action: FindingAction) => {
    deleteAction(action.id)
    refresh()
    trackEvent("finding_action_cancelled", { action_id: action.serverId || action.id, finding_id: action.findingId })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Corrective Action Management</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Actions</h1>
          <p className="mt-2 text-sm text-slate-500">Server-backed corrective actions with owner accountability, due-date monitoring and closure governance.</p>
        </div>
        <div className="flex items-center gap-3">
          {isSyncing && <span className="text-xs font-semibold text-slate-400">Syncing…</span>}
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
            <option value="all">All statuses</option><option value="open">Open</option><option value="in_review">In review</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total Actions" value={actions.length} />
        <Metric label="Open / In Review" value={activeCount} />
        <Metric label="Overdue" value={overdueCount} warning={overdueCount > 0} />
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
          {filtered.map((action) => {
            const overdue = isOverdue(action)
            return (
              <article key={action.id} className={`rounded-2xl border bg-white p-5 shadow-sm ${overdue ? "border-red-200" : "border-slate-200"}`}>
                <div className="grid gap-5 lg:grid-cols-[1.4fr_.8fr_.8fr_.8fr_auto] lg:items-center">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[11px] font-bold text-blue-600">{action.serverId || action.id}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-600">{action.priority}</span>
                      {overdue && <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-1 text-[10px] font-bold uppercase text-red-700"><TriangleAlert className="h-3 w-3" /> Overdue</span>}
                    </div>
                    <div className="mt-2 font-bold text-slate-900">{action.findingTitle}</div>
                    <div className="mt-1 text-xs text-slate-500">Finding {action.findingId}{action.notes ? ` · ${action.notes}` : ""}</div>
                  </div>
                  <div><div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><UserRound className="h-3.5 w-3.5" /> Owner</div><div className="mt-1 text-sm font-semibold">{action.owner}</div></div>
                  <div><div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><CalendarDays className="h-3.5 w-3.5" /> Due</div><div className={`mt-1 text-sm font-semibold ${overdue ? "text-red-700" : ""}`}>{action.dueDate}</div></div>
                  <div>
                    <div className="text-[10px] font-bold uppercase text-slate-400">Status</div>
                    <select value={action.status} onChange={(e) => changeStatus(action, e.target.value as ActionStatus)} className="mt-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs font-semibold">
                      <option value="open">Open</option><option value="in_review">In review</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                  {!(["completed", "cancelled"].includes(action.status)) && <button onClick={() => cancel(action)} title="Cancel action" className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><XCircle className="h-4 w-4" /></button>}
                </div>
              </article>
            )
          })}
        </div>
      )}

      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-900">
        <strong>v0.5 persistence:</strong> when the backend database is available, actions synchronize to the server and remain tenant/project/finding scoped. The browser store is retained only as a resilient cache/fallback. Actions are cancelled rather than hard-deleted to preserve governance history.
      </div>
    </div>
  )
}

const Metric = ({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) => <div className={`rounded-xl border bg-white p-5 shadow-sm ${warning ? "border-red-200" : "border-slate-200"}`}><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div><div className={`mt-2 text-3xl font-black ${warning ? "text-red-600" : "text-slate-900"}`}>{value}</div></div>

export default ActionsPage
