import React from "react"
import { Link } from "react-router-dom"
import { BrandLogo } from "@/components/common/BrandLogo"
import {
  ArrowRight,
  CheckCircle2,
  FileCheck2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  SearchCheck,
  TriangleAlert,
  Database,
  LineChart,
} from "lucide-react"

const domainCards = [
  { title: "Cost", text: "Detect overrun exposure, commitment gaps, forecast drift and EVM anomalies.", icon: LineChart },
  { title: "Schedule", text: "Flag delays, negative float, weak logic and schedule inconsistencies.", icon: SearchCheck },
  { title: "Progress", text: "Cross-check progress claims against supporting data and project evidence.", icon: CheckCircle2 },
  { title: "Data Quality", text: "Find missing fields, mismatches, duplicates and unreliable source data.", icon: Database },
]

const findings = [
  { severity: "Critical", title: "Cost Overrun Risk — WBS 03.02", detail: "Forecast EAC exceeds BAC by Rp23.6B", className: "text-red-600 bg-red-50 border-red-100" },
  { severity: "Critical", title: "Negative Total Float", detail: "5 activities detected with total float below zero", className: "text-red-600 bg-red-50 border-red-100" },
  { severity: "Warning", title: "Progress Evidence Gap", detail: "Reported progress is missing supporting evidence", className: "text-amber-700 bg-amber-50 border-amber-100" },
]

