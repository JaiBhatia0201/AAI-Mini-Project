"""Agent 6: Calibrated Practice Question Selector & On-Demand Generator."""

import json
import random
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.engines.mastery import difficulty_quota_for_mastery
from app.models import Question, SyllabusTopic, TopicMastery
from app.services.llm_client import invoke_llm_json


def _generate_fallback_questions_for_topic(topic: SyllabusTopic, existing_count: int) -> list[Question]:
    """Synthesize grounded fallback MCQs from subtopics/excerpts when a custom syllabus lacks questions."""
    subtopics = json.loads(topic.subtopics_json or "[]") or [topic.title]
    excerpt = (topic.raw_excerpt or topic.title).strip()
    templates = [
        (
            "easy",
            f"Which area is explicitly covered within {topic.title} ({topic.unit})?",
            subtopics[0],
            [
                subtopics[0],
                "Unrelated archival hardware diagnostics only",
                "Purely administrative grading policy without technical concepts",
                "External unreferenced elective workshop material",
            ],
            f"{topic.title} directly includes {subtopics[0]} as documented in {topic.unit}. Excerpt: {excerpt[:180]}",
        ),
        (
            "medium",
            f"When studying {topic.title}, which sequence best reflects conceptual mastery?",
            f"Verify foundational definitions before solving applied {subtopics[0]} problems",
            [
                f"Verify foundational definitions before solving applied {subtopics[0]} problems",
                "Memorize final answers while skipping core mechanisms",
                "Ignore prerequisite concepts and study topics in random order",
                "Avoid timed practice or spaced repetition completely",
            ],
            f"Conceptual grounding in {subtopics[0]} prevents brittle errors on medium/hard exam variations.",
        ),
        (
            "hard",
            f"If a learner scores below threshold on an assessment of {topic.title}, what indicates true remediation readiness?",
            f"Consistent accuracy on {subtopics[-1]} plus passing follow-up verification within expected time",
            [
                f"Consistent accuracy on {subtopics[-1]} plus passing follow-up verification within expected time",
                "Skimming headings once without testing",
                "Deleting all prior attempts from history",
                "Switching topics immediately without closing prerequisite gaps",
            ],
            f"Remediation requires verifying mastery retention and pacing under exam conditions for {topic.title}.",
        ),
    ]
    created: list[Question] = []
    for idx, (diff, prompt, correct, opts, expl) in enumerate(templates):
        if existing_count + len(created) >= 3:
            break
        shuffled = list(opts)
        random.Random(f"{topic.id}:{idx}").shuffle(shuffled)
        created.append(
            Question(
                syllabus_id=topic.syllabus_id,
                topic_id=topic.id,
                subtopic=subtopics[min(idx, len(subtopics) - 1)][:180],
                difficulty=diff,
                question_type="MCQ",
                prompt=prompt,
                options_json=json.dumps(shuffled),
                correct_answer=correct,
                explanation=expl,
                expected_time_sec=45 if diff == "easy" else (65 if diff == "medium" else 90),
                source_origin=topic.source_origin or "extracted_pdf_excerpt",
                is_generated=True,
            )
        )
    return created


def ensure_topic_questions(
    db: Session,
    topic: SyllabusTopic,
    min_count: int = 3,
    allow_llm: bool = True,
) -> str:
    """Generate LLM or grounded-fallback questions when an uploaded topic lacks enough items."""
    existing = (
        db.query(Question)
        .filter_by(syllabus_id=topic.syllabus_id, topic_id=topic.id)
        .count()
    )
    if existing >= min_count:
        return "deterministic"

    needed = min_count - existing
    subtopics = json.loads(topic.subtopics_json or "[]")
    llm_res = (
        invoke_llm_json(
            system_prompt="Generate rigorous multiple-choice exam questions with 4 distinct options and a concise explanation.",
            user_prompt=(
                f"Topic: {topic.title} ({topic.unit})\nSubtopics: {subtopics}\n"
                f"Syllabus excerpt: {topic.raw_excerpt[:900]}\n"
                f'Generate {needed} MCQs (mix of easy/medium/hard) as JSON: '
                '{"questions": [{"subtopic": "...", "difficulty": "easy|medium|hard", '
                '"prompt": "...", "options": ["A", "B", "C", "D"], "correct_answer": "exact option string", '
                '"explanation": "...", "expected_time_sec": 60}]}'
            ),
        )
        if allow_llm
        else None
    )

    if llm_res and llm_res.used_llm and isinstance(llm_res.parsed, dict) and isinstance(llm_res.parsed.get("questions"), list):
        new_rows: list[Question] = []
        for q in llm_res.parsed["questions"][:needed]:
            if not isinstance(q, dict) or not q.get("prompt"):
                continue
            raw_opts = q.get("options")
            opts = [str(o) for o in raw_opts] if isinstance(raw_opts, list) else []
            ans = str(q.get("correct_answer") or "")
            if len(opts) >= 2 and ans in opts:
                diff = str(q.get("difficulty") or "medium").lower()
                try:
                    exp_sec = int(q.get("expected_time_sec") or 60)
                except (TypeError, ValueError):
                    exp_sec = 60
                new_rows.append(
                    Question(
                        syllabus_id=topic.syllabus_id,
                        topic_id=topic.id,
                        subtopic=str(q.get("subtopic") or topic.title)[:180],
                        difficulty=diff if diff in {"easy", "medium", "hard"} else "medium",
                        question_type="MCQ",
                        prompt=str(q["prompt"]),
                        options_json=json.dumps(opts),
                        correct_answer=ans,
                        explanation=str(q.get("explanation") or ""),
                        expected_time_sec=exp_sec,
                        source_origin="llm_generated_summary",
                        is_generated=True,
                    )
                )
        if new_rows:
            db.add_all(new_rows)
            db.flush()
            return "llm"

    fallback_rows = _generate_fallback_questions_for_topic(topic, existing_count=existing)
    if fallback_rows:
        db.add_all(fallback_rows)
        db.flush()
    return "fallback"


