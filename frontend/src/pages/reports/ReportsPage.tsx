import React, { useEffect, useMemo, useState } from "react"
import { useProject } from "@/context/ProjectContext"
import { api, ReportPackage } from "@/lib/api"
import {
  CheckCircle2,
  Download,
  Eye,
  FileSpreadsheet,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-react"

const reportTypeLabel: Record<string, string> = {
  monthly: "Monthly Project Control",
  executive: "Executive Summary",
  cost: "Cost Performance",
  schedule: "Schedule Performance",
  progress: "Progress Performance",
}

const terminalSuccess = (status?: string) => ["succeeded", "completed"].includes(String(status || "").toLowerCase())

export const ReportsPage: React.FC = () => {
  const { currentProject, currentRun, refreshHealthAndFindings } = useProject()
  const [reports, setReports] = useState<ReportPackage[]>([])
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [reportName, setReportName] = useState("Monthly Project Control Report")
  const [reportType, setReportType] = useState("monthly")
  const [period, setPeriod] = useState(() => new Date().toLocaleDateString("en-US", { month: "short", year: "numeric" }))
  const [filterType, setFilterType] = useState("all")
  const [isLoading, setIsLoading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadReports = async () => {
    if (!currentProject?.id) {
      setReports([])
      setSelectedReportId(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.reports.listProject(currentProject.id)
      const items = Array.isArray(response?.items) ? response.items : []
      setReports(items)
      setSelectedReportId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id || null)
    } catch (err: any) {
      const status = err?.response?.status
      setReports([])
      setError(status === 500
        ? "Server report storage is not ready yet. Apply the v0.6.16 database migration, then refresh this page."
        : err?.response?.data?.error?.message || "Report history could not be loaded from the server.")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadReports()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id])

  const filteredReports = useMemo(
    () => reports.filter((report) => filterType === "all" || report.report_type === filterType),
    [reports, filterType],
  )

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedReportId) || reports[0] || null,
    [reports, selectedReportId],
  )

  const canGenerate = Boolean(currentProject?.id && currentRun?.id && terminalSuccess(currentRun.status))

  const handleGenerate = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!currentProject?.id || !currentRun?.id) return
    setError(null)
    setIsGenerating(true)
    try {
      await refreshHealthAndFindings()
      const created = await api.reports.create(currentProject.id, {
        analysis_run_id: currentRun.id,
        report_name: reportName.trim() || "Project Control Report",
        report_type: reportType,
        period: period.trim() || "Current",
      })
      setReports((current) => [created, ...current.filter((item) => item.id !== created.id)])
      setSelectedReportId(created.id)
      setShowGenerateModal(false)
    } catch (err: any) {
      const status = err?.response?.status
      setError(status === 500
        ? "Report could not be stored because the v0.6.16 database migration is not active yet."
        : err?.response?.data?.error?.message || err?.message || "Report could not be generated.")
    } finally {
      setIsGenerating(false)
    }
  }

  const handleOpenPdf = async (reportId: string) => {
    setError(null)
    try {
      await api.reports.openPdf(reportId)
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || "Persisted PDF could not be opened.")
    }
  }

  const summary = selectedReport?.snapshot?.summary || {}
  const health = selectedReport?.snapshot?.health || {}
  const findings = Array.isArray(selectedReport?.snapshot?.findings) ? selectedReport!.snapshot.findings! : []
  const evidenceCount = Number(summary.evidence_records || findings.reduce((total, finding: any) => total + (Array.isArray(finding.evidence) ? finding.evidence.length : 0), 0))

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Reporting</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Project Control Reports</h1>
          <p className="mt-1 text-xs text-slate-500">Server-persisted report packages with immutable analysis snapshots, evidence appendix, and reusable PDF files.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void loadReports()} disabled={isLoading || !currentProject?.id} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} /> Refresh
          </button>
          <button disabled={!canGenerate} onClick={() => setShowGenerateModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300">
            <Plus className="h-4 w-4" /> Generate Report
          </button>
        </div>
      </div>

      {!canGenerate && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <div className="flex items-center gap-2 font-bold"><TriangleAlert className="h-4 w-4" /> Completed analysis run required</div>
          <p className="mt-1 text-xs">ControlCheck will only generate a persisted report from a server-confirmed completed analysis run.</p>
        </div>
      )}

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">{error}</div>}

      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="text-xs font-semibold text-slate-600">Type</label>
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
          <option value="all">All reports</option>
          <option value="monthly">Monthly</option>
          <option value="executive">Executive</option>
          <option value="cost">Cost</option>
          <option value="schedule">Schedule</option>
          <option value="progress">Progress</option>
        </select>
        <span className="ml-auto text-xs text-slate-400">{filteredReports.length} server report{filteredReports.length === 1 ? "" : "s"}</span>
      </div>

      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500"><Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin" />Loading server report history…</div>
      ) : filteredReports.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <FileSpreadsheet className="mx-auto h-8 w-8 text-slate-400" />
          <h2 className="mt-4 font-bold text-slate-900">No persisted reports yet</h2>
          <p className="mt-2 text-sm text-slate-500">Generate a report to freeze the current analysis state and supporting evidence.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase text-slate-500"><tr><th className="px-4 py-3">Report</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Period</th><th className="px-4 py-3">Generated</th><th className="px-4 py-3">PDF</th><th className="px-4 py-3 text-right">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {filteredReports.map((report) => (
                <tr key={report.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3"><div className="font-bold text-slate-900">{report.report_name}</div><div className="mt-1 font-mono text-[10px] text-slate-400">Run {report.analysis_run_id}</div></td>
                  <td className="px-4 py-3 text-slate-600">{reportTypeLabel[report.report_type] || report.report_type}</td>
                  <td className="px-4 py-3 text-slate-600">{report.period}</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(report.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-500">{Math.max(1, Math.round((report.pdf_size_bytes || 0) / 1024))} KB</td>
                  <td className="px-4 py-3"><div className="flex justify-end gap-2"><button onClick={() => setSelectedReportId(report.id)} title="Preview snapshot" className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:text-blue-600"><Eye className="h-4 w-4" /></button><button onClick={() => void handleOpenPdf(report.id)} title="Open persisted PDF" className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:text-blue-600"><Download className="h-4 w-4" /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedReport && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-blue-600"><ShieldCheck className="h-4 w-4" /> Immutable Server Snapshot</div>
              <h2 className="mt-2 text-xl font-bold text-slate-900">{selectedReport.report_name}</h2>
              <p className="mt-1 text-xs text-slate-500">{String(selectedReport.snapshot.project?.name || currentProject?.name || "Project")} · {selectedReport.period}</p>
            </div>
            <button onClick={() => void handleOpenPdf(selectedReport.id)} className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-xs font-bold text-white hover:bg-slate-800"><Download className="h-4 w-4" /> Open Persisted PDF</button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <Metric label="Health" value={health.overall_score ?? "—"} />
            <Metric label="Data Quality" value={health.data_quality_score ?? "—"} />
            <Metric label="Open Critical" value={summary.open_critical ?? 0} warning />
            <Metric label="Open Warning" value={summary.open_warning ?? 0} />
            <Metric label="Resolved" value={summary.resolved ?? 0} success />
            <Metric label="Evidence" value={evidenceCount} success />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
            <div>
              <h3 className="text-xs font-black uppercase tracking-wider text-slate-500">Findings Snapshot</h3>
              <div className="mt-3 space-y-2">
                {findings.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-5 text-xs text-slate-500">No findings were captured in this report snapshot.</div> : findings.slice(0, 10).map((finding: any) => (
                  <div key={finding.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-[10px] font-black uppercase text-red-600">{finding.severity}</span><span className="text-[10px] font-bold uppercase text-slate-400">{finding.status}</span></div>
                    <div className="mt-2 text-sm font-bold text-slate-900">{finding.title}</div>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{finding.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-black uppercase tracking-wider text-slate-500">Evidence Appendix</h3>
              <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-emerald-800"><CheckCircle2 className="h-5 w-5" /> {evidenceCount} evidence record{evidenceCount === 1 ? "" : "s"} frozen</div>
                <p className="mt-2 text-xs leading-5 text-emerald-800/80">Evidence source sheets, row lineage, record IDs, fields, and aggregations are stored inside the immutable report snapshot and reproduced in the persisted PDF appendix.</p>
              </div>
              <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-500">
                <strong className="text-slate-800">Traceability:</strong> report ID {selectedReport.id}<br />
                <strong className="text-slate-800">Analysis run:</strong> {selectedReport.analysis_run_id}<br />
                <strong className="text-slate-800">Generated by:</strong> {String(selectedReport.snapshot.generated_by_name || selectedReport.generated_by || "Authenticated user")}
              </div>
            </div>
          </div>
        </section>
      )}

      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between"><h2 className="text-base font-bold text-slate-900">Generate Persisted Report</h2><button onClick={() => setShowGenerateModal(false)} className="p-1 text-slate-400 hover:text-slate-700"><X className="h-4 w-4" /></button></div>
            <p className="mt-2 text-xs leading-5 text-slate-500">This creates an immutable database snapshot and persisted PDF from analysis run <span className="font-mono">{currentRun?.id || "—"}</span>.</p>
            <form onSubmit={handleGenerate} className="mt-5 space-y-4">
              <label className="block"><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Report Name</span><input required value={reportName} onChange={(e) => setReportName(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs" /></label>
              <label className="block"><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Report Type</span><select value={reportType} onChange={(e) => setReportType(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs"><option value="monthly">Monthly Project Control</option><option value="executive">Executive Summary</option><option value="cost">Cost Performance</option><option value="schedule">Schedule Performance</option><option value="progress">Progress Performance</option></select></label>
              <label className="block"><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Period</span><input required value={period} onChange={(e) => setPeriod(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs" /></label>
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-[11px] leading-5 text-blue-800">The package freezes current finding statuses and all linked evidence for this analysis run. Later finding changes will not rewrite this historical report.</div>
              <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><button type="button" onClick={() => setShowGenerateModal(false)} className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600">Cancel</button><button disabled={isGenerating} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:bg-slate-300">{isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />} {isGenerating ? "Generating…" : "Generate & Persist"}</button></div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

const Metric = ({ label, value, warning = false, success = false }: { label: string; value: string | number; warning?: boolean; success?: boolean }) => (
  <div className={`rounded-xl border p-4 ${warning ? "border-red-200 bg-red-50" : success ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
    <div className="text-[9px] font-black uppercase tracking-wide text-slate-400">{label}</div>
    <div className={`mt-2 text-2xl font-black ${warning ? "text-red-700" : success ? "text-emerald-700" : "text-slate-900"}`}>{value}</div>
  </div>
)

export default ReportsPage