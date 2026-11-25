"""Agent 11: LangGraph StateGraph Master Orchestrator across all 6 system workflows."""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.adaptive_agent import run_adaptive_agent
from app.agents.assessment_agent import run_assessment_agent
from app.agents.coaching_agent import run_coaching_agent
from app.agents.planner_agent import run_planner_agent
from app.agents.profiling_agent import run_profiling_agent
from app.agents.question_agent import run_question_agent
from app.agents.resource_agent import run_resource_agent
from app.agents.state import TutorState
from app.agents.syllabus_agent import run_syllabus_agent
from app.agents.teaching_agent import run_teaching_agent
from app.agents.weakness_agent import run_weakness_agent


def _db_from_config(config: RunnableConfig) -> Session:
    """Retrieve the active SQLAlchemy Session from LangGraph RunnableConfig."""
    configurable = config.get("configurable") or {}
    db = configurable.get("db")
    if db is None:
        raise RuntimeError("LangGraph orchestrator requires 'db' inside RunnableConfig['configurable'].")
    return db


def _make_node(fn: Callable[[Session, TutorState], TutorState]) -> Callable[[TutorState, RunnableConfig], TutorState]:
    """Bind a database-aware domain agent function as a pure LangGraph StateGraph node."""

    def _node(state: TutorState, config: RunnableConfig) -> TutorState:
        db = _db_from_config(config)
        return fn(db, state)

    return _node


def _route_after_weakness(state: TutorState) -> str:
    """Conditional edge selecting remediation or spaced-repetition cadence."""
    return "remediate" if state.get("remediation_required") else "spaced_review"


def _route_daily_check(state: TutorState) -> str:
    """Conditional edge triggering adaptation only when weak topics or decay alerts exist."""
    return "remediate" if state.get("remediation_required") else "healthy"


def _build_onboard_graph():
    g = StateGraph(TutorState)
    g.add_node("agent_2_syllabus", _make_node(run_syllabus_agent))
    g.add_node("agent_1_profiling", _make_node(lambda db, st: run_profiling_agent(db, st, mode="profile_update")))
    g.add_node("agent_3_resources", _make_node(run_resource_agent))
    g.add_node("agent_4_planner", _make_node(run_planner_agent))
    g.add_node("agent_6_diagnostic_questions", _make_node(lambda db, st: run_question_agent(db, st, mode="diagnostic")))
    g.add_node("agent_10_coaching", _make_node(run_coaching_agent))

    g.add_edge(START, "agent_2_syllabus")
    g.add_edge("agent_2_syllabus", "agent_1_profiling")
    g.add_edge("agent_1_profiling", "agent_3_resources")
    g.add_edge("agent_3_resources", "agent_4_planner")
    g.add_edge("agent_4_planner", "agent_6_diagnostic_questions")
    g.add_edge("agent_6_diagnostic_questions", "agent_10_coaching")
    g.add_edge("agent_10_coaching", END)
    return g.compile()


def _build_diagnostic_graph():
    g = StateGraph(TutorState)
    g.add_node("agent_1_diagnostic", _make_node(lambda db, st: run_profiling_agent(db, st, mode="diagnostic")))
    g.add_node("agent_4_planner", _make_node(run_planner_agent))
    g.add_node("agent_8_weakness", _make_node(run_weakness_agent))
    g.add_node("agent_9_adaptive", _make_node(run_adaptive_agent))
    g.add_node("agent_10_coaching", _make_node(run_coaching_agent))

    g.add_edge(START, "agent_1_diagnostic")
    g.add_edge("agent_1_diagnostic", "agent_4_planner")
    g.add_edge("agent_4_planner", "agent_8_weakness")
    g.add_conditional_edges(
        "agent_8_weakness",
        _route_daily_check,
        {"remediate": "agent_9_adaptive", "healthy": "agent_10_coaching"},
    )
    g.add_edge("agent_9_adaptive", "agent_10_coaching")
    g.add_edge("agent_10_coaching", END)
    return g.compile()


