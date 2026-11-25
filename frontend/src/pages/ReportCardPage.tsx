import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Award,
  CheckCircle2,
  ClipboardList,
  Flame,
  Printer,
  Target,
  TrendingUp,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { ParentDashboardOut, StudentAnalyticsOut } from "../types/api";
import { AlertBanner, Badge, Button, Card } from "../components/ui/Primitives";

function letterGrade(score: number): {
  grade: string;
  remark: string;
  tone: "emerald" | "teal" | "indigo" | "amber" | "rose";
} {
  if (score >= 85) return { grade: "A+", remark: "Exam Ready", tone: "emerald" };
  if (score >= 75) return { grade: "A", remark: "Strong", tone: "teal" };
  if (score >= 65) return { grade: "B", remark: "On Track", tone: "indigo" };
  if (score >= 50) return { grade: "C", remark: "Developing", tone: "amber" };
  return { grade: "D", remark: "Needs Urgent Focus", tone: "rose" };
}

export function ReportCardPage() {
  const { user, activeSyllabus, setActiveTab } = useApp();
  const [analytics, setAnalytics] = useState<StudentAnalyticsOut | null>(null);
  const [parentInfo, setParentInfo] = useState<ParentDashboardOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeSyllabusId = activeSyllabus?.id;

  useEffect(() => {
    if (!activeSyllabusId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      api.getStudentAnalytics(activeSyllabusId),
      api.getParentDashboard(activeSyllabusId).catch(() => null),
    ])
      .then(([ana, pInfo]) => {
        if (!cancelled) {
          setAnalytics(ana);
          setParentInfo(pInfo);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load preparation report card.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSyllabusId]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Select or upload a syllabus to generate your Preparation Report Card.
      </Card>
    );
  }

  if (error) {
    return <AlertBanner tone="rose" title="Report Card Error" message={error} />;
  }

  if (loading || !analytics) {
    return (
      <Card className="p-8 text-center text-sm text-slate-500">
        Compiling Student Preparation Report Card...
      </Card>
    );
  }

  const pred = analytics.predictive_score;
  const overall = letterGrade(analytics.overall_mastery);
  const studentName = parentInfo?.student_name || user?.name || "Student";
  const streak = parentInfo?.study_streak ?? user?.student_profile?.study_streak ?? 0;
  const hours = parentInfo?.total_hours_logged ?? user?.student_profile?.total_hours_logged ?? 0;
  const blockers = parentInfo?.root_cause_blockers || [];

  const sortedSubjects = [...analytics.subject_breakdown].sort((a, b) => b.avg_mastery - a.avg_mastery);
  const strongSubjects = sortedSubjects.filter((s) => s.avg_mastery >= 65).slice(0, 3);
  const urgentTopics = [...analytics.weak_topics]
    .sort((a, b) => a.mastery_score - b.mastery_score)
    .slice(0, 5);
  const recentTests = analytics.recent_assessments.slice(0, 4);

  const nextSteps: string[] = [];
  if (blockers.length > 0) {
    nextSteps.push(`Clear prerequisite foundation gap first: ${blockers[0]}.`);
  }
  if (urgentTopics.length > 0) {
    nextSteps.push(
      `Revise weakest topic (${urgentTopics[0].topic_code}: ${urgentTopics[0].title} at ${urgentTopics[0].mastery_score.toFixed(0)}%) in AI Study Tutor and retake a short quiz.`,
    );
  }
  if (analytics.forgetting_alerts_count > 0) {
    nextSteps.push(
      `Complete spaced-repetition reviews for ${analytics.forgetting_alerts_count} topic(s) whose memory retention is fading.`,
    );
  }
  if (nextSteps.length === 0) {
    nextSteps.push("Maintain momentum with a weekly mixed test and scheduled spaced-repetition checkpoints.");
  }

  return (
    <div className="space-y-5">
      {/* Action Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Award className="h-5 w-5 text-indigo-600" />
            <span>Student Preparation Report Card</span>
          </h1>
          <p className="text-sm text-slate-600">
            Single-page snapshot of exam readiness, subject grades, strengths, and immediate focus areas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setActiveTab("analytics")}>
            View Full Charts
          </Button>
          <Button onClick={() => window.print()}>
            <Printer className="h-4 w-4" />
            <span>Print / Save PDF</span>
          </Button>
        </div>
      </div>

      {/* Main Report Card Sheet */}
      <Card className="space-y-6 border-2 border-slate-200 p-6 sm:p-8 print:border-none print:shadow-none">
        {/* Top Banner */}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="indigo">Official Preparation Snapshot</Badge>
              <Badge tone={overall.tone}>{pred.readiness_band}</Badge>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">{studentName}</h2>
            <p className="text-sm text-slate-600">
              <strong>{analytics.syllabus.title}</strong> ({analytics.syllabus.exam_name}) &middot; Target:{" "}
              <strong>
                {analytics.syllabus.target_score} / {analytics.syllabus.max_score}
              </strong>{" "}
              in <strong>{analytics.syllabus.days_remaining} days</strong>
            </p>
            <p className="text-xs text-slate-500">
              Generated on {new Date().toLocaleDateString()} &middot; Consistency: {streak}-day streak &middot;{" "}
              {hours} hrs logged
            </p>
          </div>

          <div className="flex items-center gap-4 rounded-2xl border border-indigo-200 bg-indigo-50/70 px-5 py-3">
            <div className="text-center">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-700">
                Overall Grade
              </div>
              <div className="text-4xl font-black text-indigo-900 tabular-nums">{overall.grade}</div>
            </div>
            <div className="h-12 w-px bg-indigo-200" />
            <div className="text-xs space-y-1 text-indigo-950">
              <div>
                <strong>Readiness:</strong> {pred.current_estimated_score} / {pred.max_score}
              </div>
              <div>
                <strong>Projected:</strong> {pred.projected_estimated_score} / {pred.max_score}
              </div>
              <div>
                <strong>Status:</strong> {overall.remark}
              </div>
            </div>
          </div>
        </div>

        {/* 4 At-a-Glance Summary Pills */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
              <TrendingUp className="h-3.5 w-3.5 text-indigo-600" />
              <span>Mean Mastery</span>
            </div>
            <div className="mt-1 text-xl font-bold text-slate-900 tabular-nums">
              {analytics.overall_mastery.toFixed(1)}%
            </div>
            <div className="text-[11px] text-slate-500">{analytics.coverage_percent}% syllabus started</div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
              <Target className="h-3.5 w-3.5 text-teal-600" />
              <span>Gap to Target</span>
            </div>
            <div className="mt-1 text-xl font-bold text-slate-900 tabular-nums">
              {pred.target_gap > 0 ? `${pred.target_gap} pts` : "Target Met"}
            </div>
            <div className="text-[11px] text-slate-500">Goal: {pred.target_score} / {pred.max_score}</div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
              <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
              <span>Weak / Fading Topics</span>
            </div>
            <div className="mt-1 text-xl font-bold text-slate-900 tabular-nums">
              {analytics.weak_topic_count} weak
            </div>
            <div className="text-[11px] text-slate-500">
              {analytics.forgetting_alerts_count} retention alert(s)
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
              <Flame className="h-3.5 w-3.5 text-amber-600" />
              <span>Study Habits</span>
            </div>
            <div className="mt-1 text-xl font-bold text-slate-900 tabular-nums">{streak} days</div>
            <div className="text-[11px] text-slate-500">{hours} total hours logged</div>
          </div>
        </div>

        {/* Subject-Wise Grade Sheet */}
        <div className="space-y-3">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-indigo-600" />
            <span>Subject-Wise Performance Sheet</span>
          </h3>
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr className="border-b border-slate-200">
                  <th className="px-4 py-2.5 font-semibold">Subject / Section</th>
                  <th className="px-4 py-2.5 font-semibold">Topics</th>
                  <th className="px-4 py-2.5 font-semibold">Mastery Progress</th>
                  <th className="px-4 py-2.5 font-semibold">Grade</th>
                  <th className="px-4 py-2.5 font-semibold">Standing</th>
                </tr>
              </thead>
              <tbody>
                {sortedSubjects.map((sub) => {
                  const g = letterGrade(sub.avg_mastery);
                  return (
                    <tr key={sub.subject} className="border-b border-slate-100 last:border-none">
                      <td className="px-4 py-2.5 font-semibold text-slate-900">{sub.subject}</td>
                      <td className="px-4 py-2.5 text-slate-600 tabular-nums">{sub.topic_count}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200">
                            <div
                              className={`h-full rounded-full ${
                                sub.avg_mastery >= 75
                                  ? "bg-emerald-500"
                                  : sub.avg_mastery >= 60
                                    ? "bg-amber-500"
                                    : "bg-rose-500"
                              }`}
                              style={{ width: `${Math.min(100, Math.max(4, sub.avg_mastery))}%` }}
                            />
                          </div>
                          <span className="font-semibold text-slate-800 tabular-nums">
                            {sub.avg_mastery.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge tone={g.tone}>{g.grade}</Badge>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{g.remark}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Strengths vs Immediate Attention */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-900 flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Key Strengths</span>
            </h3>
            {strongSubjects.length === 0 ? (
              <p className="text-xs text-emerald-900/80">
                No subject is above 65% yet—complete a diagnostic or topic quiz to build momentum.
              </p>
            ) : (
              <ul className="space-y-1.5 text-xs text-emerald-950">
                {strongSubjects.map((s) => (
                  <li key={s.subject} className="flex items-center justify-between">
                    <span className="font-medium">{s.subject}</span>
                    <span className="font-bold tabular-nums">{s.avg_mastery.toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-rose-900 flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-rose-600" />
              <span>Priority Focus Areas</span>
            </h3>
            {blockers.length > 0 && (
              <div className="rounded-lg bg-white/80 p-2 text-[11px] text-rose-900 border border-rose-200">
                <strong>Prerequisite Blockers:</strong> {blockers.slice(0, 3).join(" · ")}
              </div>
            )}
            {urgentTopics.length === 0 ? (
              <p className="text-xs text-rose-900/80">No weak topics currently below 60% mastery.</p>
            ) : (
              <ul className="space-y-1.5 text-xs text-rose-950">
                {urgentTopics.map((w) => (
                  <li key={w.topic_id} className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">
                      {w.topic_code}: {w.title}
                    </span>
                    <span className="shrink-0 font-bold tabular-nums">{w.mastery_score.toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Recent Tests + Action Plan */}
        <div className="grid gap-4 md:grid-cols-2 border-t border-slate-200 pt-5">
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Recent Assessments ({recentTests.length})
            </h3>
            {recentTests.length === 0 ? (
              <p className="text-xs text-slate-500">No completed tests yet for this syllabus.</p>
            ) : (
              <div className="space-y-1.5">
                {recentTests.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
                  >
                    <span className="truncate font-medium text-slate-800 pr-2">{t.title}</span>
                    <span className="shrink-0 font-bold text-indigo-700 tabular-nums">
                      {t.accuracy.toFixed(0)}% ({t.created_at.slice(0, 10)})
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Recommended Next Steps
            </h3>
            <ol className="list-decimal space-y-1.5 pl-4 text-xs leading-relaxed text-slate-700">
              {nextSteps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
        </div>
      </Card>
    </div>
  );
}
