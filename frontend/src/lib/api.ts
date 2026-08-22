import axios from "axios"

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || "/api"

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
})

// Attach auth token and org ID if available
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("controlcheck_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const orgId = localStorage.getItem("controlcheck_org_id")
  if (orgId) {
    config.headers["X-Organization-ID"] = orgId
  }
  return config
})

// Intercept 401s
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
      localStorage.removeItem("controlcheck_token")
    }
    return Promise.reject(error)
  }
)

export interface User {
  id: string
  email: string
  name: string
  role?: string
}

export interface Project {
  id: string
  organization_id: string
  code: string
  name: string
  client_name?: string
  currency: string
  status: string
}

export interface HealthSnapshot {
  id?: string
  overall_score: number
  cost_score: number
  schedule_score: number
  progress_score: number
  data_quality_score: number
  status_label: string
  critical_findings_count: number
  warning_findings_count: number
  observation_findings_count: number
  score_band?: string
  component_breakdown?: Record<string, any>
  key_drivers?: Array<Record<string, any>>
  data_date?: string
  created_at?: string
}

export interface Finding {
  id: string
  analysis_run_id?: string
  rule_id: string
  rule_name?: string
  entity_type?: string
  entity_id?: string
  title: string
  category: "cost" | "schedule" | "progress" | "data_quality" | "cost_control" | string
  severity: "critical" | "warning" | "observation" | string
  status: "open" | "in_review" | "resolved" | "dismissed" | string
  wbs?: string
  wbs_code?: string
  wbs_name?: string
  impact?: string
  business_impact?: string
  description?: string
  metrics?: Record<string, any>
  calculation?: Record<string, any>
  recommendation?: string
  potential_impact?: string
  detected_at?: string
  detected_on?: string
  ai_summary?: string
  budget?: string
  actual?: string
  commitment?: string
  eac?: string
  variance?: string
  variance_pct?: string
  evidence_records?: Array<{
    id: string
    source_sheet: string
    source_rows: number[]
    record_ids: string[]
    fields: Record<string, any>
    aggregation?: Record<string, any>
  }>
}

export interface AnalysisRun {
  id: string
  project_id: string
  engine_version?: string
  workbook_sha256?: string
  status: "completed" | "running" | "failed" | string
  rule_count?: number
  finding_count?: number
  duration_ms?: number
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface AIAskResponse {
  conversation_id: string
  answer: string
  key_evidence: Array<Record<string, any>>
  impact: string
  recommended_action: string
  confidence: string
  data_caveat?: string | null
  evidence_references: string[]
}

// API Methods
export const api = {
  auth: {
    login: async (credentials: { email: string; password: string }) => {
      const res = await apiClient.post("/v1/auth/login", credentials)
      return res.data
    },
    register: async (data: { email: string; password: string; full_name?: string; organization_name?: string }) => {
      const res = await apiClient.post("/v1/auth/register", data)
      return res.data
    },
  },
  projects: {
    list: async (orgId: string) => {
      const res = await apiClient.get(`/v1/organizations/${orgId}/projects`)
      return res.data
    },
    create: async (orgId: string, data: { code: string; name: string; currency?: string }) => {
      const res = await apiClient.post(`/v1/organizations/${orgId}/projects`, data)
      return res.data
    },
  },
  runs: {
    list: async (projectId: string) => {
      const res = await apiClient.get(`/v1/projects/${projectId}/analysis-runs`)
      return res.data
    },
    upload: async (projectId: string, file: File, idempotencyKey?: string) => {
      const formData = new FormData()
      formData.append("file", file)
      const headers: Record<string, string> = { "Content-Type": "multipart/form-data" }
      if (idempotencyKey) {
        headers["X-Idempotency-Key"] = idempotencyKey
      }
      const res = await apiClient.post(`/v1/projects/${projectId}/analysis-runs`, formData, { headers })
      return res.data
    },
    getHealth: async (runId: string) => {
      const res = await apiClient.get(`/v1/analysis-runs/${runId}/health`)
      return res.data
    },
    getFindings: async (runId: string, params?: { severity?: string; category?: string; status?: string }) => {
      const res = await apiClient.get(`/v1/analysis-runs/${runId}/findings`, { params })
      return res.data
    },
  },
  findings: {
    updateStatus: async (findingId: string, status: string) => {
      const res = await apiClient.patch(`/v1/findings/${findingId}/status`, { status })
      return res.data
    },
    getEvidence: async (findingId: string) => {
      const res = await apiClient.get(`/v1/findings/${findingId}/evidence`)
      return res.data
    },
  },
  health: {
    getTrend: async (projectId: string) => {
      const res = await apiClient.get(`/v1/projects/${projectId}/health-trend`)
      return res.data
    },
  },
  ai: {
    ask: async (projectId: string, question: string, conversationId?: string) => {
      const res = await apiClient.post(`/v1/projects/${projectId}/ai/ask`, {
        question,
        conversation_id: conversationId || undefined,
      })
      return res.data
    },
    listConversations: async (projectId: string) => {
      const res = await apiClient.get(`/v1/projects/${projectId}/ai/conversations`)
      return res.data
    },
    getMessages: async (conversationId: string) => {
      const res = await apiClient.get(`/v1/ai/conversations/${conversationId}/messages`)
      return res.data
    },
  },
}