def _build_study_session_graph():
    g = StateGraph(TutorState)
    g.add_node("agent_3_resources", _make_node(run_resource_agent))
    g.add_node("agent_5_teaching", _make_node(run_teaching_agent))
    g.add_node("agent_6_practice", _make_node(lambda db, st: run_question_agent(db, st, mode="practice")))
    g.add_node("agent_10_coaching", _make_node(run_coaching_agent))

    g.add_edge(START, "agent_3_resources")
    g.add_edge("agent_3_resources", "agent_5_teaching")
    g.add_edge("agent_5_teaching", "agent_6_practice")
    g.add_edge("agent_6_practice", "agent_10_coaching")
    g.add_edge("agent_10_coaching", END)
    return g.compile()


def _build_assessment_adapt_graph():
    g = StateGraph(TutorState)
    g.add_node("agent_7_assessment", _make_node(run_assessment_agent))
    g.add_node("agent_8_weakness", _make_node(run_weakness_agent))
    g.add_node("agent_9_remediate", _make_node(run_adaptive_agent))
    g.add_node("agent_9_spaced_review", _make_node(run_adaptive_agent))
    g.add_node("agent_10_coaching", _make_node(run_coaching_agent))

    g.add_edge(START, "agent_7_assessment")
    g.add_edge("agent_7_assessment", "agent_8_weakness")
    g.add_conditional_edges(
        "agent_8_weakness",
        _route_after_weakness,
        {"remediate": "agent_9_remediate", "spaced_review": "agent_9_spaced_review"},
    )
    g.add_edge("agent_9_remediate", "agent_10_coaching")
    g.add_edge("agent_9_spaced_review", "agent_10_coaching")
    g.add_edge("agent_10_coaching", END)
    return g.compile()


def _build_daily_check_graph():
    g = StateGraph(TutorState)
    g.add_node("agent_8_weakness", _make_node(run_weakness_agent))
    g.add_node("agent_9_adaptive", _make_node(run_adaptive_agent))
    g.add_node("agent_10_coaching", _make_node(run_coaching_agent))

    g.add_edge(START, "agent_8_weakness")
    g.add_conditional_edges(
        "agent_8_weakness",
        _route_daily_check,
        {"remediate": "agent_9_adaptive", "healthy": "agent_10_coaching"},
    )
    g.add_edge("agent_9_adaptive", "agent_10_coaching")
    g.add_edge("agent_10_coaching", END)
    return g.compile()


# Compile LangGraph pipelines once at import time
ONBOARD_SYLLABUS_GRAPH = _build_onboard_graph()
COMPLETE_DIAGNOSTIC_GRAPH = _build_diagnostic_graph()
STUDY_SESSION_GRAPH = _build_study_session_graph()
ASSESSMENT_ADAPT_GRAPH = _build_assessment_adapt_graph()
DAILY_CHECK_GRAPH = _build_daily_check_graph()
DEMO_SIMULATION_GRAPH = _build_daily_check_graph()


def _invoke_graph(graph: Any, db: Session, initial_state: TutorState) -> TutorState:
    """Invoke a compiled LangGraph pipeline with SQLAlchemy session in RunnableConfig."""
    return graph.invoke(initial_state, config={"configurable": {"db": db}})


def run_onboard_syllabus(
    db: Session,
    *,
    student_id: str,
    onboard_mode: str = "pdf_upload",
    pdf_bytes: bytes = b"",
    pdf_filename: str = "syllabus.pdf",
    title: str | None = None,
    exam_name: str | None = None,
    target_score: float = 75.0,
    max_score: float = 100.0,
    days_remaining: int = 60,
    daily_hours: float = 3.0,
    learning_style: str = "visual",
) -> TutorState:
    """Flow A: Ingest PDF or isolated GATE copy, build RAG/TF-IDF index, DAG plan, and diagnostic."""
    state: TutorState = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "workflow_name": "onboard_syllabus",
        "student_id": student_id,
        "persist": True,
        "is_simulation": False,
        "onboard_mode": onboard_mode,
        "pdf_bytes": pdf_bytes,
        "pdf_filename": pdf_filename,
        "title": title or "",
        "exam_name": exam_name or "",
        "target_score": target_score,
        "max_score": max_score,
        "days_remaining": days_remaining,
        "daily_hours": daily_hours,
        "learning_style": learning_style,
        "traces": [],
    }
    return _invoke_graph(ONBOARD_SYLLABUS_GRAPH, db, state)


