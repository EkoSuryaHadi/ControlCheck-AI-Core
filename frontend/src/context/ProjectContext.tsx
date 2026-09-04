import React, { createContext, useContext, useState, useEffect, useCallback } from "react"
import { api, Project, AnalysisRun, HealthSnapshot, Finding, AnalysisJob } from "@/lib/api"
import { useAuth } from "./AuthContext"
import { trackEvent } from "@/lib/analytics"
import { mapHealthSnapshot } from "@/lib/health"
import { initialProjectWorkspace, projectIdToPersist } from "@/lib/project-selection.js"
import { isPersistentWorkspaceSession } from "@/lib/demo-session.js"
import { shouldUseAsyncUpload } from "@/lib/upload-limits.js"

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const JOB_POLL_INTERVAL_MS = 3000
const JOB_POLL_TIMEOUT_MS = 15 * 60 * 1000 // 15 minutes ceiling

interface ProjectContextType {
  projects: Project[]
  currentProject: Project | null
  currentRun: AnalysisRun | null
  healthData: HealthSnapshot | null
  liveFindings: Finding[]
  isLoading: boolean
  isUploading: boolean
  setCurrentProject: (project: Project) => void
  removeProject: (projectId: string) => void
  refreshProjects: () => Promise<void>
  refreshHealthAndFindings: () => Promise<void>
  uploadWorkbook: (file: File, preset?: string) => Promise<AnalysisRun | null>
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
  const { orgId, isAuthenticated, token } = useAuth()
  const isPersistentSession = isPersistentWorkspaceSession(token)
  const initialWorkspace = initialProjectWorkspace()
  const [projects, setProjects] = useState<Project[]>(initialWorkspace.projects)
  const [currentProject, setCurrentProject] = useState<Project | null>(initialWorkspace.currentProject)
  const [currentRun, setCurrentRun] = useState<AnalysisRun | null>(null)
  const [healthData, setHealthData] = useState<HealthSnapshot | null>(initialWorkspace.healthData)
  const [liveFindings, setLiveFindings] = useState<Finding[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const refreshProjects = useCallback(async () => {
    if (!isPersistentSession) {
      setProjects([])
      setCurrentProject(null)
      setCurrentRun(null)
      setLiveFindings([])
      return
    }
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
  }, [orgId, isPersistentSession])

  const refreshHealthAndFindings = useCallback(async () => {
    if (!currentProject || !isPersistentSession) return
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
  }, [currentProject, isPersistentSession])

  const pollAnalysisJob = async (job: AnalysisJob): Promise<AnalysisJob> => {
    const deadline = Date.now() + JOB_POLL_TIMEOUT_MS
    let current = job
    while (["queued", "processing"].includes(String(current.status || "").toLowerCase())) {
      if (Date.now() > deadline) {
        throw new Error("Analysis is taking longer than expected — check the job list shortly.")
      }
      await sleep(JOB_POLL_INTERVAL_MS)
      current = await api.jobs.get(job.id)
    }
    return current
  }

  const uploadWorkbookAsync = async (file: File): Promise<AnalysisRun | null> => {
    if (!currentProject?.id) throw new Error("A project must be selected before upload.")
    trackEvent("project_check_async_upload_started", { project_id: currentProject.id, file_name: file.name, file_size: file.size })

    // 1. Ask the API for a presigned R2 upload target. Environments without
    //    presign support (local single-server deployments) fall back to the
    //    synchronous upload, which accepts .mpp when the API has a JVM.
    let upload_url: string
    let storage_key: string
    try {
      const target = await api.runs.createUploadUrl(currentProject.id, file)
      upload_url = target.upload_url
      storage_key = target.storage_key
    } catch (err: any) {
      const status = err?.response?.status
      const code = err?.response?.data?.error?.code
      if (status === 501 || status === 400 || code === "presign_unsupported") {
        const fallback = await api.runs.upload(currentProject.id, file)
        if (!fallback?.id) throw new Error("Upload API did not return a valid analysis run ID.")
        setCurrentRun(isSuccessfulRun(fallback) ? fallback : null)
        const summary = {
          runId: fallback.id,
          projectId: currentProject.id,
          ruleCount: Number(fallback.rule_count ?? 0),
          findingCount: Number(fallback.finding_count ?? 0),
          durationMs: fallback.duration_ms,
          completedAt: fallback.completed_at || null,
        }
        localStorage.setItem("controlcheck_last_analysis_summary", JSON.stringify(summary))
        trackEvent("project_check_async_upload_fallback_sync", { project_id: currentProject.id, file_name: file.name })
        if (isSuccessfulRun(fallback)) await refreshHealthAndFindings()
        return fallback
      }
      throw err
    }

    // 2. Browser streams the file straight to object storage (bypasses the
    //    serverless request-body limit entirely).
    const putResponse = await fetch(upload_url, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    })
    if (!putResponse.ok) {
      throw new Error(`Direct storage upload failed (HTTP ${putResponse.status}).`)
    }

    // 3. Record the queued job and poll until the VPS worker finishes.
    const job = await api.runs.createAsyncRun(currentProject.id, {
      storage_key,
      filename: file.name,
      content_type: file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      file_size_bytes: file.size,
      workbook_sha256: null,
    })
    const finished = await pollAnalysisJob(job)
    if (String(finished.status).toLowerCase() === "failed") {
      throw new Error(finished.error_message || "Analysis failed on the worker.")
    }
    if (!finished.analysis_run_id) {
      throw new Error("Worker finished without producing an analysis run.")
    }

    // 4. Load the completed run and refresh the workspace.
    const run = await api.runs.get(finished.analysis_run_id)
    setCurrentRun(isSuccessfulRun(run) ? run : null)
    const summary = {
      runId: run.id,
      projectId: currentProject.id,
      ruleCount: Number(run.rule_count ?? 0),
      findingCount: Number(run.finding_count ?? 0),
      durationMs: run.duration_ms,
      completedAt: run.completed_at || null,
    }
    localStorage.setItem("controlcheck_last_analysis_summary", JSON.stringify(summary))
    trackEvent("project_check_async_upload_completed", { project_id: currentProject.id, run_id: run.id, finding_count: summary.findingCount })
    if (isSuccessfulRun(run)) await refreshHealthAndFindings()
    return run
  }

