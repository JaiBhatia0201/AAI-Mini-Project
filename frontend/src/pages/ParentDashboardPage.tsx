import { useEffect, useState } from "react";
import { AlertTriangle, BookOpenCheck, Flame, ShieldCheck, TrendingUp } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { ParentDashboardOut } from "../types/api";
import { AlertBanner, Badge, Card, StatCard } from "../components/ui/Primitives";

export function ParentDashboardPage() {
  const { activeSyllabus } = useApp();
  const [data, setData] = useState<ParentDashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getParentDashboard(activeSyllabus?.id)
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Unable to load guardian dashboard."),
      );
  }, [activeSyllabus?.id]);

  if (error) {
    return <AlertBanner tone="rose" title="Access Error" message={error} />;
  }

  if (!data) {
    return <Card className="p-8 text-center text-sm text-slate-500">Loading parent/teacher analytics...</Card>;
  }

  const pred = data.predictive_score;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge tone="teal">Read-Only Analytics View</Badge>
            <Badge tone="slate">Link Code: {data.link_code}</Badge>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            Student Progress Report: {data.student_name}
          </h1>
          <p className="text-sm text-slate-600">
            Tracking <strong>{data.syllabus.title}</strong> ({data.syllabus.exam_name}) &middot; {data.student_email}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">
          <ShieldCheck className="h-4 w-4" />
          <span>{pred.readiness_band} Readiness</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          tone="indigo"
          label="Estimated Readiness Score"
          value={`${pred.current_estimated_score} / ${pred.max_score}`}
          hint={`Projected: ${pred.projected_estimated_score} · Target Gap: ${pred.target_gap}`}
          icon={<TrendingUp className="h-4 w-4 text-indigo-600" />}
        />
        <StatCard
          tone="teal"
          label="Syllabus Coverage & Mastery"
          value={`${data.coverage_percent}%`}
          hint={`Mean topic mastery: ${data.overall_mastery.toFixed(1)}%`}
          icon={<BookOpenCheck className="h-4 w-4 text-teal-600" />}
        />
        <StatCard
          tone="amber"
          label="Study Consistency"
          value={`${data.study_streak} days`}
          hint={`${data.total_hours_logged} total hours logged`}
          icon={<Flame className="h-4 w-4 text-amber-600" />}
        />
        <StatCard
          tone="rose"
          label="Weak Topics Flagged"
          value={data.weak_topics.length}
          hint={`${data.root_cause_blockers.length} upstream prerequisite blocker(s)`}
          icon={<AlertTriangle className="h-4 w-4 text-rose-600" />}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-12">
        <Card className="lg:col-span-6 space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Attention Needed: Weak Topics & Blockers</h2>
          {data.root_cause_blockers.length > 0 && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs space-y-1">
              <div className="font-bold text-rose-900">Root-Cause Prerequisite Blockers</div>
              {data.root_cause_blockers.map((b) => (
                <div key={b} className="text-rose-800">&bull; {b}</div>
              ))}
            </div>
          )}
          {data.weak_topics.length === 0 ? (
            <p className="text-xs text-slate-500">No topics currently flagged below 60% mastery.</p>
          ) : (
            <div className="space-y-2">
              {data.weak_topics.map((w) => (
                <div
                  key={w.topic_id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs"
                >
                  <span className="font-medium text-slate-900">
                    {w.topic_code}: {w.title}
                  </span>
                  <Badge tone="rose">{w.mastery_score.toFixed(1)}%</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="lg:col-span-6 space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Assessment Progression Trend</h2>
          <div className="h-64 w-full">
            {data.weekly_progression.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.weekly_progression}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="accuracy" name="Accuracy %" stroke="#4F46E5" strokeWidth={2.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-500">
                No graded tests completed yet for this syllabus.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
