"""Adaptive assessment start, closed-loop grading/adaptation submit, and history routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_assessment_adaptation
from app.agents.question_agent import select_calibrated_questions
from app.database import get_db
from app.models import Assessment, SyllabusTopic, User
from app.routers._serializers import (
    resolve_syllabus_for_user,
    serialize_adaptation,
    serialize_question,
    serialize_trace,
)
from app.schemas import (
    AssessmentHistoryOut,
    AssessmentStartRequest,
    AssessmentStartResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
    QuestionResultOut,
)
from app.services.auth import get_current_user, require_student_role, verify_syllabus_access

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.post("/start", response_model=AssessmentStartResponse)
def start_assessment(
    payload: AssessmentStartRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> AssessmentStartResponse:
    """Create an Assessment record and stage difficulty-calibrated MCQs (auto-generating if needed)."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=True)
    topic_label = ""
    if payload.topic_id:
        topic = db.get(SyllabusTopic, payload.topic_id)
        if topic is None or topic.syllabus_id != syl.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target topic not found in the specified syllabus.",
            )
        topic_label = f" - {topic.title}"

    questions, _ = select_calibrated_questions(
        db=db,
        student_id=syl.student_id,
        syllabus_id=syl.id,
        topic_id=payload.topic_id,
        count=payload.question_count,
    )
    title_prefix = {
        "diagnostic": "Diagnostic Assessment",
        "topic_quiz": "Topic Mastery Quiz",
        "weekly_test": "Weekly Comprehensive Check",
        "mock_exam": "Full Exam Readiness Mock",
    }.get(payload.assessment_type, "Practice Assessment")

    assessment = Assessment(
        student_id=syl.student_id,
        syllabus_id=syl.id,
        title=f"{title_prefix}{topic_label}",
        assessment_type=payload.assessment_type,
        max_score=float(syl.max_score),
    )
    db.add(assessment)
    db.commit()

    return AssessmentStartResponse(
        assessment_id=assessment.id,
        syllabus_id=syl.id,
        title=assessment.title,
        assessment_type=assessment.assessment_type,
        questions=[serialize_question(q) for q in questions],
    )


@router.post("/{assessment_id}/submit", response_model=AssessmentSubmitResponse)
def submit_assessment(
    assessment_id: str,
    payload: AssessmentSubmitRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> AssessmentSubmitResponse:
    """Trigger closed-loop Flow D: Agents 7 -> 8 -> 9 -> 10."""
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    syl = verify_syllabus_access(db, user, assessment.syllabus_id, write=True)

    result = run_assessment_adaptation(
        db=db,
        student_id=syl.student_id,
        syllabus_id=syl.id,
        assessment_id=assessment.id,
        submitted_answers=[a.model_dump() for a in payload.answers],
    )
    db.commit()

    return AssessmentSubmitResponse(
        run_id=result["run_id"],
        assessment_id=assessment.id,
        score=float(result.get("score", 0.0)),
        max_score=float(result.get("max_score_val", syl.max_score)),
        accuracy=float(result.get("accuracy", 0.0)),
        results=[QuestionResultOut(**r) for r in (result.get("results") or [])],
        weak_topics=list(result.get("weak_topics") or []),
        root_cause_blockers=list(result.get("root_cause_blockers") or []),
        adaptation=serialize_adaptation(result.get("adaptation_diff")),
        coaching_message=result.get("coaching_message", ""),
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )


@router.get("/history", response_model=list[AssessmentHistoryOut])
def assessment_history(
    syllabus_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AssessmentHistoryOut]:
    """Return past assessment scores/accuracy for the student's active syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    rows = (
        db.query(Assessment)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .order_by(Assessment.created_at.desc())
        .all()
    )
    return [AssessmentHistoryOut.model_validate(a) for a in rows]
