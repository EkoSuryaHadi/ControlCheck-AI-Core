import axios from "axios"
import { resolveApiBaseUrl } from "./api-base-url.js"
import { collectFindingPages } from "./findings-pagination.js"

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL as string | undefined)

export const apiClient = axios.create({ baseURL: API_BASE_URL })

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("controlcheck_token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  const orgId = localStorage.getItem("controlcheck_org_id")
  if (orgId) config.headers["X-Organization-ID"] = orgId
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
      localStorage.removeItem("controlcheck_token")
    }
    return Promise.reject(error)
  }
)

export interface User { id: string; email: string; name: string; role?: string }
export interface Project { id: string; organization_id: string; code: string; name: string; client_name?: string; currency: string; status: string }
export interface HealthSnapshot {
  id?: string; overall_score: number | null; cost_score: number | null; schedule_score: number | null; progress_score: number | null; data_quality_score: number | null;
  status_label: string; critical_findings_count: number; warning_findings_count: number; observation_findings_count: number;
  score_band?: string; computation_status?: "computed" | "partial" | "not_computed"; coverage_ratio?: number; unavailable_domains?: string[];
  component_breakdown?: Record<string, any>; key_drivers?: Array<Record<string, any>>; data_date?: string; created_at?: string
}
export interface Finding {
  id: string; analysis_run_id?: string; rule_id: string; rule_name?: string; entity_type?: string; entity_id?: string; title: string;
  category: "cost" | "schedule" | "progress" | "data_quality" | "cost_control" | string;
  severity: "critical" | "warning" | "observation" | string; status: "open" | "in_review" | "resolved" | "dismissed" | string;
  wbs?: string; wbs_code?: string; wbs_name?: string; impact?: string; business_impact?: string; description?: string;
  metrics?: Record<string, any>; calculation?: Record<string, any>; recommendation?: string; potential_impact?: string;
  detected_at?: string; detected_on?: string; ai_summary?: string; budget?: string; actual?: string; commitment?: string; eac?: string;
  variance?: string; variance_pct?: string;
  evidence_records?: Array<{ id: string; source_sheet: string; source_rows: number[]; record_ids: string[]; fields: Record<string, any>; aggregation?: Record<string, any> }>
}
export interface AnalysisRun {
  id: string; project_id: string; engine_version?: string; workbook_sha256?: string; status: "completed" | "running" | "failed" | string;
  rule_count?: number; finding_count?: number; duration_ms?: number; started_at?: string; completed_at?: string; created_at?: string
}
export interface AnalysisSummary {
  analysis_run_id: string
  snapshot_id: string
  domains: Record<string, string>
  cost: { available: boolean; budget_total: number; actual_total: number; commitment_total: number }
  schedule: {
    activity_count: number; critical_count: number; negative_float_count: number; high_float_count: number
    activities: Array<{ activity_id: string; activity_name: string; wbs_code?: string | null; baseline_finish: string; actual_finish?: string | null; planned_progress: number; actual_progress: number; total_float_days: number; critical: boolean; status: string }>
  }
  progress: { available: boolean; source: string; planned_progress: number; actual_progress: number; variance: number }
}
export interface FindingFeedback { id: string; organization_id: string; project_id: string; analysis_run_id: string; finding_id?: string | null; rating: "useful" | "not_useful"; comment?: string | null; status: string; created_at: string }
export interface OwnerMetrics { registrations: number; active_users: number; projects: number; uploads_accepted: number; analyses_completed: number; result_use_events: number; result_use_rate: number; feedback_count: number; useful_feedback_rate: number; error_rate: number; generated_at: string }
export interface AIAskResponse {
  conversation_id: string; answer: string; key_evidence: Array<Record<string, any>>; impact: string; recommended_action: string;
  confidence: string; data_caveat?: string | null; evidence_references: string[]
}
export interface PersistentFindingAction {
  id: string; organization_id: string; project_id: string; finding_id: string; title: string; owner: string; due_date: string;
  priority: "high" | "medium" | "low"; status: "open" | "in_review" | "completed" | "cancelled"; notes?: string | null;
  created_by?: string | null; completed_at?: string | null; created_at: string; updated_at: string
}
export interface ClosureReadiness {
  can_close: boolean; evidence_ready: boolean; actions_ready: boolean; approval_required: boolean; approval_ready: boolean;
  approval_decision?: string | null; approval_id?: string | null; action_count: number; open_action_count: number;
  completed_action_count: number; blockers: string[]
}
export interface GovernancePolicy {
  project_id: string; critical_sla_days: number; warning_sla_days: number; observation_sla_days: number;
  require_critical_closure_approval: boolean; require_warning_closure_approval: boolean
}
export interface ClosureApproval {
  id: string; organization_id: string; project_id: string; finding_id: string; requested_by?: string | null;
  decision: "pending" | "approved" | "rejected" | "withdrawn"; decided_by?: string | null; decision_note?: string | null;
  requested_at: string; decided_at?: string | null
}
export interface GovernanceEscalation {
  id: string; organization_id: string; project_id: string; finding_id: string; action_id?: string | null;
  escalation_type: "finding_sla" | "action_overdue"; severity: "critical" | "warning" | "observation";
  status: "open" | "acknowledged" | "resolved"; reason: string; metadata_json?: Record<string, any> | null;
  triggered_at: string; acknowledged_by?: string | null; acknowledged_at?: string | null; resolved_at?: string | null
}
export interface ReportPackage {
  id: string
  organization_id: string
  project_id: string
  analysis_run_id: string
  generated_by?: string | null
  report_name: string
  report_type: "monthly" | "executive" | "cost" | "schedule" | "progress" | string
  period: string
  snapshot: {
    schema_version?: string
    generated_at?: string
    generated_by_name?: string
    project?: Record<string, any>
    analysis_run?: Record<string, any>
    health?: Record<string, any>
    summary?: Record<string, any>
    findings?: Array<Record<string, any>>
  }
  pdf_size_bytes: number
  created_at: string
}

