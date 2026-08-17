import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";


const ARTIFACT_TOOL_DEFAULT = "file:///C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
const artifactTool = await import(process.env.CONTROLCHECK_ARTIFACT_TOOL_MODULE || ARTIFACT_TOOL_DEFAULT);
const { SpreadsheetFile, Workbook } = artifactTool;

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DATA_DIR = path.join(ROOT, "data");
const PREVIEW_ROOT = path.join(ROOT, "validation", "previews", "v0.2");
const SOURCE_WORKBOOK = path.join(DATA_DIR, "ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx");
const ONLY = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1] : "all";

const COLORS = {
  navy: "#123047",
  teal: "#0F6B6D",
  paleBlue: "#DCEAF2",
  paleGreen: "#E3F1EA",
  paleAmber: "#FFF2CC",
  ink: "#18323F",
  line: "#B9CAD3",
  white: "#FFFFFF",
};

const TABLES = {
  WBS: ["wbs_code", "wbs_name", "parent_wbs", "discipline", "level"],
  Budget: ["budget_id", "wbs_code", "cost_code", "description", "budget_amount", "status", "effective_date"],
  Actual_Cost: ["transaction_id", "transaction_date", "wbs_code", "cost_code", "vendor_id", "vendor_name", "po_number", "description", "actual_amount", "status"],
  Commitments: ["commitment_id", "wbs_code", "po_number", "vendor_id", "vendor_name", "committed_amount", "invoiced_amount", "status", "commitment_date"],
  Schedule: ["activity_id", "wbs_code", "activity_name", "discipline", "baseline_start", "baseline_finish", "actual_start", "actual_finish", "planned_progress", "actual_progress", "total_float_days", "critical", "status"],
  Progress: ["progress_id", "period", "wbs_code", "planned_progress", "actual_progress", "variance", "status"],
};

const VALIDATION_HEADERS = [
  "case_id", "rule_id", "boundary_type", "input_value", "threshold_value",
  "expected_trigger", "operator", "entity_id", "exception_id", "description",
];

function readSourceDataset() {
  const result = spawnSync(
    "python",
    [path.join(ROOT, "tools", "export_dataset_json.py"), SOURCE_WORKBOOK],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 20 * 1024 * 1024 },
  );
  if (result.status !== 0) {
    throw new Error(`Source workbook extraction failed: ${result.stderr || result.stdout}`);
  }
  return JSON.parse(result.stdout);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function dateValue(value) {
  return value ? new Date(`${value}T00:00:00Z`) : null;
}

function normalizedRows(records, headers) {
  const dateFields = new Set([
    "effective_date", "transaction_date", "commitment_date", "baseline_start",
    "baseline_finish", "actual_start", "actual_finish", "period",
  ]);
  const numericFields = new Set([
    "budget_amount", "actual_amount", "committed_amount", "invoiced_amount",
    "planned_progress", "actual_progress", "variance", "total_float_days", "level",
  ]);
  return records.map((record) => headers.map((header) => {
    const value = record[header];
    if (dateFields.has(header)) return dateValue(value);
    if (numericFields.has(header) && value !== null && value !== "") return Number(value);
    return value ?? null;
  }));
}

function columnName(index) {
  let result = "";
  for (let value = index; value > 0; value = Math.floor((value - 1) / 26)) {
    result = String.fromCharCode(65 + ((value - 1) % 26)) + result;
  }
  return result;
}

function styleTitle(range) {
  range.format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, fontSize: 15 },
    verticalAlignment: "center",
  };
  range.format.rowHeight = 30;
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.teal,
    font: { bold: true, color: COLORS.white },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: COLORS.line },
  };
  range.format.rowHeight = 28;
}

