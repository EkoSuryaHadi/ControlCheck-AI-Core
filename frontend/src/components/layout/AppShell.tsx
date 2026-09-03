import React, { useState } from "react"
import { NavLink, Outlet, useLocation, useNavigate, Link } from "react-router-dom"
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
  FileSpreadsheet,
  Settings,
  ChevronDown,
  Bell,
  Search,
  LogOut,
  ClipboardCheck,
  Activity,
  Menu,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { BrandLogo } from "@/components/common/BrandLogo"

export const AppShell: React.FC = () => {
  const { user, logout } = useAuth()
  const { currentProject, projects, setCurrentProject } = useProject()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close the mobile drawer on navigation
  React.useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  const navItems = [
    { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { name: "Projects", path: "/projects", icon: FolderKanban },
    { name: "Data", path: "/data", icon: Database },
    { name: "Findings", path: "/findings", icon: ShieldAlert },
    { name: "Actions", path: "/actions", icon: ClipboardCheck },
    { name: "Cost", path: "/cost", icon: CircleDollarSign },
    { name: "Schedule", path: "/schedule", icon: CalendarClock },
    { name: "Progress", path: "/progress", icon: LineChart },
    { name: "Reports", path: "/reports", icon: FileSpreadsheet },
    { name: "Settings", path: "/settings", icon: Settings },
    ...(user?.role === "owner" || user?.role === "org_admin" || user?.role === "org_owner" ? [{ name: "Beta Metrics", path: "/owner/metrics", icon: Activity }] : []),
  ]

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans text-slate-900">
      {/* Backdrop for the mobile drawer */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] shrink-0 flex-col justify-between border-r border-navy-900 bg-navy-950 text-slate-300 select-none transition-transform duration-200 ease-in-out",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "lg:static lg:z-30 lg:w-64 lg:translate-x-0"
        )}
      >
        <div className="flex h-full flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-navy-900">
            <Link to="/dashboard" className="flex items-center px-4 py-4 hover:opacity-90 transition-opacity" title="ControlCheck AI Dashboard">
              <BrandLogo variant="full" theme="dark" size="sm" imgClassName="h-8 w-auto max-w-[195px]" />
            </Link>
            <button onClick={() => setSidebarOpen(false)} className="mr-3 p-1 text-slate-400 hover:text-white lg:hidden" aria-label="Close menu"><X className="w-5 h-5" /></button>
          </div>

          <div className="px-3 pt-4 pb-2">
            <div className="text-[10px] font-bold text-slate-400 tracking-wider uppercase px-2 mb-1.5">Project Context</div>
            <div className="relative group">
              <select value={currentProject?.id || ""} onChange={(e) => { const p = projects.find((proj) => proj.id === e.target.value); if (p) setCurrentProject(p) }} className="w-full bg-navy-900 text-white text-xs font-medium rounded-lg px-3 py-2.5 appearance-none cursor-pointer border border-slate-700/60 focus:outline-none focus:ring-2 focus:ring-blue-500 pr-8 truncate">
                {projects.map((p) => <option key={p.id} value={p.id} className="bg-navy-900 text-white">{p.name}</option>)}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none group-hover:text-white transition-colors" />
            </div>
          </div>

          <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname.startsWith(item.path)
              return (
                <NavLink key={item.name} to={item.path} className={cn("flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 group", isActive ? "bg-blue-600 text-white font-semibold shadow-sm" : "text-slate-300 hover:bg-navy-900 hover:text-white") }>
                  <Icon className={cn("w-4 h-4 transition-colors", isActive ? "text-white" : "text-slate-400 group-hover:text-white")} />
                  <span>{item.name}</span>
                </NavLink>
              )
            })}
          </nav>

          <div className="p-3 border-t border-navy-900 bg-navy-950">
            <div className="flex items-center justify-between p-2 rounded-lg bg-navy-900 border border-slate-800/80">
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs shrink-0">{user?.name ? user.name.slice(0, 2).toUpperCase() : "EP"}</div>
                <div className="overflow-hidden"><div className="text-xs font-semibold text-white truncate">{user?.name || "Eko Prasetyo"}</div><div className="text-[10px] text-slate-400 truncate">{user?.role || "Project Control Manager"}</div></div>
              </div>
              <button onClick={() => { logout(); navigate("/login") }} title="Logout" className="text-slate-400 hover:text-red-400 p-1 rounded transition-colors"><LogOut className="w-4 h-4" /></button>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-slate-50">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-3 sm:px-6 z-20">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => setSidebarOpen(true)} className="p-1.5 -ml-1 text-slate-500 hover:bg-slate-100 rounded-lg lg:hidden" aria-label="Open menu"><Menu className="w-5 h-5" /></button>
            <h1 className="truncate text-base font-bold text-slate-900 tracking-tight">{currentProject?.name || "Gas Compression Facility Expansion"}</h1><span className="hidden sm:inline-flex text-xs font-mono px-2 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200">{currentProject?.code || "GCF-EXP-01"}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden md:block"><Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" /><input type="text" placeholder="Search findings, WBS, evidence..." className="pl-9 pr-3 py-1.5 text-xs bg-slate-100/80 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64 transition-all" /></div>
            <button title="Notifications" className="p-2 text-slate-500 hover:text-slate-900 rounded-lg hover:bg-slate-100 relative transition-colors"><Bell className="w-4 h-4" /><span className="w-2 h-2 rounded-full bg-red-500 absolute top-1.5 right-1.5" /></button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-3 sm:p-6"><Outlet /></main>
      </div>
    </div>
  )
}