export const api = {
  auth: {
    login: async (credentials: { email: string; password: string }) => (await apiClient.post("/v1/auth/login", credentials)).data,
    register: async (data: { email: string; password: string; full_name?: string; organization_name?: string }) => (await apiClient.post("/v1/auth/register", data)).data,
  },
  telemetry: {
    event: async (event_name: string, payload: { project_id?: string; analysis_run_id?: string; finding_id?: string; metadata?: Record<string, string | number | boolean | null> } = {}) =>
      (await apiClient.post("/v1/telemetry/events", { event_name, ...payload })).data,
  },
  projects: {
    list: async (orgId: string) => (await apiClient.get(`/v1/organizations/${orgId}/projects`)).data,
    create: async (orgId: string, data: { code: string; name: string; currency?: string }) => (await apiClient.post(`/v1/organizations/${orgId}/projects`, data)).data,
    remove: async (projectId: string) => (await apiClient.delete(`/v1/projects/${projectId}`)).data,
  },
  runs: {
    list: async (projectId: string) => (await apiClient.get(`/v1/projects/${projectId}/analysis-runs`)).data,
    upload: async (projectId: string, file: File, idempotencyKey?: string) => {
      const formData = new FormData(); formData.append("file", file)
      const headers: Record<string, string> = { "Content-Type": "multipart/form-data" }
      if (idempotencyKey) headers["X-Idempotency-Key"] = idempotencyKey
      return (await apiClient.post(`/v1/projects/${projectId}/analysis-runs`, formData, { headers })).data
    },
    uploadValidated: async (projectId: string, file: File, preset: string) => {
      const formData = new FormData(); formData.append("file", file)
      return (await apiClient.post(`/v1/projects/${projectId}/validated-imports/analysis-runs?preset=${encodeURIComponent(preset)}`, formData, { headers: { "Content-Type": "multipart/form-data" } })).data
    },
    getSummary: async (projectId: string, runId: string): Promise<AnalysisSummary> =>
      (await apiClient.get(`/v1/projects/${projectId}/analysis-runs/${runId}/summary`)).data,
    getHealth: async (runId: string) => (await apiClient.get(`/v1/analysis-runs/${runId}/health`)).data,
    getFindings: async (runId: string, params?: { severity?: string; category?: string; status?: string }) => collectFindingPages<Finding>(
      async (pageParams: Record<string, unknown>) => (await apiClient.get(`/v1/analysis-runs/${runId}/findings`, { params: pageParams })).data,
      params,
    ),
  },
  findings: {
    updateStatus: async (findingId: string, status: string) => (await apiClient.patch(`/v1/findings/${findingId}/status`, { status })).data,
    getEvidence: async (findingId: string) => (await apiClient.get(`/v1/findings/${findingId}/evidence`)).data,
    closureReadiness: async (findingId: string): Promise<ClosureReadiness> => (await apiClient.get(`/v1/findings/${findingId}/closure-readiness`)).data,
    closeGoverned: async (findingId: string) => (await apiClient.post(`/v1/findings/${findingId}/close`)).data,
    getClosureApproval: async (findingId: string): Promise<ClosureApproval | null> => (await apiClient.get(`/v1/findings/${findingId}/closure-approval`)).data,
    requestClosureApproval: async (findingId: string, note?: string): Promise<ClosureApproval> => (await apiClient.post(`/v1/findings/${findingId}/closure-approval`, { note })).data,
    feedback: async (findingId: string, rating: "useful" | "not_useful", comment?: string): Promise<FindingFeedback> =>
      (await apiClient.post(`/v1/findings/${findingId}/feedback`, { rating, comment })).data,
  },
  feedback: {
    run: async (runId: string, rating: "useful" | "not_useful", comment?: string): Promise<FindingFeedback> =>
      (await apiClient.post(`/v1/runs/${runId}/feedback`, { rating, comment })).data,
  },
  owner: {
    metrics: async (): Promise<OwnerMetrics> => (await apiClient.get("/v1/owner/metrics")).data,
  },
  actions: {
    listProject: async (projectId: string): Promise<{ items: PersistentFindingAction[] }> => (await apiClient.get(`/v1/projects/${projectId}/actions`)).data,
    listFinding: async (findingId: string): Promise<{ items: PersistentFindingAction[] }> => (await apiClient.get(`/v1/findings/${findingId}/actions`)).data,
    create: async (findingId: string, data: { title: string; owner: string; due_date: string; priority: string; notes?: string; actor?: string }) => (await apiClient.post(`/v1/findings/${findingId}/actions`, data)).data,
    update: async (actionId: string, data: { title?: string; owner?: string; due_date?: string; priority?: string; status?: string; notes?: string; actor?: string }) => (await apiClient.patch(`/v1/actions/${actionId}`, data)).data,
  },
  reports: {
    listProject: async (projectId: string): Promise<{ items: ReportPackage[] }> => (await apiClient.get(`/v1/projects/${projectId}/reports`)).data,
    create: async (projectId: string, data: { analysis_run_id: string; report_name: string; report_type: string; period: string }): Promise<ReportPackage> => (await apiClient.post(`/v1/projects/${projectId}/reports`, data)).data,
    get: async (reportId: string): Promise<ReportPackage> => (await apiClient.get(`/v1/reports/${reportId}`)).data,
    openPdf: async (reportId: string) => {
      const response = await apiClient.get(`/v1/reports/${reportId}/pdf`, { responseType: "blob" })
      const url = URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }))
      window.open(url, "_blank", "noopener,noreferrer")
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    },
  },
  governance: {
    getPolicy: async (projectId: string): Promise<GovernancePolicy> => (await apiClient.get(`/v1/projects/${projectId}/governance-policy`)).data,
    updatePolicy: async (projectId: string, patch: Partial<Omit<GovernancePolicy, "project_id">>): Promise<GovernancePolicy> => (await apiClient.patch(`/v1/projects/${projectId}/governance-policy`, patch)).data,
    listApprovals: async (projectId: string, decision?: string): Promise<{ items: ClosureApproval[] }> => (await apiClient.get(`/v1/projects/${projectId}/closure-approvals`, { params: { decision } })).data,
    decideApproval: async (approvalId: string, decision: "approved" | "rejected", note?: string): Promise<ClosureApproval> => (await apiClient.post(`/v1/closure-approvals/${approvalId}/decision`, { decision, note })).data,
    scanEscalations: async (projectId: string): Promise<{ items: GovernanceEscalation[] }> => (await apiClient.post(`/v1/projects/${projectId}/governance-escalations/scan`)).data,
    listEscalations: async (projectId: string, status?: string): Promise<{ items: GovernanceEscalation[] }> => (await apiClient.get(`/v1/projects/${projectId}/governance-escalations`, { params: { status } })).data,
    acknowledgeEscalation: async (escalationId: string): Promise<GovernanceEscalation> => (await apiClient.post(`/v1/governance-escalations/${escalationId}/acknowledge`)).data,
  },
  health: { getTrend: async (projectId: string) => (await apiClient.get(`/v1/projects/${projectId}/health-trend`)).data },
  ai: {
    ask: async (projectId: string, question: string, conversationId?: string) => (await apiClient.post(`/v1/projects/${projectId}/ai/ask`, { question, conversation_id: conversationId || undefined })).data,
    listConversations: async (projectId: string) => (await apiClient.get(`/v1/projects/${projectId}/ai/conversations`)).data,
    getMessages: async (conversationId: string) => (await apiClient.get(`/v1/ai/conversations/${conversationId}/messages`)).data,
  },
}

