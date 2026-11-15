"""Study planner timeline, manual task completion, and adaptive reschedule routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_daily_check
from app.database import get_db
from app.models import PlanAdaptation, StudyPlanItem, SyllabusTopic, User
from app.routers._serializers import (
    resolve_syllabus_for_user,
    serialize_adaptation,
    serialize_plan_item,
)
from app.schemas import AdaptationDiffOut, PlannerOverviewOut, StudyPlanItemOut
from app.services.auth import get_current_user, require_student_role, verify_syllabus_access

router = APIRouter(prefix="/api/planner", tags=["Study Planner"])


class PlanItemStatusPatch(BaseModel):
    status: str = "completed"


@router.get("", response_model=PlannerOverviewOut)
def get_planner(
    syllabus_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannerOverviewOut:
    """Fetch study roadmap tasks and recent AdaptationDiff records for active syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    topic_titles = {
        t.id: f"{t.topic_code}: {t.title}"
        for t in db.query(SyllabusTopic).filter_by(syllabus_id=syl.id).all()
    }
    items = (
        db.query(StudyPlanItem)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .order_by(StudyPlanItem.day_number, StudyPlanItem.scheduled_date)
        .all()
    )
    adaptations = (
        db.query(PlanAdaptation)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .order_by(PlanAdaptation.created_at.desc())
        .limit(8)
        .all()
    )
    return PlannerOverviewOut(
        syllabus_id=syl.id,
        items=[serialize_plan_item(it, topic_titles.get(it.topic_id, it.topic_id)) for it in items],
        recent_adaptations=[serialize_adaptation(adp) for adp in adaptations if adp is not None],  # type: ignore[misc]
    )


@router.post("/adapt", response_model=AdaptationDiffOut | None)
def trigger_adaptation(
    syllabus_id: str | None = Query(default=None),
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> AdaptationDiffOut | None:
    """Run real persisted adaptive evaluation (Agents 8->9->10) for active syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=True)
    result = run_daily_check(db, student_id=syl.student_id, syllabus_id=syl.id)
    db.commit()
    return serialize_adaptation(result.get("adaptation_diff"))


@router.patch("/items/{item_id}", response_model=StudyPlanItemOut)
def update_plan_item_status(
    item_id: str,
    payload: PlanItemStatusPatch,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> StudyPlanItemOut:
    """Mark a study plan task as completed/pending within owned syllabus."""
    if payload.status not in {"pending", "completed", "rescheduled"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task status.")
    item = db.get(StudyPlanItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan item not found.")
    verify_syllabus_access(db, user, item.syllabus_id, write=True)

    item.status = payload.status
    db.commit()
    topic = db.get(SyllabusTopic, item.topic_id)
    label = f"{topic.topic_code}: {topic.title}" if topic else item.topic_id
    return serialize_plan_item(item, label)
