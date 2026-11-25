"""Typed LangGraph TutorState contract and persisted/in-memory trace logger."""

from datetime import datetime, timezone
import time
from typing import Any, TypedDict
from sqlalchemy.orm import Session

from app.models import AgentExecutionLog


class TutorState(TypedDict, total=False):
    """Shared state dictionary passed across Agent 11 LangGraph StateGraph nodes."""

    run_id: str
    workflow_name: str
    student_id: str
    syllabus_id: str
    persist: bool
    is_simulation: bool
    simulate_days_elapsed: int
    eval_time_iso: str

    # Onboarding & profiling
    onboard_mode: str
    pdf_bytes: bytes
    pdf_filename: str
    title: str
    exam_name: str
    target_score: float
    max_score: float
    days_remaining: int
    daily_hours: float
    learning_style: str
    diagnostic_answers: list[dict[str, Any]]
    self_ratings: dict[str, str]
    diagnostic_questions: list[dict[str, Any]]
    topics_count: int
    prerequisites_count: int
    retrieval_mode: str

    # Teaching & practice
    topic_id: str | None
    tutor_question: str | None
    force_web: bool
    lesson_payload: dict[str, Any]
    practice_questions: list[dict[str, Any]]

    # Assessment, weakness & adaptive planning
    assessment_id: str
    submitted_answers: list[dict[str, Any]]
    results: list[dict[str, Any]]
    topic_attempt_groups: dict[str, list[dict[str, Any]]]
    score: float
    max_score_val: float
    accuracy: float
    weak_topics: list[str]
    root_cause_blockers: list[str]
    decay_alerts: list[dict[str, Any]]
    remediation_required: bool
    adaptation_diff: dict[str, Any] | None
    coaching_message: str

    # Step-by-step trace records (persisted on Flows A-E, memory-only on Flow F)
    traces: list[dict[str, Any]]


def record_trace(
    db: Session | None,
    state: TutorState,
    agent_number: int,
    agent_name: str,
    execution_mode: str,
    started_at: float,
    input_summary: str,
    output_summary: str,
    status: str = "completed",
    error_message: str | None = None,
) -> dict[str, Any]:
    """Create a structured agent trace and persist only when state['persist'] is True."""
    now = datetime.now(timezone.utc)
    latency_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
    persist = bool(state.get("persist", True))
    syllabus_id = state.get("syllabus_id")
    effective_mode = "simulation" if state.get("is_simulation") else execution_mode

    record = {
        "run_id": state["run_id"],
        "workflow_name": state["workflow_name"],
        "agent_number": agent_number,
        "agent_name": agent_name,
        "execution_mode": effective_mode,
        "status": status,
        "latency_ms": latency_ms,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "error_message": error_message,
        "created_at": now,
    }

    if persist and db is not None:
        db.add(
            AgentExecutionLog(
                run_id=record["run_id"],
                student_id=state["student_id"],
                syllabus_id=syllabus_id,
                workflow_name=record["workflow_name"],
                agent_number=agent_number,
                agent_name=agent_name,
                execution_mode=effective_mode,
                status=status,
                latency_ms=latency_ms,
                input_summary=input_summary,
                output_summary=output_summary,
                error_message=error_message,
                created_at=now,
            )
        )
        db.flush()

    traces = list(state.get("traces", []))
    traces.append(record)
    state["traces"] = traces
    return record
