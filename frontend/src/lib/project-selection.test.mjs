import assert from "node:assert/strict"
import test from "node:test"

import { projectIdToPersist } from "./project-selection.js"

test("does not overwrite a saved real project with the demo bootstrap project", () => {
  assert.equal(projectIdToPersist("demo-prj-001"), null)
})

test("persists a real project selection", () => {
  assert.equal(projectIdToPersist("project-123"), "project-123")
})
