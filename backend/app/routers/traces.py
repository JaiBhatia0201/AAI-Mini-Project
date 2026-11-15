"""LangGraph agent execution trace timeline endpoints (read-only audit view)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentExecutionLog, User
from app.routers._serializers import resolve_syllabus_for_user, serialize_trace
from app.schemas import TraceRecordOut
from app.services.auth import get_current_user, get_effective_student_id

router = APIRouter(prefix="/api/agents", tags=["Agent Traces"])


@router.get("/traces", response_model=list[TraceRecordOut])
def list_traces(
    syllabus_id: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TraceRecordOut]:
    """Fetch chronological persisted LangGraph agent execution logs scoped to syllabus."""
    student_id = get_effective_student_id(user)
    query = db.query(AgentExecutionLog).filter_by(student_id=student_id)
    if syllabus_id:
        syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
        query = query.filter_by(syllabus_id=syl.id)
    rows = query.order_by(AgentExecutionLog.created_at.desc(), AgentExecutionLog.agent_number.asc()).limit(limit).all()
    return [serialize_trace(r) for r in rows]


@router.get("/traces/{run_id}", response_model=list[TraceRecordOut])
def get_run_traces(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TraceRecordOut]:
    """Fetch all ordered steps for one workflow run_id owned by the effective student."""
    student_id = get_effective_student_id(user)
    rows = (
        db.query(AgentExecutionLog)
        .filter_by(run_id=run_id, student_id=student_id)
        .order_by(AgentExecutionLog.created_at.asc(), AgentExecutionLog.agent_number.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace run not found.")
    return [serialize_trace(r) for r in rows]
