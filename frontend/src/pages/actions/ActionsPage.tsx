import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { getActions, syncProjectActions, updateAction, FindingAction, ActionStatus } from "@/lib/actionStore"
import { trackEvent } from "@/lib/analytics"
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  ExternalLink,
  ListChecks,
  TriangleAlert,
  UserRound,
} from "lucide-react"

type ActionView = "mine" | "open" | "overdue" | "completed" | "all"

const statusLabel = (status: ActionStatus) => {
  if (status === "in_review") return "In Progress"
  if (status === "completed") return "Completed"
  if (status === "cancelled") return "Cancelled"
  return "Open"
}

export const ActionsPage: React.FC = () => {
  const { currentProject } = useProject()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [actions, setActions] = useState<FindingAction[]>(() => getActions())
  const [view, setView] = useState<ActionView>("mine")
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

  const userName = (user?.name || "").trim().toLowerCase()
  const isMine = (action: FindingAction) => {
    if (!userName) return true
    const owner = (action.owner || "").trim().toLowerCase()
    return owner.includes(userName) || userName.includes(owner) || owner.includes("project control")
  }

  const filtered = useMemo(() => {
    return actions.filter((action) => {
      if (view === "mine") return isMine(action) && !["completed", "cancelled"].includes(action.status)
      if (view === "open") return !["completed", "cancelled"].includes(action.status)
      if (view === "overdue") return isOverdue(action)
      if (view === "completed") return action.status === "completed"
      return true
    })
  }, [actions, view, userName])

  const activeCount = actions.filter((a) => !["completed", "cancelled"].includes(a.status)).length
  const overdueCount = actions.filter(isOverdue).length
  const completedCount = actions.filter((a) => a.status === "completed").length
  const myOpenCount = actions.filter((a) => isMine(a) && !["completed", "cancelled"].includes(a.status)).length

  const changeStatus = (action: FindingAction, status: ActionStatus) => {
    updateAction(action.id, { status })
    refresh()
    trackEvent("finding_action_status_changed", { action_id: action.serverId || action.id, finding_id: action.findingId, status })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Guided Resolution Work Queue</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Corrective Actions</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Complete the work required by a finding, then return to the finding to submit the resolution for approval.
          </p>
        </div>
        {isSyncing && <span className="text-xs font-semibold text-slate-400">Syncing actions…</span>}
      </div>

      <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
        <div className="flex items-start gap-3">
          <ListChecks className="mt-0.5 h-5 w-5 shrink-0 text-blue-700" />
          <div>
            <div className="text-sm font-bold text-blue-950">How this workflow works</div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-blue-800">
              <span className="rounded-lg bg-white px-3 py-2">1. Review Finding</span><ArrowRight className="h-3.5 w-3.5" />
              <span className="rounded-lg bg-white px-3 py-2">2. Complete Action</span><ArrowRight className="h-3.5 w-3.5" />
              <span className="rounded-lg bg-white px-3 py-2">3. Return to Finding</span><ArrowRight className="h-3.5 w-3.5" />
              <span className="rounded-lg bg-white px-3 py-2">4. Submit for Approval</span>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="My Open Actions" value={myOpenCount} />
        <Metric label="All Open" value={activeCount} />
        <Metric label="Overdue" value={overdueCount} warning={overdueCount > 0} />
        <Metric label="Completed" value={completedCount} success={completedCount > 0} />
      </div>

      <div className="flex flex-wrap gap-2">
        <FilterButton active={view === "mine"} onClick={() => setView("mine")}>My Actions</FilterButton>
        <FilterButton active={view === "open"} onClick={() => setView("open")}>Open</FilterButton>
        <FilterButton active={view === "overdue"} onClick={() => setView("overdue")} warning={overdueCount > 0}>Overdue</FilterButton>
        <FilterButton active={view === "completed"} onClick={() => setView("completed")}>Completed</FilterButton>
        <FilterButton active={view === "all"} onClick={() => setView("all")}>All</FilterButton>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <ClipboardCheck className="mx-auto h-8 w-8 text-slate-400" />
          <h2 className="mt-4 font-bold text-slate-900">No corrective actions in this view</h2>
          <p className="mt-2 text-sm text-slate-500">Actions are created from a finding when resolution work is required.</p>
          <button onClick={() => navigate("/findings")} className="mt-5 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-700">Open Findings</button>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((action) => {
            const overdue = isOverdue(action)
            const completed = action.status === "completed"
            const cancelled = action.status === "cancelled"
            const nextStep = completed
              ? "Return to the finding, verify evidence, then submit the resolution for approval."
              : overdue
                ? "Update this overdue action now, then complete it before the finding can move forward."
                : "Complete this corrective action before the finding can be submitted for approval."

            return (
              <article key={action.id} className={`overflow-hidden rounded-2xl border bg-white shadow-sm ${completed ? "border-emerald-200" : overdue ? "border-red-200" : "border-slate-200"}`}>
                <div className={`h-1 ${completed ? "bg-emerald-500" : overdue ? "bg-red-500" : "bg-blue-500"}`} />
                <div className="p-5">
                  <div className="grid gap-5 xl:grid-cols-[1.45fr_.65fr_.65fr_.75fr] xl:items-start">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] font-bold text-blue-600">{action.serverId || action.id}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-600">{action.priority}</span>
                        {completed && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold uppercase text-emerald-700"><CheckCircle2 className="h-3 w-3" /> Completed</span>}
                        {overdue && <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-1 text-[10px] font-bold uppercase text-red-700"><TriangleAlert className="h-3 w-3" /> Overdue</span>}
                      </div>
                      <h2 className="mt-2 text-base font-bold text-slate-900">{action.findingTitle}</h2>
                      <button onClick={() => navigate(`/findings/${action.findingId}`)} className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:underline">
                        Finding {action.findingId} <ExternalLink className="h-3 w-3" />
                      </button>
                      {action.notes && <p className="mt-3 text-xs leading-5 text-slate-600">{action.notes}</p>}
                    </div>

                    <div>
                      <div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><UserRound className="h-3.5 w-3.5" /> Owner</div>
                      <div className="mt-1 text-sm font-semibold text-slate-800">{action.owner}</div>
                    </div>

                    <div>
                      <div className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400"><CalendarDays className="h-3.5 w-3.5" /> Due</div>
                      <div className={`mt-1 text-sm font-semibold ${overdue ? "text-red-700" : "text-slate-800"}`}>{action.dueDate}</div>
                    </div>

                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-400">Status</div>
                      <select
                        value={action.status}
                        disabled={cancelled}
                        onChange={(e) => changeStatus(action, e.target.value as ActionStatus)}
                        className={`mt-1 w-full rounded-lg border px-2 py-2 text-xs font-semibold ${completed ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-700"}`}
                      >
                        <option value="open">Open</option>
                        <option value="in_review">In Progress</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                      </select>
                    </div>
                  </div>

                  <div className={`mt-5 rounded-xl border p-4 ${completed ? "border-emerald-200 bg-emerald-50" : overdue ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}>
                    <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
                      <div>
                        <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-slate-500"><Clock3 className="h-3.5 w-3.5" /> Next Step</div>
                        <p className="mt-1 text-xs font-semibold leading-5 text-slate-700">{nextStep}</p>
                      </div>
                      <button onClick={() => navigate(`/findings/${action.findingId}`)} className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold ${completed ? "bg-emerald-600 text-white hover:bg-emerald-700" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"}`}>
                        {completed ? "Return to Finding" : "Open Related Finding"} <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

const FilterButton = ({ active, onClick, children, warning = false }: { active: boolean; onClick: () => void; children: React.ReactNode; warning?: boolean }) => (
  <button onClick={onClick} className={`rounded-xl border px-4 py-2 text-xs font-bold transition ${active ? "border-blue-600 bg-blue-600 text-white" : warning ? "border-red-200 bg-red-50 text-red-700 hover:bg-red-100" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>{children}</button>
)

const Metric = ({ label, value, warning = false, success = false }: { label: string; value: number; warning?: boolean; success?: boolean }) => (
  <div className={`rounded-xl border bg-white p-5 shadow-sm ${warning ? "border-red-200" : success ? "border-emerald-200" : "border-slate-200"}`}>
    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
    <div className={`mt-2 text-3xl font-black ${warning ? "text-red-600" : success ? "text-emerald-600" : "text-slate-900"}`}>{value}</div>
  </div>
)

export default ActionsPage
