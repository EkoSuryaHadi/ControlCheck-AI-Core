import assert from "node:assert/strict"
import test from "node:test"

import { collectFindingPages } from "./findings-pagination.js"

test("collects every finding when the API result spans multiple pages", async () => {
  const calls = []
  const response = await collectFindingPages(async ({ limit, offset }) => {
    calls.push({ limit, offset })
    const all = Array.from({ length: 54 }, (_, index) => ({ id: `finding-${index + 1}` }))
    const items = all.slice(offset, offset + limit)
    return { items, total: all.length, limit, offset, has_more: offset + items.length < all.length }
  }, {}, 50)

  assert.equal(response.items.length, 54)
  assert.equal(response.total, 54)
  assert.equal(response.has_more, false)
  assert.deepEqual(calls, [{ limit: 50, offset: 0 }, { limit: 50, offset: 50 }])
})

test("preserves filters on each page request", async () => {
  const calls = []
  await collectFindingPages(async (params) => {
    calls.push(params)
    return { items: [], total: 0, has_more: false }
  }, { severity: "critical" }, 100)

  assert.deepEqual(calls, [{ severity: "critical", limit: 100, offset: 0 }])
})
