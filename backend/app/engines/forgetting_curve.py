"""Ebbinghaus forgetting-curve retention estimation and alert evaluation."""

from datetime import datetime, timezone
import math
from typing import Any, Iterable

RETENTION_ALERT_THRESHOLD = 0.65


def _as_utc(dt: datetime) -> datetime:
    """Normalize naive or aware datetimes safely to UTC."""
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_stability_days(mastery_score: float, review_count: int) -> float:
    """S_mem = 4.0 * (1 + 0.55 * n_rev) * (0.5 + M_k / 100)."""
    m_clamped = max(0.0, min(100.0, float(mastery_score)))
    revs = max(0, int(review_count))
    stability = 4.0 * (1.0 + 0.55 * revs) * (0.5 + m_clamped / 100.0)
    return round(stability, 4)


def compute_retention(
    last_practiced_at: datetime | None,
    eval_time: datetime,
    mastery_score: float,
    review_count: int = 0,
) -> tuple[float, float]:
    """Compute Ebbinghaus retention R(t) = exp(-t / S_mem) and memory stability days."""
    stability = compute_stability_days(mastery_score, review_count)
    if last_practiced_at is None:
        return 1.0, stability

    practiced_utc = _as_utc(last_practiced_at)
    eval_utc = _as_utc(eval_time)
    days_elapsed = max(0.0, (eval_utc - practiced_utc).total_seconds() / 86400.0)
    retention = math.exp(-days_elapsed / max(0.1, stability))
    return round(retention, 4), stability


def evaluate_retention_alerts(
    mastery_rows: Iterable[Any],
    topic_lookup: dict[str, Any],
    eval_time: datetime,
    threshold: float = RETENTION_ALERT_THRESHOLD,
) -> list[dict[str, Any]]:
    """Return sorted forgetting alerts for practiced topics with R(t) < threshold."""
    alerts: list[dict[str, Any]] = []
    for row in mastery_rows:
        last_practiced = getattr(row, "last_practiced_at", None)
        if last_practiced is None:
            continue
        mastery_val = float(getattr(row, "mastery_score", 40.0))
        rev_count = int(getattr(row, "review_count", 0))
        retention, stability = compute_retention(last_practiced, eval_time, mastery_val, rev_count)
        if retention < threshold:
            tid = getattr(row, "topic_id")
            topic = topic_lookup.get(tid)
            title = topic.title if topic is not None else tid
            code = getattr(topic, "topic_code", tid) if topic is not None else tid
            days_since = max(
                0.0, (_as_utc(eval_time) - _as_utc(last_practiced)).total_seconds() / 86400.0
            )
            alerts.append(
                {
                    "topic_id": tid,
                    "topic_code": code,
                    "title": title,
                    "retention_score": round(retention, 3),
                    "mastery_score": round(mastery_val, 1),
                    "stability_days": round(stability, 2),
                    "days_since_practice": round(days_since, 1),
                }
            )
    alerts.sort(key=lambda item: item["retention_score"])
    return alerts
