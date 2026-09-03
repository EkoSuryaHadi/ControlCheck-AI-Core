import React, { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { validatePublicBetaUpload } from "@/lib/upload-limits.js"
import {
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  ShieldCheck,
  Loader2,
  FileCheck2,
} from "lucide-react"

type ConnectorPreset = "standard" | "sap" | "p6" | "msproject"

type Mapping = { source: string; preview: string; canonical: string; confidence: number }

type PresetConfig = {
  name: string
  description: string
  datasetName: string
  sheetName: string
  mappings: Mapping[]
}

const PRESETS: Record<ConnectorPreset, PresetConfig> = {
  standard: {
    name: "Standard EPC Canonical Workbook",
    description: "Standard multi-tab Excel template for cost, schedule, progress, budget and commitments.",
    datasetName: "Project Control Workbook",
    sheetName: "Auto-detect",
    mappings: [
      { source: "Posting Date", preview: "25/10/2024", canonical: "transaction_date", confidence: 100 },
      { source: "Project Code", preview: "GCF-EXP-01", canonical: "project_code", confidence: 100 },
      { source: "WBS Code", preview: "03.02.01", canonical: "wbs_code", confidence: 100 },
      { source: "Cost Code", preview: "M-1010", canonical: "cost_code", confidence: 100 },
      { source: "Vendor Name", preview: "PT. Alpha Teknik", canonical: "vendor_name", confidence: 95 },
      { source: "PO Number", preview: "PO-23017", canonical: "po_number", confidence: 100 },
      { source: "Description", preview: "Piping Material", canonical: "description", confidence: 90 },
      { source: "Amount (IDR)", preview: "125,000,000", canonical: "amount", confidence: 100 },
    ],
  },
  sap: {
    name: "SAP S/4HANA & ECC",
    description: "SAP CO/PS financial and project-system spreadsheet export.",
    datasetName: "SAP Project Control Export",
    sheetName: "Auto-detect",
    mappings: [
      { source: "BLDAT", preview: "2024-10-25", canonical: "transaction_date", confidence: 98 },
      { source: "PSPID", preview: "GCF-EXP-01", canonical: "project_code", confidence: 100 },
      { source: "POSID", preview: "GCF.03.02.01", canonical: "wbs_code", confidence: 96 },
      { source: "KSTAR", preview: "51001010", canonical: "cost_code", confidence: 94 },
      { source: "NAME1", preview: "PT. Alpha Teknik", canonical: "vendor_name", confidence: 95 },
      { source: "EBELN", preview: "4500023017", canonical: "po_number", confidence: 100 },
      { source: "SGTXT", preview: "Piping Fabrication", canonical: "description", confidence: 88 },
      { source: "WRBTR", preview: "125000000.00", canonical: "amount", confidence: 100 },
    ],
  },
  p6: {
    name: "Oracle Primavera P6",
    description: "Primavera P6 activity spreadsheet export with float and progress fields.",
    datasetName: "P6 Schedule Activities",
    sheetName: "Auto-detect",
    mappings: [
      { source: "task_code", preview: "ACT-1020", canonical: "activity_id", confidence: 100 },
      { source: "task_name", preview: "Compressor Foundation Pour", canonical: "activity_name", confidence: 100 },
      { source: "wbs_id", preview: "03.02.01", canonical: "wbs_code", confidence: 98 },
      { source: "target_start_date", preview: "2024-05-10", canonical: "baseline_start", confidence: 95 },
      { source: "target_end_date", preview: "2024-06-15", canonical: "baseline_finish", confidence: 95 },
      { source: "total_float_hr_cnt", preview: "-96.0", canonical: "total_float_days", confidence: 92 },
      { source: "act_pct_comp", preview: "65.0", canonical: "physical_percent_complete", confidence: 95 },
    ],
  },
  msproject: {
    name: "Microsoft Project",
    description: "MS Project task and milestone spreadsheet export.",
    datasetName: "MS Project Task Tracking",
    sheetName: "Auto-detect",
    mappings: [
      { source: "Unique ID", preview: "104", canonical: "activity_id", confidence: 95 },
      { source: "Name", preview: "Compressor Installation", canonical: "activity_name", confidence: 100 },
      { source: "WBS", preview: "03.02.01", canonical: "wbs_code", confidence: 100 },
      { source: "Baseline Start", preview: "10/05/2024", canonical: "baseline_start", confidence: 92 },
      { source: "Baseline Finish", preview: "15/06/2024", canonical: "baseline_finish", confidence: 92 },
      { source: "% Complete", preview: "61.8%", canonical: "physical_percent_complete", confidence: 94 },
    ],
  },
}

const ALLOWED_EXTENSIONS = ["xlsx", "xls", "csv", "mpp", "mpx"]

export const DataImportWizard: React.FC = () => {
  const navigate = useNavigate()
  const { currentProject, uploadWorkbook, isUploading } = useProject()
  const [currentStep, setCurrentStep] = useState(1)
  const [selectedPreset, setSelectedPreset] = useState<ConnectorPreset>("standard")
  const [fileObject, setFileObject] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [ingestionSummary, setIngestionSummary] = useState<{ runId: string; ruleCount: number; findingCount: number; durationMs?: number } | null>(null)

  const activePresetConfig = PRESETS[selectedPreset]
  const fileSizeLabel = useMemo(() => fileObject ? `${(fileObject.size / 1024 / 1024).toFixed(2)} MB` : "No file selected", [fileObject])

  const validateFile = (file: File) => {
    const extension = file.name.split(".").pop()?.toLowerCase() || ""
    if (!ALLOWED_EXTENSIONS.includes(extension)) return "Unsupported file type. Upload .xlsx, .xls, .csv, or MS Project (.mpp)."
    if (file.size <= 0) return "The selected file is empty."
    return validatePublicBetaUpload(file)
  }

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const validationError = validateFile(file)
    if (validationError) {
      setFileObject(null)
      setUploadError(validationError)
      return
    }
    setUploadError(null)
    setIngestionSummary(null)
    setFileObject(file)
  }

  const goToStep = (step: number) => {
    if (step === 1) return setCurrentStep(1)
    if (!fileObject) {
      setUploadError("Select a project-control file before continuing.")
      setCurrentStep(1)
      return
    }
    if (step <= currentStep + 1) setCurrentStep(step)
  }

  const handleExecuteImport = async () => {
    setUploadError(null)
    setIngestionSummary(null)
    if (!fileObject) {
      setUploadError("Import blocked: no source file is selected.")
      setCurrentStep(1)
      return
    }
    if (!currentProject?.id) {
      setUploadError("Import blocked: select or create a project first.")
      return
    }

    try {
      const runRes = await uploadWorkbook(fileObject)
      if (!runRes?.id) throw new Error("The server did not return a valid analysis run. Import was not marked successful.")
      setIngestionSummary({
        runId: runRes.id,
        ruleCount: Number(runRes.rule_count ?? 0),
        findingCount: Number(runRes.finding_count ?? 0),
        durationMs: runRes.duration_ms,
      })
      setCurrentStep(4)
    } catch (err: any) {
      setUploadError(err?.response?.data?.error?.message || err?.message || "Workbook ingestion failed. No successful import was recorded.")
    }
  }

  const stepItems = [
    { step: 1, label: "Upload File" },
    { step: 2, label: "Map Columns" },
    { step: 3, label: "Preflight" },
    { step: 4, label: "Result" },
  ]

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-12">
      <div>
        <div className="mb-1 flex items-center gap-2 text-xs text-slate-500"><span>Data</span><span>&gt;</span><span className="font-semibold text-slate-900">Upload & Mapping</span></div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Project Control Data Ingestion</h1>
        <p className="mt-1 text-xs text-slate-500">A source file is mandatory. ControlCheck only reports success after the backend creates a real analysis run.</p>
      </div>

      {uploadError && <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{uploadError}</div>}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          {stepItems.map((item, index) => {
            const complete = currentStep > item.step
            const active = currentStep === item.step
            const reachable = item.step === 1 || Boolean(fileObject) && item.step <= currentStep + 1
            return <React.Fragment key={item.step}>
              <button type="button" onClick={() => reachable && goToStep(item.step)} disabled={!reachable} className="flex items-center gap-2 disabled:cursor-not-allowed">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${active ? "bg-blue-600 text-white" : complete ? "bg-emerald-500 text-white" : "bg-slate-100 text-slate-400"}`}>{complete ? <CheckCircle2 className="h-4 w-4" /> : item.step}</div>
                <span className={`text-xs font-semibold ${active ? "text-slate-900" : complete ? "text-emerald-700" : "text-slate-400"}`}>{item.label}</span>
              </button>
              {index < stepItems.length - 1 && <div className={`mx-4 h-0.5 flex-1 ${currentStep > item.step ? "bg-emerald-500" : "bg-slate-200"}`} />}
            </React.Fragment>
          })}
        </div>
      </div>

      {currentStep === 1 && <section className="mx-auto max-w-2xl space-y-5 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="text-center"><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600"><UploadCloud className="h-7 w-7" /></div><h2 className="mt-4 text-base font-bold">Upload Project Control Workbook</h2><p className="mt-1 text-xs text-slate-500">Accepted: .xlsx, .xls, .csv, .mpp · Files up to 4 MB run instantly; larger files and .mpp are processed by the worker</p></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><label className="block text-[11px] font-bold uppercase text-slate-600">Source preset</label><select value={selectedPreset} onChange={(e) => setSelectedPreset(e.target.value as ConnectorPreset)} className="mt-2 w-full rounded-lg border border-slate-200 bg-white p-2 text-xs font-semibold"><option value="standard">Standard EPC Canonical Workbook</option><option value="sap">SAP S/4HANA & ECC</option><option value="p6">Oracle Primavera P6</option><option value="msproject">Microsoft Project</option></select><p className="mt-2 text-[11px] text-slate-500">{activePresetConfig.description}</p></div>
        <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/60 p-8 text-center hover:border-blue-400"><input id="file-upload" type="file" accept=".xlsx,.xls,.csv,.mpp,.mpx" onChange={handleFileSelected} className="hidden" /><label htmlFor="file-upload" className="cursor-pointer text-xs font-semibold text-blue-600">Choose source file</label><div className="mt-2 text-[10px] text-slate-400">No demo file or simulated ingestion is used.</div></div>
        {fileObject && <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 p-4"><div className="min-w-0"><div className="truncate text-xs font-bold text-emerald-900">{fileObject.name}</div><div className="mt-1 text-[10px] text-emerald-700">{fileSizeLabel}</div></div><FileCheck2 className="h-5 w-5 text-emerald-600" /></div>}
        <div className="flex justify-end"><button onClick={() => goToStep(2)} disabled={!fileObject} className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300">Next: Map Columns <ArrowRight className="h-3.5 w-3.5" /></button></div>
      </section>}

      {currentStep === 2 && <section className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-4"><div><div className="text-[10px] font-bold uppercase text-slate-400">Selected file</div><div className="mt-1 break-all text-xs font-semibold text-slate-800">{fileObject?.name}</div><div className="mt-1 text-[10px] text-slate-400">{fileSizeLabel}</div></div><div className="border-t border-slate-100 pt-3"><div className="text-[10px] font-bold uppercase text-slate-400">Preset</div><div className="mt-1 text-sm font-bold">{activePresetConfig.name}</div></div><div className="border-t border-slate-100 pt-3"><div className="text-[10px] font-bold uppercase text-slate-400">Sheet handling</div><div className="mt-1 text-xs font-semibold">{activePresetConfig.sheetName}</div></div><div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] leading-5 text-amber-800">Mapping rows below are preset guidance. Actual workbook parsing and validation occur on the server during ingestion.</div></div>
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-8"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-bold">Canonical Mapping Preview</h2><p className="mt-1 text-xs text-slate-500">Review the expected mapping for this source type.</p></div><span className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-[10px] font-bold text-purple-700"><Sparkles className="h-3 w-3" /> Preset</span></div><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase text-slate-500"><th className="px-3 py-2.5">Source</th><th className="px-3 py-2.5">Example</th><th className="px-3 py-2.5">Canonical</th><th className="px-3 py-2.5 text-right">Confidence</th></tr></thead><tbody className="divide-y divide-slate-100">{activePresetConfig.mappings.map((mapping) => <tr key={`${mapping.source}-${mapping.canonical}`}><td className="px-3 py-2.5 font-semibold">{mapping.source}</td><td className="px-3 py-2.5 font-mono text-slate-500">{mapping.preview}</td><td className="px-3 py-2.5 font-mono text-blue-700">{mapping.canonical}</td><td className="px-3 py-2.5 text-right font-bold text-emerald-700">{mapping.confidence}%</td></tr>)}</tbody></table></div><div className="flex justify-between border-t border-slate-100 pt-4"><button onClick={() => goToStep(1)} className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold"><ArrowLeft className="h-3.5 w-3.5" /> Back</button><button onClick={() => goToStep(3)} className="flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white">Next: Preflight <ArrowRight className="h-3.5 w-3.5" /></button></div></div>
      </section>}

      {currentStep === 3 && <section className="mx-auto max-w-3xl space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600"><ShieldCheck className="h-5 w-5" /></div><div><h2 className="text-base font-bold">Ready for Server Validation</h2><p className="mt-1 text-xs text-slate-500">No validation result is claimed before the backend processes the selected file.</p></div></div><div className="space-y-2 border-t border-slate-100 pt-4 text-xs"><PreflightRow label="Source file selected" detail={fileObject?.name || "Missing"} ready={Boolean(fileObject)} /><PreflightRow label="File type and size preflight" detail={fileSizeLabel} ready={Boolean(fileObject)} /><PreflightRow label="Mapping preset configured" detail={activePresetConfig.name} ready /><PreflightRow label="Deterministic server validation" detail="Runs during ingestion" ready={false} pending /></div><div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-900">Clicking <strong>Run Ingestion & Audit</strong> sends the real file to ControlCheck. Success is shown only if the API returns a valid analysis-run ID.</div><div className="flex justify-between border-t border-slate-100 pt-4"><button onClick={() => goToStep(2)} className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold"><ArrowLeft className="h-3.5 w-3.5" /> Back</button><button onClick={handleExecuteImport} disabled={isUploading || !fileObject} className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white disabled:bg-slate-300">{isUploading ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing real file...</> : <>Run Ingestion & Audit <ArrowRight className="h-3.5 w-3.5" /></>}</button></div></section>}

      {currentStep === 4 && ingestionSummary && <section className="mx-auto max-w-2xl space-y-4 rounded-xl border border-emerald-200 bg-white p-8 text-center shadow-sm"><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 className="h-8 w-8" /></div><h2 className="text-lg font-bold">Ingestion Accepted</h2><p className="text-xs leading-5 text-slate-600">The backend created analysis run <strong className="font-mono">{ingestionSummary.runId}</strong>. Reported rules: <strong>{ingestionSummary.ruleCount}</strong>. Reported findings: <strong>{ingestionSummary.findingCount}</strong>.</p><div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-left text-[11px] leading-5 text-slate-600">This screen reflects the API response only. ControlCheck does not substitute demo counts or simulated database writes.</div><div className="flex justify-center gap-3 pt-2"><button onClick={() => navigate("/analysis-progress")} className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white">View Analysis Progress</button><button onClick={() => navigate("/findings")} className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold">Open Findings</button></div></section>}
    </div>
  )
}

const PreflightRow = ({ label, detail, ready, pending = false }: { label: string; detail: string; ready: boolean; pending?: boolean }) => <div className={`flex items-center justify-between gap-4 rounded-lg border p-3 ${ready ? "border-emerald-200 bg-emerald-50/50" : pending ? "border-blue-200 bg-blue-50/50" : "border-red-200 bg-red-50/50"}`}><div><div className="font-semibold text-slate-800">{label}</div><div className="mt-0.5 text-[10px] text-slate-500">{detail}</div></div>{ready ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : pending ? <Loader2 className="h-4 w-4 text-blue-500" /> : <AlertTriangle className="h-4 w-4 text-red-500" />}</div>

export default DataImportWizard
