"""Idempotent dataset seeder and manifest-validated count tests (Task 3)."""

import json

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
from app.schemas import (
    DailyCheckResponse,
    PredictiveScoreOut,
    QuestionOut,
    SyllabusOut,
)
from app.services.seeder import seed_demo_data


def test_seed_demo_data_matches_manifest_and_json_counts(db_session) -> None:
    """Validate seeded DB counts dynamically against dataset_manifest.json & JSON files."""
    dataset_dir = get_settings().dataset_path
    manifest = json.loads((dataset_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    sg = json.loads((dataset_dir / "syllabus_graph.json").read_text(encoding="utf-8"))
    resources = json.loads((dataset_dir / "learning_resources.json").read_text(encoding="utf-8"))
    questions = json.loads((dataset_dir / "question_bank.json").read_text(encoding="utf-8"))
    profiles = json.loads((dataset_dir / "student_profiles.json").read_text(encoding="utf-8"))
    assessments = json.loads((dataset_dir / "assessment_attempts.json").read_text(encoding="utf-8"))
    history = json.loads((dataset_dir / "mastery_history.json").read_text(encoding="utf-8"))

    counts = manifest["counts"]
    assert len(sg["topics"]) == counts["topics"]
    assert len(sg["prerequisite_edges"]) == counts["prerequisite_edges"]
    assert len(resources) == counts["learning_resources"]
    assert len(questions) == counts["questions"]
    assert len(profiles["students"]) == counts["student_profiles"]
    assert len(profiles["parent_teachers"]) == counts["parent_teacher_accounts"]
    assert len(assessments) == counts["historical_assessments"]
    assert len(history["topic_mastery_snapshots"]) == counts["mastery_snapshots"]

    result = seed_demo_data(db_session, dataset_dir=dataset_dir)
    assert result["already_seeded"] is False

    flagship_id = sg["syllabus_id"]
    flagship = db_session.get(Syllabus, flagship_id)
    assert flagship is not None
    assert flagship.max_score == float(manifest["max_score"])

    assert db_session.query(StudentProfile).count() == counts["student_profiles"]
    assert (
        db_session.query(User).filter(User.role == "parent_teacher").count()
        == counts["parent_teacher_accounts"]
    )
    assert db_session.query(Syllabus).count() == counts["student_profiles"]

    assert (
        db_session.query(SyllabusTopic).filter_by(syllabus_id=flagship_id).count()
        == counts["topics"]
    )
    assert (
        db_session.query(TopicPrerequisite).filter_by(syllabus_id=flagship_id).count()
        == counts["prerequisite_edges"]
    )
    assert (
        db_session.query(LearningResource).filter_by(syllabus_id=flagship_id).count()
        == counts["learning_resources"]
    )
    assert (
        db_session.query(Question).filter_by(syllabus_id=flagship_id).count()
        == counts["questions"]
    )
    assert db_session.query(Assessment).count() == counts["historical_assessments"]
    assert (
        db_session.query(TopicMastery)
        .filter_by(student_id="stu_aarav", syllabus_id=flagship_id)
        .count()
        == counts["mastery_snapshots"]
    )

    total_json_attempts = sum(len(a["question_attempts"]) for a in assessments)
    assert db_session.query(QuestionAttempt).count() == total_json_attempts
    assert db_session.query(PlanAdaptation).count() == len(history.get("sample_adaptations", []))

    mentor = db_session.get(User, "pt_kavita")
    assert mentor is not None
    assert mentor.linked_student_id == "stu_aarav"


def test_seed_demo_data_is_idempotent(db_session) -> None:
    """Running seed_demo_data twice must leave row counts unchanged without errors."""
    dataset_dir = get_settings().dataset_path
    first = seed_demo_data(db_session, dataset_dir=dataset_dir)
    snapshot_first = (
        db_session.query(User).count(),
        db_session.query(StudentProfile).count(),
        db_session.query(Syllabus).count(),
        db_session.query(SyllabusTopic).count(),
        db_session.query(TopicPrerequisite).count(),
        db_session.query(LearningResource).count(),
        db_session.query(Question).count(),
        db_session.query(Assessment).count(),
        db_session.query(QuestionAttempt).count(),
        db_session.query(TopicMastery).count(),
        db_session.query(StudyPlanItem).count(),
        db_session.query(PlanAdaptation).count(),
    )

    second = seed_demo_data(db_session, dataset_dir=dataset_dir)
    snapshot_second = (
        db_session.query(User).count(),
        db_session.query(StudentProfile).count(),
        db_session.query(Syllabus).count(),
        db_session.query(SyllabusTopic).count(),
        db_session.query(TopicPrerequisite).count(),
        db_session.query(LearningResource).count(),
        db_session.query(Question).count(),
        db_session.query(Assessment).count(),
        db_session.query(QuestionAttempt).count(),
        db_session.query(TopicMastery).count(),
        db_session.query(StudyPlanItem).count(),
        db_session.query(PlanAdaptation).count(),
    )

    assert first["already_seeded"] is False
    assert second["already_seeded"] is True
    assert snapshot_first == snapshot_second


def test_schemas_serialization_and_safety_flags(db_session) -> None:
    """Verify Pydantic schema serialization hides answer keys and preserves honest labels."""
    seed_demo_data(db_session)
    flagship = db_session.get(Syllabus, "gate_cse_flagship_2026")
    syl_out = SyllabusOut.model_validate(flagship)
    assert syl_out.max_score == 100.0

    q = db_session.query(Question).filter_by(syllabus_id=flagship.id).first()
    q_out = QuestionOut(
        id=q.id,
        syllabus_id=q.syllabus_id,
        topic_id=q.topic_id,
        subtopic=q.subtopic,
        difficulty=q.difficulty,
        question_type=q.question_type,
        prompt=q.prompt,
        options=json.loads(q.options_json),
        expected_time_sec=q.expected_time_sec,
        source_origin=q.source_origin,
        is_generated=q.is_generated,
    )
    assert "correct_answer" not in q_out.model_dump()

    pred = PredictiveScoreOut(
        current_estimated_score=62.5,
        projected_estimated_score=76.0,
        max_score=100.0,
        target_score=78.0,
        target_gap=15.5,
        readiness_band="On Track",
    )
    assert pred.is_estimate is True

    daily_fields = DailyCheckResponse.model_fields
    assert "is_simulation" in daily_fields
