import type { Finding } from "./api"

export function serverFindings(liveFindings: Finding[] | null | undefined): Finding[]
export function resolveServerFinding(liveFindings: Finding[] | null | undefined, findingId: string | undefined): Finding | null
export function resolveFindingEvidence(finding: Partial<Finding> | null | undefined, loadedEvidence: unknown[] | null | undefined, serverBacked: boolean): unknown[]
