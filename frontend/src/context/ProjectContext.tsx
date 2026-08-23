import React, { createContext, useContext, useState, useEffect, useCallback } from "react"
import { api, Project, AnalysisRun, HealthSnapshot, Finding } from "@/lib/api"
import { useAuth } from "./AuthContext"
import { trackEvent } from "@/lib/analytics"

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

export const DEMO_PROJECT: Project = {
  id: "demo-prj-001",
  organization_id: "demo-org-001",
  code: "GCF-EXP-01",
  name: "Gas Compression Facility Expansion",
  client_name: "PT Energi Nusantara",
  currency: "IDR",
  status: "active",
}

export const DEMO_HEALTH: HealthSnapshot = {
  overall_score: 68,
  cost_score: 58,
  schedule_score: 71,
  progress_score: 67,
  data_quality_score: 92,
  status_label: "MODERATE",
  critical_findings_count: 17,
  warning_findings_count: 23,
  observation_findings_count: 12,
  score_band: "Needs Attention",
  data_date: "2024-10-28",
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { orgId, isAuthenticated } = useAuth()
  const [projects, setProjects] = useState<Project[]>([DEMO_PROJECT])
  const [currentProject, setCurrentProject] = useState<Project | null>(DEMO_PROJECT)
  const [currentRun, setCurrentRun] = useState<AnalysisRun | null>(null)
  const [healthData, setHealthData] = useState<HealthSnapshot | null>(DEMO_HEALTH)
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
      const runs = Array.isArray(runsData) ? runsData : runsData.items || []
      if (runs.length === 0) {
        setCurrentRun(null)
        setLiveFindings([])
        return
      }

      const latestRun = runs[0]
      setCurrentRun(latestRun)

      try {
        const rawHealth = await api.runs.getHealth(latestRun.id)
        const mappedHealth: HealthSnapshot = {
          id: rawHealth.id,
          overall_score: Math.round(rawHealth.overall_score || 0),
          cost_score: Math.round(rawHealth.cost_score || 0),
          schedule_score: Math.round(rawHealth.schedule_score || 0),
          progress_score: Math.round(rawHealth.progress_score || 0),
          data_quality_score: Math.round(rawHealth.dq_score || rawHealth.data_quality_score || 0),
          status_label: rawHealth.score_band?.toUpperCase() || (rawHealth.overall_score >= 80 ? "HEALTHY" : rawHealth.overall_score >= 60 ? "MODERATE" : "HIGH RISK"),
          critical_findings_count: rawHealth.component_breakdown?.critical_count ?? 0,
          warning_findings_count: rawHealth.component_breakdown?.warning_count ?? 0,
          observation_findings_count: rawHealth.component_breakdown?.observation_count ?? 0,
          score_band: rawHealth.score_band,
          component_breakdown: rawHealth.component_breakdown,
          key_drivers: rawHealth.key_drivers,
          created_at: rawHealth.created_at,
        }
        setHealthData(mappedHealth)
      } catch {
        // Preserve prior health rather than claiming synthetic server output.
      }

      try {
        const findingsData = await api.runs.getFindings(latestRun.id)
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

      setCurrentRun(res)
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
      localStorage.setItem("controlcheck_current_project_id", currentProject.id)
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
