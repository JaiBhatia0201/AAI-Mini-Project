"""Shared ORM -> Pydantic serialization and active-syllabus resolution helpers."""

from datetime import datetime, timezone
import json
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    AgentExecutionLog,
    PlanAdaptation,
    Question,
    StudentProfile,
    StudyPlanItem,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
    User,
)
from app.schemas import (
    AdaptationDiffOut,
    QuestionOut,
    StudyPlanItemOut,
    SyllabusOut,
    SyllabusTopicOut,
    TopicPrerequisiteOut,
    TraceRecordOut,
)
from app.services.auth import get_effective_student_id, verify_syllabus_access


def serialize_syllabus(db: Session, syl: Syllabus) -> SyllabusOut:
    """Serialize Syllabus with computed topic_count and weak_count."""
    topic_count = db.query(SyllabusTopic).filter_by(syllabus_id=syl.id).count()
    weak_count = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.syllabus_id == syl.id,
            TopicMastery.student_id == syl.student_id,
            (TopicMastery.status == "weak") | (TopicMastery.mastery_score < 60.0),
        )
        .count()
    )
    return SyllabusOut(
        id=syl.id,
        student_id=syl.student_id,
        title=syl.title,
        exam_name=syl.exam_name,
        target_score=float(syl.target_score),
        max_score=float(syl.max_score),
        days_remaining=int(syl.days_remaining),
        source_type=syl.source_type,
        raw_filename=syl.raw_filename,
        last_daily_check_at=syl.last_daily_check_at,
        topic_count=topic_count,
        weak_count=weak_count,
    )


def serialize_topic(topic: SyllabusTopic, mastery: TopicMastery | None = None) -> SyllabusTopicOut:
    """Serialize SyllabusTopic merged with student mastery/retention telemetry."""
    return SyllabusTopicOut(
        id=topic.id,
        syllabus_id=topic.syllabus_id,
        topic_code=topic.topic_code,
        subject=topic.subject,
        category=topic.category,
        unit=topic.unit,
        title=topic.title,
        subtopics=json.loads(topic.subtopics_json or "[]"),
        raw_excerpt=topic.raw_excerpt or "",
        source_origin=topic.source_origin,
        difficulty=topic.difficulty,
        exam_weightage=float(topic.exam_weightage),
        estimated_hours=float(topic.estimated_hours),
        order_index=int(topic.order_index),
        mastery_score=float(mastery.mastery_score) if mastery else 40.0,
        retention_score=float(mastery.retention_score) if mastery else 1.0,
        status=mastery.status if mastery else "unstarted",
    )


def serialize_prerequisite(edge: TopicPrerequisite) -> TopicPrerequisiteOut:
    """Serialize TopicPrerequisite edge."""
    return TopicPrerequisiteOut(
        id=edge.id,
        syllabus_id=edge.syllabus_id,
        prerequisite_topic_id=edge.prerequisite_topic_id,
        dependent_topic_id=edge.dependent_topic_id,
        confidence_status=edge.confidence_status,
    )


def serialize_question(q: Question | dict[str, Any]) -> QuestionOut:
    """Serialize Question ORM row or orchestrator dict cleanly (without leaking answer)."""
    if isinstance(q, dict):
        return QuestionOut(
            id=q["id"],
            syllabus_id=q["syllabus_id"],
            topic_id=q["topic_id"],
            subtopic=q.get("subtopic", ""),
            difficulty=q.get("difficulty", "medium"),
            question_type=q.get("question_type", "MCQ"),
            prompt=q["prompt"],
            options=list(q.get("options", [])),
            expected_time_sec=int(q.get("expected_time_sec", 60)),
            source_origin=q.get("source_origin", "curated_dataset_note"),
            is_generated=bool(q.get("is_generated", False)),
        )
    return QuestionOut(
        id=q.id,
        syllabus_id=q.syllabus_id,
        topic_id=q.topic_id,
        subtopic=q.subtopic,
        difficulty=q.difficulty,
        question_type=q.question_type,
        prompt=q.prompt,
        options=json.loads(q.options_json or "[]"),
        expected_time_sec=int(q.expected_time_sec),
        source_origin=q.source_origin,
        is_generated=bool(q.is_generated),
    )


