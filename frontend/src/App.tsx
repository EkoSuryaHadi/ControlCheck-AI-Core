import React from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "@/context/AuthContext"
import { ProjectProvider } from "@/context/ProjectContext"
import { AppShell } from "@/components/layout/AppShell"

import { LoginPage } from "@/pages/auth/LoginPage"
import { DashboardPage } from "@/pages/dashboard/DashboardPage"
import { FindingsPage } from "@/pages/findings/FindingsPage"
import { FindingDetailPage } from "@/pages/findings/FindingDetailPage"
import { DataImportWizard } from "@/pages/data/DataImportWizard"
import { AIAssistantPage } from "@/pages/assistant/AIAssistantPage"
import { ReportsPage } from "@/pages/reports/ReportsPage"
import { CostPage } from "@/pages/cost/CostPage"
import { SchedulePage } from "@/pages/schedule/SchedulePage"
import { ProgressPage } from "@/pages/progress/ProgressPage"
import { ProjectsPage } from "@/pages/projects/ProjectsPage"
import { SettingsPage } from "@/pages/settings/SettingsPage"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ProjectProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              {/* Protected App Frame */}
              <Route element={<AppShell />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/data" element={<DataImportWizard />} />
                <Route path="/findings" element={<FindingsPage />} />
                <Route path="/findings/:findingId" element={<FindingDetailPage />} />
                <Route path="/cost" element={<CostPage />} />
                <Route path="/schedule" element={<SchedulePage />} />
                <Route path="/progress" element={<ProgressPage />} />
                <Route path="/assistant" element={<AIAssistantPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </BrowserRouter>
        </ProjectProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
