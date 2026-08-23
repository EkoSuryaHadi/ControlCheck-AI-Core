import React from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, ArrowRight, CheckCircle2, FileText, ShieldCheck, TriangleAlert } from "lucide-react"
import { BrandLogo } from "@/components/common/BrandLogo"

const domainScores = [
  { label: "Cost Health", score: 58 },
  { label: "Schedule Health", score: 71 },
  { label: "Progress Health", score: 67 },
  { label: "Data Quality", score: 92 },
]

const sampleFindings = [
  {
    id: "FND-001",
    severity: "Critical",
    title: "Cost Overrun Risk — WBS 03.02",
    summary: "Forecast EAC exceeds approved BAC by Rp23.6B.",
    why: "CPI is below threshold, committed cost exposure is elevated, and revised ETC pushes forecast above approved budget.",
    action: "Review ETC assumptions, outstanding PO exposure, and remaining quantities before the next forecast cycle.",
    evidence: ["Cost Report Oct-2026", "PO Register", "Forecast Rev.04", "WBS Mapping"],
  },
  {
    id: "FND-002",
    severity: "Critical",
    title: "Negative Total Float — 5 Activities",
    summary: "Five activities show total float below zero on the current schedule.",
    why: "Late critical activities are consuming available schedule contingency and may move contractual milestones.",
    action: "Validate logic ties, recovery options and milestone impact with the scheduler and construction team.",
    evidence: ["P6 Export", "Baseline Schedule", "Progress Update"],
  },
  {
    id: "FND-003",
    severity: "Warning",
    title: "Progress Evidence Gap",
    summary: "Reported progress for selected WBS items is not fully supported by uploaded evidence.",
    why: "Claimed progress exceeds the evidence coverage found in the latest supporting records.",
    action: "Complete evidence submission or revise claimed progress before approval.",
    evidence: ["Progress Report", "Inspection Records", "Photo Evidence Index"],
  },
]

export const SampleAuditPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <Link to="/" className="flex items-center gap-3"><BrandLogo theme="light" size="md" /></Link>
          <div className="flex items-center gap-2">
            <Link to="/" className="hidden items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 sm:flex"><ArrowLeft className="h-4 w-4" /> Back</Link>
            <Link to="/login" className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">Check Your Project <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-10 lg:px-8">
        <div className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div><div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700"><ShieldCheck className="h-3.5 w-3.5" /> SAMPLE AUDIT</div><h1 className="mt-4 text-3xl font-bold tracking-tight">Gas Compression Facility Expansion</h1><p className="mt-2 text-slate-600">Example project-control health assessment generated from sample project data.</p></div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-4 text-right"><div className="text-xs font-bold uppercase tracking-wider text-amber-700">Project Health</div><div className="text-4xl font-black text-amber-600">68/100</div><div className="text-xs font-bold text-amber-700">MODERATE</div></div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[['Critical','17','text-red-600'],['Warning','23','text-amber-600'],['Observation','12','text-yellow-600'],['Data Quality','92%','text-emerald-600']].map(([label,value,c]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</div><div className={`mt-2 text-3xl font-black ${c}`}>{value}</div></div>)}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[.75fr_1.25fr]">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="font-bold">Domain Health</h2><div className="mt-6 space-y-5">{domainScores.map(item => <div key={item.label}><div className="mb-2 flex items-center justify-between text-sm font-semibold"><span>{item.label}</span><span>{item.score}</span></div><div className="h-2.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{width:`${item.score}%`}} /></div></div>)}</div></div>
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="font-bold">Audit Logic</h2><p className="mt-3 text-sm leading-6 text-slate-600">ControlCheck combines deterministic rules, cross-data checks and AI-assisted interpretation. Each finding should remain traceable back to project evidence and human review.</p><div className="mt-5 grid gap-3 sm:grid-cols-3">{[{icon:CheckCircle2,t:'Rule-driven',d:'Thresholds and structured checks.'},{icon:FileText,t:'Traceable',d:'Source evidence attached to findings.'},{icon:TriangleAlert,t:'Actionable',d:'Clear reason and recommended action.'}].map(({icon:Icon,t,d}) => <div key={t} className="rounded-lg bg-slate-50 p-4"><Icon className="h-5 w-5 text-blue-600"/><div className="mt-3 text-sm font-bold">{t}</div><div className="mt-1 text-xs leading-5 text-slate-600">{d}</div></div>)}</div></div>
        </div>

        <section className="mt-8"><div className="mb-5"><div className="text-sm font-bold text-blue-600">SAMPLE FINDINGS</div><h2 className="mt-1 text-2xl font-bold">What the project team needs to review</h2></div><div className="space-y-5">{sampleFindings.map(f => <article key={f.id} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start"><div><div className="text-xs font-mono text-slate-400">{f.id}</div><h3 className="mt-1 text-lg font-bold">{f.title}</h3></div><span className={`w-fit rounded-full border px-3 py-1 text-[10px] font-bold uppercase ${f.severity==='Critical'?'border-red-200 bg-red-50 text-red-700':'border-amber-200 bg-amber-50 text-amber-700'}`}>{f.severity}</span></div><p className="mt-3 font-medium text-slate-700">{f.summary}</p><div className="mt-5 grid gap-4 lg:grid-cols-2"><div className="rounded-lg bg-slate-50 p-4"><div className="text-xs font-bold uppercase tracking-wide text-slate-500">Why it was flagged</div><p className="mt-2 text-sm leading-6 text-slate-700">{f.why}</p></div><div className="rounded-lg bg-blue-50 p-4"><div className="text-xs font-bold uppercase tracking-wide text-blue-700">Recommended action</div><p className="mt-2 text-sm leading-6 text-slate-700">{f.action}</p></div></div><div className="mt-5"><div className="text-xs font-bold uppercase tracking-wide text-slate-500">Evidence</div><div className="mt-2 flex flex-wrap gap-2">{f.evidence.map(e => <span key={e} className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600">{e}</span>)}</div></div></article>)}</div></section>

        <section className="mt-10 rounded-2xl bg-navy-950 px-6 py-10 text-center text-white sm:px-10"><h2 className="text-2xl font-bold">Ready to check your own project data?</h2><p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-300">Use ControlCheck AI to turn cost, schedule, progress and supporting data into traceable findings for project review.</p><Link to="/login" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-500">Check Your Project <ArrowRight className="h-4 w-4"/></Link></section>
      </main>
    </div>
  )
}

export default SampleAuditPage
