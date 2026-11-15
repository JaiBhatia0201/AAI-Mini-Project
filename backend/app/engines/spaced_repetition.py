"""Spaced repetition interval generator (Day 3/7/14/30 + remedial pull-forward)."""

from datetime import date, timedelta

STANDARD_REVIEW_OFFSETS = (3, 7, 14, 30)


def next_spaced_intervals(
    mastery_score: float,
    retention_score: float,
    base_date: date,
    review_count: int = 0,
) -> list[tuple[int, date, str]]:
    """Return upcoming (offset_days, scheduled_date, task_type) review checkpoints."""
    schedule: list[tuple[int, date, str]] = []
    if float(mastery_score) < 60.0 or float(retention_score) < 0.65:
        schedule.append((1, base_date + timedelta(days=1), "revision"))
        schedule.append((2, base_date + timedelta(days=2), "practice"))
        for offset in (3, 7, 14):
            schedule.append((offset, base_date + timedelta(days=offset), "spaced_rep"))
        return schedule

    start_idx = min(max(0, int(review_count)), len(STANDARD_REVIEW_OFFSETS) - 1)
    for offset in STANDARD_REVIEW_OFFSETS[start_idx:]:
        schedule.append((offset, base_date + timedelta(days=offset), "spaced_rep"))
    return schedule
