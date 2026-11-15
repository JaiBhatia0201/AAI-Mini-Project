import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { ForgettingCurveOut, StudentAnalyticsOut } from "../types/api";
import { AlertBanner, Badge, Card } from "../components/ui/Primitives";

export function AnalyticsPage() {
  const { activeSyllabus } = useApp();
  const [analytics, setAnalytics] = useState<StudentAnalyticsOut | null>(null);
  const [forgetting, setForgetting] = useState<ForgettingCurveOut | null>(null);
  const [simDays, setSimDays] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSyllabus) return;
    Promise.all([
      api.getStudentAnalytics(activeSyllabus.id),
      api.getForgettingCurve(activeSyllabus.id, simDays),
    ])
      .then(([ana, fc]) => {
        setAnalytics(ana);
        setForgetting(fc);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics."));
  }, [activeSyllabus, simDays]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Select or upload a syllabus to view mastery charts and Ebbinghaus retention curves.
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-indigo-600" />
            <span>Progress Telemetry & Ebbinghaus Forgetting Curve</span>
          </h1>
          <p className="text-sm text-slate-600">
            Estimated score projections, subject breakdowns, and retention decay analysis for {activeSyllabus.title}.
          </p>
        </div>
        {analytics && (
          <Badge tone="indigo">
            Readiness Estimate: {analytics.predictive_score.current_estimated_score} /{" "}
            {analytics.predictive_score.max_score}
          </Badge>
        )}
      </div>

      {error && <AlertBanner tone="rose" title="Analytics Error" message={error} />}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Subject / Unit Mastery Breakdown (%)</h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics?.subject_breakdown || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="subject" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="avg_mastery" name="Avg Mastery %" fill="#4F46E5" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Assessment Score & Accuracy Trajectory</h2>
          <div className="h-64 w-full">
            {analytics && analytics.mastery_history.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.mastery_history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="accuracy"
                    name="Accuracy %"
                    stroke="#0D9488"
                    fill="#CCFBF1"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-500">
                Complete at least one quiz or diagnostic check to plot score progression.
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Ebbinghaus Curve Comparison */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Ebbinghaus 30-Day Retention Model</h2>
            <p className="text-xs text-slate-500">
              Compares unreinforced weak topics vs reinforced spaced-repetition stability (Avg S ={" "}
              {forgetting?.avg_stability_days || 4} days).
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-700">Preview Topic Decay at +{simDays}d:</span>
            <input
              type="range"
              min={0}
              max={30}
              step={1}
              value={simDays}
              onChange={(e) => setSimDays(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={forgetting?.curve_series || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="reinforced_retention"
                name="Reinforced (Day +3/+7/+14/+30)"
                stroke="#059669"
                strokeWidth={2.5}
              />
              <Line
                type="monotone"
                dataKey="baseline_retention"
                name="Baseline Topic"
                stroke="#4F46E5"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="weak_topic_retention"
                name="Weak Unreviewed Topic"
                stroke="#E11D48"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(forgetting?.topics || []).slice(0, 9).map((t) => (
            <div
              key={t.topic_id}
              className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <div className="truncate font-semibold text-slate-900">
                  {t.topic_code}: {t.title}
                </div>
                <div className="text-[11px] text-slate-500">
                  Mastery {t.mastery_score}% &middot; Reviews: {t.review_count}
                </div>
              </div>
              <Badge tone={t.at_risk ? "rose" : "teal"}>
                {(t.retention_score * 100).toFixed(0)}%
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