function applyColumnFormatting(sheet, headers, rowCount) {
  headers.forEach((header, index) => {
    const letter = columnName(index + 1);
    const range = sheet.getRange(`${letter}4:${letter}${Math.max(4, rowCount + 3)}`);
    if (header.includes("date") || header.includes("finish") || header.includes("start") || header === "period") {
      range.format.numberFormat = "yyyy-mm-dd";
    } else if (header.includes("amount")) {
      range.format.numberFormat = "#,##0";
    } else if (["planned_progress", "actual_progress", "variance"].includes(header)) {
      range.format.numberFormat = "0.0%";
    } else if (["input_value", "threshold_value"].includes(header)) {
      range.format.numberFormat = "0.0000";
    }
    const width = header === "case_id" ? 26
      : header === "rule_id" ? 12
      : header === "boundary_type" ? 19
      : header === "input_value" || header === "threshold_value" ? 22
      : header === "expected_trigger" ? 16
      : header === "operator" ? 12
      : header === "entity_id" ? 24
      : header === "exception_id" ? 28
      : header.includes("description") ? 64
      : header.includes("name") ? 26
      : header.includes("amount") ? 16
      : header.includes("date") || header.includes("finish") || header.includes("start") || header === "period" ? 18
      : Math.min(20, Math.max(11, header.length + 2));
    sheet.getRange(`${letter}1:${letter}${Math.max(4, rowCount + 3)}`).format.columnWidth = width;
  });
}

function addTableSheet(workbook, name, title, headers, rows, accent = COLORS.paleBlue) {
  const sheet = workbook.worksheets.add(name);
  const last = columnName(headers.length);
  sheet.getRange(`A1:${last}1`).merge();
  sheet.getRange("A1").values = [[title]];
  styleTitle(sheet.getRange(`A1:${last}1`));
  sheet.getRange(`A3:${last}3`).values = [headers];
  styleHeader(sheet.getRange(`A3:${last}3`));
  if (rows.length) {
    sheet.getRange(`A4:${last}${rows.length + 3}`).values = rows;
    sheet.getRange(`A4:${last}${rows.length + 3}`).format = {
      font: { color: COLORS.ink, fontSize: 10 },
      verticalAlignment: "center",
    };
    sheet.getRange(`A4:${last}${rows.length + 3}`).conditionalFormats.addCustom(
      "=MOD(ROW(),2)=0",
      { fill: accent },
    );
  }
  applyColumnFormatting(sheet, headers, rows.length);
  sheet.freezePanes.freezeRows(3);
  sheet.showGridLines = false;
  return sheet;
}

function addProjectInfo(workbook, info) {
  const sheet = workbook.worksheets.add("Project_Info");
  sheet.getRange("A1:B1").merge();
  sheet.getRange("A1").values = [["CONTROLCHECK AI — VALIDATION DATASET"]];
  styleTitle(sheet.getRange("A1:B1"));
  const rows = Object.entries(info).map(([key, value]) => [key, value instanceof Date ? value : value]);
  sheet.getRange(`A2:B${rows.length + 1}`).values = rows;
  sheet.getRange(`A2:A${rows.length + 1}`).format = { font: { bold: true, color: COLORS.ink }, fill: COLORS.paleBlue };
  sheet.getRange(`B2:B${rows.length + 1}`).format = { font: { color: COLORS.ink } };
  sheet.getRange(`A1:A${rows.length + 1}`).format.columnWidth = 24;
  sheet.getRange(`B1:B${rows.length + 1}`).format.columnWidth = 48;
  const dataDateRow = Object.keys(info).indexOf("data_date") + 2;
  sheet.getRange(`B${dataDateRow}`).format.numberFormat = "yyyy-mm-dd";
  sheet.showGridLines = false;
  return sheet;
}

function addReadme(workbook, kind) {
  const rows = [
    ["Purpose", kind === "golden" ? "Exhaustive positive-fixture validation for all 20 deterministic rules." : "Literal boundary and approved-exception specification for numeric rules."],
    ["Dataset version", "0.2"],
    ["Catalogue version", "0.2"],
    ["Expected-use limitation", "Controlled-fixture quality metrics are not customer-production accuracy claims."],
    ["Ground truth policy", "Expected labels are curated independently from production rule functions."],
  ];
  addTableSheet(workbook, "README", "DEVELOPER NOTES", ["topic", "detail"], rows, COLORS.paleGreen);
}

function goldenCases() {
  return [
    ["GOLD-CST001-31", "CST-001", "planted_positive", 8490690000, 8000000000, true, ">", "3.1", null, "Adjusted WBS budget makes actual cost exceed budget."],
    ["GOLD-CST001-32", "CST-001", "planted_positive", 16595674000, 16000000000, true, ">", "3.2", null, "Adjusted WBS budget makes actual cost exceed budget."],
    ["GOLD-CST002-33", "CST-002", "planted_positive", 14375799000, 14000000000, true, ">", "3.3", null, "COM-005 remaining commitment makes exposure exceed budget."],
    ["GOLD-PRG003-31", "PRG-003", "planted_positive", 0.0, 0.02, true, "<=", "3.1", null, "Latest actual progress equals prior period while cost rises materially."],
  ];
}

