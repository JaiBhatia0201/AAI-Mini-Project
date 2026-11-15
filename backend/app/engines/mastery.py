"""Deterministic EMA mastery updates, difficulty splits, and weakness detection."""

from typing import Any, Sequence

DIFFICULTY_WEIGHTS: dict[str, float] = {
    "easy": 0.8,
    "medium": 1.0,
    "hard": 1.25,
}

SELF_RATING_PRIORS: dict[str, float] = {
    "strong": 78.0,
    "moderate": 55.0,
    "weak": 35.0,
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Restrict a floating-point score cleanly inside [low, high]."""
    return max(low, min(high, value))


def pacing_factor(is_correct: bool, time_taken_sec: int, expected_time_sec: int) -> float:
    """Reward accurate fluent answers (1.05x) and penalize excessive hesitation (0.95x)."""
    expected = max(1, int(expected_time_sec))
    taken = max(0, int(time_taken_sec))
    if is_correct and taken <= 1.2 * expected:
        return 1.05
    if taken > 1.8 * expected:
        return 0.95
    return 1.0


def compute_session_score(attempts: Sequence[dict[str, Any]]) -> float:
    """Compute difficulty- and pacing-weighted session score S_k in [0, 100]."""
    if not attempts:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for item in attempts:
        diff = str(item.get("difficulty", "medium")).lower()
        base_w = DIFFICULTY_WEIGHTS.get(diff, 1.0)
        is_correct = bool(item.get("is_correct", False))
        p_factor = pacing_factor(
            is_correct=is_correct,
            time_taken_sec=int(item.get("time_taken_sec", 60)),
            expected_time_sec=int(item.get("expected_time_sec", 60)),
        )
        weight = base_w * p_factor
        numerator += (1.0 if is_correct else 0.0) * weight
        denominator += weight
    if denominator <= 0:
        return 0.0
    return round(clamp(100.0 * (numerator / denominator)), 2)


def update_topic_mastery(old_mastery: float, attempts: Sequence[dict[str, Any]]) -> float:
    """Apply recency-weighted EMA: M_new = clamp(0.65 * M_old + 0.35 * S_k, 0, 100)."""
    if not attempts:
        return round(clamp(old_mastery), 2)
    session_score = compute_session_score(attempts)
    updated = 0.65 * float(old_mastery) + 0.35 * session_score
    return round(clamp(updated), 2)


def detect_weakness(
    new_mastery: float,
    recent_accuracies: Sequence[float] | None = None,
    consecutive_misses: int = 0,
) -> tuple[bool, list[str]]:
    """Evaluate all three deterministic weakness triggers."""
    reasons: list[str] = []
    if float(new_mastery) < 60.0:
        reasons.append(f"Mastery {new_mastery:.1f}% < 60% threshold")
    if recent_accuracies and len(recent_accuracies) >= 2:
        drop = float(recent_accuracies[-2]) - float(recent_accuracies[-1])
        if drop > 15.0:
            reasons.append(f"Accuracy dropped {drop:.1f} points across recent attempts")
    if int(consecutive_misses) >= 2:
        reasons.append(f"{consecutive_misses} consecutive incorrect responses")
    return bool(reasons), reasons


def classify_mastery_status(mastery_score: float, has_activity: bool = True) -> str:
    """Map numeric mastery to UI/DB status badge."""
    if not has_activity:
        return "unstarted"
    if mastery_score < 60.0:
        return "weak"
    if mastery_score >= 75.0:
        return "mastered"
    return "learning"


def difficulty_quota_for_mastery(mastery_score: float, total_questions: int) -> dict[str, int]:
    """Compute Easy/Medium/Hard question counts matching mastery adaptation rules."""
    total = max(1, int(total_questions))
    if mastery_score < 50.0:
        ratios = (0.60, 0.30, 0.10)
    elif mastery_score < 75.0:
        ratios = (0.25, 0.50, 0.25)
    else:
        ratios = (0.10, 0.40, 0.50)

    easy = round(total * ratios[0])
    medium = round(total * ratios[1])
    hard = total - easy - medium
    if hard < 0:
        medium = max(0, medium + hard)
        hard = 0
    return {"easy": easy, "medium": medium, "hard": hard}
