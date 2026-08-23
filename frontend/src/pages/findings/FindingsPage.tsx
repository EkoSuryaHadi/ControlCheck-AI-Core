import React, { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import { useProject } from "@/context/ProjectContext"
import { Search, ChevronLeft, ChevronRight, ArrowRight, ShieldCheck, FileCheck2, CheckCircle2 } from "lucide-react"

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
    description: "Actual cost on WBS 03.02 exceeds the approved budget by 24.3%. This indicates potential cost overrun risk if the trend continues.",
    budget: "Rp 771,000,000",
    actual: "Rp 958,400,000",
    commitment: "Rp 210,000,000",
    eac: "Rp 1,168,400,000",
    variance: "187,400,000",
    variance_pct: "24.3%",
    ai_summary: "Main cost drivers are material purchase variance and additional work order on piping modification. Review PO 23017 and 23021 for detail.",
    recommendation: "Review material quantity variance and additional work order. Negotiate with vendor and optimize installation method.",
    potential_impact: "If not addressed, potential additional cost up to Rp 414.4M (EAC over budget).",
  },
  { id: "FND-2024-002", title: "PO Exposure exceeds Budget - WBS 11", category: "Cost", severity: "critical", wbs: "11", wbs_name: "Electrical Infrastructure", impact: "Rp 28.7M", status: "open", detected_on: "28 Oct 2024", description: "Total committed purchase orders exceed allocated WBS budget." },
  { id: "FND-2024-003", title: "Activity Delay - Compressor Installation", category: "Schedule", severity: "critical", wbs: "03.02.01", wbs_name: "Mechanical Equipment", impact: "18 days", status: "open", detected_on: "28 Oct 2024", description: "Critical path activity is currently 18 days behind schedule." },
  { id: "FND-2024-004", title: "Negative Total Float - 5 Activities", category: "Schedule", severity: "critical", wbs: "Various", wbs_name: "Schedule Network", impact: "-12 days", status: "open", detected_on: "28 Oct 2024", description: "Multiple driving schedule paths exhibit negative total float." },
  { id: "FND-2024-005", title: "Cost Spike Detected - WBS 04.01", category: "Cost", severity: "warning", wbs: "04.01", wbs_name: "Civil & Structural", impact: "+132%", status: "open", detected_on: "28 Oct 2024", description: "Monthly actual cost increased by 132% compared to baseline spend." },
  { id: "FND-2024-006", title: "Progress Lag - WBS 12", category: "Progress", severity: "warning", wbs: "12", wbs_name: "Instrumentation & Control", impact: "-15%", status: "open", detected_on: "28 Oct 2024", description: "Physical progress is lagging planned value by 15 percentage points." },
  { id: "FND-2024-007", title: "Actual + Commitment exceeds Budget - WBS 03.01", category: "Cost", severity: "warning", wbs: "03.01", wbs_name: "Piping Fabrication", impact: "Rp 15.6M", status: "open", detected_on: "28 Oct 2024", description: "Incurred costs plus open commitments exceed the budget ceiling." },
  { id: "FND-2024-008", title: "Vendor Concentration Risk - PT. Alpha", category: "Cost", severity: "warning", wbs: "Various", wbs_name: "Procurement Package", impact: "68%", status: "open", detected_on: "28 Oct 2024", description: "Single vendor represents over 68% of outstanding procurement commitments." },
]

