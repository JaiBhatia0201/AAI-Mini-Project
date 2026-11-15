"""Student analytics, Ebbinghaus forgetting curves, and read-only parent dashboard routes."""

from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.forgetting_curve import compute_retention, evaluate_retention_alerts
from app.engines.predictive_score import compute_predictive_score
from app.engines.syllabus_dag import build_nx_graph, find_root_cause_blockers
from app.models import (
    Assessment,
    StudentProfile,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
    User,
)
from app.routers._serializers import resolve_syllabus_for_user, serialize_syllabus
from app.schemas import (
    AssessmentHistoryOut,
    ParentDashboardOut,
    PredictiveScoreOut,
    StudentAnalyticsOut,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _compute_analytics_bundle(db: Session, syl: Syllabus) -> dict[str, Any]:
    """Compute bounded telemetry shared between student and parent dashboards."""
    topics = (
        db.query(SyllabusTopic)
        .filter_by(syllabus_id=syl.id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )
    topic_lookup = {t.id: t for t in topics}
    mastery_rows = (
        db.query(TopicMastery)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .all()
    )
    edges = db.query(TopicPrerequisite).filter_by(syllabus_id=syl.id).all()
    assessments = (
        db.query(Assessment)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .order_by(Assessment.created_at)
        .all()
    )

    m_map = {m.topic_id: float(m.mastery_score) for m in mastery_rows}
    r_map = {m.topic_id: float(m.retention_score) for m in mastery_rows}

    total_topics = max(1, len(topics))
    overall_mastery = round(sum(m_map.values()) / len(m_map), 2) if m_map else 40.0
    active_count = sum(1 for m in mastery_rows if m.status != "unstarted" or m.last_practiced_at is not None)
    coverage_percent = round(100.0 * active_count / total_topics, 1)

    now = datetime.now(timezone.utc)
    decay_alerts = evaluate_retention_alerts(mastery_rows, topic_lookup, eval_time=now)
    pred = compute_predictive_score(
        topics=topics,
        mastery_map=m_map,
        retention_map=r_map,
        history_scores=[float(a.score) for a in assessments],
        days_remaining=int(syl.days_remaining),
        target_score=float(syl.target_score),
        max_score=float(syl.max_score),
    )

    # Subject-level aggregation
    by_subject: dict[str, list[float]] = {}
    for t in topics:
        by_subject.setdefault(t.subject, []).append(m_map.get(t.id, 40.0))
    subject_breakdown = [
        {
            "subject": subj,
            "topic_count": len(vals),
            "avg_mastery": round(sum(vals) / len(vals), 1),
        }
        for subj, vals in by_subject.items()
    ]

    weak_rows = [
        m for m in mastery_rows if float(m.mastery_score) < 60.0 or m.status == "weak"
    ]
    weak_topics_payload = [
        {
            "topic_id": m.topic_id,
            "topic_code": topic_lookup[m.topic_id].topic_code if m.topic_id in topic_lookup else m.topic_id,
            "title": topic_lookup[m.topic_id].title if m.topic_id in topic_lookup else m.topic_id,
            "subject": topic_lookup[m.topic_id].subject if m.topic_id in topic_lookup else "",
            "mastery_score": round(float(m.mastery_score), 1),
            "retention_score": round(float(m.retention_score), 3),
        }
        for m in weak_rows
    ]

    graph = build_nx_graph(topics, edges)
    blocker_ids: list[str] = []
    for m in weak_rows:
        for b_id in find_root_cause_blockers(graph, m.topic_id, m_map, threshold=65.0):
            if b_id not in blocker_ids:
                blocker_ids.append(b_id)
    blocker_labels = [
        f"{topic_lookup[b].topic_code}: {topic_lookup[b].title} ({m_map.get(b, 40.0):.0f}%)"
        if b in topic_lookup
        else b
        for b in blocker_ids
    ]

    mastery_history = [
        {
            "label": a.title[:28],
            "date": a.created_at.date().isoformat(),
            "score": float(a.score),
            "accuracy": float(a.accuracy),
            "time_taken_sec": int(a.time_taken_sec),
        }
        for a in assessments
    ]

    return {
        "overall_mastery": overall_mastery,
        "coverage_percent": coverage_percent,
        "weak_topic_count": len(weak_rows),
        "forgetting_alerts_count": len(decay_alerts),
        "predictive_score": PredictiveScoreOut(**pred),
        "subject_breakdown": subject_breakdown,
        "weak_topics": weak_topics_payload,
        "root_cause_blockers": blocker_labels,
        "recent_assessments": [AssessmentHistoryOut.model_validate(a) for a in reversed(assessments[-10:])],
        "mastery_history": mastery_history,
    }


@router.get("/student", response_model=StudentAnalyticsOut)
def get_student_analytics(
    syllabus_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudentAnalyticsOut:
    """Return telemetry, predictive readiness, and mastery history for the active syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    bundle = _compute_analytics_bundle(db, syl)
    return StudentAnalyticsOut(
        syllabus=serialize_syllabus(db, syl),
        overall_mastery=bundle["overall_mastery"],
        coverage_percent=bundle["coverage_percent"],
        weak_topic_count=bundle["weak_topic_count"],
        forgetting_alerts_count=bundle["forgetting_alerts_count"],
        predictive_score=bundle["predictive_score"],
        subject_breakdown=bundle["subject_breakdown"],
        weak_topics=bundle["weak_topics"],
        recent_assessments=bundle["recent_assessments"],
        mastery_history=bundle["mastery_history"],
    )


@router.get("/parent-dashboard", response_model=ParentDashboardOut)
def get_parent_dashboard(
    syllabus_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParentDashboardOut:
    """Read-only parent/teacher analytics view strictly bounded to linked student metrics."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    profile = db.get(StudentProfile, syl.student_id)
    if profile is None or profile.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found.")

    bundle = _compute_analytics_bundle(db, syl)
    return ParentDashboardOut(
        student_name=profile.user.name,
        student_email=profile.user.email,
        link_code=profile.link_code,
        study_streak=int(profile.study_streak),
        total_hours_logged=float(profile.total_hours_logged),
        syllabus=serialize_syllabus(db, syl),
        coverage_percent=bundle["coverage_percent"],
        overall_mastery=bundle["overall_mastery"],
        predictive_score=bundle["predictive_score"],
        weak_topics=bundle["weak_topics"],
        root_cause_blockers=bundle["root_cause_blockers"],
        weekly_progression=bundle["mastery_history"],
        read_only=True,
    )


@router.get("/forgetting-curve")
def get_forgetting_curve(
    syllabus_id: str | None = Query(default=None),
    simulate_days_elapsed: int = Query(default=0, ge=0, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return Ebbinghaus retention metrics and 30-day decay curves for the active syllabus."""
    syl = resolve_syllabus_for_user(db, user, syllabus_id=syllabus_id, write=False)
    eval_dt = datetime.now(timezone.utc) + timedelta(days=simulate_days_elapsed)
    topics = {
        t.id: t for t in db.query(SyllabusTopic).filter_by(syllabus_id=syl.id).all()
    }
    mastery_rows = (
        db.query(TopicMastery)
        .filter_by(student_id=syl.student_id, syllabus_id=syl.id)
        .all()
    )

    items: list[dict[str, Any]] = []
    for row in mastery_rows:
        t = topics.get(row.topic_id)
        if t is None:
            continue
        ret, stab = compute_retention(
            row.last_practiced_at,
            eval_dt,
            float(row.mastery_score),
            int(row.review_count),
        )
        items.append(
            {
                "topic_id": row.topic_id,
                "topic_code": t.topic_code,
                "title": t.title,
                "mastery_score": round(float(row.mastery_score), 1),
                "retention_score": ret,
                "stability_days": stab,
                "review_count": int(row.review_count),
                "at_risk": bool(row.last_practiced_at is not None and ret < 0.65),
            }
        )

    # Sort lowest retention first so forgetting alerts rise to the top
    items.sort(key=lambda x: x["retention_score"])

    # Aggregate 0..30 day theoretical retention curve comparing weak vs strong stability
    curve_series = []
    avg_stability = round(
        sum(i["stability_days"] for i in items) / max(1, len(items)), 2
    )
    for day in (0, 1, 3, 5, 7, 10, 14, 21, 30):
        future = datetime.now(timezone.utc) + timedelta(days=day)
        anchor = datetime.now(timezone.utc)
        avg_ret, _ = compute_retention(anchor, future, 70.0, 1)
        weak_ret, _ = compute_retention(anchor, future, 45.0, 0)
        strong_ret, _ = compute_retention(anchor, future, 85.0, 3)
        curve_series.append(
            {
                "day": day,
                "label": f"Day {day}",
                "baseline_retention": round(avg_ret * 100, 1),
                "weak_topic_retention": round(weak_ret * 100, 1),
                "reinforced_retention": round(strong_ret * 100, 1),
            }
        )

    return {
        "syllabus_id": syl.id,
        "simulate_days_elapsed": simulate_days_elapsed,
        "avg_stability_days": avg_stability,
        "topics": items,
        "curve_series": curve_series,
    }
