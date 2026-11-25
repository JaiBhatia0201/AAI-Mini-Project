import { AppProvider, useApp } from "./context/AppContext";
import { AppShell } from "./components/layout/AppShell";
import { AgentTracePage } from "./pages/AgentTracePage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AssessmentPage } from "./pages/AssessmentPage";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { KnowledgeGraphPage } from "./pages/KnowledgeGraphPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ParentDashboardPage } from "./pages/ParentDashboardPage";
import { PlannerPage } from "./pages/PlannerPage";
import { ReportCardPage } from "./pages/ReportCardPage";
import { ResourcesPage } from "./pages/ResourcesPage";
import { TutorPage } from "./pages/TutorPage";

function MainWorkspace() {
  const { user, loadingAuth, activeTab } = useApp();

  if (loadingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-medium text-slate-600">
        Loading AdaptivePrep Studio...
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <AppShell>
      {activeTab === "dashboard" && <DashboardPage />}
      {activeTab === "report_card" && <ReportCardPage />}
      {activeTab === "onboarding" && <OnboardingPage />}
      {activeTab === "tutor" && <TutorPage />}
      {activeTab === "graph" && <KnowledgeGraphPage />}
      {activeTab === "planner" && <PlannerPage />}
      {activeTab === "resources" && <ResourcesPage />}
      {activeTab === "assessments" && <AssessmentPage />}
      {activeTab === "analytics" && <AnalyticsPage />}
      {activeTab === "parent" && <ParentDashboardPage />}
      {activeTab === "traces" && <AgentTracePage />}
    </AppShell>
  );
}

export function App() {
  return (
    <AppProvider>
      <MainWorkspace />
    </AppProvider>
  );
}

export default App;
