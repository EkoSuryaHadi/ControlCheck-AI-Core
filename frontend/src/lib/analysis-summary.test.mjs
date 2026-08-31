import test from "node:test"
import assert from "node:assert/strict"
import { availabilityMessage } from "./analysis-summary.js"

test("reports absent cost data instead of presenting sample cost values", () => {
  assert.equal(
    availabilityMessage({ available: false }, "cost"),
    "No budget, actual cost, or commitment data was included in this import."
  )
})

test("labels MPP-derived progress clearly", () => {
  assert.equal(
    availabilityMessage({ available: true, source: "schedule_derived" }, "progress"),
    "Progress is derived from the imported MPP schedule."
  )
})
