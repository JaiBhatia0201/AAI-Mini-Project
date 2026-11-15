"""Agent 1: Deterministic Student Profiling & Diagnostic Baseline Calibration."""

from datetime import datetime, timezone
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.mastery import SELF_RATING_PRIORS, classify_mastery_status, clamp
from app.models import Assessment, Question, QuestionAttempt, StudentProfile, Syllabus, TopicMastery


def run_profiling_agent(
    db: Session,
    state: TutorState,
    mode: str = "profile_update",
) -> TutorState:
    """Calibrate learner preferences, diagnostic answers, and baseline topic priors."""
    started = time.perf_counter()
    profile = db.get(StudentProfile, state["student_id"])
    syllabus_id = state.get("syllabus_id")
    syllabus = db.get(Syllabus, syllabus_id) if syllabus_id else None

    if profile is not None:
        if state.get("daily_hours") is not None:
            profile.daily_hours = float(state["daily_hours"])
        if state.get("learning_style"):
            profile.learning_style = str(state["learning_style"])

    if syllabus is not None:
        if state.get("target_score") is not None:
            syllabus.target_score = float(state["target_score"])
        if state.get("days_remaining") is not None:
            syllabus.days_remaining = int(state["days_remaining"])

    updated_count = 0
    if mode == "diagnostic" and syllabus is not None and profile is not None:
        mastery_rows = {
            m.topic_id: m
            for m in db.query(TopicMastery)
            .filter_by(student_id=profile.id, syllabus_id=syllabus.id)
            .all()
        }
        now = datetime.now(timezone.utc)
        diag_answers = state.get("diagnostic_answers") or []
        self_ratings = state.get("self_ratings") or {}

        if diag_answers:
            q_lookup = {
                q.id: q
                for q in db.query(Question).filter_by(syllabus_id=syllabus.id).all()
            }
            topic_hits: dict[str, list[bool]] = {}
            assessment = Assessment(
                student_id=profile.id,
                syllabus_id=syllabus.id,
                title=f"Diagnostic Calibration: {syllabus.exam_name}",
                assessment_type="diagnostic",
                max_score=float(syllabus.max_score),
            )
            db.add(assessment)
            db.flush()

            correct_total = 0
            time_total = 0
            for ans in diag_answers:
                q = q_lookup.get(ans["question_id"])
                if q is None:
                    continue
                is_ok = str(ans.get("selected_answer", "")).strip().lower() == q.correct_answer.strip().lower()
                t_sec = int(ans.get("time_taken_sec", 30))
                correct_total += 1 if is_ok else 0
                time_total += t_sec
                topic_hits.setdefault(q.topic_id, []).append(is_ok)
                db.add(
                    QuestionAttempt(
                        assessment_id=assessment.id,
                        student_id=profile.id,
                        syllabus_id=syllabus.id,
                        topic_id=q.topic_id,
                        question_id=q.id,
                        selected_answer=str(ans.get("selected_answer", "")),
                        is_correct=is_ok,
                        time_taken_sec=t_sec,
                        created_at=now,
                    )
                )

            n_graded = max(1, sum(len(v) for v in topic_hits.values()))
            acc = round(100.0 * correct_total / n_graded, 2)
            assessment.accuracy = acc
            assessment.score = round(float(syllabus.max_score) * (acc / 100.0), 2)
            assessment.time_taken_sec = time_total

            for tid, hits in topic_hits.items():
                if tid in mastery_rows:
                    topic_acc = 100.0 * (sum(1 for h in hits if h) / len(hits))
                    score_prior = clamp(0.75 * topic_acc + 0.25 * 40.0, 25.0, 90.0)
                    row = mastery_rows[tid]
                    row.mastery_score = round(score_prior, 2)
                    row.status = classify_mastery_status(score_prior, has_activity=True)
                    row.last_practiced_at = now
                    updated_count += 1

        # Apply explicit self-ratings (or default 40.0 prior for unassessed topics)
        for tid, row in mastery_rows.items():
            if tid in self_ratings:
                prior = SELF_RATING_PRIORS.get(self_ratings[tid], 40.0)
                row.mastery_score = prior
                row.status = classify_mastery_status(prior, has_activity=True)
                row.last_practiced_at = now
                updated_count += 1

    db.flush()
    out_summary = (
        f"Calibrated diagnostic priors across {updated_count} topics"
        if mode == "diagnostic"
        else f"Profile validated (style={profile.learning_style if profile else 'visual'}, daily_hours={profile.daily_hours if profile else 3.0})"
    )
    record_trace(
        db=db,
        state=state,
        agent_number=1,
        agent_name="Student Profiling Agent",
        execution_mode="deterministic",
        started_at=started,
        input_summary=f"mode={mode}, syllabus={syllabus_id}",
        output_summary=out_summary,
    )
    return state
