import React from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { useProject } from "@/context/ProjectContext"
import {
  LayoutDashboard,
  FolderKanban,
  Database,
  ShieldAlert,
  CircleDollarSign,
  CalendarClock,
  LineChart,
  Bot,
  FileSpreadsheet,
  Settings,
  ChevronDown,
  Bell,
  Search,
  Plus,
  LogOut,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"

export const AppShell: React.FC = () => {
  const { user, logout } = useAuth()
  const { currentProject, projects, setCurrentProject } = useProject()
  const location = useLocation()
  const navigate = useNavigate()

  const navItems = [
    { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { name: "Projects", path: "/projects", icon: FolderKanban },
    { name: "Data", path: "/data", icon: Database },
    { name: "Findings", path: "/findings", icon: ShieldAlert },
    { name: "Cost", path: "/cost", icon: CircleDollarSign },
    { name: "Schedule", path: "/schedule", icon: CalendarClock },
    { name: "Progress", path: "/progress", icon: LineChart },
    { name: "AI Assistant", path: "/assistant", icon: Bot, isAI: true },
    { name: "Reports", path: "/reports", icon: FileSpreadsheet },
    { name: "Settings", path: "/settings", icon: Settings },
  ]

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans text-slate-900">
      {/* Dark Navy Sidebar */}
      <aside className="w-64 shrink-0 bg-navy-950 text-slate-300 flex flex-col justify-between border-r border-navy-900 select-none z-30">
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo & Brand Header */}
          <div className="p-4 flex items-center gap-3 border-b border-navy-900">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-900/50">
              <ShieldCheck className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div>
              <div className="text-white font-bold tracking-tight text-base flex items-center gap-1.5">
                CONTROL<span className="text-blue-400">CHECK</span>
                <span className="text-[10px] font-extrabold bg-blue-600/30 text-blue-400 px-1.5 py-0.2 rounded border border-blue-500/40">
                  AI
                </span>
              </div>
              <div className="text-[10px] text-slate-400 tracking-wider uppercase font-medium">
                Audit & Governance
              </div>
            </div>
          </div>

          {/* Project Selector Box */}
          <div className="px-3 pt-4 pb-2">
            <div className="text-[10px] font-bold text-slate-400 tracking-wider uppercase px-2 mb-1.5">
              Project Context
            </div>
            <div className="relative group">
              <select
                value={currentProject?.id || ""}
                onChange={(e) => {
                  const p = projects.find((proj) => proj.id === e.target.value)
                  if (p) setCurrentProject(p)
                }}
                className="w-full bg-navy-900 text-white text-xs font-medium rounded-lg px-3 py-2.5 appearance-none cursor-pointer border border-slate-700/60 focus:outline-none focus:ring-2 focus:ring-blue-500 pr-8 truncate"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-navy-900 text-white">
                    {p.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none group-hover:text-white transition-colors" />
            </div>
          </div>

          {/* Nav Items Rail */}
          <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname.startsWith(item.path)

              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 group",
                    isActive
                      ? "bg-blue-600 text-white font-semibold shadow-sm"
                      : "text-slate-300 hover:bg-navy-900 hover:text-white",
                    item.isAI && !isActive && "hover:text-purple-300"
                  )}
                >
                  <Icon
                    className={cn(
                      "w-4 h-4 transition-colors",
                      isActive
                        ? "text-white"
                        : item.isAI
                        ? "text-purple-400 group-hover:text-purple-300"
                        : "text-slate-400 group-hover:text-white"
                    )}
                  />
                  <span>{item.name}</span>
                  {item.isAI && (
                    <Sparkles className="w-3 h-3 ml-auto text-purple-400" />
                  )}
                </NavLink>
              )
            })}
          </nav>

          {/* User Profile & Logout Anchor */}
          <div className="p-3 border-t border-navy-900 bg-navy-950">
            <div className="flex items-center justify-between p-2 rounded-lg bg-navy-900 border border-slate-800/80">
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs shrink-0">
                  {user?.name ? user.name.slice(0, 2).toUpperCase() : "EP"}
                </div>
                <div className="overflow-hidden">
                  <div className="text-xs font-semibold text-white truncate">
                    {user?.name || "Eko Prasetyo"}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    {user?.role || "Project Control Manager"}
                  </div>
                </div>
              </div>
              <button
                onClick={() => {
                  logout()
                  navigate("/login")
                }}
                title="Logout"
                className="text-slate-400 hover:text-red-400 p-1 rounded transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 z-20">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-slate-900 tracking-tight">
              {currentProject?.name || "Gas Compression Facility Expansion"}
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200">
              {currentProject?.code || "GCF-EXP-01"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search findings, WBS, evidence..."
                className="pl-9 pr-3 py-1.5 text-xs bg-slate-100/80 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64 transition-all"
              />
            </div>

            <button
              title="Notifications"
              className="p-2 text-slate-500 hover:text-slate-900 rounded-lg hover:bg-slate-100 relative transition-colors"
            >
              <Bell className="w-4 h-4" />
              <span className="w-2 h-2 rounded-full bg-red-500 absolute top-1.5 right-1.5" />
            </button>

            <button
              onClick={() => navigate("/data")}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Import Dataset</span>
            </button>
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
