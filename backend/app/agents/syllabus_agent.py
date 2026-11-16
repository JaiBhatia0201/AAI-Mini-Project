"""Agent 2: Syllabus Understanding (PDF ingestion, 422 scanned-PDF gate, and DAG construction)."""

import io
import json
import re
import time
from typing import Any
from uuid import uuid4
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.agents.state import TutorState, record_trace
from app.config import get_settings
from app.engines.syllabus_dag import resolve_cycles
from app.models import StudentProfile, Syllabus, SyllabusTopic, TopicMastery, TopicPrerequisite
from app.services.llm_client import invoke_llm_json
from app.services.seeder import load_gate_bundle, seed_gate_syllabus_for_student


class ScannedPDFError(ValueError):
    """Raised when an uploaded PDF has insufficient extractable selectable text."""


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract selectable text using pypdf; reject empty or scanned image-only PDFs."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        raise ScannedPDFError(
            "Unable to read PDF structure. Please upload a valid text-selectable PDF file."
        ) from exc

    page_count = len(reader.pages)
    if page_count == 0:
        raise ScannedPDFError("Uploaded PDF contains zero pages.")

    pages_text = [(page.extract_text() or "").strip() for page in reader.pages]
    full_text = "\n\n".join(text for text in pages_text if text)
    avg_chars = len(full_text) / max(1, page_count)
    if len(full_text) < 80 or avg_chars < 50:
        raise ScannedPDFError(
            "Uploaded PDF appears to be scanned or image-only (< 50 extractable chars/page). "
            "Please upload a text-selectable syllabus PDF."
        )
    return full_text, page_count


