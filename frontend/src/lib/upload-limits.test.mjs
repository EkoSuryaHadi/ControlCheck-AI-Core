import test from "node:test"
import assert from "node:assert/strict"
import {
  PUBLIC_BETA_MAX_UPLOAD_BYTES,
  validatePublicBetaUpload,
} from "./upload-limits.js"

test("oversized workbook is rejected with actionable public beta copy", () => {
  const error = validatePublicBetaUpload({
    name: "large.xlsx",
    size: 4 * 1024 * 1024 + 1,
  })

  assert.match(error, /4 MB public beta limit/i)
})

test("workbook at the four MiB boundary is accepted", () => {
  const error = validatePublicBetaUpload({
    name: "valid.xlsx",
    size: 4 * 1024 * 1024,
  })

  assert.equal(PUBLIC_BETA_MAX_UPLOAD_BYTES, 4 * 1024 * 1024)
  assert.equal(error, null)
})
