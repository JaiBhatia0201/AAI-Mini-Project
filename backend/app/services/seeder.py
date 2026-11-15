"""Idempotent dataset seeder loading data/gate_cse/*.json into SQLite."""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any
import bcrypt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Assessment,
    LearningResource,
    PlanAdaptation,
    Question,
    QuestionAttempt,
    StudentProfile,
    StudyPlanItem,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
    User,
)


def _load_json(path: Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))

def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hash_demo_password(raw_password: str = "demo1234") -> str:
    """Hash a demo account password once using bcrypt."""
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load_gate_bundle(dataset_dir: Path) -> dict[str, Any]:
    """Load the mainfest and all JSON dataset files from disk."""
    return {
        "manifest": _load_json(dataset_dir / "dataset_manifest.json"),
        "syllabus": _load_json(dataset_dir / "syllabus_graph.json"),
        "resources": _load_json(dataset_dir / "learning_resources.json"),
        "questions": _load_json(dataset_dir / "question_bank.json"),
        "profiles": _load_json(dataset_dir / "student_profiles.json"),
        "assessments": _load_json(dataset_dir / "assessment_attempts.json"),
        "history": _load_json(dataset_dir / "mastery_history.json"),
    }


def seed_gate_syllabus_for_student(
    db: Session,
    student_id: str,
    syllabus_id: str,
    bundle: dict[str, Any],
    target_score: float = 78.0,
    days_remaining: int = 90,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
) -> tuple[Syllabus, dict[str, str], dict[str, str]]:
    """Create a complete isolated GATE CSE syllabus copy for one student."""
    sg = bundle["syllabus"]
    strength_set = set(strengths or [])
    weakness_set = set(weaknesses or [])

    syllabus = Syllabus(
        id=syllabus_id,
        student_id=student_id,
        title=sg["title"],
        exam_name=sg["exam_name"],
        target_score=target_score,
        max_score=float(sg["max_score"]),
        days_remaining=days_remaining,
        source_type="seeded",
        raw_filename="sample_syllabi/gate_cse_syllabus.pdf",
    )
    db.add(syllabus)
    db.flush()

    topic_map: dict[str, str] = {}
    mastery_rows: list[TopicMastery] = []
    for t in sg["topics"]:
        scoped_topic_id = f"{syllabus_id}::{t['topic_id']}"
        topic_map[t["topic_id"]] = scoped_topic_id
        db.add(
            SyllabusTopic(
                id=scoped_topic_id,
                syllabus_id=syllabus_id,
                topic_code=t["topic_id"],
                subject=t["subject"],
                category=t.get("category", "Core"),
                unit=t.get("unit", "Unit 1"),
                title=t["title"],
                subtopics_json=json.dumps(t.get("subtopics", [])),
                raw_excerpt=t.get("raw_excerpt", ""),
                source_origin=t.get("source_origin", "curated_dataset_note"),
                difficulty=t.get("difficulty", "medium"),
                exam_weightage=float(t.get("exam_weightage", 1.0)),
                estimated_hours=float(t.get("estimated_hours", 2.0)),
                order_index=int(t.get("order_index", 0))
            )
        )
        baseline = (
            68.0
            if t["subject"] in strength_set
            else (38.0 if t["subject"] in weakness_set else 45.0)
        )
        mastery_rows.append(
            TopicMastery(
                student_id=student_id,
                syllabus_id=syllabus_id,
                topic_id=scoped_topic_id,
                mastery_score=baseline,
                retention_score=1.0,
                stability_days=4.0,
                review_count=0,
                status="weak" if baseline < 60.0 else "learning",
            )
        )
    db.flush()
    db.add_all(mastery_rows)

    for edge in sg["prerequisite_edges"]:
        db.add(
            TopicPrerequisite(
                syllabus_id=syllabus_id,

                prerequisite_topic_id=topic_map[edge["prerequisite_topic_id"]],

                dependent_topic_id=topic_map[edge["dependent_topic_id"]], confidence_status=edge.get("confidence_status", "verified_seed"),
            )
        )

    for res in bundle["resources"]:
        db.add(
            LearningResource(
                id=f"{syllabus_id}::{res['resource_id']}",
                syllabus_id=syllabus_id,
                topic_id=topic_map[res["topic_id"]],
                modality=res["modality"],
                title=res["title"],
                source_ref=res.get("source_ref", ""),
                url_or_content=res.get("url_or_content", ""),
                summary=res.get("summary", ""),
                source_origin=res.get("source_origin", "curated_dataset_note"),
                created_by_agent="Seed Curated Bank",
            )
        )
    
    question_map: dict[str, str] = {}
    for q in bundle["questions"]:
        scoped_qid = f"{syllabus_id}::{q['question_id']}"
        question_map[q["question_id"]] = scoped_qid
        db.add(
            Question(
                id=scoped_qid,
                syllabus_id=syllabus_id,
                topic_id=topic_map[q["topic_id"]],
                subtopic=q.get("subtopic", ""),
                difficulty=q.get("difficulty", "medium"),
                question_type=q.get("question_type", "MCQ"),
                prompt=q["prompt"],
                options_json=json.dumps(q.get("options", [])),
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                expected_time_sec=int(q.get("expected_time_sec", 60)),
                source_origin=q.get("source_origin", "curated_dataset_note"),
                is_generated=False,
            )
        )
    
    db.flush()
    return syllabus, topic_map, question_map


