export type UserRole = "student" | "parent_teacher";
export type LearningStyle = "visual" | "reading" | "practice" | "mixed";
export type DemoPersona = "aarav" | "priya" | "rohan" | "meera" | "parent";
export type AssessmentType = "diagnostic" | "topic_quiz" | "weekly_test" | "mock_exam";

export interface HealthStatus {
  status: string;
  llm_mode: "llm" | "fallback";
  llm_provider: string;
  retrieval_mode: "api_faiss" | "tfidf_fallback";
}

export interface StudentProfileOut {
  id: string;
  user_id: string;
  active_syllabus_id: string | null;
  link_code: string;
  current_grade: string;
  daily_hours: number;
  learning_style: LearningStyle | string;
  study_streak: number;
  total_hours_logged: number;
  last_active_date: string | null;
  stated_strengths: string[];
  stated_weaknesses: string[];
}

export interface UserOut {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  linked_student_id: string | null;
  student_profile: StudentProfileOut | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export interface SyllabusOut {
  id: string;
  student_id: string;
  title: string;
  exam_name: string;
  target_score: number;
  max_score: number;
  days_remaining: number;
  source_type: string;
  raw_filename: string | null;
  last_daily_check_at: string | null;
  topic_count: number;
  weak_count: number;
}

export interface SyllabusTopicOut {
  id: string;
  syllabus_id: string;
  topic_code: string;
  subject: string;
  category: string;
  unit: string;
  title: string;
  subtopics: string[];
  raw_excerpt: string;
  source_origin: string;
  difficulty: string;
  exam_weightage: number;
  estimated_hours: number;
  order_index: number;
  mastery_score: number;
  retention_score: number;
  status: string;
}

export interface TopicPrerequisiteOut {
  id: string;
  syllabus_id: string;
  prerequisite_topic_id: string;
  dependent_topic_id: string;
  confidence_status: string;
}

export interface SyllabusGraphOut {
  syllabus: SyllabusOut;
  topics: SyllabusTopicOut[];
  prerequisites: TopicPrerequisiteOut[];
}

export interface TraceRecordOut {
  run_id: string;
  workflow_name: string;
  agent_number: number;
  agent_name: string;
  execution_mode: string;
  status: string;
  latency_ms: number;
  input_summary: string;
  output_summary: string;
  error_message: string | null;
  created_at: string;
}

export interface QuestionOut {
  id: string;
  syllabus_id: string;
  topic_id: string;
  subtopic: string;
  difficulty: string;
  question_type: string;
  prompt: string;
  options: string[];
  expected_time_sec: number;
  source_origin: string;
  is_generated: boolean;
}

export interface OnboardSyllabusResponse {
  run_id: string;
  syllabus: SyllabusOut;
  topics_count: number;
  prerequisites_count: number;
  diagnostic_questions: QuestionOut[];
  traces: TraceRecordOut[];
}

export interface StudyPlanItemOut {
  id: string;
  syllabus_id: string;
  topic_id: string;
  topic_title: string;
  scheduled_date: string;
  day_number: number;
  task_type: string;
  duration_hours: number;
  status: "pending" | "completed" | "rescheduled" | string;
  adaptation_reason: string | null;
}

export interface AdaptationChange {
  action: string;
  task_type: string;
  topic_id: string;
  topic_code?: string;
  day_offset: number;
  reason: string;
}

export interface AdaptationDiffOut {
  id: string | null;
  summary: string;
  weak_topics: string[];
  root_cause_blockers: string[];
  changes: AdaptationChange[];
  created_at: string | null;
}

export interface PlannerOverviewOut {
  syllabus_id: string;
  items: StudyPlanItemOut[];
  recent_adaptations: AdaptationDiffOut[];
}

export interface DiagnosticCompleteResponse {
  run_id: string;
  syllabus_id: string;
  coaching_message: string;
  adaptation: AdaptationDiffOut | null;
  traces: TraceRecordOut[];
}

export interface LearningResourceOut {
  id: string;
  syllabus_id: string;
  topic_id: string;
  modality: string;
  title: string;
  source_ref: string;
  url_or_content: string;
  summary: string;
  source_origin: string;
  created_by_agent: string;
}

export interface RetrievalSearchHit {
  doc_id: string;
  topic_id: string;
  title: string;
  snippet: string;
  score: number;
  source_origin: string;
  retrieval_mode: string;
}

export interface ResourceDiscoverResponse {
  syllabus_id: string;
  retrieval_mode: string;
  hits: RetrievalSearchHit[];
  resources: LearningResourceOut[];
}

export interface WebSourceOut {
  title: string;
  url: string;
  snippet: string;
  score: number;
  provider: string;
}

export interface TutorLessonResponse {
  run_id: string;
  topic_id: string;
  explanation: string;
  analogy: string;
  prerequisite_path: string[];
  flashcards: Array<{ front: string; back: string }>;
  practice_questions: QuestionOut[];
  source_origin: string;
  confidence_status: string;
  is_out_of_syllabus?: boolean;
  web_retrieval_mode?: string | null;
  web_sources?: WebSourceOut[];
  traces: TraceRecordOut[];
}

export interface AssessmentStartResponse {
  assessment_id: string;
  syllabus_id: string;
  title: string;
  assessment_type: string;
  questions: QuestionOut[];
}

export interface QuestionResultOut {
  question_id: string;
  topic_id: string;
  selected_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
  time_taken_sec: number;
}

export interface AssessmentSubmitResponse {
  run_id: string;
  assessment_id: string;
  score: number;
  max_score: number;
  accuracy: number;
  results: QuestionResultOut[];
  weak_topics: string[];
  root_cause_blockers: string[];
  adaptation: AdaptationDiffOut | null;
  coaching_message: string;
  traces: TraceRecordOut[];
}

export interface AssessmentHistoryOut {
  id: string;
  syllabus_id: string;
  title: string;
  assessment_type: string;
  score: number;
  max_score: number;
  accuracy: number;
  time_taken_sec: number;
  created_at: string;
}

export interface DecayAlert {
  topic_id: string;
  topic_code?: string;
  title: string;
  retention_score: number;
  stability_days: number;
  days_since_practice: number;
}

export interface DailyCheckResponse {
  run_id: string;
  syllabus_id: string;
  is_simulation: boolean;
  evaluated_at: string;
  decay_alerts: DecayAlert[];
  adaptation: AdaptationDiffOut | null;
  coaching_message: string;
  traces: TraceRecordOut[];
}

export interface PredictiveScoreOut {
  current_estimated_score: number;
  projected_estimated_score: number;
  max_score: number;
  target_score: number;
  target_gap: number;
  readiness_band: string;
  is_estimate: boolean;
  label: string;
}

export interface SubjectBreakdownItem {
  subject: string;
  topic_count: number;
  avg_mastery: number;
}

export interface WeakTopicMetric {
  topic_id: string;
  topic_code: string;
  title: string;
  subject: string;
  mastery_score: number;
  retention_score: number;
}

export interface MasteryHistoryPoint {
  label: string;
  date: string;
  score: number;
  accuracy: number;
  time_taken_sec: number;
}

export interface StudentAnalyticsOut {
  syllabus: SyllabusOut;
  overall_mastery: number;
  coverage_percent: number;
  weak_topic_count: number;
  forgetting_alerts_count: number;
  predictive_score: PredictiveScoreOut;
  subject_breakdown: SubjectBreakdownItem[];
  weak_topics: WeakTopicMetric[];
  recent_assessments: AssessmentHistoryOut[];
  mastery_history: MasteryHistoryPoint[];
}

export interface ParentDashboardOut {
  student_name: string;
  student_email: string;
  link_code: string;
  study_streak: number;
  total_hours_logged: number;
  syllabus: SyllabusOut;
  coverage_percent: number;
  overall_mastery: number;
  predictive_score: PredictiveScoreOut;
  weak_topics: WeakTopicMetric[];
  root_cause_blockers: string[];
  weekly_progression: MasteryHistoryPoint[];
  read_only: boolean;
}

export interface ForgettingCurveOut {
  syllabus_id: string;
  simulate_days_elapsed: number;
  avg_stability_days: number;
  topics: Array<{
    topic_id: string;
    topic_code: string;
    title: string;
    mastery_score: number;
    retention_score: number;
    stability_days: number;
    review_count: number;
    at_risk: boolean;
  }>;
  curve_series: Array<{
    day: number;
    label: string;
    baseline_retention: number;
    weak_topic_retention: number;
    reinforced_retention: number;
  }>;
}
