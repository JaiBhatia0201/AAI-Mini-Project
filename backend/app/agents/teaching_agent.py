"""Agent 5: Style-Adapted Teaching Agent with syllabus RAG and live out-of-syllabus web FAISS."""

import json
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.models import LearningResource, StudentProfile, SyllabusTopic, TopicPrerequisite
from app.services.llm_client import invoke_llm_json
from app.services.retrieval import get_retrieval_provider
from app.services.web_search import is_question_out_of_syllabus, search_web_with_faiss


def _run_live_web_lesson(
    db: Session,
    state: TutorState,
    started: float,
    style: str,
    tutor_question: str,
    topic_id_label: str,
) -> TutorState:
    """Answer an out-of-syllabus question using live web search + in-memory FAISS re-ranking."""
    web_hits, web_mode = search_web_with_faiss(tutor_question, top_k=4)
    web_sources = [
        {
            "title": h.title,
            "url": h.url,
            "snippet": h.snippet,
            "score": h.score,
            "provider": h.provider,
        }
        for h in web_hits
    ]

    if not web_hits:
        state["lesson_payload"] = {
            "topic_id": topic_id_label,
            "explanation": (
                f"### Out-of-Syllabus Question\n\n"
                f"Your question **\"{tutor_question}\"** is outside your active syllabus, and live internet search "
                f"could not retrieve results right now. Please check your internet connection or try rephrasing the query."
            ),
            "analogy": "Think of this like checking an online reference library when a topic isn't in your textbook—once connected, live sources will appear here.",
            "prerequisite_path": [],
            "flashcards": [],
            "source_origin": "live_web_search",
            "confidence_status": "web_unavailable",
            "is_out_of_syllabus": True,
            "web_retrieval_mode": web_mode,
            "web_sources": [],
        }
        record_trace(
            db=db,
            state=state,
            agent_number=5,
            agent_name="Teaching Agent",
            execution_mode="fallback",
            started_at=started,
            input_summary=f"out_of_syllabus=True, style={style}",
            output_summary="Out-of-syllabus query detected; live internet search unavailable",
        )
        return state

    web_context = "\n".join(
        f"- [{h.title} ({h.provider}, score={h.score})]: {h.snippet}"
        for h in web_hits
    )
    llm_prompt = (
        f"Student learning style: {style}\n"
        f"Out-of-syllabus student question: {tutor_question}\n"
        f"Top FAISS-ranked live internet snippets:\n{web_context[:2200]}\n\n"
        "Answer the student's question clearly and accurately using ONLY the provided live internet context. "
        "Structure the explanation with short headings and concise bullet points so it is easy to scan. "
        'Return JSON: {"explanation": "...", "analogy": "...", '
        '"flashcards": [{"front": "...", "back": "..."}]}'
    )
    llm_res = invoke_llm_json(
        system_prompt="You are a clear adaptive tutor answering an out-of-syllabus question strictly grounded in live web search results.",
        user_prompt=llm_prompt,
    )

    if llm_res.used_llm and isinstance(llm_res.parsed, dict) and llm_res.parsed.get("explanation"):
        data = llm_res.parsed
        exec_mode = "llm"
    else:
        bullet_lines = "\n".join(f"- **{h.title}:** {h.snippet}" for h in web_hits[:3])
        data = {
            "explanation": (
                f"### Live Internet Summary: {tutor_question}\n\n"
                f"This question is outside your active syllabus. Here are the top FAISS-ranked facts retrieved from the web:\n\n"
                f"{bullet_lines}"
            ),
            "analogy": (
                f"Because this concept sits outside your current course syllabus, treat these verified web summaries "
                f"({web_hits[0].title}) as a quick external reference guide."
            ),
            "flashcards": [
                {"front": f"What is {web_hits[0].title}?", "back": web_hits[0].snippet[:220]},
            ],
        }
        exec_mode = "fallback"

    raw_cards = data.get("flashcards")
    clean_cards: list[dict[str, str]] = []
    if isinstance(raw_cards, list):
        for card in raw_cards:
            if isinstance(card, dict) and card.get("front") and card.get("back"):
                clean_cards.append({"front": str(card["front"]), "back": str(card["back"])})

    state["lesson_payload"] = {
        "topic_id": topic_id_label,
        "explanation": str(data["explanation"]),
        "analogy": str(data.get("analogy") or ""),
        "prerequisite_path": [],
        "flashcards": clean_cards,
        "source_origin": "live_web_search",
        "confidence_status": web_mode,
        "is_out_of_syllabus": True,
        "web_retrieval_mode": web_mode,
        "web_sources": web_sources,
    }

    record_trace(
        db=db,
        state=state,
        agent_number=5,
        agent_name="Teaching Agent",
        execution_mode=exec_mode,
        started_at=started,
        input_summary=f"out_of_syllabus=True, style={style}, web_mode={web_mode}",
        output_summary=f"Answered out-of-syllabus query via live web + FAISS ({web_mode}, {len(web_sources)} sources)",
    )
    return state


