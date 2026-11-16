import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ClipboardCheck, Clock, Play, XCircle } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type {
  AssessmentHistoryOut,
  AssessmentStartResponse,
  AssessmentSubmitResponse,
  AssessmentType,
} from "../types/api";
import { AlertBanner, Badge, Button, Card, ProvenanceBadge } from "../components/ui/Primitives";

export function AssessmentPage() {
  const { user, activeSyllabus, activeGraph, refreshWorkspace } = useApp();
  const topics = activeGraph?.topics || [];

  const [assessmentType, setAssessmentType] = useState<AssessmentType>("topic_quiz");
  const [topicId, setTopicId] = useState<string>("");
  const [questionCount, setQuestionCount] = useState<number>(4);

  const [activeQuiz, setActiveQuiz] = useState<AssessmentStartResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<AssessmentSubmitResponse | null>(null);
  const [startedAtMs, setStartedAtMs] = useState<number>(Date.now());
  const [history, setHistory] = useState<AssessmentHistoryOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeSyllabusId = activeSyllabus?.id;

  const loadHistory = useCallback(async () => {
    if (!activeSyllabusId) return;
    try {
      const rows = await api.assessmentHistory(activeSyllabusId);
      setHistory(rows);
    } catch {
      // ignore initial history load error
    }
  }, [activeSyllabusId]);

  useEffect(() => {
    setActiveQuiz(null);
    setQuizResult(null);
    void loadHistory();
  }, [loadHistory]);

  if (!activeSyllabus) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Select or upload a syllabus first to take calibrated quizzes and exams.
      </Card>
    );
  }

  async function handleStartQuiz() {
    if (!activeSyllabus) return;
    setBusy(true);
    setError(null);
    setQuizResult(null);
    setAnswers({});
    try {
      const res = await api.startAssessment({
        syllabus_id: activeSyllabus.id,
        topic_id: assessmentType === "topic_quiz" && topicId ? topicId : undefined,
        assessment_type: assessmentType,
        question_count: questionCount,
      });
      setActiveQuiz(res);
      setStartedAtMs(Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start assessment.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitQuiz() {
    if (!activeQuiz || !activeSyllabus) return;
    setBusy(true);
    setError(null);
    const elapsedPerQ = Math.max(
      10,
      Math.round((Date.now() - startedAtMs) / 1000 / Math.max(1, activeQuiz.questions.length)),
    );
    try {
      const payload = activeQuiz.questions.map((q) => ({
        question_id: q.id,
        selected_answer: answers[q.id] || "",
        time_taken_sec: elapsedPerQ,
      }));
      const res = await api.submitAssessment(activeQuiz.assessment_id, payload);
      setQuizResult(res);
      setActiveQuiz(null);
      await loadHistory();
      await refreshWorkspace(activeSyllabus.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit assessment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-indigo-600" />
          <span>Practice Quizzes & Adaptive Exams</span>
        </h1>
        <p className="text-sm text-slate-600">
          Submitting triggers the closed loop: <strong>Agent 7 (Grader) &rarr; Agent 8 (Weakness &amp; Blockers) &rarr; Agent 9 (Re-Plan) &rarr; Agent 10 (Coaching)</strong>.
        </p>
      </div>

      {error && <AlertBanner tone="rose" title="Assessment Error" message={error} />}

      {!activeQuiz && user?.role === "student" && (
        <Card className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Configure New Assessment</h2>
          <div className="grid gap-3 md:grid-cols-4 md:items-end">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Assessment Mode</label>
              <select
                value={assessmentType}
                onChange={(e) => setAssessmentType(e.target.value as AssessmentType)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="topic_quiz">Topic Mastery Quiz</option>
                <option value="weekly_test">Weekly Comprehensive Test</option>
                <option value="mock_exam">Full Exam Mock</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Target Topic</label>
              <select
                disabled={assessmentType !== "topic_quiz"}
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:bg-slate-100"
              >
                <option value="">All Weak / Active Topics</option>
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.topic_code}: {t.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Questions</label>
              <select
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                {[3, 5, 8, 12, 20].map((c) => (
                  <option key={c} value={c}>
                    {c} Questions
                  </option>
                ))}
              </select>
            </div>
            <Button disabled={busy} onClick={() => void handleStartQuiz()}>
              <Play className="h-4 w-4" />
              <span>{busy ? "Staging Quiz..." : "Start Assessment"}</span>
            </Button>
          </div>
        </Card>
      )}

      {activeQuiz && (
        <div className="space-y-4">
          <AlertBanner
            tone="indigo"
            title={activeQuiz.title}
            message={`Answer ${activeQuiz.questions.length} calibrated MCQs below and submit to trigger live adaptive re-planning.`}
            action={<Clock className="h-4 w-4 text-indigo-700" />}
          />
          {activeQuiz.questions.map((q, idx) => (
            <Card key={q.id} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge tone="indigo">Question {idx + 1}</Badge>
                  <Badge tone="slate">{q.difficulty}</Badge>
                  <span className="text-xs text-slate-500">Est. {q.expected_time_sec}s</span>
                </div>
                <ProvenanceBadge origin={q.source_origin} />
              </div>
              <p className="text-sm font-semibold text-slate-900">{q.prompt}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                    className={`rounded-lg border px-3 py-2 text-left text-xs transition cursor-pointer ${
                      answers[q.id] === opt
                        ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-900"
                        : "border-slate-200 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </Card>
          ))}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setActiveQuiz(null)}>
              Cancel Quiz
            </Button>
            <Button disabled={busy} onClick={() => void handleSubmitQuiz()}>
              {busy ? "Evaluating Agents 7 -> 10..." : "Submit & Run Adaptive Loop"}
            </Button>
          </div>
        </div>
      )}

      {quizResult && (
        <Card className="border-indigo-300 bg-indigo-50/30 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <Badge tone={quizResult.accuracy >= 70 ? "emerald" : "rose"}>
                Score: {quizResult.score} / {quizResult.max_score} ({quizResult.accuracy.toFixed(1)}%)
              </Badge>
              <h2 className="mt-1 text-lg font-bold text-slate-900">Adaptive Assessment Breakdown</h2>
            </div>
            {quizResult.root_cause_blockers.length > 0 && (
              <Badge tone="rose">Root Blockers Caught: {quizResult.root_cause_blockers.length}</Badge>
            )}
          </div>

          <AlertBanner tone="teal" title="Agent 10 Coaching" message={quizResult.coaching_message} />

          {quizResult.adaptation && (
            <div className="rounded-xl border border-indigo-200 bg-white p-4 space-y-2 text-xs">
              <div className="font-bold text-indigo-950">{quizResult.adaptation.summary}</div>
              {quizResult.adaptation.changes.slice(0, 6).map((ch, idx) => (
                <div key={`${ch.topic_id}-${idx}`} className="text-slate-700">
                  &bull; <strong>+{ch.day_offset}d {ch.task_type}</strong>: {ch.reason}
                </div>
              ))}
            </div>
          )}

          <div className="space-y-2">
            {quizResult.results.map((r, i) => (
              <div
                key={r.question_id}
                className="flex items-start gap-2.5 rounded-lg border border-slate-200 bg-white p-3 text-xs"
              >
                {r.is_correct ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="font-semibold text-slate-900">
                    Q{i + 1}: Your answer &ldquo;{r.selected_answer || "Unanswered"}&rdquo;{" "}
                    {!r.is_correct && `(Correct: "${r.correct_answer}")`}
                  </div>
                  <p className="mt-0.5 text-slate-600">{r.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Historical Assessments */}
      <Card className="space-y-3">
        <h2 className="text-sm font-bold text-slate-900">Completed Assessment History ({history.length})</h2>
        {history.length === 0 ? (
          <p className="text-xs text-slate-500">No graded assessments yet for this syllabus.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-2 pr-3 font-semibold">Assessment</th>
                  <th className="py-2 pr-3 font-semibold">Type</th>
                  <th className="py-2 pr-3 font-semibold">Score</th>
                  <th className="py-2 pr-3 font-semibold">Accuracy</th>
                  <th className="py-2 font-semibold">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((a) => (
                  <tr key={a.id} className="border-b border-slate-100 last:border-none">
                    <td className="py-2 pr-3 font-medium text-slate-900">{a.title}</td>
                    <td className="py-2 pr-3 capitalize text-slate-600">{a.assessment_type.replace("_", " ")}</td>
                    <td className="py-2 pr-3 tabular-nums font-semibold">
                      {a.score} / {a.max_score}
                    </td>
                    <td className="py-2 pr-3 tabular-nums">{a.accuracy.toFixed(1)}%</td>
                    <td className="py-2 text-slate-500">{a.created_at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
