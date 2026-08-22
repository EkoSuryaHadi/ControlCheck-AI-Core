import React, { createContext, useContext, useState, useEffect } from "react"
import { api, User } from "@/lib/api"

interface AuthContextType {
  user: User | null
  token: string | null
  orgId: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string, user: User, orgId: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem("controlcheck_token"))
  const [orgId, setOrgId] = useState<string | null>(localStorage.getItem("controlcheck_org_id"))
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("controlcheck_user")
    return saved ? JSON.parse(saved) : null
  })
  const [isLoading, setIsLoading] = useState(false)

  const login = (newToken: string, newUser: User, newOrgId: string) => {
    setToken(newToken)
    setUser(newUser)
    setOrgId(newOrgId)
    localStorage.setItem("controlcheck_token", newToken)
    localStorage.setItem("controlcheck_user", JSON.stringify(newUser))
    localStorage.setItem("controlcheck_org_id", newOrgId)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    setOrgId(null)
    localStorage.removeItem("controlcheck_token")
    localStorage.removeItem("controlcheck_user")
    localStorage.removeItem("controlcheck_org_id")
    localStorage.removeItem("controlcheck_current_project_id")
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        orgId,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within an AuthProvider")
  return context
}