function buildGoldenDataset(source) {
  const dataset = clone(source);
  dataset.dataset_version = "0.2";
  for (const budget of dataset.budgets) {
    if (budget.wbs_code === "3.1") budget.budget_amount = "8000000000";
    if (budget.wbs_code === "3.2") budget.budget_amount = "16000000000";
  }
  const commitment = dataset.commitments.find((item) => item.commitment_id === "COM-005");
  commitment.invoiced_amount = "5000000000";
  const progress = dataset.progress.find((item) => item.progress_id === "PRG-31-4");
  progress.actual_progress = 0.60;
  progress.variance = progress.actual_progress - progress.planned_progress;
  return dataset;
}

function buildBoundaryDataset() {
  return {
    project: { project_id: "PRJ-CCAI-BND-001", project_name: "ControlCheck Numeric Boundary Fixture" },
    dataset_version: "0.2",
    data_date: "2026-08-15",
    wbs_nodes: [{ wbs_code: "1.0", wbs_name: "Boundary Control WBS", parent_wbs: null, discipline: "Controls", level: 1 }],
    budgets: [{ budget_id: "BUD-BND-001", wbs_code: "1.0", cost_code: "BND", description: "Boundary fixture budget", budget_amount: "1000000000", status: "Active", effective_date: "2026-01-01" }],
    actual_costs: [{ transaction_id: "ACT-BND-001", transaction_date: "2026-01-15", wbs_code: "1.0", cost_code: "BND", vendor_id: null, vendor_name: null, po_number: null, description: "Benign fixture transaction", actual_amount: "100000000", status: "Posted" }],
    commitments: [{ commitment_id: "COM-BND-001", wbs_code: "1.0", po_number: "PO-BND-001", vendor_id: null, vendor_name: null, committed_amount: "0", invoiced_amount: "0", status: "Closed", commitment_date: "2026-01-01" }],
    schedule: [{ activity_id: "ACTV-BND-001", wbs_code: "1.0", activity_name: "Benign completed activity", discipline: "Controls", baseline_start: "2026-01-01", baseline_finish: "2026-01-10", actual_start: "2026-01-01", actual_finish: "2026-01-10", planned_progress: 1, actual_progress: 1, total_float_days: 0, critical: false, status: "Complete" }],
    progress: [
      { progress_id: "PRG-BND-001", period: "2026-07-15", wbs_code: "1.0", planned_progress: 0.5, actual_progress: 0.5, variance: 0, status: "Approved" },
      { progress_id: "PRG-BND-002", period: "2026-08-15", wbs_code: "1.0", planned_progress: 0.6, actual_progress: 0.6, variance: 0, status: "Approved" },
    ],
  };
}

function boundaryCases() {
  const specs = {
    "DQ-003": [1.0, "gt"],
    "CST-001": [1.0, "gt"],
    "CST-002": [1.0, "gt"],
    "CST-003": [1.3, "gte"],
    "CST-004": [0.4, "gte"],
    "CST-005": [0.25, "gte"],
    "CST-006": [0.8, "gte"],
    "SCH-001": [1, "gte"],
    "SCH-002": [7, "gte"],
    "SCH-003": [1, "gte"],
    "SCH-004": [0.1, "gte"],
    "SCH-005": [0, "lt"],
    "PRG-001": [0.1, "gte"],
    "PRG-002": [1.0, "gt"],
    "PRG-003": [0.2, "gte"],
    "XDOM-001": [0.8, "gte"],
  };
  const rows = [];
  for (const [ruleId, [threshold, operator]] of Object.entries(specs)) {
    const dayRules = new Set(["SCH-001", "SCH-002", "SCH-003", "SCH-005"]);
    const delta = dayRules.has(ruleId) ? 1 : 0.0001;
    const values = { below: threshold - delta, equal: threshold, above: threshold + delta };
    for (const boundaryType of ["below", "equal", "above"]) {
      const value = values[boundaryType];
      const expected = operator === "lt" ? value < threshold
        : operator === "gt" ? value > threshold
        : value >= threshold;
      rows.push([
        `BND-${ruleId.replace("-", "")}-${boundaryType.toUpperCase()}`,
        ruleId,
        boundaryType,
        value,
        threshold,
        expected,
        operator,
        `${ruleId}|${boundaryType.toUpperCase()}`,
        null,
        `Literal ${boundaryType} case for ${ruleId}; evaluated independently by the boundary harness.`,
      ]);
    }
  }
  rows.push(["BND-CST005-EXC", "CST-005", "approved_exception", 0.30, 0.25, false, "exception", "CST-005|APPROVED", "EXC-ADVANCE-PAYMENT", "Approved advance payment remains auditable but is excluded from exception-aware error counts."]);
  rows.push(["BND-PRG003-EXC", "PRG-003", "approved_exception", 0.25, 0.20, false, "exception", "PRG-003|APPROVED", "EXC-ADVANCE-PROCUREMENT", "Approved advance procurement remains auditable but is excluded from exception-aware error counts."]);
  return rows;
}