def run_complete_diagnostic(
    db: Session,
    *,
    student_id: str,
    syllabus_id: str,
    diagnostic_answers: list[dict[str, Any]] | None = None,
    self_ratings: dict[str, str] | None = None,
) -> TutorState:
    """Flow B: Calibrate topic priors from diagnostic quiz + ratings and refine DAG plan."""
    state: TutorState = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "workflow_name": "complete_diagnostic",
        "student_id": student_id,
        "syllabus_id": syllabus_id,
        "persist": True,
        "is_simulation": False,
        "diagnostic_answers": diagnostic_answers or [],
        "self_ratings": self_ratings or {},
        "eval_time_iso": datetime.now(timezone.utc).isoformat(),
        "traces": [],
    }
    return _invoke_graph(COMPLETE_DIAGNOSTIC_GRAPH, db, state)


def run_study_session(
    db: Session,
    *,
    student_id: str,
    syllabus_id: str,
    topic_id: str | None = None,
    tutor_question: str | None = None,
    force_web: bool = False,
) -> TutorState:
    """Flow C: Grounded style-adapted lesson (or live web FAISS answer) + calibrated practice + coaching."""
    state: TutorState = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "workflow_name": "teach_and_practice",
        "student_id": student_id,
        "syllabus_id": syllabus_id,
        "topic_id": topic_id,
        "tutor_question": tutor_question,
        "force_web": force_web,
        "persist": True,
        "is_simulation": False,
        "traces": [],
    }
    return _invoke_graph(STUDY_SESSION_GRAPH, db, state)


def run_assessment_adaptation(
    db: Session,
    *,
    student_id: str,
    syllabus_id: str,
    assessment_id: str,
    submitted_answers: list[dict[str, Any]],
) -> TutorState:
    """Flow D: Grade assessment -> update mastery -> route remedial blocker vs spaced review."""
    state: TutorState = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "workflow_name": "assessment_adaptation",
        "student_id": student_id,
        "syllabus_id": syllabus_id,
        "assessment_id": assessment_id,
        "submitted_answers": submitted_answers,
        "persist": True,
        "is_simulation": False,
        "eval_time_iso": datetime.now(timezone.utc).isoformat(),
        "traces": [],
    }
    return _invoke_graph(ASSESSMENT_ADAPT_GRAPH, db, state)


def run_daily_check(
    db: Session,
    *,
    student_id: str,
    syllabus_id: str,
) -> TutorState:
    """Flow E: Real persisted Ebbinghaus forgetting evaluation and adaptive rescheduling."""
    state: TutorState = {
        "run_id": f"run_{uuid4().hex[:12]}",
        "workflow_name": "daily_check",
        "student_id": student_id,
        "syllabus_id": syllabus_id,
        "persist": True,
        "is_simulation": False,
        "simulate_days_elapsed": 0,
        "eval_time_iso": datetime.now(timezone.utc).isoformat(),
        "traces": [],
    }
    return _invoke_graph(DAILY_CHECK_GRAPH, db, state)


def run_demo_simulation(
    db: Session,
    *,
    student_id: str,
    syllabus_id: str,
    days_elapsed: int = 7,
) -> TutorState:
    """Flow F: Pure non-destructive time-shift preview (persist=False, zero SQLite writes)."""
    future_eval = datetime.now(timezone.utc) + timedelta(days=int(days_elapsed))
    state: TutorState = {
        "run_id": f"sim_{uuid4().hex[:12]}",
        "workflow_name": "daily_check_simulation",
        "student_id": student_id,
        "syllabus_id": syllabus_id,
        "persist": False,
        "is_simulation": True,
        "simulate_days_elapsed": int(days_elapsed),
        "eval_time_iso": future_eval.isoformat(),
        "traces": [],
    }
    return _invoke_graph(DEMO_SIMULATION_GRAPH, db, state)
