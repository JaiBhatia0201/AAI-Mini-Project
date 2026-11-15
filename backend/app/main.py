"""FastAPI application entrypoint, startup DB seeding, CORS, and health status."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import (
    analytics,
    assessments,
    auth,
    planner,
    students,
    syllabi,
    traces,
    tutor,
    workflows,
)
from app.services.seeder import seed_demo_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize SQLite schema and idempotent GATE CSE demo personas on startup."""
    settings = get_settings()
    settings.ensure_storage_dirs()
    init_db()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="PS-03 Adaptive Exam Prep & Multi-Agent Tutoring API",
    version="1.0.0",
    description="11-Agent LangGraph Exam Preparation System with Multi-Syllabus Knowledge Graphs",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(syllabi.router)
app.include_router(workflows.router)
app.include_router(planner.router)
app.include_router(tutor.router)
app.include_router(assessments.router)
app.include_router(analytics.router)
app.include_router(traces.router)


@app.get("/api/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Report backend readiness alongside honest active LLM and retrieval modes."""
    cfg = get_settings()
    llm_provider = cfg.effective_llm_provider
    emb_provider = cfg.effective_embedding_provider
    return {
        "status": "ok",
        "llm_mode": "llm" if llm_provider in {"gemini", "openai"} else "fallback",
        "llm_provider": llm_provider,
        "retrieval_mode": "api_faiss" if emb_provider in {"gemini", "openai"} else "tfidf_fallback",
    }
