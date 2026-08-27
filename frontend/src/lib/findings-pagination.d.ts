export interface FindingPage<T = Record<string, unknown>> {
  items: T[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export function collectFindingPages<T = Record<string, unknown>>(
  fetchPage: (params: Record<string, unknown>) => Promise<Partial<FindingPage<T>> | T[]>,
  filters?: Record<string, unknown>,
  pageSize?: number,
): Promise<FindingPage<T>>
