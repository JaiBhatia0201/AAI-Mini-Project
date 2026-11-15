"""Agent 5: Style-Adapted Teaching Agent with honest provenance tracking."""

import json
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.models import LearningResource, StudentProfile, SyllabusTopic, TopicPrerequisite
from app.services.llm_client import invoke_llm_json
from app.services.retrieval import get_retrieval_provider


def run_teaching_agent(db: Session, state: TutorState) -> TutorState:
    """Teach a concept adapted to learning style with explicit source_origin provenance."""
    started = time.perf_counter()
    syllabus_id = state["syllabus_id"]
    topic_id = state["topic_id"]
    tutor_question = (state.get("tutor_question") or "").strip()

    topic = db.get(SyllabusTopic, topic_id)
    if topic is None or topic.syllabus_id != syllabus_id:
        raise ValueError("Requested topic does not belong to the active syllabus.")

    profile = db.get(StudentProfile, state["student_id"])
    style = profile.learning_style if profile else "visual"

    # Build direct prerequisite breadcrumb path within active syllabus
    prereq_edges = (
        db.query(TopicPrerequisite)
        .filter_by(syllabus_id=syllabus_id, dependent_topic_id=topic_id)
        .all()
    )
    prereq_path: list[str] = []
    for edge in prereq_edges:
        pt = db.get(SyllabusTopic, edge.prerequisite_topic_id)
        if pt:
            prereq_path.append(f"{pt.topic_code}: {pt.title}")

    resources = (
        db.query(LearningResource)
        .filter_by(syllabus_id=syllabus_id, topic_id=topic_id)
        .all()
    )
    hits = get_retrieval_provider().search(
        syllabus_id,
        f"{topic.title} {tutor_question}".strip(),
        top_k=3,
    )

    subtopics = json.loads(topic.subtopics_json or "[]")
    context_snippets = "\n".join(f"- {h.title}: {h.text[:260]}" for h in hits) or topic.raw_excerpt
    res_flashcards = [
        {
            "front": r.title,
            "back": r.summary or r.url_or_content[:200],
        }
        for r in resources
        if r.modality == "flashcard"
    ]

    llm_prompt = (
        f"Student learning style: {style}\n"
        f"Topic: {topic.title} ({topic.unit} - {topic.subject})\n"
        f"Subtopics: {subtopics}\n"
        f"Prerequisite path: {prereq_path}\n"
        f"Follow-up question: {tutor_question or 'Provide a complete core concept lesson.'}\n"
        f"Grounded syllabus context:\n{context_snippets[:1600]}\n\n"
        'Return JSON: {"explanation": "...", "analogy": "...", '
        '"flashcards": [{"front": "...", "back": "..."}]}'
    )
    llm_res = invoke_llm_json(
        system_prompt="You are a clear adaptive tutor tailoring lessons strictly to the student's learning style and provided syllabus context.",
        user_prompt=llm_prompt,
    )

    if llm_res.used_llm and isinstance(llm_res.parsed, dict) and llm_res.parsed.get("explanation"):
        data = llm_res.parsed
        source_origin = "llm_generated_summary"
        confidence_status = "llm_synthesized"
        exec_mode = "llm"
    else:
        style_hint = {
            "visual": "Mental Model & Flow Breakdown",
            "reading": "Structured Conceptual Summary",
            "practice": "Applied Problem-Solving Focus",
            "mixed": "Balanced Concept & Practice Walkthrough",
        }.get(style, "Structured Walkthrough")

        qa_prefix = f"Regarding your question ('{tutor_question}'): " if tutor_question else ""
        excerpt_body = (topic.raw_excerpt or context_snippets or topic.title).strip()
        sub_list = ", ".join(subtopics) if subtopics else topic.title
        prereq_note = (
            f" Build on prerequisites ({' -> '.join(prereq_path)}) before tackling edge cases."
            if prereq_path
            else ""
        )
        data = {
            "explanation": (
                f"[{style_hint}] {qa_prefix}{topic.title} ({topic.unit}) centers on {sub_list}. "
                f"From your syllabus material: {excerpt_body[:500]}.{prereq_note}"
            ),
            "analogy": (
                f"Think of {topic.title} like organizing a pipeline: first verify your foundation "
                f"({prereq_path[0] if prereq_path else subtopics[0] if subtopics else topic.subject}), "
                f"then trace how rules transform inputs into reliable outputs."
            ),
            "flashcards": res_flashcards
            or [
                {"front": f"What is the core focus of {topic.title}?", "back": sub_list},
                {
                    "front": f"Key takeaway from {topic.unit}",
                    "back": excerpt_body[:220],
                },
            ],
        }
        source_origin = (
            "curated_dataset_note"
            if topic.source_origin == "curated_dataset_note"
            else "extracted_pdf_excerpt"
        )
        confidence_status = "fallback_grounded"
        exec_mode = "fallback"

    state["lesson_payload"] = {
        "topic_id": topic.id,
        "explanation": str(data["explanation"]),
        "analogy": str(data.get("analogy") or ""),
        "prerequisite_path": prereq_path,
        "flashcards": list(data.get("flashcards") or []),
        "source_origin": source_origin,
        "confidence_status": confidence_status,
    }

    record_trace(
        db=db,
        state=state,
        agent_number=5,
        agent_name="Teaching Agent",
        execution_mode=exec_mode,
        started_at=started,
        input_summary=f"topic={topic.topic_code}, style={style}, question={bool(tutor_question)}",
        output_summary=f"Delivered {style}-adapted lesson (source={source_origin})",
    )
    return state
