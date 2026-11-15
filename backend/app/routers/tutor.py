"""AI Tutor, Resource Library, and Question Bank endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_study_session
from app.agents.resource_agent import run_resource_agent
from app.database import get_db
from app.models import LearningResource, Question, User
from app.routers._serializers import (
    resolve_syllabus_for_user,
    serialize_question,
    serialize_trace,
)
from app.schemas import (
    LearningResourceOut,
    QuestionOut,
    ResourceDiscoverRequest,
    ResourceDiscoverResponse,
    TutorLessonRequest,
    TutorLessonResponse,
)
from app.services.auth import get_current_user, require_student_role, verify_syllabus_access
from app.services.retrieval import get_retrieval_provider

router = APIRouter(tags=["Resources, Questions & AI Tutor"])


@router.get("/api/resources", response_model=list[LearningResourceOut])
def list_resources(
    syllabus_id: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    modality: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningResourceOut]:
    """List multi-modal learning resources scoped strictly to active/owned syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    query = db.query(LearningResource).filter_by(syllabus_id=syl.id)
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    if modality:
        query = query.filter_by(modality=modality)
    rows = query.all()
    return [LearningResourceOut.model_validate(r) for r in rows]


@router.post("/api/resources/discover", response_model=ResourceDiscoverResponse)
def discover_resources(
    payload: ResourceDiscoverRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> ResourceDiscoverResponse:
    """Ensure Agent 3 resources exist for a syllabus/topic and search per-syllabus index."""
    syl = verify_syllabus_access(db, user, payload.syllabus_id, write=True)
    state = run_resource_agent(
        db,
        {
            "run_id": "discover_res",
            "workflow_name": "resource_discovery",
            "student_id": syl.student_id,
            "syllabus_id": syl.id,
            "topic_id": payload.topic_id or "",
            "persist": True,
            "is_simulation": False,
            "traces": [],
        },
    )
    db.commit()

    hits_payload: list[dict] = []
    retrieval_mode = state.get("retrieval_mode", "tfidf_lexical")
    if payload.query.strip():
        hits = get_retrieval_provider().search(syl.id, payload.query.strip(), top_k=payload.top_k)
        if hits:
            retrieval_mode = hits[0].retrieval_mode
        hits_payload = [
            {
                "doc_id": h.doc_id,
                "topic_id": h.topic_id,
                "title": h.title,
                "snippet": h.text[:260],
                "score": round(h.score, 4),
                "source_origin": h.source_origin,
                "retrieval_mode": h.retrieval_mode,
            }
            for h in hits
        ]

    res_query = db.query(LearningResource).filter_by(syllabus_id=syl.id)
    if payload.topic_id:
        res_query = res_query.filter_by(topic_id=payload.topic_id)
    resources = [LearningResourceOut.model_validate(r) for r in res_query.all()]
    return ResourceDiscoverResponse(
        syllabus_id=syl.id,
        retrieval_mode=retrieval_mode,
        hits=hits_payload,
        resources=resources,
    )


@router.post("/api/tutor/ask", response_model=TutorLessonResponse)
def ask_tutor(
    payload: TutorLessonRequest,
    user: User = Depends(require_student_role),
    db: Session = Depends(get_db),
) -> TutorLessonResponse:
    """Invoke Agent 5 (+ 3 & 6) for style-adapted teaching and Q&A within syllabus scope."""
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


@router.get("/api/questions", response_model=list[QuestionOut])
def list_questions(
    syllabus_id: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionOut]:
    """List questions scoped to the student's syllabus without leaking answer keys."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    query = db.query(Question).filter_by(syllabus_id=syl.id)
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    rows = query.limit(60).all()
    return [serialize_question(q) for q in rows]
