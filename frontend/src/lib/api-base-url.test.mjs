import assert from "node:assert/strict"
import test from "node:test"

import { resolveApiBaseUrl } from "./api-base-url.js"

test("VITE_API_BASE_URL selects the externally hosted API", () => {
  assert.equal(
    resolveApiBaseUrl("https://controlcheck-api.example.com"),
    "https://controlcheck-api.example.com",
  )
})

test("the local API route remains the development fallback", () => {
  assert.equal(resolveApiBaseUrl(undefined), "/api")
})
