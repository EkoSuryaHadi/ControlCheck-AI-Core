import test from "node:test"
import assert from "node:assert/strict"
import {
  PUBLIC_BETA_MAX_UPLOAD_BYTES,
  ASYNC_UPLOAD_MAX_BYTES,
  validatePublicBetaUpload,
  shouldUseAsyncUpload,
  isMsProjectFile,
} from "./upload-limits.js"

test("MS Project files always route to the async worker path", () => {
  const tiny = { name: "proyek.mpp", size: 1024 }
  assert.equal(isMsProjectFile(tiny), true)
  assert.equal(shouldUseAsyncUpload(tiny), true)
  assert.equal(validatePublicBetaUpload(tiny), null)
  assert.equal(shouldUseAsyncUpload({ name: "plan.mpx", size: 1024 }), true)
})

test("Excel workbooks below 4 MiB stay on the synchronous path", () => {
  const file = { name: "plan.xlsx", size: 1024 }
  assert.equal(isMsProjectFile(file), false)
  assert.equal(shouldUseAsyncUpload(file), false)
})

test("oversized workbook beyond the 500 MB worker limit is rejected", () => {
  const error = validatePublicBetaUpload({
    name: "huge.xlsx",
    size: 500 * 1024 * 1024 + 1,
  })

  assert.match(error, /500 MB worker-upload limit/i)
})

test("workbook at the 500 MiB worker boundary is accepted", () => {
  const error = validatePublicBetaUpload({
    name: "valid.xlsx",
    size: 500 * 1024 * 1024,
  })

  assert.equal(error, null)
})

test("workbook above the synchronous 4 MiB limit routes to the async worker", () => {
  const file = { name: "large.xlsx", size: PUBLIC_BETA_MAX_UPLOAD_BYTES + 1 }
  assert.equal(validatePublicBetaUpload(file), null)
  assert.equal(shouldUseAsyncUpload(file), true)
})

test("workbook at the four MiB boundary stays on the synchronous path", () => {
  const file = { name: "valid.xlsx", size: 4 * 1024 * 1024 }
  assert.equal(PUBLIC_BETA_MAX_UPLOAD_BYTES, 4 * 1024 * 1024)
  assert.equal(ASYNC_UPLOAD_MAX_BYTES, 500 * 1024 * 1024)
  assert.equal(validatePublicBetaUpload(file), null)
  assert.equal(shouldUseAsyncUpload(file), false)
})
