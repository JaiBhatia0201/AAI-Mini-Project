"""Student profile routes (student read/write, parent read-only)."""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudentProfile, User
from app.schemas import StudentProfileOut, StudentProfileUpdate
from app.services.auth import get_current_user, get_effective_student_id, require_student_role

router = APIRouter(prefix="/api/students", tags=["Students"])


def _to_profile_out(profile: StudentProfile) -> StudentProfileOut:
    return StudentProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        active_syllabus_id=profile.active_syllabus_id,
        link_code=profile.link_code,
        current_grade=profile.current_grade,
        daily_hours=float(profile.daily_hours),
        learning_style=profile.learning_style,
        study_streak=int(profile.study_streak),
        total_hours_logged=float(profile.total_hours_logged),
        last_active_date=profile.last_active_date,
        stated_strengths=json.loads(profile.stated_strengths_json or "[]"),
        stated_weaknesses=json.loads(profile.stated_weaknesses_json or "[]"),
    )


@router.get("/profile", response_model=StudentProfileOut)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudentProfileOut:
    """Fetch student profile (supports both student owner and linked read-only parent)."""
    student_id = get_effective_student_id(user)
    profile = db.get(StudentProfile, student_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    return _to_profile_out(profile)


@router.put("/profile", response_model=StudentProfileOut)
def update_profile(
    payload: StudentProfileUpdate,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> StudentProfileOut:
    """Update study preferences for the authenticated student (403 for parent/teacher)."""
    student_id = get_effective_student_id(user)
    profile = db.get(StudentProfile, student_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    if payload.current_grade is not None:
        profile.current_grade = payload.current_grade
    if payload.daily_hours is not None:
        profile.daily_hours = float(payload.daily_hours)
    if payload.learning_style is not None:
        profile.learning_style = payload.learning_style
    if payload.stated_strengths is not None:
        profile.stated_strengths_json = json.dumps(payload.stated_strengths)
    if payload.stated_weaknesses is not None:
        profile.stated_weaknesses_json = json.dumps(payload.stated_weaknesses)

    db.commit()
    db.refresh(profile)
    return _to_profile_out(profile)
