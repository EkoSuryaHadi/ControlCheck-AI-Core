export function serverFindings(liveFindings) {
  return Array.isArray(liveFindings) ? liveFindings : []
}

export function resolveServerFinding(liveFindings, findingId) {
  return serverFindings(liveFindings).find(
    (finding) => finding.id === findingId || finding.rule_id === findingId,
  ) || null
}