def seed_demo_data(db: Session, dataset_dir: Path | None = None) -> dict[str, Any]:
    """Idempotently seed GATE CSE flagship data, personas, assessments, and history."""
    base_dir = dataset_dir or get_settings().dataset_path
    bundle = load_gate_bundle(base_dir)
    manifest = bundle["manifest"]
    flagship_id = bundle["syllabus"]["syllabus_id"]

    if db.get(Syllabus, flagship_id) is not None:
        return {"already_seeded": True, "flagship_syllabus_id": flagship_id}

    pw_hash = _hash_demo_password("demo1234")
    today = date.today()
    student_maps: dict[str, tuple[str, dict[str, str], dict[str, str]]] = {}

    for stu in bundle["profiles"]["students"]:
        stu_id = stu["student_id"]
        user = User(
            id=f"usr_{stu_id}",
            name=stu["name"],
            email=stu["email"],
            password_hash=pw_hash,
            role="student",
        )
        profile = StudentProfile(
            id=stu_id,
            user_id=user.id,
            link_code=stu["link_code"],
            current_grade=stu.get("current_grade", ""),
            daily_hours=float(stu["daily_hours"]),
            learning_style=stu["learning_style"],
            study_streak=int(stu.get("study_streak", 0)),
            total_hours_logged=float(stu.get("total_hours_logged", 0.0)),
            last_active_date=today,
            stated_strengths_json=json.dumps(stu.get("stated_strengths", [])),
            stated_weaknesses_json=json.dumps(stu.get("stated_weaknesses", [])),
        )
        db.add_all([user, profile])
        db.flush()

        syl_id = flagship_id if stu_id == "stu_aarav" else f"gate_cse_{stu_id}"
        syl, t_map, q_map = seed_gate_syllabus_for_student(
            db=db,
            student_id=stu_id,
            syllabus_id=syl_id,
            bundle=bundle,
            target_score=float(stu["target_score"]),
            days_remaining=int(stu["days_remaining"]),
            strengths=stu.get("stated_strengths", []),
            weaknesses=stu.get("stated_weaknesses", []),
        )
        profile.active_syllabus_id = syl.id
        student_maps[stu_id] = (syl.id, t_map, q_map)

    # Apply historical mastery snapshots for Aarav
    aarav_syl_id, aarav_t_map, _ = student_maps["stu_aarav"]
    aarav_mastery_rows = {
        m.topic_id: m
        for m in db.query(TopicMastery)
        .filter_by(student_id="stu_aarav", syllabus_id=aarav_syl_id)
        .all()
    }
    for snap in bundle["history"]["topic_mastery_snapshots"]:
        scoped_tid = aarav_t_map[snap["topic_id"]]
        row = aarav_mastery_rows[scoped_tid]
        row.mastery_score = float(snap["mastery_score"])
        row.retention_score = float(snap["retention_score"])
        row.stability_days = float(snap["stability_days"])
        row.review_count = int(snap["review_count"])
        row.status = snap["status"]
        row.last_practiced_at = _parse_dt(snap.get("last_practiced_at"))

    # Seed started upcoming plan items for Aarav
    starter_plan = [
        ("CN-03", 0, "revision", 1.5, "Root-cause prerequisite blocker for CN-04"),
        ("CN-04", 1, "practice", 2.0, "Mastery 34% < 60% threshold"),
        ("CN-04", 2, "assessment", 1.0, "Verify remediation before advancing to CN-05"),
        ("TOC-02", 3, "revision", 1.5, "Weak topic refresher scheduled"),
        ("PS-02", 4, "learn", 2.0, "Next topological syllabus milestone"),
    ]
    for code, offset, task_type, hrs, reason in starter_plan:
        db.add(
            StudyPlanItem(
                student_id="stu_aarav",
                syllabus_id=aarav_syl_id,
                topic_id=aarav_t_map[code],
                scheduled_date=today + timedelta(days=offset),
                day_number=offset + 1,
                task_type=task_type,
                duration_hours=hrs,
                status="pending",
                adaptation_reason=reason,
            )
        )

    # Seed historical assessment & itemized question attempts BEFORE adaptations
    for asm in bundle["assessments"]:
        stu_id = asm["student_id"]
        syl_id, t_map, q_map = student_maps[stu_id]
        db.add(
            Assessment(
                id=asm["assessment_id"],
                student_id=stu_id,
                syllabus_id=syl_id,
                title=asm["title"],
                assessment_type=asm["assessment_type"],
                score=float(asm["score"]),
                max_score=float(asm["max_score"]),
                accuracy=float(asm["accuracy"]),
                time_taken_sec=int(asm["time_taken_sec"]),
                created_at=_parse_dt(asm["created_at"]),
            )
        )
        db.flush()
        for att in asm["question_attempts"]:
            db.add(
                QuestionAttempt(
                    assessment_id=asm["assessment_id"],
                    student_id=stu_id,
                    syllabus_id=syl_id,
                    topic_id=t_map[att["topic_id"]],
                    question_id=q_map[att["question_id"]],
                    selected_answer=att["selected_answer"],
                    is_correct=bool(att["is_correct"]),
                    time_taken_sec=int(att["time_taken_sec"]),
                    created_at=_parse_dt(att["created_at"]),
                )
            )
    
    for adp in bundle["history"].get("sample_adaptations", []):
        stu_id = adp["student_id"]
        syl_id, t_map, _ = student_maps[stu_id]
        db.add(
            PlanAdaptation(
                id=adp["adaptation_id"],
                student_id=stu_id,
                syllabus_id=syl_id,

                trigger_assessment_id=adp.get("trigger_assessment_id"),
                weak_topics_json=json.dumps([t_map[c] for c in adp.get("weak_topics", [])]),
                summary=adp["summary"],
                changes_json=json.dumps(adp.get("changes", [])),
                created_at=_parse_dt(adp.get("created_at")),
            )
        )
    
    for pt in bundle["profiles"].get("parent_teachers", []):
        db.add(
            User(
                id=pt["user_id"],
                name=pt["name"],
                email=pt["email"],
                password_hash=pw_hash,
                role="parent_teacher",
                linked_student_id=pt["linked_student_id"],
            )
        )
    
    db.commit()
    return {
        "already_seeded": False,
        "flagship_syllabus_id": flagship_id,
        "manifest_counts": manifest["counts"],
    }