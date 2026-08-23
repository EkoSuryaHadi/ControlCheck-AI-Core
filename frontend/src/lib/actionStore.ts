export type ActionPriority = "high" | "medium" | "low"
export type ActionStatus = "open" | "in_review" | "completed"

export interface FindingAction {
  id: string
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

export const getActionsForFinding = (findingId: string) => getActions().filter((a) => a.findingId === findingId)

export const createAction = (input: Omit<FindingAction, "id" | "createdAt" | "updatedAt">): FindingAction => {
  const now = new Date().toISOString()
  const action: FindingAction = {
    ...input,
    id: `ACT-${Date.now().toString(36).toUpperCase()}`,
    createdAt: now,
    updatedAt: now,
  }
  saveActions([action, ...getActions()])
  return action
}

export const updateAction = (id: string, patch: Partial<Pick<FindingAction, "owner" | "dueDate" | "priority" | "status" | "notes">>) => {
  const actions = getActions().map((action) => action.id === id ? { ...action, ...patch, updatedAt: new Date().toISOString() } : action)
  saveActions(actions)
  return actions.find((a) => a.id === id) || null
}

export const deleteAction = (id: string) => {
  saveActions(getActions().filter((action) => action.id !== id))
}
