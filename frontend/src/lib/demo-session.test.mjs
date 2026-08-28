import test from "node:test"
import assert from "node:assert/strict"
import { DEMO_ACCESS_TOKEN, isDemoAccessToken } from "./demo-session.js"

test("demo access token is accepted by the demo session policy", () => {
  assert.equal(isDemoAccessToken(DEMO_ACCESS_TOKEN), true)
})

test("ordinary tokens are not treated as demo sessions", () => {
  assert.equal(isDemoAccessToken("some-other-token"), false)
})
