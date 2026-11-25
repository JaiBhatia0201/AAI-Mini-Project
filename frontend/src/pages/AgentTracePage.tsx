import { useCallback, useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { TraceRecordOut } from "../types/api";
import { AlertBanner, Badge, Button, Card, FormattedText } from "../components/ui/Primitives";

export function AgentTracePage() {
  const { activeSyllabus, latestSimulation } = useApp();
  const [traces, setTraces] = useState<TraceRecordOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTraces = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const rows = await api.listTraces(activeSyllabus?.id);
      setTraces(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load agent execution logs.");
    } finally {
      setBusy(false);
    }
  }, [activeSyllabus?.id]);

  useEffect(() => {
    void loadTraces();
  }, [loadTraces]);

  const combinedTraces = latestSimulation
    ? [...latestSimulation.traces, ...traces]
    : traces;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-600" />
            <span>LangGraph Agent Execution Trace</span>
          </h1>
          <p className="text-sm text-slate-600">
            Auditable multi-agent pipeline telemetry across Agents 1-11 showing execution mode and latency.
          </p>
        </div>
        <Button variant="secondary" disabled={busy} onClick={() => void loadTraces()}>
          <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
          <span>Refresh Logs</span>
        </Button>
      </div>

      {error && <AlertBanner tone="rose" title="Trace Error" message={error} />}

      {combinedTraces.length === 0 ? (
        <Card className="p-8 text-center text-sm text-slate-500">
          No LangGraph execution logs recorded yet for this syllabus. Upload a PDF, run Tutor, or take a Quiz to trace all agents live!
        </Card>
      ) : (
        <div className="space-y-2.5">
          {combinedTraces.map((t, idx) => (
            <Card key={`${t.run_id}-${t.agent_number}-${idx}`} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="indigo">Agent {t.agent_number}</Badge>
                  <span className="text-sm font-bold text-slate-900">{t.agent_name}</span>
                  <span className="text-xs font-mono text-slate-500">{t.workflow_name}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Badge
                    tone={
                      t.execution_mode === "llm"
                        ? "indigo"
                        : t.execution_mode === "simulation"
                          ? "amber"
                          : t.execution_mode === "fallback"
                            ? "teal"
                            : "slate"
                    }
                  >
                    {t.execution_mode}
                  </Badge>
                  <span className="font-mono text-slate-500 tabular-nums">{t.latency_ms.toFixed(1)} ms</span>
                </div>
              </div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 text-xs text-slate-600">
                <div className="rounded bg-slate-50 p-2 border border-slate-100">
                  <span className="font-semibold text-slate-700">In:</span> {t.input_summary}
                </div>
                <div className="rounded bg-slate-50 p-2 border border-slate-100">
                  <span className="font-semibold text-slate-700">Out:</span>{" "}
                  <FormattedText text={t.output_summary} inline />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
