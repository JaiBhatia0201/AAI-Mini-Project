"""Agent 3: Resource Discovery & Multi-Modal Indexing using RetrievalProvider."""

import json
import time
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.models import LearningResource, SyllabusTopic
from app.services.llm_client import invoke_llm_json
from app.services.retrieval import RetrievalDocument, get_retrieval_provider


def _as_text(val: object, default: str) -> str:
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return default


def _ensure_topic_resources(
    db: Session,
    topic: SyllabusTopic,
    allow_llm: bool = True,
) -> tuple[list[LearningResource], str, bool]:
    """Ensure uploaded PDF topics also get grounded notes, flashcards, and search queries."""
    existing = (
        db.query(LearningResource)
        .filter_by(syllabus_id=topic.syllabus_id, topic_id=topic.id)
        .all()
    )
    if existing:
        return existing, "deterministic", False

    subtopics = json.loads(topic.subtopics_json or "[]")
    excerpt = (topic.raw_excerpt or f"{topic.title}: {', '.join(subtopics)}").strip()
    llm_res = (
        invoke_llm_json(
            system_prompt="You synthesize concise educational study notes and curated academic search references.",
            user_prompt=(
                f"Topic: {topic.title}\nUnit: {topic.unit}\nSubtopics: {subtopics}\nExcerpt: {excerpt[:900]}\n"
                'Return JSON: {"notes_summary": "...", "flashcard_qa": "Q: ... | A: ...", '
                '"video_query": "best lecture query terms", "textbook_ref": "standard textbook chapter"}'
            ),
        )
        if allow_llm
        else None
    )

    sub_txt = ", ".join(subtopics) if subtopics else topic.title
    default_notes = f"Core study guide for {topic.title} ({topic.unit}): Focus on {sub_txt}. Excerpt: {excerpt[:280]}"
    default_flash = f"Q: What are the key concepts in {topic.title}? | A: {sub_txt}. {excerpt[:180]}"

    if llm_res and llm_res.used_llm and isinstance(llm_res.parsed, dict):
        parsed = llm_res.parsed
        notes_text = _as_text(parsed.get("notes_summary"), default_notes)
        flash_text = _as_text(parsed.get("flashcard_qa"), default_flash)
        video_query = _as_text(parsed.get("video_query"), f"{topic.subject} {topic.title} lecture")
        textbook_ref = _as_text(parsed.get("textbook_ref"), f"{topic.subject} reference notes on {topic.title}")
        source_origin = "llm_generated_summary"
        exec_mode = "llm"
    else:
        notes_text = default_notes
        flash_text = default_flash
        video_query = f"{topic.subject} {topic.title} lecture"
        textbook_ref = f"{topic.subject} reference notes on {topic.title}"
        source_origin = topic.source_origin or "extracted_pdf_excerpt"
        exec_mode = "fallback"

    created = [
        LearningResource(
            syllabus_id=topic.syllabus_id,
            topic_id=topic.id,
            modality="notes",
            title=f"Study Notes: {topic.title}",
            source_ref=topic.unit,
            url_or_content=notes_text,
            summary=notes_text[:280],
            source_origin=source_origin,
            created_by_agent="Agent 3",
        ),
        LearningResource(
            syllabus_id=topic.syllabus_id,
            topic_id=topic.id,
            modality="flashcard",
            title=f"Quick Flashcard: {topic.title}",
            source_ref=topic.unit,
            url_or_content=flash_text,
            summary=flash_text[:220],
            source_origin=source_origin,
            created_by_agent="Agent 3",
        ),
        LearningResource(
            syllabus_id=topic.syllabus_id,
            topic_id=topic.id,
            modality="search_query",
            title=f"Recommended Lecture Search: {topic.title}",
            source_ref="Academic Video / Textbook Query",
            url_or_content=video_query,
            summary=textbook_ref[:220],
            source_origin=source_origin,
            created_by_agent="Agent 3",
        ),
    ]
    db.add_all(created)
    db.flush()
    return created, exec_mode, True


def run_resource_agent(db: Session, state: TutorState) -> TutorState:
    """Synthesize missing custom resources and rebuild (or reuse cached) isolated syllabus index."""
    started = time.perf_counter()
    syllabus_id = state["syllabus_id"]
    target_topic_id = state.get("topic_id")

    if state.get("force_web") or (state.get("workflow_name") == "teach_and_practice" and not target_topic_id):
        record_trace(
            db=db,
            state=state,
            agent_number=3,
            agent_name="Resource Discovery Agent",
            execution_mode="deterministic",
            started_at=started,
            input_summary=f"syllabus={syllabus_id}, mode=live_web",
            output_summary="Skipped syllabus re-indexing for general out-of-syllabus web query",
        )
        return state

    topics = db.query(SyllabusTopic).filter_by(syllabus_id=syllabus_id).order_by(SyllabusTopic.order_index).all()
    llm_topics = 0
    created_any = False
    if target_topic_id:
        for t in topics:
            if t.id == target_topic_id:
                _, mode, was_created = _ensure_topic_resources(db, t, allow_llm=True)
                created_any = created_any or was_created
                if mode == "llm":
                    llm_topics += 1
    else:
        for idx, t in enumerate(topics):
            # Cap live LLM calls during bulk syllabus onboarding to fit free-tier TPM limits cleanly
            _, mode, was_created = _ensure_topic_resources(db, t, allow_llm=(idx < 2))
            created_any = created_any or was_created
            if mode == "llm":
                llm_topics += 1

    provider = get_retrieval_provider()

    # Optimization: reuse existing per-syllabus index on topic study/search when no new resources were added
    cached_mode = provider.has_index(syllabus_id) if (target_topic_id and not created_any) else None
    if cached_mode is not None:
        state["retrieval_mode"] = cached_mode
        record_trace(
            db=db,
            state=state,
            agent_number=3,
            agent_name="Resource Discovery Agent",
            execution_mode="deterministic",
            started_at=started,
            input_summary=f"syllabus={syllabus_id}, topic={target_topic_id}",
            output_summary=f"Cache hit: reused existing syllabus index ({cached_mode}, skipped redundant re-indexing)",
        )
        return state

    all_resources = db.query(LearningResource).filter_by(syllabus_id=syllabus_id).all()
    docs: list[RetrievalDocument] = []
    for t in topics:
        if t.raw_excerpt:
            docs.append(
                RetrievalDocument(
                    doc_id=f"excerpt::{t.id}",
                    syllabus_id=syllabus_id,
                    topic_id=t.id,
                    title=f"{t.title} ({t.unit})",
                    text=t.raw_excerpt,
                    source_origin=t.source_origin,
                )
            )
    for r in all_resources:
        docs.append(
            RetrievalDocument(
                doc_id=r.id,
                syllabus_id=syllabus_id,
                topic_id=r.topic_id,
                title=r.title,
                text=f"{r.summary}\n{r.url_or_content}",
                source_origin=r.source_origin,
            )
        )

    retrieval_mode = provider.index_syllabus_documents(syllabus_id, docs)
    state["retrieval_mode"] = retrieval_mode

    record_trace(
        db=db,
        state=state,
        agent_number=3,
        agent_name="Resource Discovery Agent",
        execution_mode="llm" if (llm_topics > 0 or "fallback" not in retrieval_mode) else "fallback",
        started_at=started,
        input_summary=f"syllabus={syllabus_id}, docs={len(docs)}",
        output_summary=f"Indexed {len(docs)} documents ({retrieval_mode}, llm_topics={llm_topics})",
    )
    return state