def serialize_trace(t: AgentExecutionLog | dict[str, Any]) -> TraceRecordOut:
    """Serialize AgentExecutionLog row or in-memory trace dictionary."""
    if isinstance(t, dict):
        return TraceRecordOut(
            run_id=t["run_id"],
            workflow_name=t["workflow_name"],
            agent_number=int(t["agent_number"]),
            agent_name=t["agent_name"],
            execution_mode=t["execution_mode"],
            status=t.get("status", "completed"),
            latency_ms=float(t.get("latency_ms", 0.0)),
            input_summary=t.get("input_summary", ""),
            output_summary=t.get("output_summary", ""),
            error_message=t.get("error_message"),
            created_at=t.get("created_at") or datetime.now(timezone.utc),
        )
    return TraceRecordOut(
        run_id=t.run_id,
        workflow_name=t.workflow_name,
        agent_number=int(t.agent_number),
        agent_name=t.agent_name,
        execution_mode=t.execution_mode,
        status=t.status,
        latency_ms=float(t.latency_ms),
        input_summary=t.input_summary,
        output_summary=t.output_summary,
        error_message=t.error_message,
        created_at=t.created_at,
    )


def serialize_adaptation(adp: PlanAdaptation | dict[str, Any] | None) -> AdaptationDiffOut | None:
    """Serialize persisted PlanAdaptation row or in-memory AdaptationDiff dictionary."""
    if adp is None:
        return None
    if isinstance(adp, dict):
        return AdaptationDiffOut(
            id=adp.get("id"),
            summary=adp.get("summary", ""),
            weak_topics=list(adp.get("weak_topics") or []),
            root_cause_blockers=list(adp.get("root_cause_blockers") or []),
            changes=list(adp.get("changes") or []),
            created_at=adp.get("created_at"),
        )
    return AdaptationDiffOut(
        id=adp.id,
        summary=adp.summary,
        weak_topics=json.loads(adp.weak_topics_json or "[]"),
        root_cause_blockers=[],
        changes=json.loads(adp.changes_json or "[]"),
        created_at=adp.created_at,
    )


def serialize_plan_item(item: StudyPlanItem, topic_title: str = "") -> StudyPlanItemOut:
    """Serialize StudyPlanItem with resolved topic title."""
    return StudyPlanItemOut(
        id=item.id,
        syllabus_id=item.syllabus_id,
        topic_id=item.topic_id,
        topic_title=topic_title,
        scheduled_date=item.scheduled_date,
        day_number=int(item.day_number),
        task_type=item.task_type,
        duration_hours=float(item.duration_hours),
        status=item.status,
        adaptation_reason=item.adaptation_reason,
    )


def resolve_syllabus_for_user(
    db: Session,
    user: User,
    syllabus_id: str | None = None,
    write: bool = False,
) -> Syllabus:
    """Verify explicit syllabus access or resolve student's active/latest syllabus."""
    if syllabus_id:
        return verify_syllabus_access(db, user, syllabus_id, write=write)

    student_id = get_effective_student_id(user)
    profile = db.get(StudentProfile, student_id)
    if profile and profile.active_syllabus_id:
        syl = db.get(Syllabus, profile.active_syllabus_id)
        if syl and syl.student_id == student_id:
            return verify_syllabus_access(db, user, syl.id, write=write)

    latest = (
        db.query(Syllabus)
        .filter_by(student_id=student_id)
        .order_by(Syllabus.created_at.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No syllabus found for this student. Upload a syllabus PDF or adopt GATE CSE to begin.",
        )
    return verify_syllabus_access(db, user, latest.id, write=write)
