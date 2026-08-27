const DEMO_PROJECT_ID = "demo-prj-001"

export function projectIdToPersist(projectId) {
  if (!projectId || projectId === DEMO_PROJECT_ID) return null
  return projectId
}