function addDatasetSheets(workbook, dataset, kind, validationRows) {
  addProjectInfo(workbook, {
    project_id: dataset.project.project_id,
    project_name: dataset.project.project_name,
    dataset_version: dataset.dataset_version,
    catalogue_version: "0.2",
    data_date: dateValue(dataset.data_date),
    fixture_type: kind === "golden" ? "golden_positive" : "boundary_negative",
    purpose: kind === "golden" ? "Controlled exhaustive positive validation." : "Literal numeric boundary and approved-exception validation.",
  });
  const recordMap = {
    WBS: dataset.wbs_nodes,
    Budget: dataset.budgets,
    Actual_Cost: dataset.actual_costs,
    Commitments: dataset.commitments,
    Schedule: dataset.schedule,
    Progress: dataset.progress,
  };
  for (const [sheetName, headers] of Object.entries(TABLES)) {
    addTableSheet(
      workbook,
      sheetName,
      `${sheetName.toUpperCase()} — ${kind === "golden" ? "GOLDEN POSITIVE" : "BOUNDARY / NEGATIVE"}`,
      headers,
      normalizedRows(recordMap[sheetName], headers),
    );
  }
  addTableSheet(workbook, "Validation_Cases", "MACHINE-READABLE VALIDATION CASES", VALIDATION_HEADERS, validationRows, COLORS.paleAmber);
  addReadme(workbook, kind);
}

async function exportAndVerify(kind, dataset, validationRows, filename) {
  const workbook = Workbook.create();
  addDatasetSheets(workbook, dataset, kind, validationRows);
  await fs.mkdir(DATA_DIR, { recursive: true });
  const outputPath = path.join(DATA_DIR, filename).replaceAll("\\", "/");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);

  const previewDir = path.join(PREVIEW_ROOT, kind);
  await fs.mkdir(previewDir, { recursive: true });
  const inspections = [];
  for (const sheet of workbook.worksheets.items) {
    const used = sheet.getUsedRange(true);
    const inspection = await workbook.inspect({
      kind: "region,computedStyle",
      sheetId: sheet.name,
      range: used.address,
      maxChars: 3500,
      tableMaxRows: 8,
      tableMaxCols: 14,
    });
    inspections.push(`# ${sheet.name}\n${inspection.ndjson}`);
    const preview = await workbook.render({
      sheetName: sheet.name,
      autoCrop: "all",
      scale: 0.65,
      format: "png",
    });
    const safeName = sheet.name.replace(/[^A-Za-z0-9_-]+/g, "_");
    await fs.writeFile(path.join(previewDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
    console.log(`rendered:${kind}:${sheet.name}`);
  }
  await fs.writeFile(path.join(previewDir, "inspection.ndjson"), `${inspections.join("\n")}\n`, "utf8");
  console.log(`exported:${outputPath}`);
}

if (ONLY === "all" || ONLY === "golden") {
  await exportAndVerify(
    "golden",
    buildGoldenDataset(readSourceDataset()),
    goldenCases(),
    "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
  );
}
if (ONLY === "all" || ONLY === "boundary") {
  await exportAndVerify(
    "boundary",
    buildBoundaryDataset(),
    boundaryCases(),
    "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx",
  );
}