def select_calibrated_questions(
    db: Session,
    student_id: str,
    syllabus_id: str,
    topic_id: str | None = None,
    count: int = 8,
) -> tuple[list[Question], str]:
    """Select difficulty-split questions matching current student mastery."""
    topics = (
        [db.get(SyllabusTopic, topic_id)]
        if topic_id
        else db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).order_by(SyllabusTopic.order_index).all()
    )
    topics = [t for t in topics if t is not None and t.syllabus_id == syllabus_id]
    if not topics:
        return [], "deterministic"

    exec_mode = "deterministic"
    sample_targets = topics[: min(len(topics), 6)] if topic_id is None else topics
    for idx, t in enumerate(sample_targets):
        mode = ensure_topic_questions(db, t, min_count=3, allow_llm=(topic_id is not None or idx < 2))
        if mode == "llm" or (mode == "fallback" and exec_mode != "llm"):
            exec_mode = mode

    query = db.query(Question).filter_by(syllabus_id=syllabus_id)
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    pool = query.all()
    if not pool:
        return [], exec_mode

    mastery_val = 45.0
    if topic_id:
        row = (
            db.query(TopicMastery)
            .filter_by(student_id=student_id, syllabus_id=syllabus_id, topic_id=topic_id)
            .first()
        )
        if row:
            mastery_val = float(row.mastery_score)
    else:
        rows = db.query(TopicMastery).filter_by(student_id=student_id, syllabus_id=syllabus_id).all()
        if rows:
            mastery_val = sum(float(r.mastery_score) for r in rows) / len(rows)

    quota = difficulty_quota_for_mastery(mastery_val, min(count, len(pool)))
    buckets: dict[str, list[Question]] = {"easy": [], "medium": [], "hard": []}
    for q in pool:
        buckets.get(q.difficulty, buckets["medium"]).append(q)

    selected: list[Question] = []
    seen: set[str] = set()
    for diff in ("easy", "medium", "hard"):
        for q in buckets[diff][: quota[diff]]:
            selected.append(q)
            seen.add(q.id)

    for q in pool:
        if len(selected) >= min(count, len(pool)):
            break
        if q.id not in seen:
            selected.append(q)
            seen.add(q.id)

    return selected, exec_mode


def run_question_agent(
    db: Session,
    state: TutorState,
    mode: str = "diagnostic",
) -> TutorState:
    """Prepare calibrated diagnostic or practice questions and log Agent 6 trace."""
    started = time.perf_counter()
    syllabus_id = state["syllabus_id"]
    student_id = state["student_id"]

    # Skip staging unrelated syllabus MCQs when Agent 5 answered an out-of-syllabus web query
    if mode != "diagnostic" and (state.get("lesson_payload") or {}).get("is_out_of_syllabus"):
        state["practice_questions"] = []
        record_trace(
            db=db,
            state=state,
            agent_number=6,
            agent_name="Question Generator Agent",
            execution_mode="deterministic",
            started_at=started,
            input_summary=f"mode={mode}, out_of_syllabus=True",
            output_summary="Skipped syllabus MCQ staging for out-of-syllabus live web answer",
        )
        return state

    topic_id = state.get("topic_id") if mode != "diagnostic" else None
    count = 10 if mode == "diagnostic" else 5

    questions, exec_mode = select_calibrated_questions(
        db=db,
        student_id=student_id,
        syllabus_id=syllabus_id,
        topic_id=topic_id,
        count=count,
    )
    serialized = [
        {
            "id": q.id,
            "syllabus_id": q.syllabus_id,
            "topic_id": q.topic_id,
            "subtopic": q.subtopic,
            "difficulty": q.difficulty,
            "question_type": q.question_type,
            "prompt": q.prompt,
            "options": json.loads(q.options_json or "[]"),
            "expected_time_sec": q.expected_time_sec,
            "source_origin": q.source_origin,
            "is_generated": q.is_generated,
        }
        for q in questions
    ]
    if mode == "diagnostic":
        state["diagnostic_questions"] = serialized
    else:
        state["practice_questions"] = serialized

    record_trace(
        db=db,
        state=state,
        agent_number=6,
        agent_name="Question Generator Agent",
        execution_mode=exec_mode,
        started_at=started,
        input_summary=f"mode={mode}, syllabus={syllabus_id}, topic={topic_id or 'all'}",
        output_summary=f"Staged {len(serialized)} calibrated questions",
    )
    return state
