"""Authentication endpoints: register, login, demo-login, and current user profile."""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudentProfile, User
from app.schemas import (
    DemoLoginRequest,
    TokenResponse,
    UserLoginRequest,
    UserOut,
    UserRegisterRequest,
)
from app.services.auth import (
    create_access_token,
    generate_unique_link_code,
    get_current_user,
    hash_password,
    serialize_user_out,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

DEMO_PERSONA_USER_IDS = {
    "aarav": "usr_stu_aarav",
    "priya": "usr_stu_priya",
    "rohan": "usr_stu_rohan",
    "meera": "usr_stu_meera",
    "parent": "pt_kavita",
}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a brand-new student or linked read-only parent/teacher account."""
    normalized_email = payload.email.strip().lower()
    if db.query(User).filter(User.email == normalized_email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    linked_student_id: str | None = None
    if payload.role == "parent_teacher":
        if not payload.link_code or not payload.link_code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent/Teacher registration requires a student link_code.",
            )
        target_profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.link_code == payload.link_code.strip())
            .first()
        )
        if target_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No student found for the provided link_code.",
            )
        linked_student_id = target_profile.id

    user = User(
        name=payload.name.strip(),
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        linked_student_id=linked_student_id,
    )
    db.add(user)
    db.flush()

    if payload.role == "student":
        profile = StudentProfile(
            user_id=user.id,
            link_code=generate_unique_link_code(db, user.name),
            current_grade="Self-Paced Learner",
            daily_hours=3.0,
            learning_style="visual",
            last_active_date=date.today(),
        )
        db.add(profile)

    db.commit()
    db.refresh(user)
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=serialize_user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate any student or parent/teacher using email and password."""
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=serialize_user_out(user))


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(payload: DemoLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """One-click login for seeded GATE CSE demo personas or linked mentor."""
    user_id = DEMO_PERSONA_USER_IDS.get(payload.persona)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo persona account is not seeded in this database.",
        )
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=serialize_user_out(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the authenticated user's identity, role, and student profile."""
    return serialize_user_out(current_user)
