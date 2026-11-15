import { useState, type FormEvent } from "react";
import { BookOpenCheck, ShieldCheck, Sparkles, UserPlus, Users } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { DemoPersona, UserRole } from "../types/api";
import { AlertBanner, Badge, Button, Card } from "../components/ui/Primitives";

type AuthMode = "register" | "login";

const DEMO_CARDS: Array<{
  persona: DemoPersona;
  label: string;
  sub: string;
}> = [
  { persona: "aarav", label: "Aarav (GATE CSE Flagship)", sub: "Mid-prep student w/ weak CN/OS blockers" },
  { persona: "priya", label: "Priya (High Performer)", sub: "82+ mastery across core GATE topics" },
  { persona: "rohan", label: "Rohan (Struggling / Reset)", sub: "Multiple decay & prerequisite gaps" },
  { persona: "parent", label: "Kavita (Parent Read-Only)", sub: "Linked guardian analytics portal" },
];

export function AuthPage() {
  const { onAuthenticated, health } = useApp();
  const [mode, setMode] = useState<AuthMode>("register");
  const [role, setRole] = useState<UserRole>("student");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [linkCode, setLinkCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res =
        mode === "register"
          ? await api.register({
              name: name.trim(),
              email: email.trim(),
              password,
              role,
              link_code: role === "parent_teacher" ? linkCode.trim() : undefined,
            })
          : await api.login({ email: email.trim(), password });
      await onAuthenticated(res.access_token, res.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed. Check your inputs.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDemo(persona: DemoPersona) {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.demoLogin(persona);
      await onAuthenticated(res.access_token, res.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load demo persona.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-teal-50/40 px-4 py-10">
      <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-12 lg:items-start">
        <div className="space-y-6 lg:col-span-5">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-xs font-semibold text-indigo-700 shadow-2xs">
            <Sparkles className="h-3.5 w-3.5" />
            <span>PS-03 Adaptive Exam Prep & Multi-Agent Tutor</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Study Any Syllabus with an 11-Agent AI Roadmap.
          </h1>
          <p className="text-sm leading-relaxed text-slate-600">
            Create your own student account to upload any text-selectable course or exam syllabus PDF, build a live prerequisite Knowledge Graph, detect hidden root-cause blockers, and keep memory sharp with Ebbinghaus spaced repetition.
          </p>

          <div className="space-y-3 rounded-xl border border-slate-200 bg-white/90 p-4 text-xs text-slate-600">
            <div className="flex items-center gap-2 font-semibold text-slate-800">
              <BookOpenCheck className="h-4 w-4 text-indigo-600" />
              <span>Works for Any Student & Any Exam</span>
            </div>
            <p>
              New accounts start with a clean workspace: upload your own university, competitive exam, or certification PDF—or clone a fresh isolated GATE CSE workspace anytime.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge tone="indigo">LangGraph 11-Agent Pipeline</Badge>
              <Badge tone="teal">
                {health?.llm_mode === "llm" ? "LLM Mode Active" : "Deterministic + TF-IDF Offline Ready"}
              </Badge>
            </div>
          </div>

          <Card className="bg-white/90">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Or Try Seeded Demo Personas
              </span>
              <Badge tone="slate">Optional</Badge>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
              {DEMO_CARDS.map((item) => (
                <button
                  key={item.persona}
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleDemo(item.persona)}
                  className="flex flex-col items-start rounded-lg border border-slate-200 px-3 py-2 text-left transition hover:border-indigo-300 hover:bg-indigo-50/40 cursor-pointer disabled:opacity-50"
                >
                  <span className="text-xs font-semibold text-slate-900">{item.label}</span>
                  <span className="text-[11px] text-slate-500">{item.sub}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <Card className="lg:col-span-7 p-6 sm:p-8">
          <div className="mb-6 flex rounded-lg border border-slate-200 bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={`flex-1 rounded-md py-2 text-sm font-semibold transition cursor-pointer ${
                mode === "register" ? "bg-white text-indigo-700 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Create Brand-New Account
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`flex-1 rounded-md py-2 text-sm font-semibold transition cursor-pointer ${
                mode === "login" ? "bg-white text-indigo-700 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Sign In
            </button>
          </div>

          {error && (
            <div className="mb-4">
              <AlertBanner tone="rose" title="Authentication Error" message={error} />
            </div>
          )}

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            {mode === "register" && (
              <>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-slate-700">Account Role</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setRole("student")}
                      className={`flex items-center gap-2 rounded-lg border p-3 text-left text-sm cursor-pointer ${
                        role === "student"
                          ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <UserPlus className="h-4 w-4 shrink-0" />
                      <div>
                        <div className="font-semibold">Student</div>
                        <div className="text-[11px] opacity-80">Upload PDFs & study</div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setRole("parent_teacher")}
                      className={`flex items-center gap-2 rounded-lg border p-3 text-left text-sm cursor-pointer ${
                        role === "parent_teacher"
                          ? "border-teal-600 bg-teal-50 text-teal-900"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <Users className="h-4 w-4 shrink-0" />
                      <div>
                        <div className="font-semibold">Parent / Teacher</div>
                        <div className="text-[11px] opacity-80">Read-only monitor</div>
                      </div>
                    </button>
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Full Name</label>
                  <input
                    required
                    minLength={2}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Riya Sharma"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </>
            )}

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@university.edu"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Password <span className="font-normal text-slate-400">(min 6 chars)</span>
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>

            {mode === "register" && role === "parent_teacher" && (
              <div className="rounded-lg border border-teal-200 bg-teal-50/60 p-3">
                <label className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-teal-900">
                  <ShieldCheck className="h-4 w-4" />
                  <span>Student Invite Link Code</span>
                </label>
                <input
                  required
                  value={linkCode}
                  onChange={(e) => setLinkCode(e.target.value)}
                  placeholder="e.g., PREP-RIYA-4821"
                  className="w-full rounded-lg border border-teal-300 bg-white px-3 py-2 text-sm font-mono focus:border-teal-600 focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-teal-800">
                  Ask the student to share the Link Code shown in their top bar after signing up.
                </p>
              </div>
            )}

            <Button type="submit" disabled={submitting} className="w-full py-2.5">
              {submitting
                ? "Please wait..."
                : mode === "register"
                  ? "Create Account & Launch Workspace"
                  : "Sign In"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
