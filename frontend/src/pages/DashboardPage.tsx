import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Flame,
  Play,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type {
  DailyCheckResponse,
  PlannerOverviewOut,
  StudentAnalyticsOut,
} from "../types/api";
import { AlertBanner, Badge, Button, Card, StatCard } from "../components/ui/Primitives";

export function DashboardPage() {
  const {
    user,
    activeSyllabus,
    latestSimulation,
    setLatestSimulation,
    setActiveTab,
    refreshWorkspace,
  } = useApp();

  const [analytics, setAnalytics] = useState<StudentAnalyticsOut | null>(null);
  const [planner, setPlanner] = useState<PlannerOverviewOut | null>(null);
  const [dailyResult, setDailyResult] = useState<DailyCheckResponse | null>(null);
  const [simDays, setSimDays] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSyllabus) return;
    let cancelled = false;
    Promise.all([
      api.getStudentAnalytics(activeSyllabus.id),
      api.getPlanner(activeSyllabus.id),
    ])
      .then(([ana, pln]) => {
        if (!cancelled) {
          setAnalytics(ana);
          setPlanner(pln);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load dashboard metrics.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeSyllabus]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center">
        <h2 className="text-xl font-bold text-slate-900">Welcome to AdaptivePrep Studio</h2>
        <p className="mt-2 text-sm text-slate-600">
          Start by uploading your course or exam syllabus PDF (or cloning GATE CSE) to generate your Knowledge Graph and study roadmap.
        </p>
        <Button className="mt-4" onClick={() => setActiveTab("onboarding")}>
          Upload First Syllabus
        </Button>
      </Card>
    );
  }

  const pred = analytics?.predictive_score;
  const activeAlerts = latestSimulation ? latestSimulation.decay_alerts : [];
  const todaysTasks = (planner?.items || []).filter((i) => i.status === "pending").slice(0, 5);

  async function handleRunDailyCheck() {
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.runDailyCheck(activeSyllabus.id);
      setDailyResult(res);
      setLatestSimulation(null);
      await refreshWorkspace(activeSyllabus.id);
      const pln = await api.getPlanner(activeSyllabus.id);
      setPlanner(pln);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Daily check failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSimulate() {
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.simulateDailyCheck(activeSyllabus.id, simDays);
      setLatestSimulation(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleTask(itemId: string) {
    if (!activeSyllabus) return;
    try {
      await api.togglePlanItemStatus(itemId, "completed");
      const [ana, pln] = await Promise.all([
        api.getStudentAnalytics(activeSyllabus.id),
        api.getPlanner(activeSyllabus.id),
      ]);
      setAnalytics(ana);
      setPlanner(pln);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update study task.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{activeSyllabus.title}</h1>
          <p className="text-sm text-slate-600">
            Target: <strong>{activeSyllabus.target_score} / {activeSyllabus.max_score}</strong> in{" "}
            <strong>{activeSyllabus.days_remaining}</strong> days &middot; Learning style:{" "}
            <span className="capitalize font-medium">{user?.student_profile?.learning_style || "visual"}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => void handleRunDailyCheck()}>
            <CalendarClock className="h-4 w-4" />
            <span>Run Real Daily Check</span>
          </Button>
          <Button onClick={() => setActiveTab("assessments")}>
            <span>Take Practice Quiz</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && <AlertBanner tone="rose" title="Error" message={error} />}

      {dailyResult && (
        <AlertBanner
          tone="teal"
          title="Live Agent Coaching (Persisted)"
          message={dailyResult.coaching_message}
        />
      )}

      {/* Top KPI Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          tone="indigo"
          label="Estimated Readiness (Not Rank)"
          value={pred ? `${pred.current_estimated_score} / ${pred.max_score}` : "--"}
          hint={
            pred
              ? `Projected: ${pred.projected_estimated_score} / ${pred.max_score} (${pred.readiness_band})`
              : "Estimated from weighted mastery"
          }
          icon={<TrendingUp className="h-4 w-4 text-indigo-600" />}
        />
        <StatCard
          tone="teal"
          label="Overall Mastery & Coverage"
          value={analytics ? `${analytics.overall_mastery.toFixed(1)}%` : "--"}
          hint={analytics ? `${analytics.coverage_percent}% syllabus started` : ""}
          icon={<CheckCircle2 className="h-4 w-4 text-teal-600" />}
        />
        <StatCard
          tone="rose"
          label="Weak & At-Risk Topics"
          value={analytics ? analytics.weak_topic_count : 0}
          hint={`${analytics?.forgetting_alerts_count || 0} live Ebbinghaus decay alert(s)`}
          icon={<AlertTriangle className="h-4 w-4 text-rose-600" />}
        />
        <StatCard
          tone="amber"
          label="Study Streak & Hours"
          value={`${user?.student_profile?.study_streak || 0} days`}
          hint={`${user?.student_profile?.total_hours_logged || 0} hrs logged total`}
          icon={<Flame className="h-4 w-4 text-amber-600" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Today's Adaptive Tasks */}
        <Card className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Next Scheduled Study Tasks</h2>
              <p className="text-xs text-slate-500">Topologically ordered & updated automatically by Agent 9</p>
            </div>
            <Button variant="ghost" className="text-xs" onClick={() => setActiveTab("planner")}>
              Full Roadmap &rarr;
            </Button>
          </div>

          {todaysTasks.length === 0 ? (
            <p className="text-sm text-slate-500 py-4">
              All scheduled tasks completed! Run a Daily Check or start a new topic quiz.
            </p>
          ) : (
            <div className="space-y-2.5">
              {todaysTasks.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        tone={
                          item.task_type === "spaced_rep"
                            ? "amber"
                            : item.task_type === "revision"
                              ? "rose"
                              : "indigo"
                        }
                      >
                        {item.task_type}
                      </Badge>
                      <span className="truncate text-sm font-semibold text-slate-900">
                        {item.topic_title}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-xs text-slate-500">
                      Day {item.day_number} ({item.scheduled_date}) &middot; {item.duration_hours}h
                      {item.adaptation_reason ? ` — ${item.adaptation_reason}` : ""}
                    </p>
                  </div>
                  {user?.role === "student" && (
                    <Button
                      variant="secondary"
                      className="shrink-0 px-3 py-1 text-xs"
                      onClick={() => void handleToggleTask(item.id)}
                    >
                      Mark Done
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Non-Destructive Time-Shift Simulator */}
        <Card className="lg:col-span-5 space-y-4 border-amber-200 bg-amber-50/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600" />
              <h2 className="text-base font-bold text-slate-900">Non-Destructive Demo Simulator</h2>
            </div>
            <Badge tone="amber">In-Memory Only</Badge>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">
            Fast-forward the Ebbinghaus forgetting clock <strong>exp(-t / S)</strong> to preview which topics fade and how Agent 9 would reschedule—with <strong>zero database writes</strong>.
          </p>

          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-slate-700">Simulate Days Elapsed:</label>
            <select
              value={simDays}
              onChange={(e) => setSimDays(Number(e.target.value))}
              className="rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-semibold"
            >
              {[3, 7, 10, 14, 21, 30].map((d) => (
                <option key={d} value={d}>
                  +{d} Days
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              disabled={busy}
              className="ml-auto text-xs border-amber-400"
              onClick={() => void handleSimulate()}
            >
              <Play className="h-3.5 w-3.5" />
              <span>Preview +{simDays}d</span>
            </Button>
          </div>

          {latestSimulation ? (
            <div className="space-y-2 rounded-lg border border-amber-200 bg-white p-3 text-xs">
              <div className="font-semibold text-amber-900">{latestSimulation.coaching_message}</div>
              {activeAlerts.length > 0 ? (
                <ul className="space-y-1 text-slate-700">
                  {activeAlerts.slice(0, 4).map((a) => (
                    <li key={a.topic_id} className="flex justify-between tabular-nums">
                      <span className="truncate font-medium">{a.title}</span>
                      <span className="text-rose-700 font-semibold">
                        {(a.retention_score * 100).toFixed(0)}% ret
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500">All practiced topics stay above 65% retention threshold.</p>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-amber-300 bg-white/60 p-3 text-xs text-slate-600">
              Click <strong>Preview +{simDays}d</strong> to inspect hypothetical decay alerts and agent adaptation preview safely.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
