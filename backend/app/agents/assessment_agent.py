"""Agent 7: Deterministic Assessment Grader computing accuracy, score, and pacing."""

from datetime import datetime, timezone
import time
from typing import Any
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.models import Assessment, Question, QuestionAttempt, Syllabus


def run_assessment_agent(db: Session, state: TutorState) -> TutorState:
    """Grade submitted answers deterministically and persist attempt records."""
    started = time.perf_counter()
    student_id = state["student_id"]
    syllabus_id = state["syllabus_id"]
    assessment_id = state["assessment_id"]
    submitted = state.get("submitted_answers") or []

    assessment = db.get(Assessment, assessment_id)
    syllabus = db.get(Syllabus, syllabus_id)
    if assessment is None or assessment.syllabus_id != syllabus_id:
        raise ValueError("Assessment does not belong to the active syllabus.")

    q_lookup = {
        q.id: q for q in db.query(Question).filter_by(syllabus_id=syllabus_id).all()
    }
    now = datetime.now(timezone.utc)

    results: list[dict[str, Any]] = []
    topic_groups: dict[str, list[dict[str, Any]]] = {}
    correct_count = 0
    total_time = 0

    for item in submitted:
        qid = item["question_id"]
        q = q_lookup.get(qid)
        if q is None:
            continue
        selected = str(item.get("selected_answer", ""))
        t_sec = int(item.get("time_taken_sec", 30))
        is_ok = selected.strip().lower() == q.correct_answer.strip().lower()
        correct_count += 1 if is_ok else 0
        total_time += t_sec

        db.add(
            QuestionAttempt(
                assessment_id=assessment.id,
                student_id=student_id,
                syllabus_id=syllabus_id,
                topic_id=q.topic_id,
                question_id=q.id,
                selected_answer=selected,
                is_correct=is_ok,
                time_taken_sec=t_sec,
                created_at=now,
            )
        )
        results.append(
            {
                "question_id": q.id,
                "topic_id": q.topic_id,
                "selected_answer": selected,
                "correct_answer": q.correct_answer,
                "is_correct": is_ok,
                "explanation": q.explanation,
                "time_taken_sec": t_sec,
            }
        )
        topic_groups.setdefault(q.topic_id, []).append(
            {
                "question_id": q.id,
                "difficulty": q.difficulty,
                "is_correct": is_ok,
                "time_taken_sec": t_sec,
                "expected_time_sec": q.expected_time_sec,
            }
        )

    total_graded = max(1, len(results))
    accuracy = round(100.0 * correct_count / total_graded, 2)
    max_score = float(assessment.max_score or (syllabus.max_score if syllabus else 100.0))
    scaled_score = round(max_score * (accuracy / 100.0), 2)

    assessment.accuracy = accuracy
    assessment.score = scaled_score
    assessment.time_taken_sec = total_time
    db.flush()

    state["results"] = results
    state["topic_attempt_groups"] = topic_groups
    state["accuracy"] = accuracy
    state["score"] = scaled_score
    state["max_score_val"] = max_score

    record_trace(
        db=db,
        state=state,
        agent_number=7,
        agent_name="Assessment Agent",
        execution_mode="deterministic",
        started_at=started,
        input_summary=f"assessment={assessment_id}, answers={len(results)}",
        output_summary=f"Graded {correct_count}/{len(results)} correct ({accuracy:.1f}%, score {scaled_score}/{max_score})",
    )
    return state
