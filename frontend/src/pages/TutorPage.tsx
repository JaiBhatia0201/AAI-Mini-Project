import { useEffect, useState, type FormEvent } from "react";
import { BookMarked, Lightbulb, MessageSquareText, RotateCw, Send } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { TutorLessonResponse } from "../types/api";
import { AlertBanner, Badge, Button, Card, ProvenanceBadge } from "../components/ui/Primitives";

export function TutorPage() {
  const { user, activeSyllabus, activeGraph } = useApp();
  const topics = activeGraph?.topics || [];
  const [topicId, setTopicId] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [lesson, setLesson] = useState<TutorLessonResponse | null>(null);
  const [flippedCard, setFlippedCard] = useState<number | null>(null);
  const [selectedOpts, setSelectedOpts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (topics.length > 0 && !topics.some((t) => t.id === topicId)) {
      const weakFirst = topics.find((t) => t.mastery_score < 60) || topics[0];
      setTopicId(weakFirst.id);
      setLesson(null);
    }
  }, [topics, topicId]);

  if (!activeSyllabus || topics.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-slate-600">
        Upload or select an active syllabus first to launch the AI Study Tutor.
      </Card>
    );
  }

  async function requestLesson(e?: FormEvent) {
    e?.preventDefault();
    if (!activeSyllabus || !topicId) return;
    setBusy(true);
    setError(null);
    setFlippedCard(null);
    try {
      const res = await api.askTutor({
        syllabus_id: activeSyllabus.id,
        topic_id: topicId,
        question: question.trim() || undefined,
      });
      setLesson(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tutor could not generate lesson.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <MessageSquareText className="h-5 w-5 text-indigo-600" />
            <span>AI Study Assistant (Agent 5)</span>
          </h1>
          <p className="text-sm text-slate-600">
            Tailored to your <strong>{user?.student_profile?.learning_style || "visual"}</strong> learning preference with explicit source provenance.
          </p>
        </div>
        {lesson && (
          <div className="flex items-center gap-2">
            <ProvenanceBadge origin={lesson.source_origin} />
            <Badge tone="slate">{lesson.confidence_status}</Badge>
          </div>
        )}
      </div>

      {error && <AlertBanner tone="rose" title="Tutor Error" message={error} />}

      <Card>
        <form onSubmit={(e) => void requestLesson(e)} className="grid gap-3 md:grid-cols-12 md:items-end">
          <div className="md:col-span-5">
            <label className="mb-1 block text-xs font-semibold text-slate-700">Topic to Study</label>
            <select
              value={topicId}
              onChange={(e) => setTopicId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.topic_code}: {t.title} ({Math.round(t.mastery_score)}%)
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-5">
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Ask a Follow-up Doubt (Optional)
            </label>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g., Give me a concrete step-by-step example"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={busy || user?.role !== "student"} className="w-full">
              <Send className="h-4 w-4" />
              <span>{busy ? "Thinking..." : "Teach Me"}</span>
            </Button>
          </div>
        </form>
      </Card>

      {lesson ? (
        <div className="grid gap-5 lg:grid-cols-12">
          <div className="lg:col-span-8 space-y-5">
            <Card className="space-y-4">
              {lesson.prerequisite_path.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="font-semibold text-slate-500">Prerequisites:</span>
                  {lesson.prerequisite_path.map((p) => (
                    <Badge key={p} tone="indigo">
                      {p}
                    </Badge>
                  ))}
                </div>
              )}

              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <BookMarked className="h-4 w-4 text-indigo-600" />
                  <span>Structured Lesson</span>
                </h2>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700">
                  {lesson.explanation}
                </p>
              </div>

              <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-4">
                <div className="flex items-center gap-2 text-xs font-bold text-teal-900">
                  <Lightbulb className="h-4 w-4 text-teal-600" />
                  <span>Real-World Intuition & Analogy</span>
                </div>
                <p className="mt-1 text-sm text-teal-950">{lesson.analogy}</p>
              </div>
            </Card>

            {lesson.practice_questions.length > 0 && (
              <Card className="space-y-3">
                <h3 className="text-base font-bold text-slate-900">Quick Concept Check (Agent 6)</h3>
                {lesson.practice_questions.slice(0, 3).map((q, idx) => (
                  <div key={q.id} className="rounded-lg border border-slate-200 p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge tone="slate">Q{idx + 1} · {q.difficulty}</Badge>
                      <ProvenanceBadge origin={q.source_origin} />
                    </div>
                    <p className="text-sm font-medium text-slate-900">{q.prompt}</p>
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      {q.options.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => setSelectedOpts((prev) => ({ ...prev, [q.id]: opt }))}
                          className={`rounded-md border px-2.5 py-1.5 text-left text-xs cursor-pointer ${
                            selectedOpts[q.id] === opt
                              ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-900"
                              : "border-slate-200 hover:bg-slate-50"
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </Card>
            )}
          </div>

          <Card className="lg:col-span-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">Interactive Flashcards</h3>
              <Badge tone="slate">{lesson.flashcards.length} Cards</Badge>
            </div>
            <p className="text-xs text-slate-500">Click any card to flip between prompt and answer.</p>
            <div className="space-y-2.5">
              {lesson.flashcards.map((card, i) => {
                const isFlipped = flippedCard === i;
                return (
                  <button
                    key={`${card.front}-${i}`}
                    type="button"
                    onClick={() => setFlippedCard(isFlipped ? null : i)}
                    className={`w-full rounded-xl border p-4 text-left transition cursor-pointer ${
                      isFlipped
                        ? "border-indigo-500 bg-indigo-50/70"
                        : "border-slate-200 bg-slate-50 hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      <span>{isFlipped ? "Answer" : "Concept Prompt"}</span>
                      <RotateCw className="h-3.5 w-3.5" />
                    </div>
                    <p className="mt-2 text-xs font-medium text-slate-900">
                      {isFlipped ? card.back : card.front}
                    </p>
                  </button>
                );
              })}
            </div>
          </Card>
        </div>
      ) : (
        <Card className="p-8 text-center text-sm text-slate-500">
          Pick a topic above and click <strong>Teach Me</strong> to synthesize a personalized lesson grounded in your syllabus material.
        </Card>
      )}
    </div>
  );
}