export const FindingsPage: React.FC = () => {
  const navigate = useNavigate()
  const { liveFindings, refreshHealthAndFindings } = useProject()
  const [searchTerm, setSearchTerm] = useState("")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [categoryFilter, setCategoryFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")

  useEffect(() => {
    void refreshHealthAndFindings()
  }, [refreshHealthAndFindings])

  const sourceFindings = liveFindings.length > 0 ? liveFindings : INITIAL_FINDINGS

  const filteredFindings = useMemo(() => sourceFindings.filter((f: any) => {
    const title = String(f.title || "")
    const id = String(f.id || f.rule_id || "")
    const wbs = String(f.wbs || f.wbs_code || "")
    const category = String(f.category || "")
    const severity = String(f.severity || "")
    const status = String(f.status || "open")

    const matchesSearch = title.toLowerCase().includes(searchTerm.toLowerCase()) || id.toLowerCase().includes(searchTerm.toLowerCase()) || wbs.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesSeverity = severityFilter === "all" || severity.toLowerCase() === severityFilter.toLowerCase()
    const matchesCategory = categoryFilter === "all" || category.toLowerCase() === categoryFilter.toLowerCase()
    const matchesStatus = statusFilter === "all" || status.toLowerCase() === statusFilter.toLowerCase()
    return matchesSearch && matchesSeverity && matchesCategory && matchesStatus
  }), [sourceFindings, searchTerm, severityFilter, categoryFilter, statusFilter])

  const activeFindings = sourceFindings.filter((f: any) => !["resolved", "closed"].includes(String(f.status || "open").toLowerCase()))
  const criticalCount = activeFindings.filter((f: any) => String(f.severity).toLowerCase() === "critical").length
  const warningCount = activeFindings.filter((f: any) => String(f.severity).toLowerCase() === "warning").length
  const resolvedCount = sourceFindings.filter((f: any) => ["resolved", "closed"].includes(String(f.status || "").toLowerCase())).length

  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600">Project Assurance Findings</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">What needs review now</h1>
          <p className="mt-1 text-xs text-slate-500">Each finding is designed to show what happened, where, why, impact, evidence and recommended action.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 font-bold text-red-700">{criticalCount} Critical Active</div>
          <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 font-bold text-amber-700">{warningCount} Warning Active</div>
          <div className="inline-flex items-center gap-1 rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 font-bold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> {resolvedCount} Resolved</div>
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[140px_140px_140px_1fr]">
        <FilterSelect label="Severity" value={severityFilter} onChange={setSeverityFilter} options={["all","critical","warning","observation"]} />
        <FilterSelect label="Category" value={categoryFilter} onChange={setCategoryFilter} options={["all","cost","schedule","progress","data_quality"]} />
        <FilterSelect label="Status" value={statusFilter} onChange={setStatusFilter} options={["all","open","in_review","resolved"]} />
        <label className="block">
          <span className="mb-1 block text-[10px] font-bold uppercase text-slate-400">Search</span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search ID, title, WBS..." className="w-full rounded-md border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-xs outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
        </label>
      </div>

      <div className="space-y-3">
        {filteredFindings.map((f: any) => {
          const id = f.id || f.rule_id
          const evidenceCount = f.evidence_records?.length || 0
          const isResolved = ["resolved", "closed"].includes(String(f.status || "").toLowerCase())
          return (
            <article key={id} onClick={() => navigate(`/findings/${id}`)} className={`group cursor-pointer rounded-xl border bg-white p-5 shadow-sm transition-all hover:border-blue-300 hover:shadow-md ${isResolved ? "border-emerald-200 bg-emerald-50/20" : "border-slate-200"}`}>
              <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={f.severity || "observation"} />
                    <StatusBadge status={f.status || "open"} />
                    <span className="font-mono text-[11px] text-slate-400">{id}</span>
                  </div>
                  <h2 className="mt-3 text-base font-bold text-slate-900 group-hover:text-blue-700">{f.title}</h2>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{f.description || f.ai_summary || "Open this finding to review the control logic, supporting evidence and recommended action."}</p>
                </div>

                <div className="grid shrink-0 grid-cols-2 gap-3 text-xs sm:grid-cols-4 lg:w-[470px]">
                  <Meta label="WHERE" value={`${f.wbs || f.wbs_code || "Project"}${f.wbs_name ? ` · ${f.wbs_name}` : ""}`} />
                  <Meta label="IMPACT" value={f.impact || f.business_impact || f.potential_impact || "Review required"} emphasize={!isResolved} />
                  <Meta label="EVIDENCE" value={evidenceCount > 0 ? `${evidenceCount} source record${evidenceCount > 1 ? "s" : ""}` : "Trace available"} />
                  <Meta label="ACTION" value={isResolved ? "Resolution complete" : f.recommendation ? "Recommendation ready" : "Review finding"} />
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                <div className="flex items-center gap-4 text-[11px] text-slate-500">
                  <span className="inline-flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5 text-blue-600" /> Rule / audit trace</span>
                  <span className="inline-flex items-center gap-1"><FileCheck2 className="h-3.5 w-3.5 text-emerald-600" /> Evidence-backed review</span>
                </div>
                <span className={`inline-flex items-center gap-1 text-xs font-bold ${isResolved ? "text-emerald-700" : "text-blue-600"}`}>{isResolved ? "View resolution" : "Open finding"} <ArrowRight className="h-3.5 w-3.5" /></span>
              </div>
            </article>
          )
        })}

        {filteredFindings.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">No findings match the selected filters.</div>
        )}
      </div>

      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
        <span>Showing <strong className="text-slate-900">{filteredFindings.length}</strong> findings</span>
        <div className="flex items-center gap-1">
          <button className="rounded p-1 hover:bg-slate-200"><ChevronLeft className="h-4 w-4" /></button>
          <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 font-bold text-white">1</span>
          <button className="rounded p-1 hover:bg-slate-200"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  )
}

const FilterSelect = ({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) => (
  <label className="block">
    <span className="mb-1 block text-[10px] font-bold uppercase text-slate-400">{label}</span>
    <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs capitalize outline-none focus:ring-1 focus:ring-blue-500">
      {options.map((option) => <option key={option} value={option}>{option.replace("_", " ")}</option>)}
    </select>
  </label>
)

const Meta = ({ label, value, emphasize = false }: { label: string; value: string; emphasize?: boolean }) => (
  <div className="rounded-lg bg-slate-50 p-3">
    <div className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{label}</div>
    <div className={`mt-1 line-clamp-2 font-semibold ${emphasize ? "text-red-600" : "text-slate-800"}`}>{value}</div>
  </div>
)
