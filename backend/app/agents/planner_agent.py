"""Agent 4: Topological Study Planner scheduling tasks within daily hour budgets."""

from datetime import date, timedelta
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.syllabus_dag import build_nx_graph, topological_order
from app.models import (
    StudentProfile,
    StudyPlanItem,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
)


def run_planner_agent(db: Session, state: TutorState) -> TutorState:
    """Build or refresh the initial topologically valid study schedule for a syllabus."""
    started = time.perf_counter()
    student_id = state["student_id"]
    syllabus_id = state["syllabus_id"]

    profile = db.get(StudentProfile, student_id)
    syllabus = db.get(Syllabus, syllabus_id)
    daily_hours = float(profile.daily_hours if profile else 3.0)
    topics = (
        db.query(SyllabusTopic)
        .filter_by(syllabus_id=syllabus_id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )
    edges = db.query(TopicPrerequisite).filter_by(syllabus_id=syllabus_id).all()
    mastery_rows = (
        db.query(TopicMastery)
        .filter_by(student_id=student_id, syllabus_id=syllabus_id)
        .all()
    )
    mastery_map = {m.topic_id: float(m.mastery_score) for m in mastery_rows}

    # Replace only existing pending initial items cleanly so completed history remains intact
    db.query(StudyPlanItem).filter_by(
        student_id=student_id,
        syllabus_id=syllabus_id,
        status="pending",
    ).delete(synchronize_session=False)

    graph = build_nx_graph(topics, edges)
    priorities = {
        t.id: max(0.5, (105.0 - mastery_map.get(t.id, 40.0)) / 25.0) * float(t.exam_weightage)
        for t in topics
    }
    ordered_ids = topological_order(graph, priority_weights=priorities)
    topic_lookup = {t.id: t for t in topics}

    horizon = max(7, min(30, int(syllabus.days_remaining if syllabus else 30)))
    today = date.today()
    day_idx = 0
    hours_used_today = 0.0
    created_items: list[StudyPlanItem] = []

    for tid in ordered_ids:
        t = topic_lookup.get(tid)
        if t is None:
            continue
        m_val = mastery_map.get(tid, 40.0)
        task_type = "revision" if m_val >= 72.0 else "learn"
        dur = round(min(daily_hours, max(1.0, float(t.estimated_hours) * 0.5)), 1)

        if hours_used_today + dur > daily_hours and hours_used_today > 0:
            day_idx += 1
            hours_used_today = 0.0
        if day_idx >= horizon:
            break

        reason = (
            f"Priority baseline topic (mastery {m_val:.0f}%)"
            if m_val < 60.0
            else "Topological syllabus roadmap milestone"
        )
        created_items.append(
            StudyPlanItem(
                student_id=student_id,
                syllabus_id=syllabus_id,
                topic_id=tid,
                scheduled_date=today + timedelta(days=day_idx),
                day_number=day_idx + 1,
                task_type=task_type,
                duration_hours=dur,
                status="pending",
                adaptation_reason=reason,
            )
        )
        hours_used_today += dur

        # Schedule paired practice right after learning weak/unstarted topics
        if m_val < 75.0 and day_idx + 1 < horizon:
            p_day = day_idx if (hours_used_today + 1.0 <= daily_hours) else day_idx + 1
            created_items.append(
                StudyPlanItem(
                    student_id=student_id,
                    syllabus_id=syllabus_id,
                    topic_id=tid,
                    scheduled_date=today + timedelta(days=p_day),
                    day_number=p_day + 1,
                    task_type="practice",
                    duration_hours=1.0,
                    status="pending",
                    adaptation_reason="Paired practice reinforcement",
                )
            )
            if p_day == day_idx:
                hours_used_today += 1.0
            else:
                day_idx = p_day
                hours_used_today = 1.0

    db.add_all(created_items)
    db.flush()

    record_trace(
        db=db,
        state=state,
        agent_number=4,
        agent_name="Study Planner Agent",
        execution_mode="deterministic",
        started_at=started,
        input_summary=f"topics={len(topics)}, daily_hours={daily_hours}",
        output_summary=f"Scheduled {len(created_items)} DAG-ordered study items across {day_idx + 1} days",
    )
    return state
