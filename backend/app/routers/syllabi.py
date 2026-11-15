"""Multi-syllabus management and interactive knowledge graph (DAG) endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.syllabus_dag import resolve_cycles
from app.models import (
    StudentProfile,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
    User,
)
from app.routers._serializers import serialize_prerequisite, serialize_syllabus, serialize_topic
from app.schemas import PrerequisitePatchRequest, SyllabusGraphOut, SyllabusOut
from app.services.auth import get_current_user, get_effective_student_id, verify_syllabus_access

router = APIRouter(prefix="/api/syllabi", tags=["Syllabi & Knowledge Graph"])


def _build_graph_response(db: Session, syl: Syllabus) -> SyllabusGraphOut:
    topics = (
        db.query(SyllabusTopic)
        .filter_by(syllabus_id=syl.id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )
    masteries = {
        m.topic_id: m
        for m in db.query(TopicMastery)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .all()
    }
    edges = db.query(TopicPrerequisite).filter_by(syllabus_id=syl.id).all()
    return SyllabusGraphOut(
        syllabus=serialize_syllabus(db, syl),
        topics=[serialize_topic(t, masteries.get(t.id)) for t in topics],
        prerequisites=[serialize_prerequisite(e) for e in edges],
    )


@router.get("", response_model=list[SyllabusOut])
def list_syllabi(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SyllabusOut]:
    """List all syllabi belonging to the student (or parent's linked student)."""
    student_id = get_effective_student_id(user)
    rows = (
        db.query(Syllabus)
        .filter_by(student_id=student_id)
        .order_by(Syllabus.created_at.desc())
        .all()
    )
    return [serialize_syllabus(db, s) for s in rows]


@router.post("/{syllabus_id}/activate", response_model=SyllabusOut)
def activate_syllabus(
    syllabus_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusOut:
    """Switch the student's active_syllabus_id cleanly (403 for unowned/parent)."""
    syl = verify_syllabus_access(db, user, syllabus_id, write=True)
    profile = db.get(StudentProfile, syl.student_id)
    if profile is not None:
        profile.active_syllabus_id = syl.id
    db.commit()
    return serialize_syllabus(db, syl)


@router.get("/{syllabus_id}/graph", response_model=SyllabusGraphOut)
def get_syllabus_graph(
    syllabus_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusGraphOut:
    """Return topics (w/ mastery color states) and prerequisite edges for React Flow."""
    syl = verify_syllabus_access(db, user, syllabus_id, write=False)
    return _build_graph_response(db, syl)


@router.patch("/{syllabus_id}/prerequisites", response_model=SyllabusGraphOut)
def patch_prerequisites(
    syllabus_id: str,
    payload: PrerequisitePatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusGraphOut:
    """Confirm, remove, or safely add DAG edges while enforcing acyclicity and scope."""
    syl = verify_syllabus_access(db, user, syllabus_id, write=True)
    topics = db.query(SyllabusTopic).filter_by(syllabus_id=syl.id).all()
    topic_orders = {t.id: int(t.order_index) for t in topics}

    for item in payload.updates:
        if item.prerequisite_topic_id not in topic_orders or item.dependent_topic_id not in topic_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prerequisite topics must belong strictly to the target syllabus.",
            )
        if item.prerequisite_topic_id == item.dependent_topic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A topic cannot depend on itself.",
            )

        existing = (
            db.query(TopicPrerequisite)
            .filter_by(
                syllabus_id=syl.id,
                prerequisite_topic_id=item.prerequisite_topic_id,
                dependent_topic_id=item.dependent_topic_id,
            )
            .first()
        )
        if item.action == "remove":
            if existing is not None:
                db.delete(existing)
        elif item.action == "confirm":
            if existing is not None:
                existing.confidence_status = "user_confirmed"
        elif item.action == "add":
            if existing is None:
                db.add(
                    TopicPrerequisite(
                        syllabus_id=syl.id,
                        prerequisite_topic_id=item.prerequisite_topic_id,
                        dependent_topic_id=item.dependent_topic_id,
                        confidence_status="user_confirmed",
                    )
                )

    db.flush()

    # Verify DAG remains cycle-free after edits
    all_edges = db.query(TopicPrerequisite).filter_by(syllabus_id=syl.id).all()
    edge_tuples = [
        (e.prerequisite_topic_id, e.dependent_topic_id, e.confidence_status)
        for e in all_edges
    ]
    _, dropped = resolve_cycles(edge_tuples, order_lookup=topic_orders)
    if dropped:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposed prerequisite edge creates a cyclic dependency.",
        )

    db.commit()
    return _build_graph_response(db, syl)
