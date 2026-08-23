import React from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "@/context/AuthContext"
import { ProjectProvider } from "@/context/ProjectContext"
import { AppShell } from "@/components/layout/AppShell"

import { HomePage } from "@/pages/public/HomePage"
import { SampleAuditPage } from "@/pages/public/SampleAuditPage"
import { LoginPage } from "@/pages/auth/LoginPage"
import { RegisterPage } from "@/pages/auth/RegisterPage"
import { OnboardingPage } from "@/pages/onboarding/OnboardingPage"
import { DashboardPage } from "@/pages/dashboard/DashboardPage"
import { FindingsPage } from "@/pages/findings/FindingsPage"
import { FindingDetailV2Page } from "@/pages/findings/FindingDetailV2Page"
import { ActionsPage } from "@/pages/actions/ActionsPage"
import { DataImportWizard } from "@/pages/data/DataImportWizard"
import { AnalysisProgressPage } from "@/pages/analysis/AnalysisProgressPage"
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
              <Route path="/" element={<HomePage />} />
              <Route path="/demo" element={<SampleAuditPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/onboarding" element={<OnboardingPage />} />

              <Route element={<AppShell />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/data" element={<DataImportWizard />} />
                <Route path="/analysis-progress" element={<AnalysisProgressPage />} />
                <Route path="/findings" element={<FindingsPage />} />
                <Route path="/findings/:findingId" element={<FindingDetailV2Page />} />
                <Route path="/actions" element={<ActionsPage />} />
                <Route path="/cost" element={<CostPage />} />
                <Route path="/schedule" element={<SchedulePage />} />
                <Route path="/progress" element={<ProgressPage />} />
                <Route path="/assistant" element={<AIAssistantPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ProjectProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