export const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <BrandLogo theme="light" size="md" imgClassName="h-9" />
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex">
            <a href="#how" className="hover:text-slate-950">How it works</a>
            <a href="#checks" className="hover:text-slate-950">What it checks</a>
            <a href="#findings" className="hover:text-slate-950">Findings</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="hidden rounded-lg px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 sm:inline-flex">Sign in</Link>
            <Link to="/demo" className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700">
              View Sample Audit <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden bg-navy-950 text-white">
          <div className="absolute inset-0 opacity-30 [background:radial-gradient(circle_at_70%_20%,#1769E8_0,transparent_35%)]" />
          <div className="relative mx-auto grid max-w-7xl gap-12 px-5 py-20 lg:grid-cols-[1.05fr_.95fr] lg:px-8 lg:py-28">
            <div className="flex flex-col justify-center">
              <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-blue-400/30 bg-blue-400/10 px-3 py-1 text-xs font-semibold text-blue-200">
                <ShieldCheck className="h-3.5 w-3.5" /> Project Control Assurance Platform
              </div>
              <h1 className="max-w-4xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
                Don&apos;t Ask AI About Your Project. <span className="text-blue-400">Let AI Check Your Project.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
                Detect inconsistencies in cost, schedule, progress and project-control data before they become bigger problems.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link to="/login" className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-500">
                  Run Project Check <ArrowRight className="h-4 w-4" />
                </Link>
                <Link to="/demo" className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-600 bg-white/5 px-5 py-3 text-sm font-bold text-white hover:bg-white/10">
                  View Sample Audit
                </Link>
              </div>
              <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-xs font-medium text-slate-400">
                <span>Deterministic Checks</span><span>•</span><span>AI Analysis</span><span>•</span><span>Traceable Evidence</span><span>•</span><span>Human Review</span>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-700 bg-white p-4 text-slate-900 shadow-2xl shadow-blue-950/30">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Gas Compression Facility Expansion</div>
                    <div className="mt-1 text-sm font-semibold text-slate-800">Project Health Overview</div>
                  </div>
                  <div className="text-right"><div className="text-4xl font-black text-amber-500">68</div><div className="text-[10px] font-bold text-amber-700">MODERATE</div></div>
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[['CRITICAL','17','text-red-600'],['WARNING','23','text-amber-600'],['OBSERVATION','12','text-yellow-600'],['DATA QUALITY','92%','text-emerald-600']].map(([label,value,c]) => (
                    <div key={label} className="rounded-lg border border-slate-200 bg-white p-3"><div className="text-[10px] font-bold text-slate-500">{label}</div><div className={`mt-1 text-2xl font-black ${c}`}>{value}</div></div>
                  ))}
                </div>
                <div className="mt-4 space-y-3 rounded-lg bg-white p-4">
                  {[['Cost Health',58],['Schedule Health',71],['Progress Health',67],['Data Quality',92]].map(([label,score]) => (
                    <div key={String(label)}><div className="mb-1 flex justify-between text-xs font-semibold"><span>{label}</span><span>{score}</span></div><div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-600" style={{width:`${score}%`}} /></div></div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
          <div className="max-w-2xl"><div className="text-sm font-bold text-blue-600">HOW IT WORKS</div><h2 className="mt-2 text-3xl font-bold tracking-tight">From project data to actionable findings.</h2></div>
          <div className="mt-10 grid gap-4 md:grid-cols-4">
            {[{icon:UploadCloud,t:'1. Project Data',d:'Excel, CSV, schedule, cost and progress data.'},{icon:SearchCheck,t:'2. Control Check Engine',d:'Rules, cross-checks and AI-assisted analysis.'},{icon:TriangleAlert,t:'3. Findings',d:'Critical, warning and observation findings.'},{icon:FileCheck2,t:'4. Evidence & Action',d:'Traceable source, reason and recommended action.'}].map(({icon:Icon,t,d}) => <div key={t} className="rounded-xl border border-slate-200 p-5"><Icon className="h-6 w-6 text-blue-600"/><h3 className="mt-4 font-bold">{t}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{d}</p></div>)}
          </div>
        </section>

        <section id="checks" className="bg-slate-50 py-20">
          <div className="mx-auto max-w-7xl px-5 lg:px-8"><div className="max-w-2xl"><div className="text-sm font-bold text-blue-600">WHAT IT CHECKS</div><h2 className="mt-2 text-3xl font-bold">Built for real project-control workflows.</h2></div><div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-4">{domainCards.map(({title,text,icon:Icon}) => <div key={title} className="rounded-xl border border-slate-200 bg-white p-6"><Icon className="h-6 w-6 text-blue-600"/><h3 className="mt-4 font-bold">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></div>)}</div></div>
        </section>

        <section id="findings" className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-2"><div><div className="text-sm font-bold text-blue-600">EVIDENCE-BACKED FINDINGS</div><h2 className="mt-2 text-3xl font-bold">Every finding should explain what, where, why, evidence and action.</h2><p className="mt-4 max-w-xl text-slate-600">ControlCheck is designed to show why an issue was flagged and what project evidence supports it—not just produce a generic AI answer.</p><Link to="/demo" className="mt-6 inline-flex items-center gap-2 font-bold text-blue-600">Explore sample audit <ArrowRight className="h-4 w-4"/></Link></div><div className="space-y-3">{findings.map(f => <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${f.className}`}>{f.severity}</div><div className="mt-3 font-bold">{f.title}</div><div className="mt-1 text-sm text-slate-600">{f.detail}</div></div>)}</div></div>
        </section>

        <section className="bg-navy-950 py-16 text-white"><div className="mx-auto max-w-5xl px-5 text-center"><Sparkles className="mx-auto h-7 w-7 text-blue-400"/><h2 className="mt-4 text-3xl font-bold">AI-assisted. Rule-driven. Evidence-backed.</h2><p className="mx-auto mt-4 max-w-2xl text-slate-300">Turn project-control data into traceable findings your team can review, discuss and act on.</p><div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row"><Link to="/login" className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold hover:bg-blue-500">Try ControlCheck AI</Link><Link to="/demo" className="rounded-xl border border-slate-600 px-5 py-3 text-sm font-bold hover:bg-white/10">View Sample Audit</Link></div></div></section>
      </main>

      <footer className="border-t border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between lg:px-8"><BrandLogo theme="light" size="sm"/><span>Project Control Assurance Platform</span></div></footer>
    </div>
  )
}

export default HomePage
