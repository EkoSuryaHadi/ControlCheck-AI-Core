import React, { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { apiClient } from "@/lib/api"
import { useProject } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { isDemoAccessToken } from "@/lib/demo-session.js"
import {
  UploadCloud, ShieldCheck, AlertTriangle, XCircle, CheckCircle2,
  Loader2, ArrowRight, Download, Settings2, CalendarCheck2, Network,
  FileCog, Plus, LogIn,
} from "lucide-react"

type Preset = "standard" | "msproject" | "p6" | "sap"

type Issue = { row: number; field: string; severity: string; code: string; message: string; value?: unknown }
type Result = {
  filename: string; sheet: string; total_rows: number; detected_headers: string[]; preview: Array<Record<string, unknown>>;
  issues: Issue[]; error_count: number; warning_count: number; data_quality_score: number; schedule_quality_score: number;
  logic_check_count: number; logic_failure_count: number; can_import: boolean;
  relationship_metrics?: {
    relationship_count: number; logic_density: number; open_start_count: number; open_finish_count: number;
    excessive_lag_count: number; negative_lag_count: number; excessive_float_count: number; hard_constraint_count: number;
  }
}

const downloadIssues = (result: Result) => {
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`
  const rows = [["Row","Severity","Field","Code","Value","Message"].join(",")]
  result.issues.forEach(i => rows.push([i.row,i.severity,i.field,i.code,i.value,i.message].map(esc).join(",")))
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${result.filename.replace(/\.[^.]+$/, "")}_validation_report.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export const ValidatedImportPage: React.FC = () => {
  const navigate = useNavigate()
  const { token } = useAuth()
  const { projects, currentProject, setCurrentProject, uploadWorkbook, isUploading } = useProject()
  const [preset, setPreset] = useState<Preset>("msproject")
  const [file, setFile] = useState<File | null>(null)
  const [convertedFile, setConvertedFile] = useState<File | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [validating, setValidating] = useState(false)
  const [convertingMpp, setConvertingMpp] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const errors = useMemo(() => result?.issues.filter(i => i.severity === "error") || [], [result])
  const warnings = useMemo(() => result?.issues.filter(i => i.severity === "warning") || [], [result])
  const isMpp = Boolean(file?.name.toLowerCase().endsWith(".mpp"))
  const isDemo = Boolean(token && isDemoAccessToken(token))

  const convertMpp = async (source: File): Promise<File> => {
    setConvertingMpp(true)
    try {
      const response = await apiClient.post("/mpp-convert", source, {
        responseType: "arraybuffer",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-File-Name": source.name,
          "X-Project-Code": currentProject?.code || "DEMO-PREFLIGHT",
          "X-Project-Name": currentProject?.name || "Demo Preflight Project",
        },
      })
      const outputName = `${source.name.replace(/\.mpp$/i, "")}_ControlCheck.xlsx`
      return new File([response.data], outputName, {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      })
    } finally {
      setConvertingMpp(false)
    }
  }

  const validate = async () => {
    if (!file) return
    setValidating(true); setError(null); setResult(null); setDone(false); setConvertedFile(null)
    try {
      let validationFile = file
      let validationPreset = preset
      if (file.name.toLowerCase().endsWith(".mpp")) {
        validationFile = await convertMpp(file)
        // /mpp-convert yields the canonical governed workbook, which the
        // standard preset validates (not the MS Project export aliases).
        validationPreset = "standard"
        setConvertedFile(validationFile)
      }
      const form = new FormData(); form.append("file", validationFile)
      const response = await apiClient.post(`/v1/imports/preflight?preset=${encodeURIComponent(validationPreset)}`, form, { headers: { "Content-Type": "multipart/form-data" } })
      if (response.data?.error) throw new Error(response.data.error.message)
      setResult(response.data as Result)
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || err?.message || "Validation failed")
    } finally { setValidating(false) }
  }

  const importData = async () => {
    const importFile = convertedFile || file
    if (!importFile || !result?.can_import) return
    if (isDemo) {
      setError("Demo validation is complete. Sign in with a workspace account to persist the project and start analysis.")
      return
    }
    if (!currentProject) {
      setError("Validation passed. Select or create a project before starting the final import and analysis.")
      return
    }
    setError(null)
    try {
      // .mpp files were converted to the canonical workbook, so they run
      // straight through the analysis pipeline (no preset re-mapping).
      if (file?.name.toLowerCase().endsWith(".mpp")) {
        await uploadWorkbook(importFile)
      } else {
        await uploadWorkbook(importFile, preset)
      }
      setDone(true)
    }
    catch (err: any) { setError(err?.response?.data?.error?.message || err?.message || "Import failed") }
  }

  const m = result?.relationship_metrics

  return <div className="mx-auto max-w-7xl space-y-6 pb-12">
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div><div className="mb-1 text-xs text-slate-500">Data &gt; <span className="font-semibold text-slate-900">Validated Import</span></div><h1 className="text-2xl font-bold">Validated Import</h1><p className="mt-1 text-sm text-slate-500">Upload Microsoft Project MPP directly, or validate Excel/CSV schedule data before analysis.</p></div>
      <button onClick={() => navigate("/data/advanced")} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold"><Settings2 className="h-4 w-4" /> Advanced Mapping</button>
    </div>

    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-4">
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="space-y-2">
            <div className="text-[10px] font-bold uppercase text-slate-500">Project</div>
            {!isDemo && projects.length > 0 ? (
              <select
                value={currentProject?.id || ""}
                onChange={(e) => {
                  const selected = projects.find((project) => project.id === e.target.value)
                  if (selected) { setCurrentProject(selected); setError(null) }
                }}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold"
              >
                <option value="" disabled>Select project</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.code} — {project.name}</option>)}
              </select>
            ) : (
              <div className="text-sm font-bold">{isDemo ? "Demo preflight — no persistent project" : "No project selected"}</div>
            )}

            {isDemo ? (
              <div className="space-y-2">
                <div className="text-[10px] leading-4 text-amber-700">Demo mode can convert and validate MPP files, but persistent import and analysis require a real workspace.</div>
                <button onClick={() => navigate("/login?next=%2Fdata&source=demo_import")} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700"><LogIn className="h-3.5 w-3.5" /> Sign in to import</button>
              </div>
            ) : (
              <div className="space-y-2">
                {!currentProject && <div className="text-[10px] leading-4 text-amber-700">Select an existing project or create one before the final import. Validation can run before project creation.</div>}
                <button onClick={() => navigate("/onboarding?next=%2Fdata")} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"><Plus className="h-3.5 w-3.5" /> New Project</button>
              </div>
            )}
          </div>

          <div><label className="text-[10px] font-bold uppercase text-slate-500">Data Source</label><select value={preset} onChange={e => { setPreset(e.target.value as Preset); setResult(null); setConvertedFile(null) }} className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold"><option value="msproject">Microsoft Project — Native MPP / Excel / CSV</option><option value="standard">Standard EPC / ControlCheck</option><option value="p6">Oracle Primavera P6 Export</option><option value="sap">SAP Project/Cost Export</option></select></div>
          {preset === "msproject" && <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-[11px] leading-5 text-blue-900"><b>Native .mpp supported in this preview.</b> ControlCheck converts the MPP in memory to its governed workbook, preserves task hierarchy and predecessor logic for validation, then imports the canonical workbook after approval.</div>}
          <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/70 p-6 text-center"><input id="validated-file" type="file" accept=".mpp,.xlsx,.xlsm,.csv" className="hidden" onChange={e => { const next = e.target.files?.[0] || null; setFile(next); setPreset(next?.name.toLowerCase().endsWith(".mpp") ? "msproject" : preset); setConvertedFile(null); setResult(null); setError(null) }} /><label htmlFor="validated-file" className="block cursor-pointer"><UploadCloud className="mx-auto h-8 w-8 text-blue-600" /><div className="mt-2 text-xs font-semibold">{file?.name || "Choose project file"}</div><div className="mt-1 text-[10px] text-slate-400">MPP, XLSX, XLSM or CSV · public beta limit 4 MB</div></label></div>
          {isMpp && <div className="flex items-center gap-2 rounded-lg border border-purple-100 bg-purple-50 p-3 text-[11px] text-purple-900"><FileCog className="h-4 w-4 shrink-0" /> Native MPP conversion will run automatically before validation.</div>}
          <button onClick={validate} disabled={!file || validating || convertingMpp} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{validating || convertingMpp ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{convertingMpp ? "Converting MPP..." : validating ? "Validating..." : "Validate Before Import"}</button>
        </div>

        {result && <>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="text-[10px] font-bold uppercase text-slate-400">Data Quality</div><div className="mt-1 text-4xl font-bold">{result.data_quality_score}<span className="text-sm font-normal text-slate-400"> / 100</span></div><div className="mt-4 grid grid-cols-3 gap-2"><div className="rounded-lg bg-slate-50 p-2"><div className="text-lg font-bold">{result.total_rows}</div><div className="text-[9px] uppercase text-slate-400">Rows</div></div><div className="rounded-lg bg-red-50 p-2"><div className="text-lg font-bold text-red-700">{result.error_count}</div><div className="text-[9px] uppercase text-red-500">Errors</div></div><div className="rounded-lg bg-amber-50 p-2"><div className="text-lg font-bold text-amber-700">{result.warning_count}</div><div className="text-[9px] uppercase text-amber-500">Warnings</div></div></div></div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><div><div className="text-[10px] font-bold uppercase text-slate-400">Schedule Quality</div><div className="mt-1 text-4xl font-bold">{result.schedule_quality_score}<span className="text-sm font-normal text-slate-400"> / 100</span></div></div><CalendarCheck2 className="h-8 w-8 text-blue-500" /></div></div>
          {m && <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-2"><Network className="h-4 w-4 text-purple-500"/><div className="text-[10px] font-bold uppercase text-slate-400">Relationship Intelligence</div></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div>Logic density <b>{m.logic_density}</b></div><div>Relationships <b>{m.relationship_count}</b></div><div>Open starts <b>{m.open_start_count}</b></div><div>Open finishes <b>{m.open_finish_count}</b></div><div>Excessive lag <b>{m.excessive_lag_count}</b></div><div>Negative lag <b>{m.negative_lag_count}</b></div><div>High float <b>{m.excessive_float_count}</b></div><div>Hard constraints <b>{m.hard_constraint_count}</b></div></div></div>}
        </>}
      </div>

      <div className="space-y-4 lg:col-span-8">
        {error && <div className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><XCircle className="h-5 w-5 shrink-0" />{error}</div>}
        {!result && !error && <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm"><ShieldCheck className="mx-auto h-10 w-10 text-slate-300" /><h2 className="mt-3 text-sm font-bold">Ready for preflight</h2><p className="mt-1 text-xs text-slate-500">Choose an MPP, Excel or CSV file and run validation.</p></div>}
        {result && <>
          {convertedFile && <div className="flex items-start gap-3 rounded-xl border border-purple-200 bg-purple-50 p-4"><FileCog className="h-5 w-5 text-purple-600"/><div><div className="text-sm font-bold text-purple-900">MPP converted successfully</div><div className="mt-1 text-xs text-purple-700">Canonical workbook: {convertedFile.name}. Original MPP remains unchanged.</div></div></div>}
          <div className={`flex items-start gap-3 rounded-xl border p-4 ${result.can_import ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>{result.can_import ? <CheckCircle2 className="h-5 w-5 text-emerald-600"/> : <XCircle className="h-5 w-5 text-red-600"/>}<div className="flex-1"><div className="text-sm font-bold">{result.can_import ? "Validation passed — ready to import" : "Import blocked — fix critical errors first"}</div><div className="mt-1 text-xs opacity-75">Sheet: {result.sheet} · {result.detected_headers.filter(Boolean).length} detected columns</div></div>{result.issues.length > 0 && <button onClick={() => downloadIssues(result)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold"><Download className="h-3.5 w-3.5"/> Error Report</button>}</div>
          {(errors.length > 0 || warnings.length > 0) && <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 px-5 py-4"><h2 className="text-sm font-bold">Validation Issues</h2></div><div className="max-h-[520px] divide-y divide-slate-100 overflow-y-auto">{result.issues.slice(0,150).map((i, idx) => <div key={`${i.row}-${i.code}-${idx}`} className="flex items-start gap-3 px-5 py-3">{i.severity === "error" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500"/> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"/>}<div><div className="text-xs font-semibold">Row {i.row} · {i.field}</div><div className="mt-0.5 text-[11px] text-slate-500">{i.message}</div></div></div>)}</div></div>}
          {isDemo && result.can_import && <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-800">MPP validation passed in Demo mode. Sign in with your workspace account to persist this project and start the full ControlCheck analysis.</div>}
          <div className="flex justify-end gap-3">{done && <div className="mr-auto inline-flex items-center gap-2 text-xs font-semibold text-emerald-700"><CheckCircle2 className="h-4 w-4"/> Import completed and analysis started.</div>}<button onClick={importData} disabled={!result.can_import || isUploading || done || !currentProject || isDemo} title={isDemo ? "Sign in with a workspace account to start final import" : !currentProject ? "Select or create a project to start final import and analysis" : undefined} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{isUploading ? <Loader2 className="h-4 w-4 animate-spin"/> : <ArrowRight className="h-4 w-4"/>}{isUploading ? "Importing..." : isDemo ? "Sign in to Import" : convertedFile ? "Import Converted MPP" : "Import Validated Data"}</button></div>
        </>}
      </div>
    </div>
  </div>
}

