"""Predictive exam readiness estimation scaled to any syllabus max_score."""

from typing import Any, Sequence


def compute_predictive_score(
    topics: Sequence[Any],
    mastery_map: dict[str, float],
    retention_map: dict[str, float],
    history_scores: Sequence[float] | None = None,
    days_remaining: int = 60,
    target_score: float = 75.0,
    max_score: float = 100.0,
) -> dict[str, Any]:
    """Compute honest Estimated Readiness Projections without ungrounded rank claims."""
    effective_max = max(1.0, float(max_score))
    if not topics:
        return {
            "current_estimated_score": 0.0,
            "projected_estimated_score": 0.0,
            "max_score": effective_max,
            "target_score": float(target_score),
            "target_gap": round(float(target_score), 1),
            "readiness_band": "Early Stage",
            "is_estimate": True,
            "label": "Estimated Readiness Projection",
        }

    weighted_sum = 0.0
    weight_total = 0.0
    for topic in topics:
        tid = topic["id"] if isinstance(topic, dict) else topic.id
        w = max(0.1, float(topic.get("exam_weightage", 1.0) if isinstance(topic, dict) else topic.exam_weightage))
        m = max(0.0, min(100.0, float(mastery_map.get(tid, 40.0))))
        r = max(0.0, min(1.0, float(retention_map.get(tid, 1.0))))
        weighted_sum += w * (m / 100.0) * (0.7 + 0.3 * r)
        weight_total += w

    current_ratio = weighted_sum / max(1e-6, weight_total)
    current_score = round(min(effective_max, max(0.0, effective_max * current_ratio)), 1)

    # Estimate weekly progress slope (points per week on max_score scale)
    scores = [float(s) for s in (history_scores or [])]
    if len(scores) >= 2:
        n = len(scores)
        mean_x = (n - 1) / 2.0
        mean_y = sum(scores) / n
        num = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(scores))
        den = sum((i - mean_x) ** 2 for i in range(n))
        slope = max(0.6, min(4.5, num / den)) if den > 0 else 1.5
    else:
        slope = 1.8 * (effective_max / 100.0)

    weeks_rem = max(1.0, min(16.0, float(days_remaining) / 7.0))
    headroom_factor = max(0.15, (effective_max * 0.95 - current_score) / effective_max)
    projected_gain = slope * min(weeks_rem, 8.0) * headroom_factor
    projected_score = round(
        min(effective_max * 0.95, max(current_score, current_score + projected_gain)),
        1,
    )

    if current_score >= target_score:
        band = "Exam Ready"
    elif projected_score >= target_score:
        band = "On Track"
    elif (target_score - projected_score) <= (0.12 * effective_max):
        band = "Needs Acceleration"
    else:
        band = "At Risk"

    return {
        "current_estimated_score": current_score,
        "projected_estimated_score": projected_score,
        "max_score": effective_max,
        "target_score": round(float(target_score), 1),
        "target_gap": round(float(target_score) - current_score, 1),
        "readiness_band": band,
        "is_estimate": True,
        "label": "Estimated Readiness Projection",
    }
