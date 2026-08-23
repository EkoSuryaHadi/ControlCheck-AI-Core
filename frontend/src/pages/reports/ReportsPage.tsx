import React, { useMemo, useState } from "react"
import { useProject } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { FileSpreadsheet, Plus, Download, Eye, Printer, X, CheckCircle2, TriangleAlert } from "lucide-react"

interface ReportSnapshot {
  id: string
  name: string
  type: string
  generatedOn: string
  generatedBy: string
  projectName: string
  projectCode: string
  runId: string | null
  healthScore: number | null
  healthStatus: string
  dataQualityScore: number | null
  criticalOpen: number
  warningOpen: number
  resolvedCount: number
  totalFindings: number
  topFindings: Array<{ id: string; title: string; severity: string; status: string; impact: string }>
}

const storageKey = (projectId?: string) => `controlcheck_reports_${projectId || "none"}`

const loadStoredReports = (projectId?: string): ReportSnapshot[] => {
  try {
    const raw = localStorage.getItem(storageKey(projectId))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const escapeHtml = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#039;",
}[char] || char))

export const ReportsPage: React.FC = () => {
  const { currentProject, currentRun, healthData, liveFindings, refreshHealthAndFindings } = useProject()
  const { user } = useAuth()
  const [reports, setReports] = useState<ReportSnapshot[]>(() => loadStoredReports(currentProject?.id))
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [newReportName, setNewReportName] = useState("Monthly Project Control Report")
  const [newReportType, setNewReportType] = useState("Monthly")
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [reportTypeFilter, setReportTypeFilter] = useState("all")
  const [reportError, setReportError] = useState<string | null>(null)

  const filteredReports = useMemo(
    () => reports.filter((report) => reportTypeFilter === "all" || report.type.toLowerCase() === reportTypeFilter),
    [reports, reportTypeFilter],
  )

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedReportId) || reports[0] || null,
    [reports, selectedReportId],
  )

  const buildSnapshot = (): ReportSnapshot => {
    if (!currentProject?.id) throw new Error("Select a project before generating a report.")
    if (!currentRun?.id) throw new Error("A real analysis run is required before generating a report.")

    const findings = liveFindings || []
    const isResolved = (status?: string) => ["resolved", "closed"].includes(String(status || "").toLowerCase())
    const active = findings.filter((finding: any) => !isResolved(finding.status))
    const severityCount = (severity: string) => active.filter((finding: any) => String(finding.severity || "").toLowerCase() === severity).length

    return {
      id: `REP-${Date.now()}`,
      name: newReportName.trim() || "Project Control Report",
      type: newReportType,
      generatedOn: new Date().toISOString(),
      generatedBy: user?.name || user?.email || "Authenticated user",
      projectName: currentProject.name,
      projectCode: currentProject.code,
      runId: currentRun.id,
      healthScore: typeof healthData?.overall_score === "number" ? healthData.overall_score : null,
      healthStatus: healthData?.status_label || healthData?.score_band || "Not available",
      dataQualityScore: typeof healthData?.data_quality_score === "number" ? healthData.data_quality_score : null,
      criticalOpen: severityCount("critical"),
      warningOpen: severityCount("warning"),
      resolvedCount: findings.filter((finding: any) => isResolved(finding.status)).length,
      totalFindings: findings.length,
      topFindings: active.slice(0, 8).map((finding: any) => ({
        id: String(finding.id || finding.rule_id || "—"),
        title: String(finding.title || "Untitled finding"),
        severity: String(finding.severity || "observation"),
        status: String(finding.status || "open"),
        impact: String(finding.impact || finding.business_impact || finding.potential_impact || "Review required"),
      })),
    }
  }

  const generateReport = async (event: React.FormEvent) => {
    event.preventDefault()
    setReportError(null)
    try {
      await refreshHealthAndFindings()
      const snapshot = buildSnapshot()
      const next = [snapshot, ...reports]
      setReports(next)
      localStorage.setItem(storageKey(currentProject?.id), JSON.stringify(next))
      setSelectedReportId(snapshot.id)
      setShowGenerateModal(false)
    } catch (error: any) {
      setReportError(error?.message || "Report could not be generated.")
    }
  }

  const openPrintableReport = (report: ReportSnapshot, autoPrint = false) => {
    const popup = window.open("", "_blank", "noopener,noreferrer")
    if (!popup) {
      setReportError("Please allow pop-ups to preview or export the report.")
      return
    }

    const findingsRows = report.topFindings.length
      ? report.topFindings.map((finding) => `<tr><td>${escapeHtml(finding.id)}</td><td>${escapeHtml(finding.title)}</td><td>${escapeHtml(finding.severity)}</td><td>${escapeHtml(finding.status)}</td><td>${escapeHtml(finding.impact)}</td></tr>`).join("")
      : `<tr><td colspan="5">No active findings in this report snapshot.</td></tr>`

    popup.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(report.name)}</title><style>
      body{font-family:Arial,sans-serif;color:#0f172a;margin:40px;line-height:1.45}h1{font-size:24px;margin:0 0 6px}.muted{color:#64748b;font-size:12px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.card{border:1px solid #cbd5e1;border-radius:10px;padding:14px}.label{font-size:10px;text-transform:uppercase;color:#64748b;font-weight:700}.value{font-size:22px;font-weight:800;margin-top:4px}table{width:100%;border-collapse:collapse;margin-top:16px;font-size:12px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left}th{background:#f8fafc}.footer{margin-top:28px;font-size:10px;color:#64748b}@media print{body{margin:18mm}.no-print{display:none}}
    </style></head><body>
      <div class="no-print" style="margin-bottom:18px"><button onclick="window.print()">Print / Save as PDF</button></div>
      <div class="muted">CONTROLCHECK AI · AI-assisted, rule-driven, evidence-backed</div>
      <h1>${escapeHtml(report.name)}</h1>
      <div class="muted">${escapeHtml(report.projectName)} · ${escapeHtml(report.projectCode)} · Run ${escapeHtml(report.runId || "—")}</div>
      <div class="muted">Generated ${escapeHtml(new Date(report.generatedOn).toLocaleString())} by ${escapeHtml(report.generatedBy)}</div>
      <div class="grid">
        <div class="card"><div class="label">Project Health</div><div class="value">${escapeHtml(report.healthScore ?? "—")}</div><div class="muted">${escapeHtml(report.healthStatus)}</div></div>
        <div class="card"><div class="label">Open Critical</div><div class="value">${report.criticalOpen}</div></div>
        <div class="card"><div class="label">Open Warning</div><div class="value">${report.warningOpen}</div></div>
        <div class="card"><div class="label">Resolved</div><div class="value">${report.resolvedCount}</div><div class="muted">of ${report.totalFindings} findings</div></div>
      </div>
      <h2>Finding Summary</h2>
      <table><thead><tr><th>ID</th><th>Finding</th><th>Severity</th><th>Status</th><th>Impact</th></tr></thead><tbody>${findingsRows}</tbody></table>
      <div class="footer">Snapshot report generated from the selected project analysis state. Deterministic rules and traceable evidence remain the review basis.</div>
      ${autoPrint ? `<script>window.onload=()=>setTimeout(()=>window.print(),200)</script>` : ""}
    </body></html>`)
    popup.document.close()
  }

  const canGenerate = Boolean(currentProject?.id && currentRun?.id)

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Reporting</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Project Control Reports</h1>
          <p className="mt-1 text-xs text-slate-500">Generate evidence-backed snapshots from the latest project analysis state.</p>
        </div>
        <button disabled={!canGenerate} onClick={() => setShowGenerateModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"><Plus className="h-4 w-4" /> Generate Report</button>
      </div>

      {!canGenerate && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><div className="flex items-center gap-2 font-bold"><TriangleAlert className="h-4 w-4" /> Analysis run required</div><p className="mt-1 text-xs">Run a real project analysis before generating a report. ControlCheck will not create a synthetic report.</p></div>}
      {reportError && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">{reportError}</div>}

      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-xs font-semibold text-slate-600">Type</label>
        <select value={reportTypeFilter} onChange={(e) => setReportTypeFilter(e.target.value)} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"><option value="all">All reports</option><option value="monthly">Monthly</option><option value="executive">Executive</option><option value="cost">Cost</option><option value="schedule">Schedule</option></select>
        <span className="ml-auto text-xs text-slate-400">{filteredReports.length} generated report{filteredReports.length === 1 ? "" : "s"}</span>
      </div>

      {filteredReports.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><FileSpreadsheet className="mx-auto h-8 w-8 text-slate-400" /><h2 className="mt-4 font-bold text-slate-900">No generated reports yet</h2><p className="mt-2 text-sm text-slate-500">Generate a report after a real analysis run is available.</p></div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><table className="w-full text-left text-xs"><thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase text-slate-500"><tr><th className="px-4 py-3">Report</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Generated</th><th className="px-4 py-3">Run</th><th className="px-4 py-3 text-right">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{filteredReports.map((report) => <tr key={report.id} className="hover:bg-slate-50"><td className="px-4 py-3"><div className="font-bold text-slate-900">{report.name}</div><div className="mt-1 text-[10px] text-slate-400">{report.projectName}</div></td><td className="px-4 py-3 text-slate-600">{report.type}</td><td className="px-4 py-3 text-slate-500">{new Date(report.generatedOn).toLocaleString()}</td><td className="px-4 py-3 font-mono text-[10px] text-slate-500">{report.runId || "—"}</td><td className="px-4 py-3"><div className="flex justify-end gap-2"><button onClick={() => { setSelectedReportId(report.id); openPrintableReport(report, false) }} title="Preview" className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:text-blue-600"><Eye className="h-4 w-4" /></button><button onClick={() => openPrintableReport(report, true)} title="Print / Save as PDF" className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:text-blue-600"><Download className="h-4 w-4" /></button></div></td></tr>)}</tbody></table></div>
      )}

      {selectedReport && <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex items-start justify-between gap-4"><div><div className="text-[10px] font-black uppercase tracking-wider text-blue-600">Latest snapshot</div><h2 className="mt-1 text-lg font-bold text-slate-900">{selectedReport.name}</h2><p className="mt-1 text-xs text-slate-500">{selectedReport.projectName} · {selectedReport.projectCode}</p></div><button onClick={() => openPrintableReport(selectedReport, true)} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"><Printer className="h-4 w-4" /> Print / PDF</button></div><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><Metric label="Health" value={selectedReport.healthScore ?? "—"} /><Metric label="DQ" value={selectedReport.dataQualityScore ?? "—"} /><Metric label="Open Critical" value={selectedReport.criticalOpen} warning /><Metric label="Open Warning" value={selectedReport.warningOpen} /><Metric label="Resolved" value={selectedReport.resolvedCount} success /></div></section>}

      {showGenerateModal && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"><div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-base font-bold">Generate Report Snapshot</h2><button onClick={() => setShowGenerateModal(false)} className="p-1 text-slate-400 hover:text-slate-700"><X className="h-4 w-4" /></button></div><form onSubmit={generateReport} className="mt-5 space-y-4"><label className="block"><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Report name</span><input required value={newReportName} onChange={(e) => setNewReportName(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs" /></label><label className="block"><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">Report type</span><select value={newReportType} onChange={(e) => setNewReportType(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"><option value="Monthly">Monthly Project Control</option><option value="Executive">Executive Summary</option><option value="Cost">Cost Performance</option><option value="Schedule">Schedule Performance</option></select></label><div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800"><div className="flex items-center gap-2 font-bold"><CheckCircle2 className="h-4 w-4" /> Source snapshot ready</div><p className="mt-1">Project, run, health and finding statuses will be captured from the current workspace state.</p></div><div className="flex justify-end gap-2 pt-2"><button type="button" onClick={() => setShowGenerateModal(false)} className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-bold">Cancel</button><button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700">Generate</button></div></form></div></div>}
    </div>
  )
}

const Metric = ({ label, value, warning = false, success = false }: { label: string; value: string | number; warning?: boolean; success?: boolean }) => <div className={`rounded-xl border p-4 ${warning ? "border-red-200 bg-red-50" : success ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}><div className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{label}</div><div className={`mt-2 text-2xl font-black ${warning ? "text-red-700" : success ? "text-emerald-700" : "text-slate-900"}`}>{value}</div></div>

export default ReportsPage
