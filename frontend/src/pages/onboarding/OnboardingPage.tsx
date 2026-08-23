import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"
import { useProject } from "@/context/ProjectContext"
import { trackEvent } from "@/lib/analytics"
import { ArrowRight, CheckCircle2, FolderKanban, UploadCloud } from "lucide-react"

export const OnboardingPage: React.FC = () => {
  const navigate = useNavigate()
  const { orgId, isAuthenticated } = useAuth()
  const { refreshProjects } = useProject()
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [currency, setCurrency] = useState("IDR")
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  if (!isAuthenticated) {
    navigate("/login?next=/onboarding", { replace: true })
    return null
  }

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!orgId) return
    setError(null)
    setIsSaving(true)
    trackEvent("onboarding_project_create_started")

    try {
      const project = await api.projects.create(orgId, { code, name, currency })
      if (project?.id) localStorage.setItem("controlcheck_current_project_id", project.id)
      await refreshProjects()
      trackEvent("onboarding_project_created", { project_code: code, currency })
      navigate("/data?onboarding=1")
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Project could not be created. Please check the details and try again.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-5 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">First project setup</div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Run your first ControlCheck audit</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Create the project context first. Next, upload your project-control workbook and ControlCheck will generate findings for review.</p>
        </div>

        <div className="mb-8 grid gap-3 md:grid-cols-3">
          <Step active icon={<FolderKanban className="h-5 w-5" />} number="01" title="Create Project" text="Define project code and currency." />
          <Step icon={<UploadCloud className="h-5 w-5" />} number="02" title="Upload Data" text="Import cost, schedule or progress data." />
          <Step icon={<CheckCircle2 className="h-5 w-5" />} number="03" title="Review Findings" text="Inspect evidence, reasons and actions." />
        </div>

        <form onSubmit={createProject} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
          <div className="border-b border-slate-100 pb-5">
            <h2 className="text-lg font-bold text-slate-900">Project details</h2>
            <p className="mt-1 text-sm text-slate-500">You can update project information later from Settings.</p>
          </div>

          {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold uppercase text-slate-600">Project code</span>
              <input required value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="e.g. GCF-EXP-01" className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold uppercase text-slate-600">Currency</span>
              <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500">
                <option value="IDR">IDR — Indonesian Rupiah</option>
                <option value="USD">USD — US Dollar</option>
              </select>
            </label>
            <label className="block md:col-span-2">
              <span className="mb-1.5 block text-xs font-bold uppercase text-slate-600">Project name</span>
              <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Gas Compression Facility Expansion" className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
          </div>

          <div className="mt-7 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <button type="button" onClick={() => navigate("/dashboard")} className="text-sm font-semibold text-slate-500 hover:text-slate-900">Skip and explore demo workspace</button>
            <button disabled={isSaving} className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50">
              {isSaving ? "Creating project..." : "Create Project & Upload Data"} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const Step = ({ active = false, icon, number, title, text }: { active?: boolean; icon: React.ReactNode; number: string; title: string; text: string }) => (
  <div className={`rounded-xl border p-4 ${active ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-white"}`}>
    <div className="flex items-center justify-between"><span className={active ? "text-blue-600" : "text-slate-400"}>{icon}</span><span className="text-xs font-mono text-slate-400">{number}</span></div>
    <div className="mt-4 text-sm font-bold text-slate-900">{title}</div>
    <div className="mt-1 text-xs leading-5 text-slate-500">{text}</div>
  </div>
)

export default OnboardingPage
