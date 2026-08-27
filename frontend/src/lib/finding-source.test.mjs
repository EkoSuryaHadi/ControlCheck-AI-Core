import assert from "node:assert/strict"
import test from "node:test"

import { resolveServerFinding, serverFindings } from "./finding-source.js"

test("protected findings use only records returned by the server", () => {
  const live = [{ id: "server-1", title: "Server finding" }]
  assert.equal(serverFindings(live), live)
  assert.deepEqual(serverFindings(undefined), [])
})

test("an unknown route never substitutes a demo finding", () => {
  assert.equal(resolveServerFinding([], "FND-2024-001"), null)
})

test("resolves a real finding by persistent ID or rule ID", () => {
  const finding = { id: "uuid-1", rule_id: "CST-001" }
  assert.equal(resolveServerFinding([finding], "uuid-1"), finding)
  assert.equal(resolveServerFinding([finding], "CST-001"), finding)
})
