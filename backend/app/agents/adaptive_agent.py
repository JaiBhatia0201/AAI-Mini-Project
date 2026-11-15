"""Agent 9: Deterministic Adaptive Planner Re-Scheduler & AdaptationDiff Builder."""

from datetime import date, timedelta
import json
import time
from typing import Any
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.spaced_repetition import next_spaced_intervals
from app.models import PlanAdaptation, StudyPlanItem, SyllabusTopic, TopicMastery


def run_adaptive_agent(db: Session, state: TutorState) -> TutorState:
    """Insert remedial/blocker tasks or Day 3/7/14/30 spaced reviews; strictly in-memory if persist=False."""
    started = time.perf_counter()
    student_id = state["student_id"]
    syllabus_id = state["syllabus_id"]
    persist = bool(state.get("persist", True))

    weak_topics = list(state.get("weak_topics") or [])
    blockers = list(state.get("root_cause_blockers") or [])
    decay_alerts = list(state.get("decay_alerts") or [])
    topic_groups = state.get("topic_attempt_groups") or {}

    topics = {
        t.id: t for t in db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).all()
    }
    mastery_by_tid = {
        m.topic_id: m
        for m in db.query(TopicMastery)
        .filter_by(student_id=student_id, syllabus_id=syllabus_id)
        .all()
    }

    today = date.today()
    sim_offset = int(state.get("simulate_days_elapsed") or 0)
    eval_base_date = today + timedelta(days=sim_offset)
    changes: list[dict[str, Any]] = []
    new_plan_rows: list[StudyPlanItem] = []

    if state.get("remediation_required"):
        # 1) Schedule upstream prerequisite root-cause blockers first (Day 0/1)
        for idx, b_tid in enumerate(blockers[:3]):
            t = topics.get(b_tid)
            label = f"{t.topic_code}: {t.title}" if t else b_tid
            reason = f"Root-cause prerequisite blocker remediation ({label})"
            changes.append(
                {
                    "action": "insert",
                    "task_type": "revision",
                    "topic_id": b_tid,
                    "topic_code": t.topic_code if t else b_tid,
                    "day_offset": idx,
                    "reason": reason,
                }
            )
            if persist:
                new_plan_rows.append(
                    StudyPlanItem(
                        student_id=student_id,
                        syllabus_id=syllabus_id,
                        topic_id=b_tid,
                        scheduled_date=today + timedelta(days=idx),
                        day_number=idx + 1,
                        task_type="revision",
                        duration_hours=1.5,
                        status="pending",
                        adaptation_reason=reason,
                    )
                )

        # 2) Insert remedial practice + re-test + Day 1/2 pull-forward for weak or decaying topics
        priority_targets = list(dict.fromkeys(weak_topics + [a["topic_id"] for a in decay_alerts[:3]]))
        for tid in priority_targets[:4]:
            t = topics.get(tid)
            m_row = mastery_by_tid.get(tid)
            m_val = float(m_row.mastery_score) if m_row else 45.0
            r_val = float(m_row.retention_score) if m_row else 0.5
            intervals = next_spaced_intervals(m_val, r_val, eval_base_date)

            for offset, sched_dt, ttype in intervals[:3]:
                reason = (
                    f"Remedial pull-forward (mastery {m_val:.0f}%, retention {r_val:.2f})"
                    if offset <= 2
                    else f"Follow-up Day +{offset} spaced retention check"
                )
                changes.append(
                    {
                        "action": "insert",
                        "task_type": ttype,
                        "topic_id": tid,
                        "topic_code": t.topic_code if t else tid,
                        "day_offset": offset,
                        "reason": reason,
                    }
                )
                if persist:
                    new_plan_rows.append(
                        StudyPlanItem(
                            student_id=student_id,
                            syllabus_id=syllabus_id,
                            topic_id=tid,
                            scheduled_date=sched_dt,
                            day_number=offset + 1,
                            task_type=ttype,
                            duration_hours=1.0 if ttype != "practice" else 1.5,
                            status="pending",
                            adaptation_reason=reason,
                        )
                    )

        # Add verification re-test checkpoint for weak assessed topics
        for tid in weak_topics[:2]:
            t = topics.get(tid)
            reason = "Follow-up verification quiz before advancing dependents"
            changes.append(
                {
                    "action": "insert",
                    "task_type": "assessment",
                    "topic_id": tid,
                    "topic_code": t.topic_code if t else tid,
                    "day_offset": 3,
                    "reason": reason,
                }
            )
            if persist:
                new_plan_rows.append(
                    StudyPlanItem(
                        student_id=student_id,
                        syllabus_id=syllabus_id,
                        topic_id=tid,
                        scheduled_date=today + timedelta(days=3),
                        day_number=4,
                        task_type="assessment",
                        duration_hours=0.75,
                        status="pending",
                        adaptation_reason=reason,
                    )
                )

        summary = (
            f"Adaptive intervention triggered: prioritized {len(blockers)} prerequisite blockers, "
            f"{len(weak_topics)} weak topics, and {len(decay_alerts)} retention-decay alerts."
        )
    else:
        # Target met: schedule Day 3/7/14/30 spaced repetition checkpoints
        for tid in list(topic_groups.keys())[:3]:
            t = topics.get(tid)
            m_row = mastery_by_tid.get(tid)
            m_val = float(m_row.mastery_score) if m_row else 78.0
            rev_c = int(m_row.review_count) if m_row else 0
            intervals = next_spaced_intervals(m_val, 1.0, eval_base_date, review_count=rev_c)
            for offset, sched_dt, ttype in intervals:
                reason = f"Day +{offset} spaced repetition checkpoint (target met)"
                changes.append(
                    {
                        "action": "insert",
                        "task_type": ttype,
                        "topic_id": tid,
                        "topic_code": t.topic_code if t else tid,
                        "day_offset": offset,
                        "reason": reason,
                    }
                )
                if persist:
                    new_plan_rows.append(
                        StudyPlanItem(
                            student_id=student_id,
                            syllabus_id=syllabus_id,
                            topic_id=tid,
                            scheduled_date=sched_dt,
                            day_number=offset + 1,
                            task_type=ttype,
                            duration_hours=0.5,
                            status="pending",
                            adaptation_reason=reason,
                        )
                    )
        summary = (
            "Performance met mastery target; scheduled Day +3/+7/+14/+30 spaced repetition checkpoints."
            if changes
            else "All active topics remain above mastery and retention thresholds."
        )

    blocker_labels = [
        f"{topics[b].topic_code} ({mastery_by_tid[b].mastery_score:.0f}%)"
        if b in topics and b in mastery_by_tid
        else b
        for b in blockers
    ]

    adaptation_id: str | None = None
    if persist and new_plan_rows:
        targeted_ids = {row.topic_id for row in new_plan_rows}
        db.query(StudyPlanItem).filter(
            StudyPlanItem.student_id == student_id,
            StudyPlanItem.syllabus_id == syllabus_id,
            StudyPlanItem.topic_id.in_(targeted_ids),
            StudyPlanItem.status == "pending",
        ).update({"status": "rescheduled"}, synchronize_session=False)
        db.add_all(new_plan_rows)

        adp = PlanAdaptation(
            student_id=student_id,
            syllabus_id=syllabus_id,
            trigger_assessment_id=state.get("assessment_id"),
            weak_topics_json=json.dumps(weak_topics),
            summary=summary,
            changes_json=json.dumps(changes),
        )
        db.add(adp)
        db.flush()
        adaptation_id = adp.id

    state["adaptation_diff"] = {
        "id": adaptation_id,
        "summary": summary,
        "weak_topics": weak_topics,
        "root_cause_blockers": blocker_labels,
        "changes": changes,
    }

    record_trace(
        db=db,
        state=state,
        agent_number=9,
        agent_name="Adaptive Planner Agent",
        execution_mode="deterministic",
        started_at=started,
        input_summary=f"remediation={bool(state.get('remediation_required'))}, persist={persist}",
        output_summary=f"Generated {len(changes)} schedule updates (persisted={persist})",
    )
    return state
