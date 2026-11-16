"""End-to-end REST API integration tests using FastAPI TestClient & isolated SQLite."""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, build_sqlite_engine, get_db
from app.main import app
from app.models import (
    AgentExecutionLog,
    PlanAdaptation,
    Question,
    StudyPlanItem,
    Syllabus,
    TopicMastery,
)
from app.services.seeder import seed_demo_data
from tests.test_agents_and_orchestrator import _make_blank_pdf_bytes, _make_text_pdf_bytes


@pytest.fixture()
def api_client(tmp_path: Path):
    """Provide TestClient wired to a fresh seeded temporary SQLite database."""
    db_file = tmp_path / "e2e_test.db"
    test_engine = build_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=Session)

    seed_db = TestingSessionLocal()
    try:
        seed_demo_data(seed_db)
    finally:
        seed_db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, TestingSessionLocal
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_brand_new_student_end_to_end_and_rbac(api_client):
    client, SessionCls = api_client

    # 1. Health check reports honest active/fallback mode
    from app.config import get_settings

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["llm_mode"] in {"llm", "fallback"}
    assert health.json()["retrieval_mode"] in {"api_faiss", "tfidf_fallback"}
    if health.json()["llm_provider"] == "none":
        assert health.json()["llm_mode"] == "fallback"
    if get_settings().effective_embedding_provider == "local":
        assert health.json()["retrieval_mode"] == "tfidf_fallback"

    # 2. Register brand-new student (not in dataset)
    reg = client.post(
        "/api/auth/register",
        json={
            "name": "Ananya Verma",
            "email": "ananya.new@example.com",
            "password": "password123",
            "role": "student",
        },
    )
    assert reg.status_code == 201, reg.text
    student_token = reg.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    link_code = reg.json()["user"]["student_profile"]["link_code"]
    assert link_code

    # Update profile preferences
    prof_res = client.put(
        "/api/students/profile",
        headers=student_headers,
        json={"daily_hours": 3.5, "learning_style": "practice", "current_grade": "B.Tech Sem 6"},
    )
    assert prof_res.status_code == 200
    assert prof_res.json()["learning_style"] == "practice"

    # 3. Scanned PDF rejected with 422 before creating any DB records
    scan_res = client.post(
        "/api/workflows/onboard-syllabus",
        headers=student_headers,
        data={"onboard_mode": "pdf_upload", "title": "Bad PDF", "exam_name": "Test"},
        files={"file": ("scan.pdf", _make_blank_pdf_bytes(), "application/pdf")},
    )
    assert scan_res.status_code == 422

    # 4. Upload real text-selectable custom syllabus PDF
    pdf_bytes = _make_text_pdf_bytes(
        [
            "Unit 1: Operating Systems",
            "1.1 Process Scheduling: FCFS, Round Robin, CPU bursts, deadlock prevention",
            "1.2 Virtual Memory: Paging, TLB hit ratio, page replacement policies",
            "Unit 2: Database Management",
            "2.1 Relational Algebra & Normalization: BCNF, functional dependencies, transactions",
        ]
    )
    onboard_res = client.post(
        "/api/workflows/onboard-syllabus",
        headers=student_headers,
        data={
            "onboard_mode": "pdf_upload",
            "title": "Sem 6 Core CS",
            "exam_name": "Endsem CS-601",
            "target_score": "85",
            "max_score": "100",
            "days_remaining": "45",
            "daily_hours": "3.5",
            "learning_style": "practice",
        },
        files={"file": ("cs601.pdf", pdf_bytes, "application/pdf")},
    )
    assert onboard_res.status_code == 200, onboard_res.text
    onboard_data = onboard_res.json()
    custom_syl_id = onboard_data["syllabus"]["id"]
    assert onboard_data["topics_count"] >= 3
    assert len(onboard_data["diagnostic_questions"]) >= 3
    run_id = onboard_data["run_id"]

    # 5. Inspect Knowledge Graph & confirm a needs_review edge
    graph_res = client.get(f"/api/syllabi/{custom_syl_id}/graph", headers=student_headers)
    assert graph_res.status_code == 200
    graph_json = graph_res.json()
    topics = graph_json["topics"]
    edges = graph_json["prerequisites"]
    if edges:
        patch_res = client.patch(
            f"/api/syllabi/{custom_syl_id}/prerequisites",
            headers=student_headers,
            json={
                "updates": [
                    {
                        "prerequisite_topic_id": edges[0]["prerequisite_topic_id"],
                        "dependent_topic_id": edges[0]["dependent_topic_id"],
                        "action": "confirm",
                    }
                ]
            },
        )
        assert patch_res.status_code == 200
        assert any(e["confidence_status"] == "user_confirmed" for e in patch_res.json()["prerequisites"])

    # 6. Complete diagnostic calibration
    diag_res = client.post(
        "/api/workflows/complete-diagnostic",
        headers=student_headers,
        json={
            "syllabus_id": custom_syl_id,
            "answers": [
                {
                    "question_id": q["id"],
                    "topic_id": q["topic_id"],
                    "selected_answer": "__wrong__",
                    "time_taken_sec": 40,
                }
                for q in onboard_data["diagnostic_questions"][:3]
            ],
            "self_ratings": {topics[-1]["id"]: "strong"},
        },
    )
    assert diag_res.status_code == 200
    assert diag_res.json()["coaching_message"]

    # 7. Resources + RAG/TF-IDF discovery + AI Tutor session
    res_list = client.get(f"/api/resources?syllabus_id={custom_syl_id}", headers=student_headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 3

    disc = client.post(
        "/api/resources/discover",
        headers=student_headers,
        json={"syllabus_id": custom_syl_id, "query": "paging TLB memory", "top_k": 3},
    )
    assert disc.status_code == 200
    assert len(disc.json()["hits"]) >= 1

    tutor_res = client.post(
        "/api/tutor/ask",
        headers=student_headers,
        json={
            "syllabus_id": custom_syl_id,
            "topic_id": topics[0]["id"],
            "question": "Explain CPU scheduling step by step",
        },
    )
    assert tutor_res.status_code == 200
    assert tutor_res.json()["topic_id"] == topics[0]["id"]
    assert len(tutor_res.json()["practice_questions"]) >= 1

    # 8. Planner + Mark item completed + Manual adaptive check
    plan_res = client.get(f"/api/planner?syllabus_id={custom_syl_id}", headers=student_headers)
    assert plan_res.status_code == 200
    plan_items = plan_res.json()["items"]
    assert len(plan_items) >= 1

    toggle_res = client.patch(
        f"/api/planner/items/{plan_items[0]['id']}",
        headers=student_headers,
        json={"status": "completed"},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["status"] == "completed"

    # 9. Start & Submit Assessment -> closed-loop adaptation
    start_ass = client.post(
        "/api/assessments/start",
        headers=student_headers,
        json={"syllabus_id": custom_syl_id, "topic_id": topics[0]["id"], "assessment_type": "topic_quiz", "question_count": 3},
    )
    assert start_ass.status_code == 200
    ass_id = start_ass.json()["assessment_id"]
    ass_qs = start_ass.json()["questions"]

    submit_ass = client.post(
        f"/api/assessments/{ass_id}/submit",
        headers=student_headers,
        json={
            "answers": [
                {"question_id": q["id"], "selected_answer": "__wrong__", "time_taken_sec": 70}
                for q in ass_qs
            ]
        },
    )
    assert submit_ass.status_code == 200
    assert submit_ass.json()["adaptation"] is not None

    hist = client.get(f"/api/assessments/history?syllabus_id={custom_syl_id}", headers=student_headers)
    assert hist.status_code == 200
    assert len(hist.json()) >= 2

    # 10. Non-destructive simulation: zero DB mutation
    db_check = SessionCls()
    before_m = [(m.topic_id, float(m.mastery_score), float(m.retention_score)) for m in db_check.query(TopicMastery).filter_by(syllabus_id=custom_syl_id).all()]
    before_plans = db_check.query(StudyPlanItem).filter_by(syllabus_id=custom_syl_id).count()
    before_adps = db_check.query(PlanAdaptation).filter_by(syllabus_id=custom_syl_id).count()
    before_logs = db_check.query(AgentExecutionLog).filter_by(syllabus_id=custom_syl_id).count()
    db_check.close()

    sim_res = client.post(
        "/api/workflows/daily-check/simulate",
        headers=student_headers,
        json={"syllabus_id": custom_syl_id, "simulate_days_elapsed": 14},
    )
    assert sim_res.status_code == 200
    assert sim_res.json()["is_simulation"] is True
    assert len(sim_res.json()["traces"]) >= 2

    db_check = SessionCls()
    after_m = [(m.topic_id, float(m.mastery_score), float(m.retention_score)) for m in db_check.query(TopicMastery).filter_by(syllabus_id=custom_syl_id).all()]
    assert before_m == after_m
    assert db_check.query(StudyPlanItem).filter_by(syllabus_id=custom_syl_id).count() == before_plans
    assert db_check.query(PlanAdaptation).filter_by(syllabus_id=custom_syl_id).count() == before_adps
    assert db_check.query(AgentExecutionLog).filter_by(syllabus_id=custom_syl_id).count() == before_logs
    db_check.close()

    # 11. Student analytics, forgetting curve, and execution traces
    ana_res = client.get(f"/api/analytics/student?syllabus_id={custom_syl_id}", headers=student_headers)
    assert ana_res.status_code == 200
    assert ana_res.json()["predictive_score"]["is_estimate"] is True

    fc_res = client.get(f"/api/analytics/forgetting-curve?syllabus_id={custom_syl_id}&simulate_days_elapsed=7", headers=student_headers)
    assert fc_res.status_code == 200
    assert len(fc_res.json()["curve_series"]) >= 5

    tr_res = client.get(f"/api/agents/traces/{run_id}", headers=student_headers)
    assert tr_res.status_code == 200
    assert len(tr_res.json()) >= 5

    # 12. Parent links via Ananya's link_code -> reads allowed, writes strictly 403, cross-student 403!
    p_reg = client.post(
        "/api/auth/register",
        json={
            "name": "Parent Verma",
            "email": "parent.verma@example.com",
            "password": "password123",
            "role": "parent_teacher",
            "link_code": link_code,
        },
    )
    assert p_reg.status_code == 201
    parent_headers = {"Authorization": f"Bearer {p_reg.json()['access_token']}"}

    p_dash = client.get(f"/api/analytics/parent-dashboard?syllabus_id={custom_syl_id}", headers=parent_headers)
    assert p_dash.status_code == 200
    assert p_dash.json()["read_only"] is True
    assert p_dash.json()["student_name"] == "Ananya Verma"

    # Parent writes MUST return 403
    assert client.put("/api/students/profile", headers=parent_headers, json={"daily_hours": 5.0}).status_code == 403
    assert client.post("/api/workflows/daily-check", headers=parent_headers, json={"syllabus_id": custom_syl_id}).status_code == 403
    assert client.post("/api/planner/adapt", headers=parent_headers).status_code == 403

    # Demo student Aarav's syllabus MUST return 403 to Ananya and her parent
    demo_login = client.post("/api/auth/demo-login", json={"persona": "aarav"})
    assert demo_login.status_code == 200
    aarav_headers = {"Authorization": f"Bearer {demo_login.json()['access_token']}"}
    aarav_syls = client.get("/api/syllabi", headers=aarav_headers).json()
    assert len(aarav_syls) >= 1
    aarav_syl_id = aarav_syls[0]["id"]

    assert client.get(f"/api/syllabi/{aarav_syl_id}/graph", headers=student_headers).status_code == 403
    assert client.get(f"/api/syllabi/{aarav_syl_id}/graph", headers=parent_headers).status_code == 403
