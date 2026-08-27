import React, { createContext, useContext, useState, useEffect, useCallback } from "react"
import { api, Project, AnalysisRun, HealthSnapshot, Finding } from "@/lib/api"
import { useAuth } from "./AuthContext"
import { trackEvent } from "@/lib/analytics"
import { mapHealthSnapshot } from "@/lib/health"
import { initialProjectWorkspace, projectIdToPersist } from "@/lib/project-selection.js"

interface ProjectContextType {
  projects: Project[]
  currentProject: Project | null
  currentRun: AnalysisRun | null
  healthData: HealthSnapshot | null
  liveFindings: Finding[]
  isLoading: boolean
  isUploading: boolean
  setCurrentProject: (project: Project) => void
  refreshProjects: () => Promise<void>
  refreshHealthAndFindings: () => Promise<void>
  uploadWorkbook: (file: File) => Promise<AnalysisRun | null>
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

const isSuccessfulRun = (run: AnalysisRun) => ["succeeded", "completed"].includes(String(run.status || "").toLowerCase())

const runTimestamp = (run: AnalysisRun) => {
  const raw = run.completed_at || run.started_at || run.created_at || ""
  const value = Date.parse(raw)
  return Number.isFinite(value) ? value : 0
}

const latestSuccessfulRun = (runs: AnalysisRun[]): AnalysisRun | null => {
  const successful = runs.filter(isSuccessfulRun)
  if (successful.length === 0) return null
  return [...successful].sort((a, b) => runTimestamp(b) - runTimestamp(a))[0]
}

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { orgId, isAuthenticated } = useAuth()
  const initialWorkspace = initialProjectWorkspace()
  const [projects, setProjects] = useState<Project[]>(initialWorkspace.projects)
  const [currentProject, setCurrentProject] = useState<Project | null>(initialWorkspace.currentProject)
  const [currentRun, setCurrentRun] = useState<AnalysisRun | null>(null)
  const [healthData, setHealthData] = useState<HealthSnapshot | null>(initialWorkspace.healthData)
  const [liveFindings, setLiveFindings] = useState<Finding[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const refreshProjects = useCallback(async () => {
    if (!orgId) return
    try {
      setIsLoading(true)
      const data = await api.projects.list(orgId)
      const items = Array.isArray(data) ? data : data.items || []
      if (items.length > 0) {
        setProjects(items)
        const savedId = localStorage.getItem("controlcheck_current_project_id")
        const found = items.find((p: Project) => p.id === savedId) || items[0]
        setCurrentProject(found)
      }
    } catch {
      // Keep current state; do not synthesize server success.
    } finally {
      setIsLoading(false)
    }
  }, [orgId])

  const refreshHealthAndFindings = useCallback(async () => {
    if (!currentProject) return
    try {
      const runsData = await api.runs.list(currentProject.id)
      const runs: AnalysisRun[] = Array.isArray(runsData) ? runsData : runsData.items || []
      if (runs.length === 0) {
        setCurrentRun(null)
        setLiveFindings([])
        return
      }

      const successfulRun = latestSuccessfulRun(runs)
      if (!successfulRun) {
        setCurrentRun(null)
        setLiveFindings([])
        return
      }

      setCurrentRun(successfulRun)

      try {
        const rawHealth = await api.runs.getHealth(successfulRun.id)
        const mappedHealth = mapHealthSnapshot(rawHealth)
        setHealthData(mappedHealth)
      } catch {
        // Preserve prior health rather than claiming synthetic server output.
      }

      try {
        const findingsData = await api.runs.getFindings(successfulRun.id)
        const items = Array.isArray(findingsData) ? findingsData : findingsData.items || []
        setLiveFindings(items)
      } catch {
        // Preserve current findings if the server read fails.
      }
    } catch {
      // Preserve current workspace state on transient failures.
    }
  }, [currentProject])

  const uploadWorkbook = async (file: File): Promise<AnalysisRun | null> => {
    if (!currentProject?.id) throw new Error("A project must be selected before upload.")
    if (!file || file.size <= 0) throw new Error("A non-empty source file is required.")

    try {
      setIsUploading(true)
      trackEvent("project_check_upload_started", { project_id: currentProject.id, file_name: file.name })

      const res = await api.runs.upload(currentProject.id, file)
      if (!res?.id) throw new Error("Upload API did not return a valid analysis run ID.")

      setCurrentRun(isSuccessfulRun(res) ? res : null)
      const summary = {
        runId: res.id,
        projectId: currentProject.id,
        ruleCount: Number(res.rule_count ?? 0),
        findingCount: Number(res.finding_count ?? 0),
        durationMs: res.duration_ms,
        completedAt: res.completed_at || null,
      }
      localStorage.setItem("controlcheck_last_analysis_summary", JSON.stringify(summary))
      trackEvent("project_check_upload_accepted", { project_id: currentProject.id, run_id: res.id, finding_count: summary.findingCount })
      return res
    } catch (err) {
      console.error("Upload error:", err)
      trackEvent("project_check_upload_failed", { project_id: currentProject.id })
      throw err
    } finally {
      setIsUploading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated && orgId) refreshProjects()
  }, [isAuthenticated, orgId, refreshProjects])

  useEffect(() => {
    if (currentProject) {
      const projectId = projectIdToPersist(currentProject.id)
      if (projectId) localStorage.setItem("controlcheck_current_project_id", projectId)
      refreshHealthAndFindings()
    }
  }, [currentProject, refreshHealthAndFindings])

  return (
    <ProjectContext.Provider value={{ projects, currentProject, currentRun, healthData, liveFindings, isLoading, isUploading, setCurrentProject, refreshProjects, refreshHealthAndFindings, uploadWorkbook }}>
      {children}
    </ProjectContext.Provider>
  )
}

export const useProject = () => {
  const context = useContext(ProjectContext)
  if (!context) throw new Error("useProject must be used within a ProjectProvider")
  return context
}
