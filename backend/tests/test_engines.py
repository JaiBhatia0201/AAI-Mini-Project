"""Unit tests for all 5 deterministic learning-science engines (Task 5)."""

from datetime import date, datetime, timedelta, timezone
import math
import networkx as nx

from app.engines.forgetting_curve import (
    compute_retention,
    compute_stability_days,
    evaluate_retention_alerts,
)
from app.engines.mastery import (
    classify_mastery_status,
    compute_session_score,
    detect_weakness,
    difficulty_quota_for_mastery,
    update_topic_mastery,
)
from app.engines.predictive_score import compute_predictive_score
from app.engines.spaced_repetition import next_spaced_intervals
from app.engines.syllabus_dag import (
    build_nx_graph,
    find_root_cause_blockers,
    resolve_cycles,
    topological_order,
)


def test_dag_cycle_breaking_topological_order_and_blockers() -> None:
    """DAG engine breaks cycles deterministically and finds weak ancestor blockers."""
    edges = [
        ("T1", "T2", "verified_seed"),
        ("T2", "T3", "verified_seed"),
        ("T3", "T1", "needs_review"),  # Cycle closing edge
    ]
    kept, removed = resolve_cycles(edges, order_lookup={"T1": 1, "T2": 2, "T3": 3})
    assert len(removed) == 1
    assert removed[0] == ("T3", "T1", "needs_review")

    topics = [
        {"id": "T1", "title": "Foundations", "subject": "CN", "order_index": 1, "exam_weightage": 2.0},
        {"id": "T2", "title": "Subnetting", "subject": "CN", "order_index": 2, "exam_weightage": 3.0},
        {"id": "T3", "title": "Routing", "subject": "CN", "order_index": 3, "exam_weightage": 3.0},
    ]
    edge_dicts = [
        {"prerequisite_topic_id": u, "dependent_topic_id": v, "confidence_status": c}
        for u, v, c in kept
    ]
    graph = build_nx_graph(topics, edge_dicts)
    assert nx.is_directed_acyclic_graph(graph)
    order = topological_order(graph)
    assert order == ["T1", "T2", "T3"]

    blockers = find_root_cause_blockers(
        graph,
        "T3",
        mastery_map={"T1": 72.0, "T2": 41.0, "T3": 34.0},
        threshold=65.0,
    )
    assert blockers == ["T2"]


def test_mastery_ema_weakness_and_difficulty_split() -> None:
    """Verify weighted EMA formula, weakness rules, and question difficulty splits."""
    attempts = [
        {"difficulty": "hard", "is_correct": True, "time_taken_sec": 45, "expected_time_sec": 60},
        {"difficulty": "easy", "is_correct": False, "time_taken_sec": 120, "expected_time_sec": 40},
    ]
    s_k = compute_session_score(attempts)
    expected_num = 1.25 * 1.05
    expected_den = (1.25 * 1.05) + (0.8 * 0.95)
    assert math.isclose(s_k, round(100.0 * expected_num / expected_den, 2), rel_tol=1e-3)

    m_new = update_topic_mastery(50.0, attempts)
    assert 0.0 <= m_new <= 100.0
    assert math.isclose(m_new, round(0.65 * 50.0 + 0.35 * s_k, 2), rel_tol=1e-3)

    is_weak, reasons = detect_weakness(55.0, recent_accuracies=[80.0, 58.0], consecutive_misses=2)
    assert is_weak is True
    assert len(reasons) == 3
    assert classify_mastery_status(55.0) == "weak"
    assert classify_mastery_status(82.0) == "mastered"

    assert difficulty_quota_for_mastery(40.0, 10) == {"easy": 6, "medium": 3, "hard": 1}
    assert difficulty_quota_for_mastery(62.0, 12) == {"easy": 3, "medium": 6, "hard": 3}
    assert difficulty_quota_for_mastery(85.0, 10) == {"easy": 1, "medium": 4, "hard": 5}


def test_forgetting_curve_and_spaced_repetition() -> None:
    """Verify Ebbinghaus exponential decay and remedial spaced-repetition pull-forward."""
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    r0, stability = compute_retention(now, now, mastery_score=50.0, review_count=0)
    assert r0 == 1.0
    assert math.isclose(stability, compute_stability_days(50.0, 0), rel_tol=1e-4)

    r_after = compute_retention(now - timedelta(days=5), now, mastery_score=50.0, review_count=0)[0]
    assert r_after < 0.65

    class _Row:
        def __init__(self, tid, m, rc, lp):
            self.topic_id = tid
            self.mastery_score = m
            self.review_count = rc
            self.last_practiced_at = lp

    class _Topic:
        topic_code = "T1"
        title = "OSI Model"

    alerts = evaluate_retention_alerts(
        [_Row("T1", 50.0, 0, now - timedelta(days=5)), _Row("T2", 80.0, 2, now)],
        {"T1": _Topic()},
        eval_time=now,
    )
    assert len(alerts) == 1
    assert alerts[0]["topic_id"] == "T1"

    base = date(2026, 11, 15)
    remedial = next_spaced_intervals(48.0, 0.50, base)
    assert remedial[0] == (1, date(2026, 11, 16), "revision")
    assert remedial[1] == (2, date(2026, 11, 17), "practice")

    standard = next_spaced_intervals(82.0, 0.90, base, review_count=0)
    assert [d[0] for d in standard] == [3, 7, 14, 30]


def test_predictive_score_bounded_and_scalable() -> None:
    """Predictive exam estimator scales to configurable max_score and labels estimates honestly."""
    topics = [
        {"id": "T1", "exam_weightage": 2.0},
        {"id": "T2", "exam_weightage": 3.0},
    ]
    pred_gate = compute_predictive_score(
        topics=topics,
        mastery_map={"T1": 80.0, "T2": 50.0},
        retention_map={"T1": 0.9, "T2": 0.7},
        history_scores=[48.5, 55.0, 62.5],
        days_remaining=60,
        target_score=78.0,
        max_score=100.0,
    )
    assert pred_gate["is_estimate"] is True
    assert 0.0 <= pred_gate["current_estimated_score"] <= 100.0
    assert pred_gate["current_estimated_score"] <= pred_gate["projected_estimated_score"] <= 95.0

    pred_300 = compute_predictive_score(
        topics=topics,
        mastery_map={"T1": 80.0, "T2": 50.0},
        retention_map={"T1": 0.9, "T2": 0.7},
        history_scores=[140.0, 165.0],
        days_remaining=45,
        target_score=240.0,
        max_score=300.0,
    )
    assert pred_300["max_score"] == 300.0
    assert pred_300["current_estimated_score"] > 100.0
