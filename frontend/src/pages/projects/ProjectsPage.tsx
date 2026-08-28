import React from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { FolderKanban, Plus, ExternalLink, Trash2 } from "lucide-react"
import { api } from "@/lib/api"

export const ProjectsPage: React.FC = () => {
  const { projects, setCurrentProject, removeProject } = useProject()
  const navigate = useNavigate()

  const handleDelete = async (projectId: string, projectName: string) => {
    if (!window.confirm(`Hapus project "${projectName}"? Semua data analisa terkait akan ikut terhapus.`)) return
    try {
      await api.projects.remove(projectId)
      removeProject(projectId)
    } catch {
      window.alert("Project gagal dihapus. Pastikan project tidak sedang diproses.")
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Project Portfolio</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Active capital projects and audit workspace registries
          </p>
        </div>
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Project</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((p) => (
          <div
            key={p.id}
            onClick={() => setCurrentProject(p)}
            className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:border-blue-400 hover:shadow-md transition-all cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold text-blue-600 px-2 py-0.5 bg-blue-50 rounded">
                  {p.code}
                </span>
                <div className="flex items-center gap-2"><span className="text-xs font-semibold px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">{p.status}</span><button type="button" title="Delete project" aria-label={`Delete ${p.name}`} onClick={(event) => { event.stopPropagation(); void handleDelete(p.id, p.name) }} className="rounded-md p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button></div>
              </div>
              <h2 className="text-sm font-bold text-slate-900 mt-1">{p.name}</h2>
              <div className="text-xs text-slate-500 mt-1">{p.client_name || "Enterprise Client"}</div>
            </div>

            <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-400">Currency: {p.currency}</span>
              <span className="text-blue-600 font-semibold flex items-center gap-1">
                <span>Select Project</span>
                <ExternalLink className="w-3 h-3" />
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
