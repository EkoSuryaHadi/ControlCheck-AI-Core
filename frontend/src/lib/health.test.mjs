import assert from "node:assert/strict"
import test from "node:test"

import { mapHealthSnapshot } from "./health.js"

for (const [status, scoreBand] of [
  ["partial", "Partial"],
  ["not_computed", "Not Computed"],
]) {
  test(`unavailable health is never labeled healthy (${status})`, () => {
    const health = mapHealthSnapshot({
      overall_score: null,
      cost_score: null,
      schedule_score: null,
      progress_score: null,
      dq_score: null,
      computation_status: status,
      coverage_ratio: status === "partial" ? 0.6 : 0,
      unavailable_domains: ["progress"],
      score_band: scoreBand,
      component_breakdown: {},
      key_drivers: [],
    })

    assert.equal(health.overall_score, null)
    assert.equal(health.status_label, scoreBand.toUpperCase())
    assert.notEqual(health.status_label, "HEALTHY")
  })
}

test("fully computed healthy scores remain compatible", () => {
  const health = mapHealthSnapshot({
    overall_score: 92.4,
    cost_score: 91,
    schedule_score: 93,
    progress_score: 94,
    dq_score: 90,
    computation_status: "computed",
    coverage_ratio: 1,
    unavailable_domains: [],
    score_band: "Healthy",
    component_breakdown: {},
    key_drivers: [],
  })

  assert.equal(health.overall_score, 92)
  assert.equal(health.status_label, "HEALTHY")
})

test("partial health preserves available schedule score while keeping overall unavailable", () => {
  const health = mapHealthSnapshot({
    overall_score: null,
    cost_score: null,
    schedule_score: 70.6,
    progress_score: null,
    dq_score: null,
    computation_status: "partial",
    coverage_ratio: 0.25,
    unavailable_domains: ["cost", "progress", "data_quality"],
    score_band: "Partial",
    component_breakdown: {},
    key_drivers: [],
  })

  assert.equal(health.overall_score, null)
  assert.equal(health.schedule_score, 71)
  assert.equal(health.cost_score, null)
})
