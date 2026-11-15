import { useCallback, useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, RefreshCw, Sparkles } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { PlannerOverviewOut } from "../types/api";
import { AlertBanner, Badge, Button, Card } from "../components/ui/Primitives";

export function PlannerPage() {
  const { user, activeSyllabus, latestSimulation } = useApp();
  const [planner, setPlanner] = useState<PlannerOverviewOut | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPlanner = useCallback(async () => {
    if (!activeSyllabus) return;
    try {
      const res = await api.getPlanner(activeSyllabus.id);
      setPlanner(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load study plan.");
    }
  }, [activeSyllabus]);

  useEffect(() => {
    void loadPlanner();
  }, [loadPlanner]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Select a syllabus to view your personalized adaptive roadmap.
      </Card>
    );
  }

  const isStudent = user?.role === "student";
  const items = (planner?.items || []).filter(
    (item) => filterStatus === "all" || item.status === filterStatus,
  );

  async function handleAdaptNow() {
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    try {
      await api.adaptPlanner(activeSyllabus.id);
      await loadPlanner();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to run adaptive scheduler.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggle(itemId: string, currentStatus: string) {
    setError(null);
    try {
      const next = currentStatus === "completed" ? "pending" : "completed";
      await api.togglePlanItemStatus(itemId, next);
      await loadPlanner();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update task status.");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-indigo-600" />
            <span>Personalized Study Planner & Adaptation Diff</span>
          </h1>
          <p className="text-sm text-slate-600">
            Learn, Practice, Spaced Repetition (Day 3/7/14/30), and Remedial Blocker insertions scoped to {activeSyllabus.title}.
          </p>
        </div>
        {isStudent && (
          <Button disabled={busy} onClick={() => void handleAdaptNow()}>
            <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
            <span>Trigger Adaptive Check (Agents 8 &rarr; 9)</span>
          </Button>
        )}
      </div>

      {error && <AlertBanner tone="rose" title="Planner Error" message={error} />}

      {latestSimulation?.adaptation && (
        <Card className="border-amber-300 bg-amber-50/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" />
              Hypothetical Simulation Adaptation Preview (Not Persisted)
            </span>
            <Badge tone="amber">{latestSimulation.adaptation.changes.length} Previewed Shifts</Badge>
          </div>
          <p className="text-xs text-amber-950">{latestSimulation.adaptation.summary}</p>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-12">
        {/* Study Schedule Timeline */}
        <Card className="lg:col-span-7 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-bold text-slate-900">
              Schedule Timeline ({items.length})
            </h2>
            <div className="flex gap-1.5">
              {["all", "pending", "completed", "rescheduled"].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setFilterStatus(st)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium capitalize cursor-pointer ${
                    filterStatus === st
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 text-xs"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold text-slate-500">Day {item.day_number}</span>
                    <Badge
                      tone={
                        item.task_type === "spaced_rep"
                          ? "amber"
                          : item.task_type === "revision"
                            ? "rose"
                            : item.task_type === "assessment"
                              ? "teal"
                              : "indigo"
                      }
                    >
                      {item.task_type}
                    </Badge>
                    <span className="font-semibold text-slate-900 truncate">{item.topic_title}</span>
                  </div>
                  <p className="mt-1 text-slate-500">
                    {item.scheduled_date} &middot; {item.duration_hours}h
                    {item.adaptation_reason ? ` · ${item.adaptation_reason}` : ""}
                  </p>
                </div>

                {isStudent && item.status !== "rescheduled" ? (
                  <Button
                    variant={item.status === "completed" ? "ghost" : "secondary"}
                    className="shrink-0 px-2.5 py-1 text-xs"
                    onClick={() => void handleToggle(item.id, item.status)}
                  >
                    <CheckCircle2
                      className={`h-4 w-4 ${
                        item.status === "completed" ? "text-emerald-600" : "text-slate-400"
                      }`}
                    />
                    <span>{item.status === "completed" ? "Completed" : "Complete"}</span>
                  </Button>
                ) : (
                  <Badge tone={item.status === "rescheduled" ? "slate" : "emerald"}>{item.status}</Badge>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Persisted Adaptation Diff Audit Log */}
        <Card className="lg:col-span-5 space-y-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Persisted Adaptation Diffs</h2>
            <p className="text-xs text-slate-500">
              Recorded plan rewrites whenever quizzes or daily checks find weaknesses or decay.
            </p>
          </div>

          {(planner?.recent_adaptations || []).length === 0 ? (
            <p className="text-xs text-slate-500 py-4">
              No persisted plan rewrites yet. Take a quiz or click Trigger Adaptive Check.
            </p>
          ) : (
            <div className="space-y-3 max-h-[540px] overflow-y-auto pr-1">
              {planner?.recent_adaptations.map((adp, idx) => (
                <div key={adp.id || idx} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-2">
                  <div className="font-semibold text-slate-900">{adp.summary}</div>
                  {adp.changes.slice(0, 6).map((ch, cIdx) => (
                    <div
                      key={`${ch.topic_id}-${cIdx}`}
                      className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] text-slate-700"
                    >
                      <span className="font-semibold text-indigo-700 uppercase">+{ch.day_offset}d {ch.task_type}</span>{" "}
                      ({ch.topic_code || ch.topic_id}): {ch.reason}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
