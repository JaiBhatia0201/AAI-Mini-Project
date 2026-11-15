import { type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  FilePlus2,
  GitFork,
  GraduationCap,
  LayoutDashboard,
  Library,
  LogOut,
  MessageSquareText,
  RefreshCw,
  ShieldAlert,
  Users,
} from "lucide-react";
import { useApp, type NavTab } from "../../context/AppContext";
import { AlertBanner, Badge, Button, cn } from "../ui/Primitives";

const STUDENT_NAV: Array<{ id: NavTab; label: string; icon: typeof LayoutDashboard }> = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "onboarding", label: "Upload / New Syllabus", icon: FilePlus2 },
  { id: "tutor", label: "AI Study Tutor", icon: MessageSquareText },
  { id: "graph", label: "Knowledge Graph", icon: GitFork },
  { id: "planner", label: "Study Planner", icon: CalendarDays },
  { id: "resources", label: "Resources", icon: Library },
  { id: "assessments", label: "Quizzes & Exams", icon: ClipboardCheck },
  { id: "analytics", label: "Analytics & Decay", icon: BarChart3 },
  { id: "parent", label: "Parent Portal Preview", icon: Users },
  { id: "traces", label: "Agent Trace", icon: Activity },
];

const PARENT_NAV: Array<{ id: NavTab; label: string; icon: typeof LayoutDashboard }> = [
  { id: "parent", label: "Parent / Teacher View", icon: Users },
  { id: "analytics", label: "Progress & Decay", icon: BarChart3 },
  { id: "graph", label: "Syllabus Graph (RO)", icon: GitFork },
  { id: "planner", label: "Roadmap (RO)", icon: CalendarDays },
  { id: "traces", label: "Agent Trace (RO)", icon: Activity },
];

export function AppShell({ children }: { children: ReactNode }) {
  const {
    user,
    health,
    syllabi,
    activeSyllabus,
    activeTab,
    latestSimulation,
    loadingWorkspace,
    setActiveTab,
    setLatestSimulation,
    switchSyllabus,
    refreshWorkspace,
    logout,
  } = useApp();

  const isParent = user?.role === "parent_teacher";
  const navItems = isParent ? PARENT_NAV : STUDENT_NAV;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Persistent Top Workspace Bar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-xs">
              <GraduationCap className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-900">AdaptivePrep Studio</span>
                <Badge tone={health?.llm_mode === "llm" ? "indigo" : "teal"}>
                  {health?.llm_mode === "llm" ? "LLM Mode Active" : "Deterministic + TF-IDF"}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-700">{user?.name}</span>
                {isParent ? (
                  <Badge tone="amber">Read-Only Guardian</Badge>
                ) : (
                  user?.student_profile?.link_code && (
                    <span className="font-mono text-[11px] text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                      Parent Link Code: {user.student_profile.link_code}
                    </span>
                  )
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {syllabi.length > 0 && (
              <div className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1.5">
                <BookOpen className="h-4 w-4 text-indigo-600" />
                <select
                  aria-label="Active Syllabus"
                  value={activeSyllabus?.id || ""}
                  onChange={(e) => void switchSyllabus(e.target.value)}
                  className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
                >
                  {syllabi.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title} ({s.exam_name})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {!isParent && (
              <Button
                variant="secondary"
                className="px-3 py-1.5 text-xs"
                onClick={() => setActiveTab("onboarding")}
              >
                <FilePlus2 className="h-3.5 w-3.5" />
                <span>+ New Syllabus</span>
              </Button>
            )}

            <Button
              variant="ghost"
              className="px-2.5 py-1.5 text-xs"
              disabled={loadingWorkspace}
              onClick={() => void refreshWorkspace(activeSyllabus?.id)}
              title="Refresh Workspace"
            >
              <RefreshCw className={cn("h-4 w-4", loadingWorkspace && "animate-spin")} />
            </Button>

            <Button variant="ghost" className="px-2.5 py-1.5 text-xs text-rose-600" onClick={logout}>
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign Out</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-6 px-4 py-6">
        {/* Desktop Sidebar */}
        <aside className="hidden w-60 shrink-0 lg:block">
          <nav className="sticky top-22 space-y-1 rounded-xl border border-slate-200 bg-white p-2 shadow-xs">
            {navItems.map((item) => {
              const Icon = item.icon;
              const selected = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition cursor-pointer",
                    selected
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="min-w-0 flex-1 space-y-5">
          {/* Mobile Tab Strip */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 lg:hidden">
            {navItems.map((item) => {
              const Icon = item.icon;
              const selected = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium cursor-pointer",
                    selected
                      ? "border-indigo-600 bg-indigo-600 text-white"
                      : "border-slate-200 bg-white text-slate-600",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          {isParent && (
            <AlertBanner
              tone="amber"
              title="Read-Only Parent / Teacher Portal"
              message="All write actions, assessments, and workflow triggers are disabled for linked guardian accounts."
              action={<ShieldAlert className="h-4 w-4 text-amber-700" />}
            />
          )}

          {latestSimulation && (
            <AlertBanner
              tone="amber"
              title="Non-Destructive Demo Simulation Active"
              message={`Previewing hypothetical forgetting & adaptation state (+${
                latestSimulation.decay_alerts.length
              } decay alert(s)). SQLite mastery & study plans remain untouched.`}
              action={
                <Button
                  variant="secondary"
                  className="px-2.5 py-1 text-xs"
                  onClick={() => setLatestSimulation(null)}
                >
                  Clear Preview
                </Button>
              }
            />
          )}

          {children}
        </main>
      </div>
    </div>
  );
}
