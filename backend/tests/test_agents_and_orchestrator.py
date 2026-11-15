"""Integration tests for Agents 1-10 and Agent 11 LangGraph Orchestrator."""

import io
from pathlib import Path
from pypdf import PdfWriter
import pytest
from sqlalchemy.orm import Session

from app.agents.orchestrator import (
    run_assessment_adaptation,
    run_complete_diagnostic,
    run_demo_simulation,
    run_onboard_syllabus,
    run_study_session,
)
from app.agents.syllabus_agent import ScannedPDFError
from app.config import get_settings
from app.models import (
    AgentExecutionLog,
    Assessment,
    PlanAdaptation,
    Question,
    StudentProfile,
    StudyPlanItem,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    User,
)
from app.services.auth import hash_password


def _make_blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_text_pdf_bytes(lines: list[str]) -> bytes:
    """Create a valid minimal text-selectable PDF readable by pypdf without extra deps."""
    escaped = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in lines]
    text_ops = ["BT", "/F1 12 Tf", "50 740 Td"]
    for i, ln in enumerate(escaped):
        if i > 0:
            text_ops.append("0 -18 Td")
        text_ops.append(f"({ln}) Tj")
    text_ops.append("ET")
    stream_bytes = "\n".join(text_ops).encode("latin-1", errors="replace")

    objs: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
        + stream_bytes
        + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def _create_fresh_student(db: Session, student_id: str = "stu_new_01") -> StudentProfile:
    user = User(
        id=f"usr_{student_id}",
        email=f"{student_id}@example.com",
        password_hash=hash_password("pass1234"),
        name="New Custom Student",
        role="student",
    )
    profile = StudentProfile(
        id=student_id,
        user_id=user.id,
        daily_hours=3.0,
        learning_style="visual",
        link_code=f"LNK-{student_id[-4:].upper()}",
    )
    db.add_all([user, profile])
    db.commit()
    return profile


def test_scanned_pdf_rejected_before_db_writes(db_session: Session):
    profile = _create_fresh_student(db_session, "stu_scan")
    with pytest.raises(ScannedPDFError):
        run_onboard_syllabus(
            db_session,
            student_id=profile.id,
            onboard_mode="pdf_upload",
            pdf_bytes=_make_blank_pdf_bytes(),
            pdf_filename="scanned.pdf",
        )
    assert db_session.query(Syllabus).filter_by(student_id=profile.id).count() == 0
    assert db_session.query(AgentExecutionLog).filter_by(student_id=profile.id).count() == 0


