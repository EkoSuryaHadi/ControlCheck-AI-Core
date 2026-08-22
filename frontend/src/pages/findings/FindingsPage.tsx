import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import {
  Search,
  Filter,
  Download,
  Plus,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ShieldAlert,
} from "lucide-react"

export const INITIAL_FINDINGS = [
  {
    id: "FND-2024-001",
    title: "Cost Overrun Risk - WBS 03.02",
    category: "Cost",
    severity: "critical",
    wbs: "03.02",
    wbs_name: "Compressor Package",
    impact: "Rp 187.4M (24.3%)",
    status: "open",
    detected_on: "28 Oct 2024",
    description:
      "Actual cost on WBS 03.02 exceeds the approved budget by 24.3%. This indicates potential cost overrun risk if the trend continues.",
    budget: "Rp 771,000,000",
    actual: "Rp 958,400,000",
    commitment: "Rp 210,000,000",
    eac: "Rp 1,168,400,000",
    variance: "187,400,000",
    variance_pct: "24.3%",
    ai_summary:
      "Main cost drivers are material purchase variance and additional work order on piping modification. Review PO 23017 and 23021 for detail.",
    recommendation:
      "Review material quantity variance and additional work order. Negotiate with vendor and optimize installation method.",
    potential_impact:
      "If not addressed, potential additional cost up to Rp 414.4M (EAC over budget).",
  },
  {
    id: "FND-2024-002",
    title: "PO Exposure exceeds Budget - WBS 11",
    category: "Cost",
    severity: "critical",
    wbs: "11",
    wbs_name: "Electrical Infrastructure",
    impact: "Rp 28.7M",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Total committed purchase orders exceed allocated WBS budget.",
  },
  {
    id: "FND-2024-003",
    title: "Activity Delay - Compressor Installation",
    category: "Schedule",
    severity: "critical",
    wbs: "03.02.01",
    wbs_name: "Mechanical Equipment",
    impact: "18 days",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Critical path activity is currently 18 days behind schedule.",
  },
  {
    id: "FND-2024-004",
    title: "Negative Total Float - 5 Activities",
    category: "Schedule",
    severity: "critical",
    wbs: "Various",
    wbs_name: "Schedule Network",
    impact: "-12 days",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Multiple driving schedule paths exhibit negative total float.",
  },
  {
    id: "FND-2024-005",
    title: "Cost Spike Detected - WBS 04.01",
    category: "Cost",
    severity: "warning",
    wbs: "04.01",
    wbs_name: "Civil & Structural",
    impact: "+132%",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Monthly actual cost increased by 132% compared to baseline spend.",
  },
  {
    id: "FND-2024-006",
    title: "Progress Lag - WBS 12",
    category: "Progress",
    severity: "warning",
    wbs: "12",
    wbs_name: "Instrumentation & Control",
    impact: "-15%",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Physical progress is lagging planned value by 15 percentage points.",
  },
  {
    id: "FND-2024-007",
    title: "Actual + Commitment exceeds Budget - WBS 03.01",
    category: "Cost",
    severity: "warning",
    wbs: "03.01",
    wbs_name: "Piping Fabrication",
    impact: "Rp 15.6M",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Incurred costs plus open commitments exceed the budget ceiling.",
  },
  {
    id: "FND-2024-008",
    title: "Vendor Concentration Risk - PT. Alpha",
    category: "Cost",
    severity: "warning",
    wbs: "Various",
    wbs_name: "Procurement Package",
    impact: "68%",
    status: "open",
    detected_on: "28 Oct 2024",
    description: "Single vendor represents over 68% of outstanding procurement commitments.",
  },
]

export const FindingsPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchTerm, setSearchTerm] = useState("")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [categoryFilter, setCategoryFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")

  const filteredFindings = INITIAL_FINDINGS.filter((f) => {
    const matchesSearch =
      f.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.wbs.toLowerCase().includes(searchTerm.toLowerCase())

    const matchesSeverity =
      severityFilter === "all" || f.severity.toLowerCase() === severityFilter.toLowerCase()

    const matchesCategory =
      categoryFilter === "all" || f.category.toLowerCase() === categoryFilter.toLowerCase()

    const matchesStatus =
      statusFilter === "all" || f.status.toLowerCase() === statusFilter.toLowerCase()

    return matchesSearch && matchesSeverity && matchesCategory && matchesStatus
  })

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-12">
      {/* Header with Title and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Findings</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Central project-control risk register and deterministic audit findings
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => alert("Action creation modal triggered")}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Action</span>
          </button>
          <button
            onClick={() => alert("Exporting findings to CSV...")}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar matching Mockup */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-3">
        {/* Severity */}
        <div className="flex flex-col min-w-30">
          <label className="text-[10px] uppercase font-bold text-slate-400 mb-1">Severity</label>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="observation">Observation</option>
          </select>
        </div>

        {/* Category */}
        <div className="flex flex-col min-w-30">
          <label className="text-[10px] uppercase font-bold text-slate-400 mb-1">Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="cost">Cost</option>
            <option value="schedule">Schedule</option>
            <option value="progress">Progress</option>
          </select>
        </div>

        {/* Status */}
        <div className="flex flex-col min-w-30">
          <label className="text-[10px] uppercase font-bold text-slate-400 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="in_review">In Review</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Search bar */}
        <div className="flex flex-col flex-1 min-w-50">
          <label className="text-[10px] uppercase font-bold text-slate-400 mb-1">Search</label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search findings by ID, title, WBS..."
              className="w-full text-xs pl-8 pr-3 py-1 bg-slate-50 border border-slate-200 rounded-md text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Dense Enterprise Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">ID</th>
                <th className="py-3 px-4">Title</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">WBS</th>
                <th className="py-3 px-4 text-right">Impact</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Detected On</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {filteredFindings.map((f) => (
                <tr
                  key={f.id}
                  onClick={() => navigate(`/findings/${f.id}`)}
                  className="hover:bg-blue-50/40 cursor-pointer transition-colors group"
                >
                  <td className="py-3 px-4 font-mono font-bold text-blue-600 group-hover:underline">
                    {f.id}
                  </td>
                  <td className="py-3 px-4 text-slate-900 font-semibold max-w-xs truncate">
                    {f.title}
                  </td>
                  <td className="py-3 px-4 text-slate-600">{f.category}</td>
                  <td className="py-3 px-4">
                    <SeverityBadge severity={f.severity} />
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-700">{f.wbs}</td>
                  <td className="py-3 px-4 text-right font-bold text-slate-900 tabular-nums">
                    {f.impact}
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={f.status} />
                  </td>
                  <td className="py-3 px-4 text-slate-500">{f.detected_on}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <div>
            Showing <strong className="text-slate-900">1-{filteredFindings.length}</strong> of{" "}
            <strong className="text-slate-900">{filteredFindings.length}</strong> findings
          </div>
          <div className="flex items-center gap-1">
            <button className="p-1 rounded hover:bg-slate-200 text-slate-600 disabled:opacity-40">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button className="w-6 h-6 rounded bg-blue-600 text-white font-bold text-xs flex items-center justify-center">
              1
            </button>
            <button className="w-6 h-6 rounded hover:bg-slate-200 text-slate-700 text-xs flex items-center justify-center">
              2
            </button>
            <button className="w-6 h-6 rounded hover:bg-slate-200 text-slate-700 text-xs flex items-center justify-center">
              3
            </button>
            <button className="p-1 rounded hover:bg-slate-200 text-slate-600">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
