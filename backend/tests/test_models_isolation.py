"""Schema completeness and SQLite cross-syllabus composite FK isolation tests."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    LearningResource,
    Question,
    StudentProfile,
    Syllabus,
    SyllabusTopic,
    TopicMastery,
    TopicPrerequisite,
    User,
)

EXPECTED_TABLES = {
    "users",
    "student_profiles",
    "syllabi",
    "syllabus_topics",
    "topic_prerequisites",
    "topic_mastery",
    "learning_resources",
    "questions",
    "study_plan_items",
    "assessments",
    "question_attempts",
    "plan_adaptations",
    "agent_execution_logs",
}


def _create_student_and_syllabus(
    db_session,
    suffix: str,
    user_id: str | None = None,
    profile_id: str | None = None,
) -> tuple[StudentProfile, Syllabus]:
    """Helper local to schema isolation tests to create a student + syllabus cleanly."""
    if user_id is None:
        user = User(
            id=f"usr_{suffix}",
            name=f"Student {suffix}",
            email=f"student_{suffix}@test.edu",
            password_hash="hashed_pw",
            role="student",
        )
        db_session.add(user)
        db_session.flush()
        profile = StudentProfile(
            id=f"stu_{suffix}",
            user_id=user.id,
            link_code=f"LINK-{suffix}",
        )
        db_session.add(profile)
        db_session.flush()
        student_id = profile.id
    else:
        student_id = profile_id
        profile = db_session.get(StudentProfile, student_id)

    syllabus = Syllabus(
        id=f"syl_{suffix}",
        student_id=student_id,
        title=f"Syllabus {suffix}",
        exam_name="Test Exam",
    )
    db_session.add(syllabus)
    db_session.flush()
    return profile, syllabus


def test_all_13_tables_created(db_session) -> None:
    """Verify Base.metadata creates every required table."""
    actual_tables = set(inspect(db_session.get_bind()).get_table_names())
    assert EXPECTED_TABLES.issubset(actual_tables)
    assert len(EXPECTED_TABLES) == 13


def test_sqlite_foreign_keys_pragma_enabled(db_session) -> None:
    """Verify SQLAlchemy connect listener turns PRAGMA foreign_keys=ON in tests."""
    fk_flag = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert fk_flag == 1


def test_same_syllabus_prerequisite_succeeds(db_session) -> None:
    """Prerequisite edges within the same syllabus commit without error."""
    _, syl = _create_student_and_syllabus(db_session, "same")
    t1 = SyllabusTopic(
        id="syl_same::T1",
        syllabus_id=syl.id,
        topic_code="T1",
        subject="OS",
        title="Processes",
    )
    t2 = SyllabusTopic(
        id="syl_same::T2",
        syllabus_id=syl.id,
        topic_code="T2",
        subject="OS",
        title="Deadlocks",
    )
    db_session.add_all([t1, t2])
    db_session.flush()

    edge = TopicPrerequisite(
        syllabus_id=syl.id,
        prerequisite_topic_id=t1.id,
        dependent_topic_id=t2.id,
        confidence_status="verified_seed",
    )
    db_session.add(edge)
    db_session.commit()

    saved = db_session.query(TopicPrerequisite).filter_by(syllabus_id=syl.id).all()
    assert len(saved) == 1


def test_cross_syllabus_prerequisite_rejected_by_db(db_session) -> None:
    """Review Focus #2: Prerequisite spanning two syllabi raises IntegrityError."""
    profile, syl_1 = _create_student_and_syllabus(db_session, "s1")
    _, syl_2 = _create_student_and_syllabus(
        db_session,
        "s2",
        user_id=profile.user_id,
        profile_id=profile.id,
    )

    topic_a = SyllabusTopic(
        id="syl_s1::A",
        syllabus_id=syl_1.id,
        topic_code="A",
        subject="CS",
        title="Topic A",
    )
    topic_b = SyllabusTopic(
        id="syl_s2::B",
        syllabus_id=syl_2.id,
        topic_code="B",
        subject="Math",
        title="Topic B",
    )
    db_session.add_all([topic_a, topic_b])
    db_session.commit()

    bad_edge = TopicPrerequisite(
        syllabus_id=syl_1.id,
        prerequisite_topic_id=topic_a.id,
        dependent_topic_id=topic_b.id,
    )
    db_session.add(bad_edge)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cross_syllabus_and_cross_student_isolation(db_session) -> None:
    """Verify TopicMastery, LearningResource, and Question enforce composite FKs."""
    stu_1, syl_1 = _create_student_and_syllabus(db_session, "u1")
    stu_2, syl_2 = _create_student_and_syllabus(db_session, "u2")

    t1 = SyllabusTopic(
        id="syl_u1::T1",
        syllabus_id=syl_1.id,
        topic_code="T1",
        subject="DBMS",
        title="ER Model",
    )
    t2 = SyllabusTopic(
        id="syl_u2::T2",
        syllabus_id=syl_2.id,
        topic_code="T2",
        subject="CN",
        title="Routing",
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Wrong topic syllabus in TopicMastery
    db_session.add(
        TopicMastery(student_id=stu_1.id, syllabus_id=syl_1.id, topic_id=t2.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Wrong student owning syllabus in TopicMastery
    db_session.add(
        TopicMastery(student_id=stu_2.id, syllabus_id=syl_1.id, topic_id=t1.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Wrong syllabus topic in LearningResource
    db_session.add(
        LearningResource(
            syllabus_id=syl_1.id,
            topic_id=t2.id,
            modality="notes",
            title="Leak Check",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Wrong syllabus topic in Question
    db_session.add(
        Question(
            syllabus_id=syl_1.id,
            topic_id=t2.id,
            prompt="Cross-syllabus leak?",
            correct_answer="No",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

