"""All 13 SQLAlechemy ORM models with composite multi-syllabus isolation."""

from datetime import date, datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    """Generate a new unique string primary key."""
    return str(uuid4())


def _utcnow() -> datetime:
    """Return current timezone-aware UTC timestamp (Python 3.13 safe)."""
    return datetime.now(timezone.utc)


class User(Base):
    """Authenticated account for either a student or read-only parent/teacher."""

    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="student")
    linked_student_id = Column(
        String(64),
        ForeignKey(
            "student_profiles.id",
            use_alter=True,
            name="fk_user_linked_student",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        foreign_keys="[StudentProfile.user_id]",
        uselist=False,
        cascade="all, delete-orphan",
    )


class StudentProfile(Base):
    """Learner preferences, study streak, link code, and active syllabus pointer."""

    __tablename__ = "student_profiles"

    id = Column(String(64), primary_key=True, default=_uuid)
    user_id = Column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_syllabus_id = Column(
        String(64),
        ForeignKey(
            "syllabi.id",
            use_alter=True,
            name="fk_profile_active_syllabus",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    link_code = Column(String(32), unique=True, index=True, nullable=False)
    current_grade = Column(String(100), nullable=False, default="")
    daily_hours = Column(Float, nullable=False, default=3.0)
    learning_style = Column(String(32), nullable=False, default="visual")
    study_streak = Column(Integer, nullable=False, default=0)
    total_hours_logged = Column(Float, nullable=False, default=0.0)
    last_active_date = Column(Date, nullable=True)
    stated_strengths_json = Column(Text, nullable=False, default="[]")
    stated_weaknesses_json = Column(Text, nullable=False, default="[]")

    user = relationship(
        "User",
        back_populates="student_profile",
        foreign_keys=[user_id],
    )
    syllabi = relationship(
        "Syllabus",
        back_populates="student",
        foreign_keys="[Syllabus.student_id]",
        cascade="all, delete-orphan",
    )


class Syllabus(Base):
    """Per-student syllabus container (seeded flagship or uploaded custom PDF)."""

    __tablename__ = "syllabi"
    __table_args__ = (
        UniqueConstraint("student_id", "id", name="uq_syllabi_student_id"),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    student_id = Column(
        String(64),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=False)
    exam_name = Column(String(120), nullable=False, default="Custom Course")
    target_score = Column(Float, nullable=False, default=75.0)
    max_score = Column(Float, nullable=False, default=100.0)
    days_remaining = Column(Integer, nullable=False, default=60)
    source_type = Column(String(32), nullable=False, default="seeded")
    raw_filename = Column(String(255), nullable=True)
    last_daily_check_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    student = relationship(
        "StudentProfile",
        back_populates="syllabi",
        foreign_keys=[student_id],
    )
    topics = relationship(
        "SyllabusTopic",
        back_populates="syllabus",
        cascade="all, delete-orphan",
    )


class SyllabusTopic(Base):
    """Individual topic node inside a specific syllabus DAG."""

    __tablename__ = "syllabus_topics"
    __table_args__ = (
        UniqueConstraint("syllabus_id", "id", name="uq_topics_syllabus_id"),
        UniqueConstraint("syllabus_id", "topic_code", name="uq_topics_syllabus_code"),
    )

    id = Column(String(100), primary_key=True, default=_uuid)
    syllabus_id = Column(
        String(64),
        ForeignKey("syllabi.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_code = Column(String(64), nullable=False)
    subject = Column(String(120), nullable=False)
    category = Column(String(120), nullable=False, default="Core")
    unit = Column(String(200), nullable=False, default="Unit 1")
    title= Column(String(255), nullable=False)
    subtopics_json = Column(Text, nullable=False, default="[]")
    raw_excerpt = Column(Text, nullable=False, default="")
    source_origin = Column(String(64), nullable=False, default="extracted_pdf_excerpt")
    difficulty = Column(String(32), nullable=False, default="medium")
    exam_weightage = Column(Float, nullable=False, default=1.0)
    estimated_hours = Column(Float, nullable=False, default=2.0)
    order_index = Column(Integer, nullable=False, default=0)

    syllabus = relationship("Syllabus", back_populates="topics")


class TopicPrerequisite(Base):
    """Directed prerequisite edge strictly bounded within a single syllabus_id."""

    __tablename__ = "topic_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "syllabus_id",
            "prerequisite_topic_id",
            "dependent_topic_id",
            name="uq_prereq_edge",
        ),
        ForeignKeyConstraint(
            ["syllabus_id"],
            ["syllabi.id"],
            ondelete="CASCADE",
            name="fk_prereq_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "prerequisite_topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_prereq_source_topic",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "dependent_topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_prereq_target_topic",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    syllabus_id = Column(String(64), nullable=False, index=True)
    prerequisite_topic_id = Column(String(100), nullable=False)
    dependent_topic_id = Column(String(100), nullable=False)
    confidence_status = Column(String(32), nullable=False, default="verified_seed")

class TopicMastery(Base):
    """Tracks EMA mastery score and Ebbinghaus retention memory per topic."""

    __tablename__ = "topic_mastery"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "syllabus_id",
            "topic_id",
            name="uq_mastery_student_syllabus_topic",
        ),
        ForeignKeyConstraint(
            ["student_id", "syllabus_id"],
            ["syllabi.student_id", "syllabi.id"],
            ondelete="CASCADE",
            name="fk_mastery_student_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_mastery_syllabus_topic",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    student_id = Column(String(64), nullable=False, index=True)
    syllabus_id = Column(String(64), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False)
    mastery_score = Column(Float, nullable=False, default=40.0)
    retention_score = Column(Float, nullable=False, default=1.0)
    stability_days = Column(Float, nullable=False, default=4.0)
    review_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="unstarted")
    last_practiced_at = Column(DateTime(timezone=True), nullable=True)


class LearningResource(Base):
    """Multi-modal curated or synthesized resource scoped to a syllabus topic."""

    __tablename__ = "learning_resources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["syllabus_id"],
            ["syllabi.id"],
            ondelete="CASCADE",
            name="fk_resource_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_resource_syllabus_topic",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    syllabus_id = Column(String(64), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False, index=True)
    modality = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    source_ref = Column(String(255), nullable=False, default="")
    url_or_content = Column(Text, nullable=False, default="")
    summary = Column(Text, nullable=False, default="")
    source_origin = Column(String(64), nullable=False, default="curated_dataset_note")
    created_by_agent = Column(String(64), nullable=False, default="Agent 3")


class Question(Base):
    """Practice or exam question calibrated by difficulty and expected pacing."""

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("syllabus_id", "id", name="uq_questions_syllabus_id"),
        ForeignKeyConstraint(
            ["syllabus_id"],
            ["syllabi.id"],
            ondelete="CASCADE",
            name="fk_question_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_question_syllabus_topic",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    syllabus_id = Column(String(64), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False, index=True)
    subtopic = Column(String(200), nullable=False, default="")
    difficulty = Column(String(32), nullable=False, default="medium")
    question_type = Column(String(32), nullable=False, default="MCQ")
    prompt = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False, default="[]")
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False, default="")
    expected_time_sec = Column(Integer, nullable=False, default=60)
    source_origin = Column(String(64), nullable=False, default="curated_dataset_note")
    is_generated = Column(Boolean, nullable=False, default=False)


class StudyPlanItem(Base):
    """Scheduled learning, practice, revision, speced-repetition, or test task."""

    __tablename__ = "study_plan_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "syllabus_id"],
            ["syllabi.student_id", "syllabi.id"],
            ondelete="CASCADE",
            name="fk_plan_student_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_plan_syllabus_topic",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    student_id = Column(String(64), nullable=False, index=True)
    syllabus_id = Column(String(64), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False, default=date.today)
    day_number = Column(Integer, nullable=False, default=1)
    task_type = Column(String(32), nullable=False, default="learn")
    duration_hours = Column(Float, nullable=False, default=1.0)
    status = Column(String(32), nullable=False, default="pending")
    adaptation_reason = Column(Text, nullable=True)


class Assessment(Base):
    """Completed or in-progress diagnostic, quiz, weekly test, or mock exam."""

    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("syllabus_id", "id", name="uq_assessments_syllabus_id"),
        ForeignKeyConstraint(
            ["student_id", "syllabus_id"],
            ["syllabi.student_id", "syllabi.id"],
            ondelete="CASCADE",
            name="fk_assessment_student_syllabus",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    student_id = Column(String(64), nullable=False, index=True)
    syllabus_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    assessment_type = Column(String(32), nullable=False, default="topic_quiz")
    score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=False, default=100.0)
    accuracy=Column(Float, nullable=False, default=0.0)
    time_taken_sec = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    attempts = relationship(
        "QuestionAttempt",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class QuestionAttempt(Base):
    """Single answered question linked strictly to assessment, syllabus and topic."""

    __tablename__ = "question_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "syllabus_id"],
            ["syllabi.student_id", "syllabi.id"],
            ondelete="CASCADE",
            name="fk_attempt_student_syllabus",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "assessment_id"],
            ["assessments.syllabus_id", "assessments.id"],
            ondelete="CASCADE",
            name="fk_attempt_syllabus_assessment",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "topic_id"],
            ["syllabus_topics.syllabus_id", "syllabus_topics.id"],
            ondelete="CASCADE",
            name="fk_attempt_syllabus_topic",
        ),
        ForeignKeyConstraint(
            ["syllabus_id", "question_id"],
            ["questions.syllabus_id", "questions.id"],
            ondelete="CASCADE",
            name="fk_attempt_syllabus_question",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    assessment_id = Column(String(64), nullable=False, index=True)
    student_id = Column(String(64), nullable=False, index=True)
    syllabus_id = Column(String(64), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False, index=True)
    question_id = Column(String(64), nullable=False, index=True)
    selected_answer = Column(Text, nullable=False, default="")
    is_correct = Column(Boolean, nullable=False, default=False)
    time_taken_sec = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    assessment = relationship("Assessment", back_populates="attempts")


class PlanAdaptation(Base):
    """Recorded AdaptationDiff history whenever Agent 9 rewrites future tasks."""

    __tablename__ = "plan_adaptations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "syllabus_id"],
            ["syllabi.student_id", "syllabi.id"],
            ondelete="CASCADE",
            name="fk_adaptation_student_syllabus",
        ),
    )

    id = Column(String(64), primary_key=True, default=_uuid)
    student_id = Column(String(64), nullable=False, index=True)
    syllabus_id = Column(String(64), nullable=False, index=True)
    trigger_assessment_id = Column(
        String(64),
        ForeignKey("assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    weak_topics_json = Column(Text, nullable=False, default="[]")
    summary = Column(Text, nullable=False, default="")
    changes_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AgentExecutionLog(Base):
    """Persisted step-by-step LangGraph workflow trace (Flows A-E only)."""

    __tablename__ = "agent_execution_logs"

    id = Column(String(64), primary_key=True, default=_uuid)
    run_id = Column(String(64), nullable=False, index=True)
    student_id = Column(
        String(64),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    syllabus_id = Column(
        String(64),
        ForeignKey("syllabi.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    workflow_name = Column(String(64), nullable=False)
    agent_number = Column(Integer, nullable=False)
    agent_name = Column(String(100), nullable=False)
    execution_mode = Column(String(32), nullable=False, default="deterministic")
    status=Column(String(32), nullable=False, default="completed")
    latency_ms = Column(Float, nullable=False, default=0.0)
    input_summary = Column(Text, nullable=False, default="")
    output_summary = Column(Text, nullable=False, default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)