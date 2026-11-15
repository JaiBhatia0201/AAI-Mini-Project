"""Centralized configurations loaded from the repository .env file."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always anchor relative paths and .env lookup to the Mini-Project root
# so launching uvicorn from backend/ behaves identically to pytest from root.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_provider(
    configured: str,
    gemini_key: str,
    openai_key: str,
    offline_fallback: str,
) -> str:
    """Resolve an auto/explicit provider setting into an active provider name."""
    mode = configured.strip().lower()
    has_gemini = bool(gemini_key.strip())
    has_openai = bool(openai_key.strip())

    if mode in {"none", "local", "offline"}:
        return offline_fallback
    if mode == "gemini":
        return "gemini" if has_gemini else offline_fallback
    if mode == "openai":
        return "openai" if has_openai else offline_fallback
    if mode == "auto":
        if has_gemini:
            return "gemini"
        if has_openai:
            return "openai"
    return offline_fallback


class Settings(BaseSettings):
    """Typed application settings validated via pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Adaptive Exam Prep Agent (PS-03)"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./backend/adaptive_tutor.db"

    # Security & JWT (>= 32 bytes avoids PyJWT InsecureKeyLengthWarning)
    jwt_secret_key: str = "change-this-to-a-long-random-secret-key-before-demo"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM Providers
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 20

    # Modular Retrieval
    embedding_provider: str = "auto"

    # Storage Paths
    dataset_dir: str = "data/gate_cse"
    upload_dir: str = "backend/uploads"
    faiss_index_dir: str = "backend/faiss_indices"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def resolve_path(self, raw_path: str) -> Path:
        """Resolve a configured directory path relative to REPO_ROOT if not absolute."""
        candidate = Path(raw_path)
        return candidate if candidate.is_absolute() else (REPO_ROOT / candidate)

    @property
    def dataset_path(self) -> Path:
        """Absolute path to the extracted GATE CSE flagship dataset directory."""
        return self.resolve_path(self.dataset_dir)

    @property
    def upload_path(self) -> Path:
        """Absolute path where uploaded custom syllabus PDFs are stored."""
        return self.resolve_path(self.upload_dir)

    @property
    def faiss_index_path(self) -> Path:
        """Absolute path where per-syllabus FAISS indices are stored."""
        return self.resolve_path(self.faiss_index_dir)

    @property
    def resolved_database_url(self) -> str:
        """Anchor relative sqlite:///./ paths to REPO_ROOT across working directories."""
        prefix = "sqlite:///./"
        if self.database_url.startswith(prefix):
            rel_db = self.database_url[len(prefix) :]
            abs_db = (REPO_ROOT / rel_db).resolve()
            return f"sqlite:///{abs_db.as_posix()}"
        return self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        """Split comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_llm_provider(self) -> str:
        """Return active LLM backend ('gemini', 'openai', or 'none' for offline fallback)."""
        return _resolve_provider(
            self.llm_provider,
            self.gemini_api_key,
            self.openai_api_key,
            offline_fallback="none",
        )

    
    @property
    def effective_embedding_provider(self) -> str:
        """Return active retrieval embedding backend ('gemini', 'openai', or 'local')."""
        return _resolve_provider(
            self.embedding_provider,
            self.gemini_api_key,
            self.openai_api_key,
            offline_fallback="local",
        )

    def ensure_storage_dirs(self) -> None:
        """Create upload, FAISS index, and SQLite parent directories if absent."""
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.faiss_index_path.mkdir(parents=True, exist_ok=True)
        url = self.resolved_database_url
        if url.startswith("sqlite:///") and ":memory:" not in url:
            db_file = Path(url[len("sqlite:///") :])
            db_file.parent.mkdir(parents=True, exist_ok=True)

@lru_cache
def get_settings() -> Settings:
    """return a cached instance shared across FastAPI dependencies."""
    return Settings()