import type { HealthSnapshot } from "./api"

export interface RawHealthSnapshot {
  id?: string
  overall_score: number | null
  cost_score: number | null
  schedule_score: number | null
  progress_score: number | null
  dq_score?: number | null
  data_quality_score?: number | null
  computation_status?: "computed" | "partial" | "not_computed"
  coverage_ratio?: number
  unavailable_domains?: string[]
  score_band?: string
  component_breakdown?: Record<string, any>
  key_drivers?: Array<Record<string, any>>
  created_at?: string
}

export function mapHealthSnapshot(raw: RawHealthSnapshot): HealthSnapshot
