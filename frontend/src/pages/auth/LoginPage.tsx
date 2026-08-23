import React, { useState } from "react"
import { useNavigate, Link, useSearchParams } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { api } from "@/lib/api"
import { normalizeAuthResponse } from "@/lib/authSession"
import { trackEvent } from "@/lib/analytics"
import { Lock, Mail, ArrowRight, AlertCircle } from "lucide-react"
import { BrandLogo } from "@/components/common/BrandLogo"

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login } = useAuth()
  const [email, setEmail] = useState("admin@controlcheck.ai")
  const [password, setPassword] = useState("controlcheck123")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const nextPath = searchParams.get("next") || "/dashboard"
  const source = searchParams.get("source") || "direct"

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)
    trackEvent("login_started", { source })

    try {
      const res = await api.auth.login({ email, password })
      const identity = normalizeAuthResponse(res, { email })
      login(
        identity.accessToken,
        { id: identity.userId, email: identity.email, name: identity.fullName, role: identity.role },
        identity.orgId
      )
      trackEvent("login_completed", { source, role: identity.role })
      navigate(nextPath, { replace: true })
    } catch (err: any) {
      const apiMessage = err?.response?.data?.error?.message || err?.response?.data?.detail
      setError(apiMessage || err?.message || "Invalid email or password.")
      trackEvent("login_failed", { source, status: err?.response?.status || 0 })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDemoLogin = () => {
    login(
      "demo-jwt-token",
      { id: "demo-usr-01", email: "demo@controlcheck.ai", name: "Demo User", role: "Project Control Manager" },
      "demo-org-01"
    )
    trackEvent("demo_login_used", { source })
    navigate(nextPath, { replace: true })
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-navy-950 px-4 font-sans">
      <div className="w-full max-w-md bg-white rounded-2xl p-8 shadow-2xl border border-slate-700/50 space-y-6">
        <div className="text-center space-y-3 pb-2 border-b border-slate-100">
          <Link to="/"><BrandLogo variant="full" theme="light" size="lg" className="mx-auto" imgClassName="h-11 w-auto max-w-[240px]" /></Link>
          <p className="text-[11px] text-slate-500 font-medium">Project Control Assurance Platform</p>
        </div>

        {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>{error}</span></div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[11px] font-bold uppercase text-slate-600 block mb-1">Email Address</label>
            <div className="relative"><Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" /><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="you@company.com" /></div>
          </div>
          <div>
            <label className="text-[11px] font-bold uppercase text-slate-600 block mb-1">Password</label>
            <div className="relative"><Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" /><input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="••••••••" /></div>
          </div>
          <button type="submit" disabled={isLoading} className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 flex items-center justify-center gap-1.5 transition-all"><span>{isLoading ? "Signing in..." : "Sign In to Workspace"}</span><ArrowRight className="w-4 h-4" /></button>
        </form>

        <button onClick={handleDemoLogin} className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100">Enter Demo Workspace</button>

        <div className="rounded-xl bg-slate-50 p-4 text-center"><div className="text-xs text-slate-500">New to ControlCheck?</div><Link to={`/register?source=${encodeURIComponent(source)}`} className="mt-1 inline-flex items-center gap-1 text-sm font-bold text-blue-600 hover:text-blue-700">Create workspace <ArrowRight className="h-3.5 w-3.5" /></Link></div>
      </div>
    </div>
  )
}

export default LoginPage
