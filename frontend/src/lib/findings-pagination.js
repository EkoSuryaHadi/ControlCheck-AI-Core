export async function collectFindingPages(fetchPage, filters = {}, pageSize = 100) {
  const items = []
  let offset = 0
  let total = 0

  for (;;) {
    const page = await fetchPage({ ...filters, limit: pageSize, offset })
    const pageItems = Array.isArray(page) ? page : (page?.items || [])
    items.push(...pageItems)
    total = Number(page?.total ?? items.length)

    const hasMore = Boolean(page?.has_more ?? (items.length < total))
    if (!hasMore || pageItems.length === 0) break
    offset += pageItems.length
  }

  return { items, total: Math.max(total, items.length), limit: items.length, offset: 0, has_more: false }
}
