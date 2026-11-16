import { useState, type FormEvent } from "react";
import { CheckCircle2, FileUp, Sparkles, UploadCloud } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { LearningStyle, OnboardSyllabusResponse } from "../types/api";
import { AlertBanner, Badge, Button, Card } from "../components/ui/Primitives";

export function OnboardingPage() {
  const {
    user,
    pendingDiagnostic,
    setPendingDiagnostic,
    refreshWorkspace,
    setActiveTab,
  } = useApp();

  const [mode, setMode] = useState<"pdf_upload" | "seeded_gate">("pdf_upload");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [examName, setExamName] = useState("");
  const [targetScore, setTargetScore] = useState(80);
  const [maxScore, setMaxScore] = useState(100);
  const [daysRemaining, setDaysRemaining] = useState(60);
  const [dailyHours, setDailyHours] = useState(user?.student_profile?.daily_hours || 3);
  const [learningStyle, setLearningStyle] = useState<LearningStyle>(
    (user?.student_profile?.learning_style as LearningStyle) || "visual",
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagResult, setDiagResult] = useState<OnboardSyllabusResponse | null>(pendingDiagnostic);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [ratings, setRatings] = useState<Record<string, "strong" | "moderate" | "weak">>({});
  const [completionMsg, setCompletionMsg] = useState<string | null>(null);

  async function handleOnboard(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setCompletionMsg(null);
    if (mode === "pdf_upload" && !pdfFile) {
      setError("Please select a text-selectable syllabus PDF file first.");
      return;
    }

    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("onboard_mode", mode);
      if (title.trim()) fd.append("title", title.trim());
      if (examName.trim()) fd.append("exam_name", examName.trim());
      fd.append("target_score", String(targetScore));
      fd.append("max_score", String(maxScore));
      fd.append("days_remaining", String(daysRemaining));
      fd.append("daily_hours", String(dailyHours));
      fd.append("learning_style", learningStyle);
      if (mode === "pdf_upload" && pdfFile) {
        fd.append("file", pdfFile);
      }

      const res = await api.onboardSyllabus(fd);
      setDiagResult(res);
      setPendingDiagnostic(res);
      await refreshWorkspace(res.syllabus.id);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Syllabus onboarding failed. Ensure your PDF has selectable text.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCompleteDiagnostic(skipQuiz = false) {
    if (!diagResult) return;
    setError(null);
    setSubmitting(true);
    try {
      const submittedAnswers = skipQuiz
        ? []
        : diagResult.diagnostic_questions
            .filter((q) => Boolean(answers[q.id]))
            .map((q) => ({
              question_id: q.id,
              topic_id: q.topic_id,
              selected_answer: answers[q.id],
              time_taken_sec: 35,
            }));

      const done = await api.completeDiagnostic({
        syllabus_id: diagResult.syllabus.id,
        answers: submittedAnswers,
        self_ratings: ratings,
        daily_hours: dailyHours,
        learning_style: learningStyle,
        target_score: targetScore,
        days_remaining: daysRemaining,
      });
      setCompletionMsg(done.coaching_message || "Diagnostic calibrated and study plan generated.");
      setPendingDiagnostic(null);
      await refreshWorkspace(diagResult.syllabus.id);
      setActiveTab("dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to complete diagnostic calibration.");
    } finally {
      setSubmitting(false);
    }
  }

  if (diagResult) {
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Badge tone="teal">Step 2 of 2 · Baseline Calibration</Badge>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">
              Diagnostic Check: {diagResult.syllabus.title}
            </h2>
            <p className="text-sm text-slate-600">
              Extracted <strong>{diagResult.topics_count}</strong> topics and{" "}
              <strong>{diagResult.prerequisites_count}</strong> prerequisite links. Answer these diagnostic items to calibrate initial mastery priors.
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={submitting}
            onClick={() => void handleCompleteDiagnostic(true)}
          >
            Skip Quiz & Use Baseline Priors
          </Button>
        </div>

        {error && <AlertBanner tone="rose" title="Error" message={error} />}
        {completionMsg && <AlertBanner tone="teal" title="Calibrated" message={completionMsg} />}

        <div className="space-y-4">
          {diagResult.diagnostic_questions.slice(0, 8).map((q, idx) => (
            <Card key={q.id} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-indigo-700">Q{idx + 1}</span>
                  <Badge tone="slate">{q.difficulty}</Badge>
                  <Badge tone={q.source_origin === "extracted_pdf_excerpt" ? "teal" : "slate"}>
                    {q.subtopic || "Core Concept"}
                  </Badge>
                </div>
                <select
                  aria-label="Topic familiarity"
                  value={ratings[q.topic_id] || "moderate"}
                  onChange={(e) =>
                    setRatings((prev) => ({
                      ...prev,
                      [q.topic_id]: e.target.value as "strong" | "moderate" | "weak",
                    }))
                  }
                  className="rounded-md border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700"
                >
                  <option value="weak">Self-rating: Weak</option>
                  <option value="moderate">Self-rating: Moderate</option>
                  <option value="strong">Self-rating: Strong</option>
                </select>
              </div>
              <p className="text-sm font-medium text-slate-900">{q.prompt}</p>
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
        </div>

        <div className="flex items-center justify-end gap-3">
          <Button variant="secondary" onClick={() => setDiagResult(null)}>
            Back to Syllabus Upload
          </Button>
          <Button disabled={submitting} onClick={() => void handleCompleteDiagnostic(false)}>
            <CheckCircle2 className="h-4 w-4" />
            <span>{submitting ? "Calibrating Plan..." : "Finish Calibration & Build Plan"}</span>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <Badge tone="indigo">Step 1 of 2 · Syllabus Ingestion (Agent 2 + 3 + 4 + 6)</Badge>
        <h2 className="mt-1 text-2xl font-bold text-slate-900">Onboard a Custom Syllabus or Exam</h2>
        <p className="text-sm text-slate-600">
          Upload any text-selectable course or competitive exam PDF to build an isolated Knowledge Graph, study roadmap, notes, and diagnostic quiz—or clone an isolated GATE CSE workspace.
        </p>
      </div>

      {error && <AlertBanner tone="rose" title="Onboarding Error" message={error} />}

      <Card>
        <div className="mb-5 grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMode("pdf_upload")}
            className={`flex items-start gap-3 rounded-xl border p-4 text-left cursor-pointer transition ${
              mode === "pdf_upload"
                ? "border-indigo-600 bg-indigo-50/70"
                : "border-slate-200 hover:bg-slate-50"
            }`}
          >
            <UploadCloud className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold text-slate-900">Upload Your Own Syllabus PDF</div>
              <div className="text-xs text-slate-600">
                Works for any course, university midsem, certification, or competitive exam. Scanned image-only PDFs are rejected clearly.
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setMode("seeded_gate")}
            className={`flex items-start gap-3 rounded-xl border p-4 text-left cursor-pointer transition ${
              mode === "seeded_gate"
                ? "border-teal-600 bg-teal-50/70"
                : "border-slate-200 hover:bg-slate-50"
            }`}
          >
            <Sparkles className="h-5 w-5 text-teal-600 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold text-slate-900">Clone Isolated GATE CSE Workspace</div>
              <div className="text-xs text-slate-600">
                Provision the full curated 22-topic GATE CSE curriculum & question bank strictly inside your own account.
              </div>
            </div>
          </button>
        </div>

        <form onSubmit={(e) => void handleOnboard(e)} className="space-y-4">
          {mode === "pdf_upload" && (
            <div className="rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center">
              <FileUp className="mx-auto h-8 w-8 text-indigo-600" />
              <p className="mt-2 text-sm font-semibold text-slate-800">
                {pdfFile ? pdfFile.name : "Select a text-selectable syllabus PDF"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Must contain extractable text (&ge; 50 chars/page)
              </p>
              <label className="mt-3 inline-block cursor-pointer rounded-lg border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100">
                <span>Browse PDF File</span>
                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                />
              </label>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Syllabus Title {mode === "seeded_gate" && "(Optional)"}
              </label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={mode === "pdf_upload" ? "e.g., Sem 7 Distributed Systems" : "GATE CSE Workspace"}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Exam / Course Name</label>
              <input
                value={examName}
                onChange={(e) => setExamName(e.target.value)}
                placeholder={mode === "pdf_upload" ? "e.g., CS-701 Endsem" : "GATE CSE"}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Target Score</label>
              <input
                type="number"
                min={1}
                value={targetScore}
                onChange={(e) => setTargetScore(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Exam Max Score</label>
              <input
                type="number"
                min={10}
                value={maxScore}
                onChange={(e) => setMaxScore(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Days Remaining</label>
              <input
                type="number"
                min={7}
                max={365}
                value={daysRemaining}
                onChange={(e) => setDaysRemaining(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Daily Study Hours</label>
              <input
                type="number"
                step="0.5"
                min={0.5}
                max={16}
                value={dailyHours}
                onChange={(e) => setDailyHours(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Preferred Learning Style</label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["visual", "reading", "practice", "mixed"] as LearningStyle[]).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setLearningStyle(st)}
                  className={`rounded-lg border px-3 py-2 text-xs font-semibold capitalize cursor-pointer ${
                    learningStyle === st
                      ? "border-indigo-600 bg-indigo-50 text-indigo-800"
                      : "border-slate-200 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Running Agents 1 -> 2 -> 3 -> 4 -> 6..." : "Build Knowledge Graph & Diagnostic"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
