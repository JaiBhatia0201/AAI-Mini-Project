"""Authentication, syllabus ownership, and parent/teacher read-only RBAC tests (Task 4)."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Syllabus, User
from app.routers import auth as auth_router
from app.services.auth import (
    get_effective_student_id,
    require_student_role,
    verify_syllabus_access,
)
from app.services.seeder import seed_demo_data


def _build_auth_test_app(db_session: Session) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[get_db] = lambda: db_session

    @app.get("/_test/syllabi/{syllabus_id}")
    def read_syllabus(
        syllabus_id: str,
        user: User = Depends(auth_router.get_current_user),
        db: Session = Depends(get_db),
    ):
        syl = verify_syllabus_access(db, user, syllabus_id, write=False)
        return {"id": syl.id, "student_id": syl.student_id}

    @app.post("/_test/syllabi/{syllabus_id}/mutate")
    def mutate_syllabus(
        syllabus_id: str,
        user: User = Depends(require_student_role),
        db: Session = Depends(get_db),
    ):
        syl = verify_syllabus_access(db, user, syllabus_id, write=True)
        return {"ok": True, "syllabus_id": syl.id}

    @app.get("/_test/students/{student_id}")
    def read_student(
        student_id: str,
        user: User = Depends(auth_router.get_current_user),
    ):
        return {"student_id": get_effective_student_id(user, requested_student_id=student_id)}

    return app


def test_register_login_and_parent_link_code_flow(db_session) -> None:
    """New student gets a unique link_code; new parent links cleanly via link_code."""
    app = _build_auth_test_app(db_session)
    client = TestClient(app)

    reg_resp = client.post(
        "/api/auth/register",
        json={
            "name": "Aditi Kulkarni",
            "email": "aditi.new@example.com",
            "password": "securePassword123",
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201
    stu_data = reg_resp.json()
    assert stu_data["user"]["email"] == "aditi.new@example.com"
    link_code = stu_data["user"]["student_profile"]["link_code"]
    student_id = stu_data["user"]["student_profile"]["id"]
    assert link_code.startswith("PREP-")

    login_resp = client.post(
        "/api/auth/login",
        json={"email": "aditi.new@example.com", "password": "securePassword123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "aditi.new@example.com"

    bad_parent = client.post(
        "/api/auth/register",
        json={
            "name": "Wrong Code Mentor",
            "email": "bad@example.com",
            "password": "password123",
            "role": "parent_teacher",
            "link_code": "INVALID-CODE",
        },
    )
    assert bad_parent.status_code == 404

    good_parent = client.post(
        "/api/auth/register",
        json={
            "name": "Parent Kulkarni",
            "email": "parent.kulkarni@example.com",
            "password": "password123",
            "role": "parent_teacher",
            "link_code": link_code,
        },
    )
    assert good_parent.status_code == 201
    assert good_parent.json()["user"]["linked_student_id"] == student_id


def test_ownership_and_read_only_parent_rbac(db_session) -> None:
    """Review Focus #2 & #4: cross-student access and parent writes must return 403."""
    seed_demo_data(db_session)
    app = _build_auth_test_app(db_session)
    client = TestClient(app)

    aarav_tok = client.post("/api/auth/demo-login", json={"persona": "aarav"}).json()["access_token"]
    priya_tok = client.post("/api/auth/demo-login", json={"persona": "priya"}).json()["access_token"]
    parent_tok = client.post("/api/auth/demo-login", json={"persona": "parent"}).json()["access_token"]

    aarav_h = {"Authorization": f"Bearer {aarav_tok}"}
    priya_h = {"Authorization": f"Bearer {priya_tok}"}
    parent_h = {"Authorization": f"Bearer {parent_tok}"}

    flagship_id = "gate_cse_flagship_2026"
    priya_syl_id = db_session.query(Syllabus).filter_by(student_id="stu_priya").first().id

    # Owner reads and mutates own syllabus cleanly
    assert client.get(f"/_test/syllabi/{flagship_id}", headers=aarav_h).status_code == 200
    assert client.post(f"/_test/syllabi/{flagship_id}/mutate", headers=aarav_h).status_code == 200

    # Student B blocked from Student A's syllabus
    assert client.get(f"/_test/syllabi/{flagship_id}", headers=priya_h).status_code == 403
    assert client.post(f"/_test/syllabi/{flagship_id}/mutate", headers=priya_h).status_code == 403
    assert client.get(f"/_test/syllabi/{priya_syl_id}", headers=priya_h).status_code == 200

    # Parent/Teacher reads linked student (Aarav) cleanly, blocked from mutations and unlinked Priya
    assert client.get(f"/_test/syllabi/{flagship_id}", headers=parent_h).status_code == 200
    assert client.post(f"/_test/syllabi/{flagship_id}/mutate", headers=parent_h).status_code == 403
    assert client.get("/_test/students/stu_priya", headers=parent_h).status_code == 403
    assert client.get(f"/_test/syllabi/{priya_syl_id}", headers=parent_h).status_code == 403

    # Missing/bad bearer token -> 401
    assert client.get("/api/auth/me").status_code == 401