def run_teaching_agent(db: Session, state: TutorState) -> TutorState:
    """Teach a concept adapted to learning style; auto-route out-of-syllabus doubts to live web + FAISS."""
    started = time.perf_counter()
    syllabus_id = state["syllabus_id"]
    raw_topic_id = (state.get("topic_id") or "").strip()
    tutor_question = (state.get("tutor_question") or "").strip()
    force_web = bool(state.get("force_web", False))

    profile = db.get(StudentProfile, state["student_id"])
    style = profile.learning_style if profile else "visual"

    # Explicit General / Out-of-Syllabus Web Mode
    if force_web or not raw_topic_id or raw_topic_id == "__general__":
        if not tutor_question:
            raise ValueError("Please enter a question to search from the internet.")
        return _run_live_web_lesson(
            db=db,
            state=state,
            started=started,
            style=style,
            tutor_question=tutor_question,
            topic_id_label="__general__",
        )

    topic = db.get(SyllabusTopic, raw_topic_id)
    if topic is None or topic.syllabus_id != syllabus_id:
        raise ValueError("Requested topic does not belong to the active syllabus.")

    provider = get_retrieval_provider()

    # Automatic Out-of-Syllabus Detection using question-only FAISS similarity + syllabus vocabulary
    if tutor_question:
        all_topics = db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).all()
        q_only_hits = provider.search(syllabus_id, tutor_question, top_k=3)
        if is_question_out_of_syllabus(tutor_question, all_topics, q_only_hits, selected_topic=topic):
            return _run_live_web_lesson(
                db=db,
                state=state,
                started=started,
                style=style,
                tutor_question=tutor_question,
                topic_id_label=topic.id,
            )

    # Build direct prerequisite breadcrumb path within active syllabus
    prereq_edges = (
        db.query(TopicPrerequisite)
        .filter_by(syllabus_id=syllabus_id, dependent_topic_id=topic.id)
        .all()
    )
    prereq_path: list[str] = []
    for edge in prereq_edges:
        pt = db.get(SyllabusTopic, edge.prerequisite_topic_id)
        if pt:
            prereq_path.append(f"{pt.topic_code}: {pt.title}")

    resources = (
        db.query(LearningResource)
        .filter_by(syllabus_id=syllabus_id, topic_id=topic.id)
        .all()
    )
    hits = provider.search(
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
        "Structure the explanation clearly with short headings and concise bullet points so a student can scan it easily. "
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

    raw_cards = data.get("flashcards")
    clean_cards: list[dict[str, str]] = []
    if isinstance(raw_cards, list):
        for card in raw_cards:
            if isinstance(card, dict) and card.get("front") and card.get("back"):
                clean_cards.append({"front": str(card["front"]), "back": str(card["back"])})

    state["lesson_payload"] = {
        "topic_id": topic.id,
        "explanation": str(data["explanation"]),
        "analogy": str(data.get("analogy") or ""),
        "prerequisite_path": prereq_path,
        "flashcards": clean_cards or res_flashcards,
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
