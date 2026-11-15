import type {
  AdaptationDiffOut,
  AssessmentHistoryOut,
  AssessmentStartResponse,
  AssessmentSubmitResponse,
  AssessmentType,
  DailyCheckResponse,
  DemoPersona,
  DiagnosticCompleteResponse,
  ForgettingCurveOut,
  HealthStatus,
  LearningResourceOut,
  LearningStyle,
  OnboardSyllabusResponse,
  ParentDashboardOut,
  PlannerOverviewOut,
  QuestionOut,
  ResourceDiscoverResponse,
  StudentAnalyticsOut,
  StudentProfileOut,
  StudyPlanItemOut,
  SyllabusGraphOut,
  SyllabusOut,
  TokenResponse,
  TraceRecordOut,
  TutorLessonResponse,
  UserOut,
  UserRole,
} from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const TOKEN_KEY = "adaptive_prep_jwt";

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isMultipart = false,
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!isMultipart && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const parsed = await res.json();
      if (typeof parsed?.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed?.detail) && parsed.detail[0]?.msg) {
        detail = parsed.detail[0].msg;
      }
    } catch {
      // keep generic fallback message
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),

  register: (payload: {
    name: string;
    email: string;
    password: string;
    role: UserRole;
    link_code?: string;
  }) =>
    request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  demoLogin: (persona: DemoPersona) =>
    request<TokenResponse>("/api/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ persona }),
    }),

  me: () => request<UserOut>("/api/auth/me"),

  getProfile: () => request<StudentProfileOut>("/api/students/profile"),

  updateProfile: (payload: {
    current_grade?: string;
    daily_hours?: number;
    learning_style?: LearningStyle;
  }) =>
    request<StudentProfileOut>("/api/students/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  listSyllabi: () => request<SyllabusOut[]>("/api/syllabi"),

  activateSyllabus: (syllabusId: string) =>
    request<SyllabusOut>(`/api/syllabi/${syllabusId}/activate`, { method: "POST" }),

  getSyllabusGraph: (syllabusId: string) =>
    request<SyllabusGraphOut>(`/api/syllabi/${syllabusId}/graph`),

  patchPrerequisites: (
    syllabusId: string,
    updates: Array<{
      prerequisite_topic_id: string;
      dependent_topic_id: string;
      action: "confirm" | "remove" | "add";
    }>,
  ) =>
    request<SyllabusGraphOut>(`/api/syllabi/${syllabusId}/prerequisites`, {
      method: "PATCH",
      body: JSON.stringify({ updates }),
    }),

  onboardSyllabus: (formData: FormData) =>
    request<OnboardSyllabusResponse>(
      "/api/workflows/onboard-syllabus",
      { method: "POST", body: formData },
      true,
    ),

  completeDiagnostic: (payload: {
    syllabus_id: string;
    answers: Array<{ question_id: string; topic_id?: string; selected_answer: string; time_taken_sec: number }>;
    self_ratings: Record<string, "strong" | "moderate" | "weak">;
    daily_hours?: number;
    learning_style?: LearningStyle;
    target_score?: number;
    days_remaining?: number;
  }) =>
    request<DiagnosticCompleteResponse>("/api/workflows/complete-diagnostic", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPlanner: (syllabusId?: string) =>
    request<PlannerOverviewOut>(
      `/api/planner${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
    ),

  adaptPlanner: (syllabusId?: string) =>
    request<AdaptationDiffOut | null>(
      `/api/planner/adapt${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
      { method: "POST" },
    ),

  togglePlanItemStatus: (itemId: string, status: "pending" | "completed") =>
    request<StudyPlanItemOut>(`/api/planner/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  listResources: (syllabusId: string, topicId?: string, modality?: string) => {
    const params = new URLSearchParams({ syllabus_id: syllabusId });
    if (topicId) params.set("topic_id", topicId);
    if (modality) params.set("modality", modality);
    return request<LearningResourceOut[]>(`/api/resources?${params.toString()}`);
  },

  discoverResources: (payload: {
    syllabus_id: string;
    topic_id?: string;
    query: string;
    top_k?: number;
  }) =>
    request<ResourceDiscoverResponse>("/api/resources/discover", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  askTutor: (payload: { syllabus_id: string; topic_id: string; question?: string }) =>
    request<TutorLessonResponse>("/api/tutor/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listQuestions: (syllabusId: string, topicId?: string) => {
    const params = new URLSearchParams({ syllabus_id: syllabusId });
    if (topicId) params.set("topic_id", topicId);
    return request<QuestionOut[]>(`/api/questions?${params.toString()}`);
  },

  startAssessment: (payload: {
    syllabus_id: string;
    topic_id?: string;
    assessment_type: AssessmentType;
    question_count: number;
  }) =>
    request<AssessmentStartResponse>("/api/assessments/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  submitAssessment: (
    assessmentId: string,
    answers: Array<{ question_id: string; selected_answer: string; time_taken_sec: number }>,
  ) =>
    request<AssessmentSubmitResponse>(`/api/assessments/${assessmentId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  assessmentHistory: (syllabusId?: string) =>
    request<AssessmentHistoryOut[]>(
      `/api/assessments/history${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
    ),

  runDailyCheck: (syllabusId: string) =>
    request<DailyCheckResponse>("/api/workflows/daily-check", {
      method: "POST",
      body: JSON.stringify({ syllabus_id: syllabusId, simulate_days_elapsed: 0 }),
    }),

  simulateDailyCheck: (syllabusId: string, daysElapsed: number) =>
    request<DailyCheckResponse>("/api/workflows/daily-check/simulate", {
      method: "POST",
      body: JSON.stringify({ syllabus_id: syllabusId, simulate_days_elapsed: daysElapsed }),
    }),

  getStudentAnalytics: (syllabusId?: string) =>
    request<StudentAnalyticsOut>(
      `/api/analytics/student${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
    ),

  getParentDashboard: (syllabusId?: string) =>
    request<ParentDashboardOut>(
      `/api/analytics/parent-dashboard${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
    ),

  getForgettingCurve: (syllabusId: string, simulateDays = 0) =>
    request<ForgettingCurveOut>(
      `/api/analytics/forgetting-curve?syllabus_id=${encodeURIComponent(syllabusId)}&simulate_days_elapsed=${simulateDays}`,
    ),

  listTraces: (syllabusId?: string) =>
    request<TraceRecordOut[]>(
      `/api/agents/traces${syllabusId ? `?syllabus_id=${encodeURIComponent(syllabusId)}` : ""}`,
    ),
};
