import React, { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"
import { trackEvent } from "@/lib/analytics"
import { BrandLogo } from "@/components/common/BrandLogo"
import { ArrowRight, Building2, Lock, Mail, User } from "lucide-react"

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login } = useAuth()
  const [fullName, setFullName] = useState("")
  const [organizationName, setOrganizationName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)
    trackEvent("registration_started", { source: searchParams.get("source") || "direct" })

    try {
      const res = await api.auth.register({
        email,
        password,
        full_name: fullName,
        organization_name: organizationName,
      })

      if (res.access_token) {
        login(
          res.access_token,
          { id: res.user_id || "usr-new", email, name: res.name || fullName, role: "Project Control" },
          res.org_id || "org-new"
        )
      }

      trackEvent("registration_completed", { source: searchParams.get("source") || "direct" })
      navigate("/onboarding")
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Registration could not be completed. Please try again or sign in if you already have an account.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy-950 px-4 py-10 text-slate-900">
      <div className="mx-auto w-full max-w-lg rounded-2xl border border-slate-700/50 bg-white p-8 shadow-2xl">
        <div className="text-center">
          <Link to="/"><BrandLogo variant="full" theme="light" size="lg" className="mx-auto" imgClassName="h-11 w-auto max-w-[240px]" /></Link>
          <h1 className="mt-5 text-2xl font-bold">Create your ControlCheck workspace</h1>
          <p className="mt-2 text-sm text-slate-500">Set up your account, create a project, then run your first project-control check.</p>
        </div>

        {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{error}</div>}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Field label="Full name" icon={<User className="h-4 w-4" />} value={fullName} onChange={setFullName} placeholder="Your name" />
          <Field label="Organization" icon={<Building2 className="h-4 w-4" />} value={organizationName} onChange={setOrganizationName} placeholder="Company or team" />
          <Field label="Email" type="email" icon={<Mail className="h-4 w-4" />} value={email} onChange={setEmail} placeholder="you@company.com" />
          <Field label="Password" type="password" icon={<Lock className="h-4 w-4" />} value={password} onChange={setPassword} placeholder="Minimum 8 characters" minLength={8} />

          <button disabled={isLoading} className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50">
            {isLoading ? "Creating workspace..." : "Create Workspace"} <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-500">Already have an account? <Link to="/login" className="font-bold text-blue-600">Sign in</Link></div>
      </div>
    </div>
  )
}

const Field = ({ label, icon, value, onChange, placeholder, type = "text", minLength }: { label: string; icon: React.ReactNode; value: string; onChange: (v: string) => void; placeholder: string; type?: string; minLength?: number }) => (
  <label className="block">
    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-600">{label}</span>
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{icon}</span>
      <input required type={type} minLength={minLength} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
    </div>
  </label>
)

export default RegisterPage
