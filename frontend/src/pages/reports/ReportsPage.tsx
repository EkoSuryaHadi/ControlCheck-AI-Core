import React, { useState } from "react"
import { useProject } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import {
  FileSpreadsheet,
  Plus,
  Download,
  Eye,
  MoreVertical,
  ShieldCheck,
  Calendar,
  Filter,
  Printer,
  X,
  CheckCircle2,
  Sparkles,
} from "lucide-react"
import { HealthGauge } from "@/components/ui/HealthGauge"

interface ReportItem {
  id: string
  name: string
  type: string
  period: string
  generated_on: string
  generated_by: string
}

export const ReportsPage: React.FC = () => {
  const { currentProject, healthData } = useProject()
  const { user } = useAuth()

  const [reportType, setReportType] = useState("all")
  const [period, setPeriod] = useState("Oct 2024")
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [newReportName, setNewReportName] = useState("Monthly Project Control Report")
  const [newReportType, setNewReportType] = useState("Monthly")

  const [reports, setReports] = useState<ReportItem[]>([
    {
      id: "REP-001",
      name: "Monthly Project Control Report",
      type: "Monthly",
      period: "Oct 2024",
      generated_on: "28 Oct 2024 14:30",
      generated_by: "Eko Prasetyo",
    },
    {
      id: "REP-002",
      name: "Executive Summary",
      type: "Executive",
      period: "Oct 2024",
      generated_on: "28 Oct 2024 14:29",
      generated_by: "Eko Prasetyo",
    },
    {
      id: "REP-003",
      name: "Cost Performance Report",
      type: "Cost",
      period: "Oct 2024",
      generated_on: "28 Oct 2024 14:28",
      generated_by: "Eko Prasetyo",
    },
    {
      id: "REP-004",
      name: "Schedule Performance Report",
      type: "Schedule",
      period: "Oct 2024",
      generated_on: "28 Oct 2024 14:27",
      generated_by: "Eko Prasetyo",
    },
    {
      id: "REP-005",
      name: "Progress Report",
      type: "Progress",
      period: "Oct 2024",
      generated_on: "28 Oct 2024 14:26",
      generated_by: "Eko Prasetyo",
    },
  ])

  const handleGenerateReport = (e: React.FormEvent) => {
    e.preventDefault()

    const item: ReportItem = {
      id: `REP-00${reports.length + 1}`,
      name: newReportName,
      type: newReportType,
      period: period,
      generated_on: new Date().toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }),
      generated_by: user?.name || "Eko Prasetyo",
    }

    setReports((prev) => [item, ...prev])
    setShowGenerateModal(false)
  }

  const handlePrintReport = (reportName: string) => {
    window.print()
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Executive Reports</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit deliverables, executive briefings, and monthly project control packages
          </p>
        </div>

        <button
          onClick={() => setShowGenerateModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Generate New Report</span>
        </button>
      </div>

      {/* Main Grid: Left Filter & Right Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Filter Card */}
        <div className="lg:col-span-3 bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4 h-fit">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            REPORT FILTERS
          </h2>

          <div>
            <label className="text-[10px] uppercase font-bold text-slate-500 block mb-1">
              Report Type
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              <option value="monthly">Monthly Project Control</option>
              <option value="executive">Executive Summary</option>
              <option value="cost">Cost Performance</option>
              <option value="schedule">Schedule Performance</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] uppercase font-bold text-slate-500 block mb-1">
              Period
            </label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="Oct 2024">Oct 2024</option>
              <option value="Sep 2024">Sep 2024</option>
              <option value="Aug 2024">Aug 2024</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] uppercase font-bold text-slate-500 block mb-1">
              Project
            </label>
            <input
              type="text"
              readOnly
              value={currentProject?.name || "Gas Compression Facility Expansion"}
              className="w-full text-xs bg-slate-100 border border-slate-200 rounded-lg p-2 text-slate-600 font-medium truncate"
            />
          </div>

          <button className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors">
            Apply Filter
          </button>
        </div>

        {/* Right Content Area: Table + Preview Card */}
        <div className="lg:col-span-9 space-y-6">
          {/* Reports Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 font-semibold uppercase">
                    <th className="py-3 px-4">Report Name</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Period</th>
                    <th className="py-3 px-4">Generated On</th>
                    <th className="py-3 px-4">Generated By</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {reports.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900 flex items-center gap-2">
                        <FileSpreadsheet className="w-4 h-4 text-blue-600" />
                        <span>{r.name}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-600">{r.type}</td>
                      <td className="py-3 px-4 text-slate-700 font-mono">{r.period}</td>
                      <td className="py-3 px-4 text-slate-500">{r.generated_on}</td>
                      <td className="py-3 px-4 text-slate-700">{r.generated_by}</td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2 text-slate-500">
                          <button
                            title="Print / Save as PDF"
                            onClick={() => handlePrintReport(r.name)}
                            className="p-1 hover:text-blue-600 rounded transition-colors"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            title="Preview"
                            onClick={() => handlePrintReport(r.name)}
                            className="p-1 hover:text-slate-900 rounded transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sample Preview Card */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                SAMPLE PREVIEW (PRINT READY)
              </h2>
              <button
                onClick={() => handlePrintReport("Monthly Report")}
                className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-semibold"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Print / Export PDF</span>
              </button>
            </div>

            <div className="p-6 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col md:flex-row items-center justify-between gap-6">
              {/* Document Title Header */}
              <div className="space-y-2 text-center md:text-left">
                <div className="flex items-center gap-2 justify-center md:justify-start text-blue-600 font-bold text-sm">
                  <ShieldCheck className="w-5 h-5" />
                  <span>CONTROLCHECK AI</span>
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  MONTHLY PROJECT CONTROL REPORT
                </h3>
                <div className="text-xs text-slate-500">
                  {currentProject?.name || "Gas Compression Facility Expansion"} • October 2024
                </div>
              </div>

              {/* Health Ring */}
              <div className="flex flex-col items-center">
                <span className="text-[10px] uppercase font-bold text-slate-400 mb-1">
                  PROJECT HEALTH
                </span>
                <div className="w-16 h-16 rounded-full border-4 border-amber-500 flex flex-col items-center justify-center bg-white shadow-sm">
                  <span className="text-lg font-bold text-slate-900 tabular-nums">
                    {healthData?.overall_score || 68}
                  </span>
                  <span className="text-[8px] font-bold text-slate-500 uppercase">
                    {healthData?.status_label || "MODERATE"}
                  </span>
                </div>
              </div>

              {/* Key Highlights */}
              <div className="space-y-1 text-xs text-slate-700 bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
                <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">
                  KEY HIGHLIGHTS
                </div>
                <div>• Cost variance: <strong className="text-red-600">-Rp 20.9B</strong> (CPI 0.92)</div>
                <div>• Schedule delay: <strong className="text-red-600">18 days</strong></div>
                <div>• Critical findings: <strong className="text-red-600">{healthData?.critical_findings_count || 17}</strong></div>
                <div>• Data quality score: <strong className="text-emerald-600">{healthData?.data_quality_score || 92}</strong></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal: Generate New Report */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-2xl p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900">Generate New Report Package</h2>
              <button
                onClick={() => setShowGenerateModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleGenerateReport} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Report Name *</label>
                <input
                  type="text"
                  required
                  value={newReportName}
                  onChange={(e) => setNewReportName(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Report Type *</label>
                <select
                  value={newReportType}
                  onChange={(e) => setNewReportType(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Monthly">Monthly Project Control Report</option>
                  <option value="Executive">Executive Summary (One-Pager)</option>
                  <option value="Cost">Cost Performance & Variance Analysis</option>
                  <option value="Schedule">Schedule Critical Path & Delay Briefing</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Audit Run Period</label>
                <select
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Oct 2024">Oct 2024 (Latest Run)</option>
                  <option value="Sep 2024">Sep 2024</option>
                  <option value="Aug 2024">Aug 2024</option>
                </select>
              </div>

              <div className="p-3 bg-purple-50 text-purple-900 border border-purple-200 rounded-lg text-[11px] flex items-start gap-2">
                <Sparkles className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                <span>
                  The report will automatically embed deterministic health metrics, S-curve charts, and evidence-grounded AI executive summaries.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-sm"
                >
                  Generate Package
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
