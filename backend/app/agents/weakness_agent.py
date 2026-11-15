"""Agent 8: Deterministic Weakness, Ebbinghaus Retention, and Ancestor Blocker Detector."""

from datetime import datetime, timezone
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.forgetting_curve import compute_retention, evaluate_retention_alerts
from app.engines.mastery import (
    classify_mastery_status,
    detect_weakness,
    update_topic_mastery,
)
from app.engines.syllabus_dag import build_nx_graph, find_root_cause_blockers
from app.models import Assessment, QuestionAttempt, SyllabusTopic, TopicMastery, TopicPrerequisite


def _parse_eval_time(raw_iso: str | None) -> datetime:
    if not raw_iso:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(raw_iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run_weakness_agent(db: Session, state: TutorState) -> TutorState:
    """Update EMA mastery (when persisted), evaluate Ebbinghaus decay, and isolate blockers."""
    started = time.perf_counter()
    student_id = state["student_id"]
    syllabus_id = state["syllabus_id"]
    persist = bool(state.get("persist", True))
    eval_dt = _parse_eval_time(state.get("eval_time_iso"))

    topics = db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).all()
    topic_lookup = {t.id: t for t in topics}
    edges = db.query(TopicPrerequisite).filter_by(syllabus_id=syllabus_id).all()
    mastery_rows = (
        db.query(TopicMastery)
        .filter_by(student_id=student_id, syllabus_id=syllabus_id)
        .all()
    )
    mastery_by_tid = {m.topic_id: m for m in mastery_rows}
    topic_groups = state.get("topic_attempt_groups") or {}

    weak_topics: list[str] = []
    blockers: list[str] = []

    if persist and topic_groups:
        # Compute EMA updates cleanly and check drop / consecutive miss rules
        prior_assessments = (
            db.query(Assessment)
            .filter_by(student_id=student_id, syllabus_id=syllabus_id)
            .order_by(Assessment.created_at)
            .all()
        )
        recent_acc_list = [float(a.accuracy) for a in prior_assessments if a.accuracy is not None][-2:]

        for tid, attempts in topic_groups.items():
            row = mastery_by_tid.get(tid)
            if row is None:
                continue
            new_m = update_topic_mastery(float(row.mastery_score), attempts)
            recent_misses = (
                db.query(QuestionAttempt)
                .filter_by(student_id=student_id, syllabus_id=syllabus_id, topic_id=tid)
                .order_by(QuestionAttempt.created_at.desc())
                .limit(3)
                .all()
            )
            streak_miss = 0
            for att in recent_misses:
                if not att.is_correct:
                    streak_miss += 1
                else:
                    break

            is_weak, _ = detect_weakness(new_m, recent_accuracies=recent_acc_list, consecutive_misses=streak_miss)
            row.mastery_score = new_m
            row.last_practiced_at = eval_dt
            row.review_count = int(row.review_count) + (1 if not is_weak else 0)
            retention, stability = compute_retention(
                last_practiced_at=eval_dt,
                eval_time=eval_dt,
                mastery_score=new_m,
                review_count=int(row.review_count),
            )
            row.retention_score = retention
            row.stability_days = stability
            row.status = "weak" if is_weak else classify_mastery_status(new_m, has_activity=True)
            if is_weak:
                weak_topics.append(tid)
        db.flush()
    else:
        for tid, m in mastery_by_tid.items():
            if float(m.mastery_score) < 60.0 or m.status == "weak":
                weak_topics.append(tid)

    # Evaluate Ebbinghaus retention decay using eval_dt (real 'now' or in-memory simulated future)
    decay_alerts = evaluate_retention_alerts(mastery_rows, topic_lookup, eval_time=eval_dt)
    if persist and not topic_groups:
        # Refresh persisted retention scores on real daily check only (NEVER on simulation!)
        for row in mastery_rows:
            if row.last_practiced_at is not None:
                ret, stab = compute_retention(
                    row.last_practiced_at,
                    eval_dt,
                    float(row.mastery_score),
                    int(row.review_count),
                )
                row.retention_score = ret
                row.stability_days = stab
        db.flush()

    mastery_map = {tid: float(row.mastery_score) for tid, row in mastery_by_tid.items()}
    graph = build_nx_graph(topics, edges)
    target_checks = weak_topics if topic_groups else [a["topic_id"] for a in decay_alerts]
    for tid in target_checks:
        found = find_root_cause_blockers(graph, tid, mastery_map, threshold=65.0)
        for b in found:
            if b not in blockers:
                blockers.append(b)

    state["weak_topics"] = weak_topics
    state["root_cause_blockers"] = blockers
    state["decay_alerts"] = decay_alerts
    state["remediation_required"] = bool(weak_topics or decay_alerts)

    record_trace(
        db=db,
        state=state,
        agent_number=8,
        agent_name="Weakness Detection Agent",
        execution_mode="deterministic",
        started_at=started,
        input_summary=f"persist={persist}, eval_at={eval_dt.date().isoformat()}",
        output_summary=(
            f"Weak={len(weak_topics)}, DecayAlerts={len(decay_alerts)}, "
            f"AncestorBlockers={len(blockers)}"
        ),
    )
    return state
