"""Pydantic v2 request and response schemas for the PS-03 REST API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

# --- Authentication & Profile Schemas ---

class UserRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "parent_teacher"] = "student"
    link_code: str | None = None

class UserLoginRequest(BaseModel):
    email: str
    password: str


class DemoLoginRequest(BaseModel):
    persona: Literal["aarav", "priya", "rohan", "meera", "parent"] = "aarav"


class StudentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    active_syllabus_id: str | None = None
    link_code: str
    current_grade: str = ""
    daily_hours: float
    learning_style: str
    study_streak: int
    total_hours_logged: float
    last_active_date: date | None = None
    stated_strengths: list[str] = Field(default_factory=list)
    stated_weaknesses: list[str] = Field(default_factory=list)


class StudentProfileUpdate(BaseModel):
    current_grade: str | None = None
    daily_hours: float | None = Field(default=None, ge=0.5, le=16.0)
    learning_style: Literal["visual", "reading", "practice", "mixed"] | None = None
    stated_strengths: list[str] | None = None
    stated_weaknesses: list[str] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str
    linked_student_id: str | None = None
    student_profile: StudentProfileOut | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Multi-Syllabus & Knowledge Graph Schemas ---


class SyllabusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    title: str
    exam_name: str
    target_score: float
    max_score: float
    days_remaining: int
    source_type: str
    raw_filename: str | None = None
    last_daily_check_at: datetime | None = None
    topic_count: int = 0
    weak_count: int = 0


class SyllabusTopicOut(BaseModel):
    id: str
    syllabus_id: str
    topic_code: str
    subject: str
    category: str
    unit: str
    title: str
    subtopics: list[str] = Field(default_factory=list)
    raw_excerpt: str = ""
    source_origin: str
    difficulty: str
    exam_weightage: float
    estimated_hours: float
    order_index: int
    mastery_score: float = 40.0
    retention_score: float = 1.0
    status: str = "unstarted"


class TopicPrerequisiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    syllabus_id: str
    prerequisite_topic_id: str
    dependent_topic_id: str
    confidence_status: str


class SyllabusGraphOut(BaseModel):
    syllabus: SyllabusOut
    topics: list[SyllabusTopicOut]
    prerequisites: list[TopicPrerequisiteOut]


class PrerequisitePatchItem(BaseModel):
    prerequisite_topic_id: str
    dependent_topic_id: str
    action: Literal["confirm", "remove", "add"] = "confirm"


class PrerequisitePatchRequest(BaseModel):
    updates: list[PrerequisitePatchItem] = Field(default_factory=list)


# --- Study Resources, Questions & Tutor Schemas ---


class LearningResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    syllabus_id: str
    topic_id: str
    modality: str
    title: str
    source_ref: str
    url_or_content: str
    summary: str
    source_origin: str
    created_by_agent: str


class ResourceDiscoverRequest(BaseModel):
    syllabus_id: str
    topic_id: str | None = None
    query: str = ""
    top_k: int = Field(default=5, ge=1, le=20)


class TutorLessonRequest(BaseModel):
    syllabus_id: str
    topic_id: str | None = None
    question: str | None = None
    force_web: bool = False


class WebSourceOut(BaseModel):
    title: str
    url: str
    snippet: str
    score: float = 0.0
    provider: str = "web"


class TutorLessonResponse(BaseModel):
    run_id: str
    topic_id: str
    explanation: str
    analogy: str
    prerequisite_path: list[str] = Field(default_factory=list)
    flashcards: list[dict[str, str]] = Field(default_factory=list)
    practice_questions: list[QuestionOut] = Field(default_factory=list)
    source_origin: str
    confidence_status: str
    is_out_of_syllabus: bool = False
    web_retrieval_mode: str | None = None
    web_sources: list[WebSourceOut] = Field(default_factory=list)
    traces: list[TraceRecordOut] = Field(default_factory=list)


class ResourceDiscoverResponse(BaseModel):
    syllabus_id: str
    retrieval_mode: str
    hits: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[LearningResourceOut] = Field(default_factory=list)


class DiagnosticCompleteResponse(BaseModel):
    run_id: str
    syllabus_id: str
    coaching_message: str = ""
    adaptation: AdaptationDiffOut | None = None
    traces: list[TraceRecordOut] = Field(default_factory=list)


class QuestionOut(BaseModel):
    id: str
    syllabus_id: str
    topic_id: str
    subtopic: str
    difficulty: str
    question_type: str
    prompt: str
    options: list[str] = Field(default_factory=list)
    expected_time_sec: int
    source_origin: str
    is_generated: bool


# --- Workflows, Planner & Closed-Loop Assessment Schemas ---


class OnboardSyllabusResponse(BaseModel):
    run_id: str
    syllabus: SyllabusOut
    topics_count: int
    prerequisites_count: int
    diagnostic_questions: list[QuestionOut] = Field(default_factory=list)
    traces: list[TraceRecordOut] = Field(default_factory=list)


class AnswerSubmission(BaseModel):
    question_id: str
    topic_id: str | None = None
    selected_answer: str
    time_taken_sec: int = Field(default=30, ge=0)


class DiagnosticSubmitRequest(BaseModel):
    syllabus_id: str
    answers: list[AnswerSubmission] = Field(default_factory=list)
    self_ratings: dict[str, Literal["strong", "moderate", "weak"]] = Field(
        default_factory=dict
    )
    daily_hours: float | None = Field(default=None, ge=0.5, le=16.0)
    learning_style: Literal["visual", "reading", "practice", "mixed"] | None = None
    target_score: float | None = Field(default=None, gt=0)
    days_remaining: int | None = Field(default=None, ge=7, le=365)


class StudyPlanItemOut(BaseModel):
    id: str
    syllabus_id: str
    topic_id: str
    topic_title: str = ""
    scheduled_date: date
    day_number: int
    task_type: str
    duration_hours: float
    status: str
    adaptation_reason: str | None = None

class AdaptationDiffOut(BaseModel):
    id: str | None = None
    summary: str
    weak_topics: list[str] = Field(default_factory=list)
    root_cause_blockers: list[str] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None

class PlannerOverviewOut(BaseModel):
    syllabus_id: str
    items: list[StudyPlanItemOut] = Field(default_factory=list)
    recent_adaptations: list[AdaptationDiffOut] = Field(default_factory=list)


class AssessmentStartRequest(BaseModel):
    syllabus_id: str
    topic_id: str | None = None
    assessment_type: Literal["diagnostic", "topic_quiz", "weekly_test", "mock_exam"] = (
        "topic_quiz"
    )
    question_count: int = Field(default=6, ge=1, le=40)


class AssessmentStartResponse(BaseModel):
    assessment_id: str
    syllabus_id: str
    title: str
    assessment_type: str
    questions: list[QuestionOut] = Field(default_factory=list)


class AssessmentSubmitRequest(BaseModel):
    answers: list[AnswerSubmission] = Field(default_factory=list)


class QuestionResultOut(BaseModel):
    question_id: str
    topic_id: str
    selected_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str
    time_taken_sec: int


class AssessmentSubmitResponse(BaseModel):
    run_id: str
    assessment_id: str
    score: float
    max_score: float
    accuracy: float
    results: list[QuestionResultOut] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    root_cause_blockers: list[str] = Field(default_factory=list)
    adaptation: AdaptationDiffOut | None = None
    coaching_message: str = ""
    traces: list[TraceRecordOut] = Field(default_factory=list)


class AssessmentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    syllabus_id: str
    title: str
    assessment_type: str
    score: float
    max_score: float
    accuracy: float
    time_taken_sec: int
    created_at: datetime


class DailyCheckRequest(BaseModel):
    syllabus_id: str
    simulate_days_elapsed: int = Field(default=0, ge=0, le=180)


class DailyCheckResponse(BaseModel):
    run_id: str
    syllabus_id: str
    is_simulation: bool
    evaluated_at: datetime
    decay_alerts: list[dict[str, Any]] = Field(default_factory=list)
    adaptation: AdaptationDiffOut | None = None
    coaching_message: str = ""
    traces: list[TraceRecordOut] = Field(default_factory=list)


# --- Analytics & Observability Schemas ---


class TraceRecordOut(BaseModel):
    run_id: str
    workflow_name: str
    agent_number: int
    agent_name: str
    execution_mode: str
    status: str
    latency_ms: float
    input_summary: str
    output_summary: str
    error_message: str | None = None
    created_at: datetime


class PredictiveScoreOut(BaseModel):
    current_estimated_score: float
    projected_estimated_score: float
    max_score: float
    target_score: float
    target_gap: float
    readiness_band: str
    is_estimate: bool = True
    label: str = "Estimated Readiness Projection"


class StudentAnalyticsOut(BaseModel):
    syllabus: SyllabusOut
    overall_mastery: float
    coverage_percent: float
    weak_topic_count: int
    forgetting_alerts_count: int
    predictive_score: PredictiveScoreOut
    subject_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    recent_assessments: list[AssessmentHistoryOut] = Field(default_factory=list)
    mastery_history: list[dict[str, Any]] = Field(default_factory=list)


class ParentDashboardOut(BaseModel):
    student_name: str
    student_email: str
    link_code: str
    study_streak: int
    total_hours_logged: float
    syllabus: SyllabusOut
    coverage_percent: float
    overall_mastery: float
    predictive_score: PredictiveScoreOut
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    root_cause_blockers: list[str] = Field(default_factory=list)
    weekly_progression: list[dict[str, Any]] = Field(default_factory=list)
    read_only: bool = True