def _parse_syllabus_fallback(
    full_text: str,
    title: str,
    exam_name: str,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Deterministically extract units, topics, verbatim excerpts, and safe intra-unit links."""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    heading_pat = re.compile(
        r"^(?:(?:Unit|Module|Chapter|Section|Part|Week)\s*[\dIVX]+[:.\-\s]*.*|"
        r"\d+(?:\.\d+)?[\).:\s]+[A-Z][A-Za-z0-9\s,&/\-:()]{3,80})$",
        re.IGNORECASE,
    )

    sections: list[dict[str, Any]] = []
    current_unit = "Unit 1"
    current_subject = exam_name or title or "Course Core"

    for idx, line in enumerate(lines):
        if re.match(r"^(?:Unit|Module|Chapter|Part)\s*[\dIVX]+", line, re.IGNORECASE):
            current_unit = line[:120]
            if ":" in line:
                tail = line.split(":", 1)[1].strip()
                if tail:
                    sections.append(
                        {"unit": current_unit, "title": tail[:140], "line_idx": idx}
                    )
            continue

        if heading_pat.match(line) and len(line) <= 110:
            cleaned = re.sub(r"^\d+(?:\.\d+)?[\).:\s]+", "", line).strip()
            if len(cleaned) >= 4:
                sections.append({"unit": current_unit, "title": cleaned[:140], "line_idx": idx})

    # Fallback chunking if PDF had plain paragraphs without clear headings
    if len(sections) < 2:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", full_text) if len(p.strip()) > 30]
        if not paragraphs:
            words = full_text.split()
            chunk_size = max(40, len(words) // 4)
            paragraphs = [
                " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
            ][:8]
        sections = []
        for idx, para in enumerate(paragraphs[:10], start=1):
            first_clause = re.split(r"[.;:\n]", para, maxsplit=1)[0].strip()
            topic_title = (first_clause[:80] if len(first_clause) >= 4 else f"Topic {idx}")
            sections.append({"unit": f"Unit {((idx - 1) // 3) + 1}", "title": topic_title, "excerpt": para})

    topics: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for i, sec in enumerate(sections[:24], start=1):
        t_title = sec["title"]
        key = t_title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        if "excerpt" in sec:
            excerpt = sec["excerpt"][:800]
        else:
            start = sec["line_idx"]
            end = sections[i]["line_idx"] if i < len(sections) and "line_idx" in sections[i] else min(len(lines), start + 8)
            excerpt = "\n".join(lines[start : max(start + 2, end)])[:800]

        subtopics = [
            s.strip(" -•*")
            for s in re.split(r"[,;\n•]", excerpt)
            if 4 <= len(s.strip(" -•*")) <= 70
        ][:4] or [t_title]

        topics.append(
            {
                "topic_code": f"TOP-{len(topics) + 1:02d}",
                "subject": current_subject[:100],
                "category": "Uploaded Syllabus",
                "unit": sec["unit"][:180],
                "title": t_title[:200],
                "subtopics": subtopics,
                "raw_excerpt": excerpt,
                "source_origin": "extracted_pdf_excerpt",
                "difficulty": "medium",
                "exam_weightage": 2.0,
                "estimated_hours": 3.0,
                "order_index": len(topics) + 1,
            }
        )

    # Strictly connect intra-unit adjacent sequence only as needs_review (no invented cross-unit edges)
    edges: list[tuple[str, str, str]] = []
    for i in range(len(topics) - 1):
        if topics[i]["unit"] == topics[i + 1]["unit"]:
            edges.append((topics[i]["topic_code"], topics[i + 1]["topic_code"], "needs_review"))

    return topics, edges


def run_syllabus_agent(db: Session, state: TutorState) -> TutorState:
    """Create either an isolated GATE CSE copy or a PDF-parsed syllabus knowledge graph."""
    started = time.perf_counter()
    student_id = state["student_id"]
    profile = db.get(StudentProfile, student_id)
    mode = state.get("onboard_mode", "pdf_upload")

    if mode == "seeded_gate":
        bundle = load_gate_bundle(get_settings().dataset_path)
        new_syl_id = f"gate_cse_{student_id}_{uuid4().hex[:6]}"
        syl, topic_map, _ = seed_gate_syllabus_for_student(
            db=db,
            student_id=student_id,
            syllabus_id=new_syl_id,
            bundle=bundle,
            target_score=float(state.get("target_score") or 78.0),
            days_remaining=int(state.get("days_remaining") or 90),
        )
        if profile is not None:
            profile.active_syllabus_id = syl.id
        db.flush()
        state["syllabus_id"] = syl.id
        state["topics_count"] = len(topic_map)
        state["prerequisites_count"] = len(bundle["syllabus"]["prerequisite_edges"])
        state["max_score"] = float(syl.max_score)
        record_trace(
            db=db,
            state=state,
            agent_number=2,
            agent_name="Syllabus Understanding Agent",
            execution_mode="deterministic",
            started_at=started,
            input_summary="mode=seeded_gate",
            output_summary=f"Provisioned isolated GATE CSE copy ({len(topic_map)} topics)",
        )
        return state

    pdf_bytes = state.get("pdf_bytes") or b""
    full_text, page_count = extract_pdf_text(pdf_bytes)  # May raise ScannedPDFError -> 422 before DB writes

    raw_filename = state.get("pdf_filename") or "custom_syllabus.pdf"
    title = (state.get("title") or raw_filename.rsplit(".", 1)[0].replace("_", " ").title()).strip()
    exam_name = (state.get("exam_name") or title or "Custom Exam").strip()
    target_score = float(state.get("target_score") or 75.0)
    max_score = float(state.get("max_score") or 100.0)
    days_remaining = int(state.get("days_remaining") or 60)

    llm_prompt = (
        "Extract 8 to 16 major prerequisite-aware topics and dependency edges as JSON from this syllabus text. "
        "Keep each raw_excerpt under 120 characters (verbatim from the text) and subtopics concise (2-4 items). "
        'Return JSON: {"topics": [{"topic_code": "TOP-01", "subject": "...", "unit": "...", '
        '"title": "...", "subtopics": ["..."], "raw_excerpt": "short quote from text", '
        '"difficulty": "easy|medium|hard", "exam_weightage": 2.0, "estimated_hours": 3.0}], '
        '"prerequisite_edges": [{"prerequisite_code": "TOP-01", "dependent_code": "TOP-02"}]}.\n\n'
        f"Syllabus Text:\n{full_text[:6000]}"
    )
    llm_res = invoke_llm_json(
        system_prompt="You are a precise academic curriculum parser. Only cite excerpts present in the input text.",
        user_prompt=llm_prompt,
    )

    topics_spec: list[dict[str, Any]] = []
    raw_edges: list[tuple[str, str, str]] = []
    exec_mode = "fallback"

    if llm_res.used_llm and isinstance(llm_res.parsed, dict) and isinstance(llm_res.parsed.get("topics"), list):
        raw_topics = [item for item in llm_res.parsed["topics"] if isinstance(item, dict)]
        seen_codes: set[str] = set()
        for idx, item in enumerate(raw_topics[:30], start=1):
            code = str(item.get("topic_code") or f"TOP-{idx:02d}")[:40]
            if code in seen_codes:
                code = f"TOP-{idx:02d}"
            seen_codes.add(code)
            try:
                weightage = float(item.get("exam_weightage") or 2.0)
            except (TypeError, ValueError):
                weightage = 2.0
            try:
                est_hours = float(item.get("estimated_hours") or 3.0)
            except (TypeError, ValueError):
                est_hours = 3.0
            raw_subs = item.get("subtopics")
            subtopics = [str(s) for s in raw_subs][:6] if isinstance(raw_subs, list) else []
            topics_spec.append(
                {
                    "topic_code": code,
                    "subject": str(item.get("subject") or exam_name)[:100],
                    "category": "Uploaded Syllabus",
                    "unit": str(item.get("unit") or "Unit 1")[:180],
                    "title": str(item.get("title") or f"Topic {idx}")[:200],
                    "subtopics": subtopics,
                    "raw_excerpt": str(item.get("raw_excerpt") or full_text[:450])[:800],
                    "source_origin": "extracted_pdf_excerpt",
                    "difficulty": str(item.get("difficulty") or "medium").lower(),
                    "exam_weightage": weightage,
                    "estimated_hours": est_hours,
                    "order_index": idx,
                }
            )
        raw_edge_list = llm_res.parsed.get("prerequisite_edges")
        if isinstance(raw_edge_list, list):
            for edge in raw_edge_list:
                if not isinstance(edge, dict):
                    continue
                src_c = str(edge.get("prerequisite_code", ""))
                dst_c = str(edge.get("dependent_code", ""))
                if src_c in seen_codes and dst_c in seen_codes and src_c != dst_c:
                    raw_edges.append((src_c, dst_c, "llm_extracted"))
        if topics_spec:
            exec_mode = "llm"

    if not topics_spec:
        topics_spec, raw_edges = _parse_syllabus_fallback(full_text, title=title, exam_name=exam_name)

    order_lookup = {t["topic_code"]: t["order_index"] for t in topics_spec}
    clean_edges, _ = resolve_cycles(raw_edges, order_lookup=order_lookup)

    syllabus_id = f"syl_{uuid4().hex[:12]}"
    syllabus = Syllabus(
        id=syllabus_id,
        student_id=student_id,
        title=title,
        exam_name=exam_name,
        target_score=target_score,
        max_score=max_score,
        days_remaining=days_remaining,
        source_type="pdf_upload",
        raw_filename=raw_filename,
    )
    db.add(syllabus)
    db.flush()

    code_to_id: dict[str, str] = {}
    for t in topics_spec:
        tid = f"{syllabus_id}::{t['topic_code']}"
        code_to_id[t["topic_code"]] = tid
        db.add(
            SyllabusTopic(
                id=tid,
                syllabus_id=syllabus_id,
                topic_code=t["topic_code"],
                subject=t["subject"],
                category=t["category"],
                unit=t["unit"],
                title=t["title"],
                subtopics_json=json.dumps(t["subtopics"]),
                raw_excerpt=t["raw_excerpt"],
                source_origin=t["source_origin"],
                difficulty=t["difficulty"] if t["difficulty"] in {"easy", "medium", "hard"} else "medium",
                exam_weightage=t["exam_weightage"],
                estimated_hours=t["estimated_hours"],
                order_index=t["order_index"],
            )
        )
        db.add(
            TopicMastery(
                student_id=student_id,
                syllabus_id=syllabus_id,
                topic_id=tid,
                mastery_score=40.0,
                retention_score=1.0,
                stability_days=4.0,
                review_count=0,
                status="unstarted",
            )
        )
    db.flush()

    for src_c, dst_c, conf in clean_edges:
        db.add(
            TopicPrerequisite(
                syllabus_id=syllabus_id,
                prerequisite_topic_id=code_to_id[src_c],
                dependent_topic_id=code_to_id[dst_c],
                confidence_status=conf,
            )
        )

    if profile is not None:
        profile.active_syllabus_id = syllabus_id
    db.flush()

    state["syllabus_id"] = syllabus_id
    state["topics_count"] = len(topics_spec)
    state["prerequisites_count"] = len(clean_edges)
    state["max_score"] = max_score

    record_trace(
        db=db,
        state=state,
        agent_number=2,
        agent_name="Syllabus Understanding Agent",
        execution_mode=exec_mode,
        started_at=started,
        input_summary=f"pdf={raw_filename}, pages={page_count}",
        output_summary=f"Extracted {len(topics_spec)} topics and {len(clean_edges)} DAG edges (mode={exec_mode})",
    )
    return state
