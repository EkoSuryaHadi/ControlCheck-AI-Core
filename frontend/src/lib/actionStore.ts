import { api, PersistentFindingAction } from "@/lib/api"

export type ActionPriority = "high" | "medium" | "low"
export type ActionStatus = "open" | "in_review" | "completed" | "cancelled"

export interface FindingAction {
  id: string
  serverId?: string
  projectId?: string
  findingId: string
  findingTitle: string
  owner: string
  dueDate: string
  priority: ActionPriority
  status: ActionStatus
  notes?: string
  createdAt: string
  updatedAt: string
}

const STORAGE_KEY = "controlcheck_finding_actions_v1"

export const getActions = (): FindingAction[] => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")
  } catch {
    return []
  }
}

const saveActions = (actions: FindingAction[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(actions))
  window.dispatchEvent(new CustomEvent("controlcheck-actions-updated"))
}

const isUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)

const mapServerAction = (item: PersistentFindingAction, existing?: FindingAction): FindingAction => ({
  id: item.id,
  serverId: item.id,
  projectId: item.project_id,
  findingId: item.finding_id,
  findingTitle: existing?.findingTitle || `Finding ${item.finding_id.slice(0, 8)}`,
  owner: item.owner,
  dueDate: item.due_date,
  priority: item.priority,
  status: item.status,
  notes: item.notes || undefined,
  createdAt: item.created_at,
  updatedAt: item.updated_at,
})

export const syncProjectActions = async (projectId: string): Promise<FindingAction[]> => {
  try {
    const response = await api.actions.listProject(projectId)
    const local = getActions()
    const mapped = response.items.map((item) => {
      const existing = local.find((action) => action.serverId === item.id || action.id === item.id || action.findingId === item.finding_id)
      return mapServerAction(item, existing)
    })
    const localOnly = local.filter((action) => !action.serverId && !mapped.some((serverAction) => serverAction.findingId === action.findingId && serverAction.owner === action.owner && serverAction.dueDate === action.dueDate))
    const merged = [...mapped, ...localOnly]
    saveActions(merged)
    return merged
  } catch {
    return getActions()
  }
}

export const getActionsForFinding = (findingId: string) => getActions().filter((a) => a.findingId === findingId)

export const createAction = (input: Omit<FindingAction, "id" | "createdAt" | "updatedAt" | "serverId">): FindingAction => {
  const now = new Date().toISOString()
  const action: FindingAction = {
    ...input,
    id: `ACT-${Date.now().toString(36).toUpperCase()}`,
    createdAt: now,
    updatedAt: now,
  }
  saveActions([action, ...getActions()])

  if (isUuid(input.findingId)) {
    void api.actions.create(input.findingId, {
      title: input.findingTitle,
      owner: input.owner,
      due_date: input.dueDate,
      priority: input.priority,
      notes: input.notes,
    }).then((server: PersistentFindingAction) => {
      const actions = getActions().map((item) => item.id === action.id ? mapServerAction(server, item) : item)
      saveActions(actions)
    }).catch(() => {})
  }

  return action
}

export const updateAction = (id: string, patch: Partial<Pick<FindingAction, "owner" | "dueDate" | "priority" | "status" | "notes">>) => {
  const current = getActions().find((item) => item.id === id)
  const actions = getActions().map((action) => action.id === id ? { ...action, ...patch, updatedAt: new Date().toISOString() } : action)
  saveActions(actions)
  const updated = actions.find((a) => a.id === id) || null

  const serverId = current?.serverId || (current && isUuid(current.id) ? current.id : undefined)
  if (serverId) {
    void api.actions.update(serverId, {
      owner: patch.owner,
      due_date: patch.dueDate,
      priority: patch.priority,
      status: patch.status,
      notes: patch.notes,
    }).catch(() => {})
  }
  return updated
}

export const deleteAction = (id: string) => {
  const current = getActions().find((action) => action.id === id)
  if (!current) return

  const serverId = current.serverId || (isUuid(current.id) ? current.id : undefined)
  if (serverId) {
    updateAction(id, { status: "cancelled" })
    return
  }

  saveActions(getActions().filter((action) => action.id !== id))
}
