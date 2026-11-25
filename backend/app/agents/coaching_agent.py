"""Agent 10: Grounded Motivation & Coaching Agent backed by predictive readiness metrics."""

import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.predictive_score import compute_predictive_score
from app.models import Assessment, StudentProfile, Syllabus, SyllabusTopic, TopicMastery
from app.services.llm_client import invoke_llm_text


def run_coaching_agent(db: Session, state: TutorState) -> TutorState:
    """Produce concise metric-grounded motivational coaching without hallucinated figures."""
    started = time.perf_counter()
    student_id = state["student_id"]
    syllabus_id = state["syllabus_id"]

    profile = db.get(StudentProfile, student_id)
    syllabus = db.get(Syllabus, syllabus_id)
    topics = db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).all()
    mastery_rows = (
        db.query(TopicMastery)
        .filter_by(student_id=student_id, syllabus_id=syllabus_id)
        .all()
    )
    assessments = (
        db.query(Assessment)
        .filter_by(student_id=student_id, syllabus_id=syllabus_id)
        .order_by(Assessment.created_at)
        .all()
    )

    m_map = {m.topic_id: float(m.mastery_score) for m in mastery_rows}
    r_map = {m.topic_id: float(m.retention_score) for m in mastery_rows}
    pred = compute_predictive_score(
        topics=topics,
        mastery_map=m_map,
        retention_map=r_map,
        history_scores=[float(a.score) for a in assessments],
        days_remaining=int(syllabus.days_remaining if syllabus else 60),
        target_score=float(syllabus.target_score if syllabus else 75.0),
        max_score=float(syllabus.max_score if syllabus else 100.0),
    )

    weak_count = len(state.get("weak_topics") or [])
    alert_count = len(state.get("decay_alerts") or [])
    raw_blockers = state.get("root_cause_blockers") or []
    topic_lookup = {t.id: t for t in topics}
    blockers = [
        f"{topic_lookup[b].topic_code}: {topic_lookup[b].title}"
        if b in topic_lookup
        else (b.split("::", 1)[-1] if "::" in b else b)
        for b in raw_blockers
    ]
    exam_name = syllabus.exam_name if syllabus else "your exam"
    streak = int(profile.study_streak if profile else 0)

    prompt = (
        f"Exam: {exam_name}\n"
        f"Estimated Current Score: {pred['current_estimated_score']} / {pred['max_score']} "
        f"(Projected: {pred['projected_estimated_score']} / {pred['max_score']}, Target: {pred['target_score']})\n"
        f"Readiness Band: {pred['readiness_band']}\n"
        f"Positive Study Consistency Streak: {streak} consecutive active day(s)\n"
        f"Weak topics count: {weak_count}, Forgetting alerts count: {alert_count}\n"
        f"Priority prerequisite topics to review first: {blockers[:3] if blockers else 'None'}\n"
        f"Mention {exam_name} and write 2-3 clear, encouraging, human-readable sentences referencing ONLY those exact numbers "
        f"and recommending the immediate next step. Do NOT include raw markdown stars (**), internal IDs, or call the study streak negative."
    )
    llm_res = invoke_llm_text(
        system_prompt="You are a supportive academic coach. Write clean, readable plain English citing exact provided metrics; never invent scores, ranks, or internal IDs.",
        user_prompt=prompt,
    )

    if llm_res.used_llm and llm_res.content:
        message = llm_res.content
        exec_mode = "llm"
    else:
        if state.get("is_simulation"):
            message = (
                f"Simulation Preview (+{state.get('simulate_days_elapsed', 0)} days): "
                f"Estimated readiness stands at {pred['current_estimated_score']} / {pred['max_score']} "
                f"with {alert_count} topics projected to need spaced review before retention slips."
            )
        elif weak_count or alert_count:
            blocker_note = f" Start with prerequisite blocker(s) ({', '.join(blockers[:2])}) first." if blockers else ""
            message = (
                f"Estimated {exam_name} readiness is {pred['current_estimated_score']} / {pred['max_score']} "
                f"(projected {pred['projected_estimated_score']} / {pred['max_score']}). "
                f"Closing {weak_count} weak topic(s) and {alert_count} fading review(s) keeps you moving toward "
                f"your {pred['target_score']} goal.{blocker_note}"
            )
        else:
            message = (
                f"Solid consistency ({streak}-day streak)! Estimated {exam_name} readiness is "
                f"{pred['current_estimated_score']} / {pred['max_score']} (projected {pred['projected_estimated_score']} "
                f"/ {pred['max_score']}, status: {pred['readiness_band']}). Keep following your spaced checkpoints."
            )
        exec_mode = "fallback"

    state["coaching_message"] = message
    record_trace(
        db=db,
        state=state,
        agent_number=10,
        agent_name="Motivation & Coaching Agent",
        execution_mode=exec_mode,
        started_at=started,
        input_summary=f"band={pred['readiness_band']}, score={pred['current_estimated_score']}/{pred['max_score']}",
        output_summary=message[:160],
    )
    return state
