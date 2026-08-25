const roundedScore = (value, computed) =>
  computed && typeof value === "number" && Number.isFinite(value)
    ? Math.round(value)
    : null

export const mapHealthSnapshot = (raw) => {
  const computationStatus = raw.computation_status ?? "computed"
  const computed = computationStatus === "computed"
  const overallScore = roundedScore(raw.overall_score, computed)
  const scoreBand =
    raw.score_band ??
    (computationStatus === "partial"
      ? "Partial"
      : computationStatus === "not_computed"
        ? "Not Computed"
        : overallScore !== null && overallScore >= 80
          ? "Healthy"
          : overallScore !== null && overallScore >= 60
            ? "Needs Attention"
            : "At Risk")

  return {
    id: raw.id,
    overall_score: overallScore,
    cost_score: roundedScore(raw.cost_score, computed),
    schedule_score: roundedScore(raw.schedule_score, computed),
    progress_score: roundedScore(raw.progress_score, computed),
    data_quality_score: roundedScore(
      raw.dq_score ?? raw.data_quality_score,
      computed,
    ),
    status_label: scoreBand.toUpperCase(),
    critical_findings_count: raw.component_breakdown?.critical_count ?? 0,
    warning_findings_count: raw.component_breakdown?.warning_count ?? 0,
    observation_findings_count: raw.component_breakdown?.observation_count ?? 0,
    score_band: scoreBand,
    computation_status: computationStatus,
    coverage_ratio: raw.coverage_ratio ?? (computed ? 1 : 0),
    unavailable_domains: raw.unavailable_domains ?? [],
    component_breakdown: raw.component_breakdown,
    key_drivers: raw.key_drivers,
    created_at: raw.created_at,
  }
}
