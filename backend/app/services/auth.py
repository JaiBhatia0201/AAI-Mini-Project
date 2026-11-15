"""Authentication, JWT tokens, syllabus ownership guards, and read-only RBAC."""

from datetime import datetime, timedelta, timezone
import json
import secrets
from typing import Any
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import StudentProfile, Syllabus, User
from app.schemas import StudentProfileOut, UserOut

security_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Has a plaintext password using bcrypt with a fresh per-user salt."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its stored bcrypt hash."""
    if not plain_password or not password_hash:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user: User, expires_minutes: int | None = None) -> str:
    """Create a signed HS256 JWT containing user ID and role."""
    settings = get_settings()
    ttl = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=ttl)
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token, raising HTTP 401 on invalid or expired tokens."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency returning the authenticated User from Bearer JWT."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_student_role(current_user: User = Depends(get_current_user)) -> User:
    """Block read-only parent/teacher accounts from mutating student data."""
    if current_user.role != "student" or current_user.student_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts may perform write or workflow actions.",
        )
    return current_user


def get_effective_student_id(
    current_user: User,
    requested_student_id: str | None = None,
) -> str:
    """Resolve the authorized student_id for either a student or linked mentor."""
    if current_user.role == "student":
        if current_user.student_profile is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student profile is missing for this account.",
            )
        own_id = current_user.student_profile.id
        if requested_student_id and requested_student_id != own_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student cannot access another student's records.",
            )
        return own_id

    if current_user.role == "parent_teacher":
        linked_id = current_user.linked_student_id
        if not linked_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent/Teacher account is not linked to any student.",
            )
        if requested_student_id and requested_student_id != linked_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not linked to the requested student.",
            )
        return linked_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unsupported user role."
    )


def verify_syllabus_access(
    db: Session,
    user: User,
    syllabus_id: str,
    write: bool = False,
) -> Syllabus:
    """Enforce ownership and read-only parent/teacher RBAC on a syllabus."""
    if write and user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only parent/teacher accounts cannot modify syllabi or trigger workflows.",
        )
    effective_student_id = get_effective_student_id(user)
    syllabus = db.get(Syllabus, syllabus_id)
    if syllabus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus not found.",
        )
    if syllabus.student_id != effective_student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this syllabus.",
        )
    return syllabus


def generate_unique_link_code(db: Session, name: str) -> str:
    """Generate a unique readable student link code (e.g., PREP-JAI-4821)."""
    alpha = "".join(ch for ch in name.upper() if ch.isalpha())
    prefix = alpha[:4] or "PREP"
    for _ in range(20):
        candidate = f"PREP-{prefix}-{secrets.randbelow(9000) + 1000}"
        if db.query(StudentProfile).filter_by(link_code=candidate).first() is None:
            return candidate
    return f"PREP-{secrets.token_hex(4).upper()}"


def serialize_user_out(user: User) -> UserOut:
    """Convert an ORM User (and optional StudentProfile) into UserOut cleanly."""
    profile_out = None
    if user.student_profile is not None:
        p = user.student_profile
        profile_out = StudentProfileOut(
            id=p.id,
            user_id=p.user_id,
            active_syllabus_id=p.active_syllabus_id,
            link_code=p.link_code,
            current_grade=p.current_grade,
            daily_hours=p.daily_hours,
            learning_style=p.learning_style,
            study_streak=p.study_streak,
            total_hours_logged=p.total_hours_logged,
            last_active_date=p.last_active_date,
            stated_strengths=json.loads(p.stated_strengths_json or "[]"),
            stated_weaknesses=json.loads(p.stated_weaknesses_json or "[]"),
        )
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        linked_student_id=user.linked_student_id,
        student_profile=profile_out,
    )