  const uploadWorkbook = async (file: File, preset?: string): Promise<AnalysisRun | null> => {
    if (!isPersistentSession) throw new Error("Demo mode is limited to preflight validation.")
    if (!currentProject?.id) throw new Error("A project must be selected before upload.")
    if (!file || file.size <= 0) throw new Error("A non-empty source file is required.")

    // Large workbooks bypass the serverless body limit: browser → R2 → VPS
    // worker queue. Small workbooks keep the synchronous fast path.
    if (!preset && shouldUseAsyncUpload(file)) {
      try {
        setIsUploading(true)
        return await uploadWorkbookAsync(file)
      } finally {
        setIsUploading(false)
      }
    }

    try {
      setIsUploading(true)
      trackEvent("project_check_upload_started", { project_id: currentProject.id, file_name: file.name })

      const res = preset
        ? await api.runs.uploadValidated(currentProject.id, file, preset)
        : await api.runs.upload(currentProject.id, file)
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
      if (isSuccessfulRun(res)) await refreshHealthAndFindings()
      return res
    } catch (err) {
      console.error("Upload error:", err)
      trackEvent("project_check_upload_failed", { project_id: currentProject.id })
      throw err
    } finally {
      setIsUploading(false)
    }
  }

  const removeProject = (projectId: string) => {
    setProjects((current) => {
      const remaining = current.filter((project) => project.id !== projectId)
      setCurrentProject((selected) => selected?.id === projectId ? (remaining[0] || null) : selected)
      if (remaining.length === 0) localStorage.removeItem("controlcheck_current_project_id")
      return remaining
    })
  }

  useEffect(() => {
    if (isAuthenticated && orgId) refreshProjects()
  }, [isAuthenticated, orgId, refreshProjects])

  useEffect(() => {
    if (currentProject && isPersistentSession) {
      const projectId = projectIdToPersist(currentProject.id)
      if (projectId) localStorage.setItem("controlcheck_current_project_id", projectId)
      refreshHealthAndFindings()
    }
  }, [currentProject, isPersistentSession, refreshHealthAndFindings])

  return (
    <ProjectContext.Provider value={{ projects, currentProject, currentRun, healthData, liveFindings, isLoading, isUploading, setCurrentProject, removeProject, refreshProjects, refreshHealthAndFindings, uploadWorkbook }}>
      {children}
    </ProjectContext.Provider>
  )
}

export const useProject = () => {
  const context = useContext(ProjectContext)
  if (!context) throw new Error("useProject must be used within a ProjectProvider")
  return context
}




