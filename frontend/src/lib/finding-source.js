export function serverFindings(liveFindings) {
  return Array.isArray(liveFindings) ? liveFindings : []
}

export function resolveServerFinding(liveFindings, findingId) {
  return serverFindings(liveFindings).find(
    (finding) => finding.id === findingId || finding.rule_id === findingId,
  ) || null
}

export function resolveFindingEvidence(finding, loadedEvidence, serverBacked) {
  if (serverBacked) return Array.isArray(loadedEvidence) ? loadedEvidence : []
  return Array.isArray(finding?.evidence_records) ? finding.evidence_records : []
}
