"""LangGraph orchestrated multi-agent workflow endpoints (Flows A-F)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import (
    run_complete_diagnostic,
    run_daily_check,
    run_demo_simulation,
    run_onboard_syllabus,
    run_study_session,
)
from app.agents.syllabus_agent import ScannedPDFError
from app.config import get_settings
from app.database import get_db
from app.models import Syllabus, User
from app.routers._serializers import (
    serialize_adaptation,
    serialize_question,
    serialize_syllabus,
    serialize_trace,
)
from app.schemas import (
    DailyCheckRequest,
    DailyCheckResponse,
    DiagnosticCompleteResponse,
    DiagnosticSubmitRequest,
    OnboardSyllabusResponse,
    TutorLessonRequest,
    TutorLessonResponse,
)
from app.services.auth import get_current_user, require_student_role, verify_syllabus_access

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


@router.post("/onboard-syllabus", response_model=OnboardSyllabusResponse)
def onboard_syllabus(
    onboard_mode: Literal["pdf_upload", "seeded_gate"] = Form("pdf_upload"),
    title: str | None = Form(None),
    exam_name: str | None = Form(None),
    target_score: float = Form(75.0),
    max_score: float = Form(100.0),
    days_remaining: int = Form(60),
    daily_hours: float = Form(3.0),
    learning_style: Literal["visual", "reading", "practice", "mixed"] = Form("visual"),
    file: UploadFile | None = File(None),
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> OnboardSyllabusResponse:
    """Flow A: Ingest custom syllabus PDF (422 if scanned) or seed an isolated GATE CSE copy."""
    pdf_bytes = b""
    safe_filename = "custom_syllabus.pdf"

    if onboard_mode == "pdf_upload":
        if file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please attach a text-selectable syllabus PDF when onboard_mode is 'pdf_upload'.",
            )
        pdf_bytes = file.file.read()
        raw_name = Path(file.filename or "syllabus.pdf").name
        safe_filename = raw_name or "syllabus.pdf"

    student_id = user.student_profile.id  # type: ignore[union-attr]
    try:
        result = run_onboard_syllabus(
            db=db,
            student_id=student_id,
            onboard_mode=onboard_mode,
            pdf_bytes=pdf_bytes,
            pdf_filename=safe_filename,
            title=title,
            exam_name=exam_name,
            target_score=target_score,
            max_score=max_score,
            days_remaining=days_remaining,
            daily_hours=daily_hours,
            learning_style=learning_style,
        )
    except ScannedPDFError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Onboarding failed ({type(exc).__name__}): {exc}",
        ) from exc

    # Save valid uploaded PDF copy safely in backend/uploads only AFTER validation passes
    if onboard_mode == "pdf_upload" and pdf_bytes:
        settings = get_settings()
        settings.ensure_storage_dirs()
        stored_name = f"{result['syllabus_id']}_{uuid4().hex[:6]}_{safe_filename}"
        (settings.upload_path / stored_name).write_bytes(pdf_bytes)

    db.commit()
    syl = db.get(Syllabus, result["syllabus_id"])
    return OnboardSyllabusResponse(
        run_id=result["run_id"],
        syllabus=serialize_syllabus(db, syl),  # type: ignore[arg-type]
        topics_count=int(result.get("topics_count", 0)),
        prerequisites_count=int(result.get("prerequisites_count", 0)),
        diagnostic_questions=[
            serialize_question(q) for q in (result.get("diagnostic_questions") or [])
        ],
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )


@router.post("/complete-diagnostic", response_model=DiagnosticCompleteResponse)
def complete_diagnostic(
    payload: DiagnosticSubmitRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> DiagnosticCompleteResponse:
    """Flow B: Score baseline diagnostic + self-ratings and calibrate initial DAG roadmap."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=True)
    profile = user.student_profile  # type: ignore[assignment]
    if profile is not None:
        if payload.daily_hours is not None:
            profile.daily_hours = float(payload.daily_hours)
        if payload.learning_style is not None:
            profile.learning_style = payload.learning_style
    if payload.target_score is not None:
        syl.target_score = float(payload.target_score)
    if payload.days_remaining is not None:
        syl.days_remaining = int(payload.days_remaining)
    db.flush()

    result = run_complete_diagnostic(
        db=db,
        student_id=syl.student_id,
        syllabus_id=syl.id,
        diagnostic_answers=[a.model_dump() for a in payload.answers],
        self_ratings=dict(payload.self_ratings),
    )
    db.commit()
    return DiagnosticCompleteResponse(
        run_id=result["run_id"],
        syllabus_id=syl.id,
        coaching_message=result.get("coaching_message", ""),
        adaptation=serialize_adaptation(result.get("adaptation_diff")),
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )


@router.post("/teach-and-practice", response_model=TutorLessonResponse)
def teach_and_practice(
    payload: TutorLessonRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> TutorLessonResponse:
    """Flow C: Deliver style-adapted lesson + calibrated topic practice MCQs."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=True)
    try:
        result = run_study_session(
            db=db,
            student_id=syl.student_id,
            syllabus_id=syl.id,
            topic_id=payload.topic_id,
            tutor_question=payload.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db.commit()
    lesson = result["lesson_payload"]
    return TutorLessonResponse(
        run_id=result["run_id"],
        topic_id=lesson["topic_id"],
        explanation=lesson["explanation"],
        analogy=lesson["analogy"],
        prerequisite_path=list(lesson.get("prerequisite_path") or []),
        flashcards=list(lesson.get("flashcards") or []),
        practice_questions=[
            serialize_question(q) for q in (result.get("practice_questions") or [])
        ],
        source_origin=lesson["source_origin"],
        confidence_status=lesson["confidence_status"],
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )


@router.post("/daily-check", response_model=DailyCheckResponse)
def daily_check(
    payload: DailyCheckRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> DailyCheckResponse:
    """Flow E: Evaluate real Ebbinghaus retention decay and persist adaptive updates."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=True)
    now = datetime.now(timezone.utc)
    result = run_daily_check(db=db, student_id=syl.student_id, syllabus_id=syl.id)
    syl.last_daily_check_at = now
    db.commit()
    return DailyCheckResponse(
        run_id=result["run_id"],
        syllabus_id=syl.id,
        is_simulation=False,
        evaluated_at=now,
        decay_alerts=list(result.get("decay_alerts") or []),
        adaptation=serialize_adaptation(result.get("adaptation_diff")),
        coaching_message=result.get("coaching_message", ""),
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )


@router.post("/daily-check/simulate", response_model=DailyCheckResponse)
def daily_check_simulate(
    payload: DailyCheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyCheckResponse:
    """Flow F: Read-only non-destructive time-shift preview (zero SQLite writes)."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=False)
    eval_dt = datetime.now(timezone.utc) + timedelta(days=payload.simulate_days_elapsed)
    result = run_demo_simulation(
        db=db,
        student_id=syl.student_id,
        syllabus_id=syl.id,
        days_elapsed=payload.simulate_days_elapsed,
    )
    return DailyCheckResponse(
        run_id=result["run_id"],
        syllabus_id=syl.id,
        is_simulation=True,
        evaluated_at=eval_dt,
        decay_alerts=list(result.get("decay_alerts") or []),
        adaptation=serialize_adaptation(result.get("adaptation_diff")),
        coaching_message=result.get("coaching_message", ""),
        traces=[serialize_trace(t) for t in (result.get("traces") or [])],
    )