def test_custom_pdf_onboard_diagnostic_teach_assess_and_simulation(db_session: Session):
    profile = _create_fresh_student(db_session, "stu_custom")
    custom_pdf = _make_text_pdf_bytes(
        [
            "Unit 1: Linear Algebra Foundations",
            "1.1 Matrix Rank and Eigenvalues: vector spaces, determinants, spectral decomposition",
            "1.2 Linear Transformations: kernel, range, orthogonal projections",
            "Unit 2: Probability and Statistics",
            "2.1 Random Variables and Distributions: Bayes rule, variance, Gaussian density",
        ]
    )

    onboard = run_onboard_syllabus(
        db_session,
        student_id=profile.id,
        onboard_mode="pdf_upload",
        pdf_bytes=custom_pdf,
        pdf_filename="ml_math_syllabus.pdf",
        title="ML Mathematics",
        exam_name="University ML Midsem",
        target_score=80.0,
        max_score=100.0,
        days_remaining=30,
        daily_hours=2.5,
        learning_style="visual",
    )
    db_session.commit()

    syl_id = onboard["syllabus_id"]
    assert onboard["topics_count"] >= 3
    assert len(onboard["diagnostic_questions"]) >= 3
    assert len(onboard["traces"]) >= 5
    assert "University ML Midsem" in onboard["coaching_message"]

    # Complete diagnostic (mix of correct + incorrect on first topics)
    topics = db_session.query(SyllabusTopic).filter_by(syllabus_id=syl_id).order_by(SyllabusTopic.order_index).all()
    diag_qs = db_session.query(Question).filter_by(syllabus_id=syl_id).all()
    answers = [
        {"question_id": q.id, "selected_answer": "__wrong__" if i == 0 else q.correct_answer, "time_taken_sec": 30}
        for i, q in enumerate(diag_qs[:4])
    ]
    diag = run_complete_diagnostic(
        db_session,
        student_id=profile.id,
        syllabus_id=syl_id,
        diagnostic_answers=answers,
        self_ratings={topics[-1].id: "strong"},
    )
    db_session.commit()
    assert db_session.query(StudyPlanItem).filter_by(student_id=profile.id, syllabus_id=syl_id).count() > 0
    assert diag["coaching_message"]

    # Teach and practice Flow C
    target_topic = topics[-1]
    lesson_state = run_study_session(
        db_session,
        student_id=profile.id,
        syllabus_id=syl_id,
        topic_id=target_topic.id,
        tutor_question="Explain why this concept matters",
    )
    db_session.commit()
    assert lesson_state["lesson_payload"]["topic_id"] == target_topic.id
    assert lesson_state["lesson_payload"]["source_origin"]
    assert len(lesson_state["practice_questions"]) >= 1

    # Flow D weak conditional branch: fail topic questions deliberately (even with prerequisite weak)
    first_topic = topics[0]
    first_m = (
        db_session.query(TopicMastery)
        .filter_by(student_id=profile.id, syllabus_id=syl_id, topic_id=first_topic.id)
        .first()
    )
    assert first_m is not None
    first_m.mastery_score = 35.0
    db_session.flush()

    dep_topic = topics[1]
    dep_qs = db_session.query(Question).filter_by(syllabus_id=syl_id, topic_id=dep_topic.id).all()
    weak_assess = Assessment(
        student_id=profile.id,
        syllabus_id=syl_id,
        title="Module Check",
        assessment_type="practice_quiz",
        max_score=100.0,
    )
    db_session.add(weak_assess)
    db_session.flush()

    weak_out = run_assessment_adaptation(
        db_session,
        student_id=profile.id,
        syllabus_id=syl_id,
        assessment_id=weak_assess.id,
        submitted_answers=[
            {"question_id": q.id, "selected_answer": "__wrong__", "time_taken_sec": 75}
            for q in dep_qs
        ],
    )
    db_session.commit()
    assert weak_out["remediation_required"] is True
    assert dep_topic.id in weak_out["weak_topics"]
    assert weak_out["adaptation_diff"] is not None
    assert len(weak_out["adaptation_diff"]["changes"]) >= 1

    # Flow D strong conditional branch: pass all questions cleanly -> +3/+7/+14/+30 spaced checkpoints
    strong_assess = Assessment(
        student_id=profile.id,
        syllabus_id=syl_id,
        title="Mastery Check",
        assessment_type="practice_quiz",
        max_score=100.0,
    )
    db_session.add(strong_assess)
    db_session.flush()
    strong_qs = db_session.query(Question).filter_by(syllabus_id=syl_id, topic_id=target_topic.id).all()
    target_m = (
        db_session.query(TopicMastery)
        .filter_by(student_id=profile.id, syllabus_id=syl_id, topic_id=target_topic.id)
        .first()
    )
    assert target_m is not None
    target_m.mastery_score = 80.0
    db_session.flush()

    strong_out = run_assessment_adaptation(
        db_session,
        student_id=profile.id,
        syllabus_id=syl_id,
        assessment_id=strong_assess.id,
        submitted_answers=[
            {"question_id": q.id, "selected_answer": q.correct_answer, "time_taken_sec": 30}
            for q in strong_qs
        ],
    )
    db_session.commit()
    assert strong_out["remediation_required"] is False
    offsets = {c["day_offset"] for c in strong_out["adaptation_diff"]["changes"]}
    assert {7, 14, 30}.issubset(offsets)

    # Flow F non-destructive simulation check
    before_mastery = [
        (m.topic_id, float(m.mastery_score), float(m.retention_score), m.status)
        for m in db_session.query(TopicMastery).filter_by(student_id=profile.id, syllabus_id=syl_id).all()
    ]
    before_plan_count = db_session.query(StudyPlanItem).filter_by(student_id=profile.id, syllabus_id=syl_id).count()
    before_adp_count = db_session.query(PlanAdaptation).filter_by(student_id=profile.id, syllabus_id=syl_id).count()
    before_trace_count = db_session.query(AgentExecutionLog).filter_by(student_id=profile.id, syllabus_id=syl_id).count()

    sim_out = run_demo_simulation(db_session, student_id=profile.id, syllabus_id=syl_id, days_elapsed=21)
    db_session.commit()

    assert sim_out["is_simulation"] is True
    assert len(sim_out["decay_alerts"]) >= 1
    assert all(t["execution_mode"] == "simulation" for t in sim_out["traces"])

    after_mastery = [
        (m.topic_id, float(m.mastery_score), float(m.retention_score), m.status)
        for m in db_session.query(TopicMastery).filter_by(student_id=profile.id, syllabus_id=syl_id).all()
    ]
    assert before_mastery == after_mastery
    assert db_session.query(StudyPlanItem).filter_by(student_id=profile.id, syllabus_id=syl_id).count() == before_plan_count
    assert db_session.query(PlanAdaptation).filter_by(student_id=profile.id, syllabus_id=syl_id).count() == before_adp_count
    assert db_session.query(AgentExecutionLog).filter_by(student_id=profile.id, syllabus_id=syl_id).count() == before_trace_count


def test_real_gate_pdf_ingestion_works(db_session: Session):
    profile = _create_fresh_student(db_session, "stu_gate_pdf")
    gate_pdf = Path(get_settings().dataset_path) / "sample_syllabi" / "gate_cse_syllabus.pdf"
    assert gate_pdf.exists(), f"Missing dataset PDF at {gate_pdf}"

    state = run_onboard_syllabus(
        db_session,
        student_id=profile.id,
        onboard_mode="pdf_upload",
        pdf_bytes=gate_pdf.read_bytes(),
        pdf_filename=gate_pdf.name,
        title="GATE CSE PDF Copy",
        exam_name="GATE CSE",
    )
    db_session.commit()
    assert state["topics_count"] >= 4
    assert len(state["diagnostic_questions"]) >= 4
