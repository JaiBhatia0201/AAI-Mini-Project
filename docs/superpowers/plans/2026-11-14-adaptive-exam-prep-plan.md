# Adaptive Exam Prep Agent (PS-03) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development`) strictly adapted to the author's **Manual-Typing + Interactive Command Workflow** in Global Constraints below. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous, multi-syllabus, 11-agent Adaptive Exam Prep platform (`PS-03`) featuring a decoupled FastAPI + LangGraph hybrid backend, deterministic learning-science engines, a React + TypeScript EdTech SaaS frontend, and Phase-0 academic/dataset deliverables (`Problem_Definition_and_Scope.docx` and `gate_cse_adaptive_dataset.zip`).

**Architecture:** FastAPI serves authenticated REST APIs backed by SQLite + SQLAlchemy (`PRAGMA foreign_keys=ON`), NetworkX prerequisite DAGs, and modular per-syllabus FAISS/TF-IDF retrieval. Agent 11 (LangGraph `StateGraph`) coordinates 5 LLM-backed cognitive agents (with deterministic/PDF-excerpt fallbacks) and 5 deterministic learning-science engines across scoped workflows, logging real runs to SQLite while returning Demo Simulation traces strictly in memory.

**Tech Stack:** Python 3.13.5 (root `.venv`, Windows wheels verified via `pip --dry-run`), FastAPI, SQLAlchemy, PyJWT, `bcrypt`, LangGraph, `langchain-google-genai`, `langchain-openai`, `pypdf`, NetworkX, FAISS (`faiss-cpu==1.16.0`), `scikit-learn`, `numpy`, `pytest`, `httpx`, React 18+, TypeScript, Vite, Tailwind CSS, `shadcn/ui`, Framer Motion, React Flow, Recharts.

**Spec:** [2026-11-14-adaptive-exam-prep-design.md](file:///d:/Jai/Study%20Material/Sem%207/AI%20AGENT%20Lab/Mini-Project/docs/superpowers/specs/2026-11-14-adaptive-exam-prep-design.md)

---

## Global Constraints

- **Phase 0 Preserved:** `Problem_Definition_and_Scope.docx` and `gate_cse_adaptive_dataset.zip` are already generated and verified in the root directory. Do not regenerate them unnecessarily.
- **Chat-Only Application Code Delivery:** Never directly create, edit, overwrite, or modify application source files (`backend/app/**`, `frontend/src/**`, `backend/requirements.txt`, `.gitignore`, `.env.example`) in the workspace. Present one complete file (or small logical component) at a time in chat with beginner-friendly explanations (purpose, path, imports, classes/functions/variables, API/LangGraph flow), wait for user confirmation, then proceed.
- **User-Executed Commands (Git Bash):** Provide Git Bash-compatible commands (`git`, ZIP extraction, `.venv`, `pip`, `npm`, server start/stop, DB operations) with clear explanation of purpose, changes, and expected output before asking the user to run them.
- **Antigravity-Owned Automated Test Suite (`backend/tests/`):** Antigravity creates, maintains, and runs durable `pytest` files inside `backend/tests/` plus frontend build checks (`tsc --noEmit`, `npm run build`) via terminal without modifying application source code or asking the user to manually write/run standalone test scripts. Report tested scope, commands, and results after each relevant task.
- **Verified Environment Baseline (No Global Python Edits):** Python `3.13.5` (`cp313-win_amd64` wheels verified via `pip install --dry-run` for `faiss-cpu==1.16.0`, `scikit-learn==1.9.1`, `numpy==2.5.4`, `sqlalchemy==2.1.8`, `bcrypt==5.0.0`, and `py3-none-any` wheels for `fastapi`, `langgraph`, `PyJWT`, `pypdf`), Node `v22.18.0`, npm `11.7.0`, Git `2.51.0`. Uses `PyJWT` + `bcrypt` directly (avoiding legacy `passlib`/`python-jose` incompatibilities on Python 3.13).
- **Multi-Syllabus & RBAC Integrity:** Every protected route checks JWT ownership (`syllabus.student_id == effective_student_id`). `topic_prerequisites` enforces composite same-syllabus FKs `(syllabus_id, topic_id)`. `parent_teacher` accounts have strict read-only access to their `linked_student_id` (`403` on mutations/unlinked access).
- **Honest Fallbacks & Non-Destructive Simulation:** Scanned PDFs with insufficient extractable text return `422`. Offline retrieval is labeled lexical TF-IDF (SVD only when `n_docs >= 32` and `n_features >= 32`, else direct sparse TF-IDF—no hashed projections). Real workflows persist `agent_execution_logs`; Demo Simulation (`daily-check/simulate`) returns execution traces strictly **in memory** with zero database writes. GATE CSE defaults to `max_score = 100.0`; predictive scores are labeled estimates; rank/percentile is excluded.

## Review Focus

1. **Scanned/image-only PDF upload (`422`):** Empty or `< 50` chars/page PDF uploaded to `/api/workflows/onboard-syllabus` must reject cleanly with `422 Unprocessable Entity` and never create an empty syllabus record (tested in `backend/tests/test_agents_tier1.py` & `test_api_tier1.py`).
2. **Cross-syllabus leakage & ownership bypass:** Attempting to insert a prerequisite edge spanning two `syllabus_id`s or requesting another student's `syllabus_id` must fail at DB FK (`IntegrityError`) and API (`403`/`404`) levels (tested in `backend/tests/test_models_isolation.py` & `test_auth_rbac.py`).
3. **Non-destructive demo time simulation (data + traces):** Calling `POST /api/workflows/daily-check/simulate` with `simulate_days_elapsed=14` must return retention alerts (`is_simulation=True`) and in-memory execution traces while leaving `last_practiced_at`, `topic_mastery`, `study_plan_items`, `plan_adaptations`, and `agent_execution_logs` rows unchanged in SQLite (tested in `backend/tests/test_simulation_and_analytics.py`).
4. **Parent/Teacher read-only authorization:** A `parent_teacher` token calling any write route (`POST /api/assessments/start`, `POST /api/workflows/onboard-syllabus`, `PATCH /api/syllabi/{id}/prerequisites`) or querying an unlinked student must get `403 Forbidden` (tested in `backend/tests/test_auth_rbac.py` & `test_simulation_and_analytics.py`).
5. **Small-corpus offline TF-IDF retrieval:** Running Resource Discovery offline on a 3-topic custom PDF (`n_docs < 32`) must bypass `TruncatedSVD` without raising dimension errors and return cosine-ranked results tagged `lexical_tfidf_fallback` (tested in `backend/tests/test_retrieval.py`).

---

## Target File Structure Map

```text
Mini-Project/
├── Problem_Definition_and_Scope.docx          # Phase 0A (COMPLETED & VERIFIED)
├── gate_cse_adaptive_dataset.zip              # Phase 0B (COMPLETED & VERIFIED)
├── data/gate_cse/                             # Extracted dataset JSONs + sample PDF (Task 1)
├── .env.example / .gitignore                  # User-typed setup files (Task 1)
├── backend/
│   ├── requirements.txt                       # User-typed dependency manifest (Task 1)
│   ├── app/                                   # Chat-only manual typing by User
│   │   ├── main.py                            # FastAPI entrypoint, CORS, startup seed
│   │   ├── config.py                          # Settings (.env, LLM provider, paths)
│   │   ├── database.py                        # SQLAlchemy engine, PRAGMA foreign_keys=ON, Session
│   │   ├── models.py                          # All 13 SQLite ORM tables w/ composite FKs
│   │   ├── schemas.py                         # Pydantic request/response contracts
│   │   ├── services/
│   │   │   ├── auth.py                        # bcrypt hash, PyJWT, RBAC & ownership guards
│   │   │   ├── seeder.py                      # Loads data/gate_cse/*.json into SQLite
│   │   │   ├── llm_client.py                  # Gemini/OpenAI wrapper + safe timeout/fallback
│   │   │   └── retrieval.py                   # RetrievalProvider (API FAISS vs TF-IDF/SVD)
│   │   ├── engines/
│   │   │   ├── syllabus_dag.py                # NetworkX DAG, cycle break, layout coords
│   │   │   ├── mastery.py                     # EMA + difficulty/pacing mastery estimation
│   │   │   ├── forgetting_curve.py            # Ebbinghaus R(t) & retention alerts
│   │   │   ├── spaced_repetition.py           # Day 3/7/14/30 + remedial pull-forward
│   │   │   └── predictive_score.py            # Score_curr, velocity projection, readiness band
│   │   ├── agents/
│   │   │   ├── state.py                       # Typed TutorState & TraceRecord
│   │   │   ├── profiling_agent.py             # Agent 1 (Deterministic)
│   │   │   ├── syllabus_agent.py              # Agent 2 (PDF parse, raw_excerpt, LLM/fallback)
│   │   │   ├── resource_agent.py              # Agent 3 (Tier 2: Retrieval + LLM/fallback synthesis)
│   │   │   ├── planner_agent.py               # Agent 4 (DAG topological scheduler)
│   │   │   ├── teaching_agent.py              # Agent 5 (Tier 2: Style-adapted lesson + provenance)
│   │   │   ├── question_agent.py              # Agent 6 (Tier 2: Difficulty-calibrated Q bank + LLM)
│   │   │   ├── assessment_agent.py            # Agent 7 (Deterministic grading & breakdown)
│   │   │   ├── weakness_agent.py              # Agent 8 (EMA + decay + ancestor blocker)
│   │   │   ├── adaptive_agent.py              # Agent 9 (Re-scheduler & AdaptationDiff)
│   │   │   ├── coaching_agent.py              # Agent 10 (Tier 2: Metrics + predictive + narrative)
│   │   │   └── orchestrator.py                # Agent 11 (LangGraph StateGraph; grows across Tiers 1–2)
│   │   └── routers/
│   │       ├── auth.py                        # /api/auth/*
│   │       ├── students.py                    # /api/students/*
│   │       ├── syllabi.py                     # /api/syllabi/*
│   │       ├── workflows.py                   # /api/workflows/* (onboard, daily-check, simulate)
│   │       ├── planner.py                     # /api/planner/*
│   │       ├── tutor.py                       # /api/tutor/* & /api/resources/* & /api/questions/*
│   │       ├── assessments.py                 # /api/assessments/*
│   │       ├── analytics.py                   # /api/analytics/*
│   │       └── traces.py                      # /api/agents/traces/*
│   └── tests/                                 # Antigravity-owned pytest suite (Tasks 2–15)
│       ├── conftest.py                        # Isolated in-memory/temp SQLite fixtures & TestClient
│       ├── test_models_isolation.py           # Schema & cross-syllabus composite FK tests
│       ├── test_seeder.py                     # Idempotent dataset loader & manifest count tests
│       ├── test_auth_rbac.py                  # Ownership checks & parent/teacher read-only RBAC
│       ├── test_engines.py                    # DAG, mastery, forgetting curve, SR, predictive math
│       ├── test_agents_tier1.py               # Agents 1, 2 (w/ scanned PDF 422), 4, 7, 8, 9
│       ├── test_orchestrator_tier1.py         # Tier-1 LangGraph workflows & trace persistence
│       ├── test_api_tier1.py                  # Tier-1 FastAPI integration tests
│       ├── test_retrieval.py                  # Online FAISS & small-corpus TF-IDF fallback tests
│       ├── test_agents_tier2.py               # Agents 3, 5 (source_origin), 6, 10 + extensions
│       ├── test_simulation_and_analytics.py   # Non-destructive simulate & parent analytics tests
│       └── test_e2e_regression.py             # Full Tier 1–3 smoke regression suite
└── frontend/
    ├── [CLI Auto-Generated]: package.json, tsconfig*.json, vite.config.ts, components.json, src/lib/utils.ts, src/components/ui/*.tsx, src/vite-env.d.ts
    ├── [User Updates Setup]: index.html, src/index.css, src/main.tsx, vite.config.ts
    └── src/                                   # User manual typing (chat-only one file at a time)
        ├── types/api.ts                       # Shared TypeScript interfaces
        ├── lib/api.ts                         # Typed fetch/JWT/syllabus-scoped client
        ├── context/AppContext.tsx             # Auth session + activeSyllabusId state
        ├── components/layout/AppShell.tsx     # Sidebar, Top-Bar Syllabus Switcher, Persona toggle
        ├── App.tsx                            # Route definitions & auth gate
        └── pages/
            ├── AuthPage.tsx                   # Login / Register / One-Click Demo Personas
            ├── OnboardingPage.tsx             # Two-step syllabus upload/seed + diagnostic
            ├── DashboardPage.tsx              # Tier 2: Tasks, estimates, alerts, Demo Sim drawer
            ├── TutorPage.tsx                  # Tier 2: AI Study Assistant + provenance badges
            ├── KnowledgeGraphPage.tsx         # Tier 2: React Flow DAG + needs_review controls
            ├── PlannerPage.tsx                # Tier 1: Adaptive Timeline + Adaptation Diff
            ├── ResourcesPage.tsx              # Tier 2: Multi-modal library + retrieval search
            ├── AssessmentPage.tsx             # Tier 1: Topic/Weekly/Mock quiz + adaptive trigger
            ├── AnalyticsPage.tsx              # Tier 2: Recharts mastery, retention & trajectory
            ├── ParentDashboardPage.tsx        # Tier 2: Read-only Parent/Teacher monitor
            └── AgentTracePage.tsx             # Tier 1: Live LangGraph execution trace inspector
```

---

## Phase 0: Formal Documentation & Flagship Dataset (Completed & Verified)

### Task 0A: `Problem_Definition_and_Scope.docx` *(Completed)*
- [x] Generated and verified in workspace root (`46,251 bytes`, 36 paragraphs, 8 tables). Do not regenerate.

### Task 0B: `gate_cse_adaptive_dataset.zip` *(Completed)*
- [x] Generated and verified in workspace root (`78,806 bytes`, 9 files: `README.md`, `dataset_manifest.json`, `sample_syllabi/gate_cse_syllabus.pdf`, `syllabus_graph.json`, `learning_resources.json`, `question_bank.json`, `student_profiles.json`, `assessment_attempts.json`, `mastery_history.json`).
- [x] Inspected archive layout: files sit directly at archive root (with `sample_syllabi/` subfolder) — extracting into `data/gate_cse/` creates clean non-nested layout. Do not regenerate.

---

## Tier 1: Core Implementation (End-to-End Adaptive Loop)

> **Execution Note:** Follow Global Constraints strictly: deliver setup/config/application files **one file at a time in chat** for manual typing, explain Git Bash commands before asking the user to run them, and run Antigravity-owned `backend/tests/` verification automatically after each milestone.

### Task 1: Environment Setup, Dataset Extraction, Git Initialization & `.venv`

**Files (Chat-only one file at a time, typed by User before `pip install`):**
- Create: `.gitignore`, `.env.example`, `backend/requirements.txt`
- Extract: `gate_cse_adaptive_dataset.zip` → `data/gate_cse/`

**Compatibility Verified:**
- Confirmed Windows Python 3.13.5 wheels exist and resolve cleanly (`pip install --dry-run` exited 0) for `faiss-cpu==1.16.0`, `scikit-learn==1.9.1`, `numpy==2.5.4`, `sqlalchemy==2.1.8`, `bcrypt==5.0.0`, `PyJWT`, `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-multipart`, `pypdf`, `networkx`, `langgraph`, `langchain-core`, `langchain-google-genai`, `langchain-openai`, `pytest`, `httpx`. No global Python modification required.

- [ ] **Step 1: Deliver and explain `.gitignore`, `.env.example`, and `backend/requirements.txt` one file at a time in chat**
  User creates each file manually and confirms before proceeding to Step 2.
- [ ] **Step 2: Guide user through Git Bash commands (explained one step at a time)**
  1. `git init` and verify initial status (`git status`).
  2. Extract dataset cleanly: `mkdir -p data/gate_cse && unzip -o gate_cse_adaptive_dataset.zip -d data/gate_cse/` (creating `data/gate_cse/syllabus_graph.json`, `data/gate_cse/sample_syllabi/gate_cse_syllabus.pdf`, etc.).
  3. Create & activate project-local Python 3.13.5 environment: `python -m venv .venv` followed by `source .venv/Scripts/activate`.
  4. Install backend stack strictly inside `.venv`: `python -m pip install --upgrade pip && pip install -r backend/requirements.txt`.
  5. Initial commit (`git add ... && git commit -m "chore: init repo, environment config, and Phase 0 deliverables"`).
- [ ] **Step 3: Antigravity runs environment & extracted dataset verification**
  Verify `.venv/Scripts/python -c "import fastapi, sqlalchemy, jwt, bcrypt, langgraph, networkx, pypdf, faiss, sklearn, pytest; print('ENV OK')"` and confirm all 9 files exist inside `data/gate_cse/`.
  Expected: `ENV OK` and all 9 extracted dataset files verified.

### Task 2: Configuration, SQLite Engine & Multi-Syllabus ORM Models

**Files (Chat-only for `backend/app/`; Antigravity creates `backend/tests/`):**
- App Create (User types): `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/database.py`, `backend/app/models.py`
- Test Create (Antigravity): `backend/tests/conftest.py`, `backend/tests/test_models_isolation.py`

**Interfaces:**
- Produces: `Settings` (`get_settings()`), `engine`, `SessionLocal`, `get_db()`, and all 13 ORM classes (`User`, `StudentProfile`, `Syllabus`, `SyllabusTopic`, `TopicPrerequisite`, `TopicMastery`, `LearningResource`, `Question`, `StudyPlanItem`, `Assessment`, `QuestionAttempt`, `PlanAdaptation`, `AgentExecutionLog`) with `UNIQUE(syllabus_id, id)` on `syllabus_topics` and composite FKs on `topic_prerequisites`.

- [ ] **Step 1: Deliver `backend/app/__init__.py`, `config.py`, `database.py` (w/ SQLite `PRAGMA foreign_keys=ON`), and `models.py` one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/conftest.py` and `backend/tests/test_models_isolation.py` and runs pytest (Review Focus #2)**
  Verify all 13 tables create cleanly and assert inserting a `TopicPrerequisite` linking `topic_a` (`syllabus_1`) to `topic_b` (`syllabus_2`) raises `sqlalchemy.exc.IntegrityError`.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_models_isolation.py -v`
  Expected: PASS.

### Task 3: Pydantic Contracts & Dataset Seeder

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/schemas.py`, `backend/app/services/__init__.py`, `backend/app/services/seeder.py`
- Test Create (Antigravity): `backend/tests/test_seeder.py`

**Interfaces:**
- Consumes: `models.*`, `data/gate_cse/*.json`
- Produces: Request/response schemas + `seed_demo_data(db: Session) -> dict` (idempotent seeding of demo students, linked read-only `parent_teacher` account with `link_code`, GATE CSE syllabus, 40 topics, 40 prerequisites, 160 resources, 240 questions, historical assessments/mastery, and initial plan).

- [ ] **Step 1: Deliver `schemas.py`, `services/__init__.py`, and `services/seeder.py` one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_seeder.py` and runs pytest**
  Assert `seed_demo_data()` runs idempotently twice on a temp SQLite DB without duplicate rows and matches `dataset_manifest.json` counts (`max_score=100.0`).
  Run: `.venv/Scripts/python -m pytest backend/tests/test_seeder.py -v`
  Expected: PASS.

### Task 4: Authentication, Ownership Guards & Parent/Teacher Read-Only RBAC

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/services/auth.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Test Create (Antigravity): `backend/tests/test_auth_rbac.py`

**Interfaces:**
- Consumes: `models.User`, `models.StudentProfile`, `models.Syllabus`
- Produces: `hash_password` (`bcrypt`), `verify_password`, `create_access_token` (`PyJWT`), `get_current_user`, `require_student_role`, `verify_syllabus_access(db, user, syllabus_id, write=False) -> Syllabus`, `auth.router`.

- [ ] **Step 1: Deliver `services/auth.py`, `routers/__init__.py`, and `routers/auth.py` one file at a time in chat** (including `demo-login` and `link_code` association). Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_auth_rbac.py` and runs pytest (Review Focus #2 & #4)**
  Verify student owns syllabus (`200`), unowned syllabus raises `403`, `parent_teacher` reads linked student (`write=False`) and fails with `403` on `write=True` or unlinked student.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_auth_rbac.py -v`
  Expected: PASS.

### Task 5: Deterministic Learning-Science Engines

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/engines/__init__.py`, `syllabus_dag.py`, `mastery.py`, `forgetting_curve.py`, `spaced_repetition.py`, `predictive_score.py`
- Test Create (Antigravity): `backend/tests/test_engines.py`

**Interfaces:**
- Produces:
  - `build_nx_graph(topics, edges) -> nx.DiGraph`, `resolve_cycles(edges)`, `topological_order(G, priority_weights)`, `find_root_cause_blockers(G, topic_id, mastery_map, threshold=65.0)`
  - `update_topic_mastery(old_mastery, attempts) -> float` (`0.65 * M_old + 0.35 * S_k`, difficulty weights `0.8/1.0/1.25`, pacing `1.05/0.95/1.0`)
  - `compute_retention(last_practiced_at, eval_time, mastery, review_count) -> float` (`exp(-t / S_mem)`)
  - `next_spaced_intervals(mastery, retention, base_date) -> list[tuple[int, date, str]]` (`+3/+7/+14/+30` or `+1/+2` remedial pull-forward)
  - `compute_predictive_score(topics, mastery_map, retention_map, history, days_remaining, max_score) -> dict` (`current_estimated_score`, `projected_estimated_score`, `readiness_band`, `is_estimate=True`)

- [ ] **Step 1: Deliver each engine module incrementally one file at a time in chat** with math walkthroughs. Wait for confirmation after each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_engines.py` and runs pytest**
  Verify EMA bounds (`[0, 100]`), DAG cycle breaking + ancestor blocker detection, Ebbinghaus decay (`R(0)=1.0`, decay `<0.65` triggers alert), spaced repetition pull-forward when `M<60`, and GATE CSE predictive estimates bounded in `[0, 100]`.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_engines.py -v`
  Expected: PASS.

### Task 6: Agents 1, 2 & 4 (Profiling, Syllabus PDF Ingestion, DAG Study Planner)

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/services/llm_client.py`, `backend/app/agents/__init__.py`, `state.py`, `profiling_agent.py`, `syllabus_agent.py`, `planner_agent.py`
- Test Create (Antigravity): `backend/tests/test_agents_tier1.py` (part 1)

**Interfaces:**
- Consumes: `engines.*`, `pypdf`
- Produces: `TutorState`, `TraceRecord`, `run_profiling_agent`, `run_syllabus_agent` (w/ scanned-PDF `< 50 chars/page` `ScannedPDFError -> 422`, `raw_excerpt`, `confidence_status="needs_review"` for offline heading fallback without silent cross-unit edge invention), `run_planner_agent`.

- [ ] **Step 1: Deliver `llm_client.py`, `agents/__init__.py`, `state.py`, `profiling_agent.py`, `syllabus_agent.py`, and `planner_agent.py` one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_agents_tier1.py` and tests PDF parsing & scanned-PDF rejection (Review Focus #1)**
  Test `run_syllabus_agent` on `data/gate_cse/sample_syllabi/gate_cse_syllabus.pdf` AND on a blank/image-only synthetic PDF (must raise `ScannedPDFError` cleanly without DB writes).
  Run: `.venv/Scripts/python -m pytest backend/tests/test_agents_tier1.py -v`
  Expected: PASS.

### Task 7: Agents 7, 8 & 9 (Assessment Grader, Weakness Detection, Adaptive Planner)

**Files (Chat-only for `backend/app/`; Antigravity updates tests):**
- App Create (User types): `backend/app/agents/assessment_agent.py`, `weakness_agent.py`, `adaptive_agent.py`
- Test Update (Antigravity): append closed-loop tests to `backend/tests/test_agents_tier1.py`

**Interfaces:**
- Consumes: `engines.*`, `models.*`
- Produces: `run_assessment_agent`, `run_weakness_agent(state, eval_time=None, persist=True)`, `run_adaptive_agent(state, persist=True)` returning `AdaptationDiff`.

- [ ] **Step 1: Deliver `assessment_agent.py`, `weakness_agent.py`, and `adaptive_agent.py` one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity runs `backend/tests/test_agents_tier1.py`**
  Verify low-scoring Computer Networks answers trigger Weakness Detection (`mastery < 60`), catch weak prerequisite blocker `CN-03`, and invoke Adaptive Planner to insert revision + practice + re-test items and `plan_adaptations`.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_agents_tier1.py -v`
  Expected: PASS.

### Task 8: Tier-1 Agent 11 (LangGraph `StateGraph` Master Orchestrator + Persisted Trace Logger)

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/agents/orchestrator.py` (Tier 1 version)
- Test Create (Antigravity): `backend/tests/test_orchestrator_tier1.py`

**Interfaces:**
- Consumes **ONLY already-implemented Tier 1 agents** (`profiling_agent` [1], `syllabus_agent` [2], `planner_agent` [4], `assessment_agent` [7], `weakness_agent` [8], `adaptive_agent` [9]) — zero unresolved imports or stub modules.
- Produces: `log_agent_step(..., persist: bool = True)` (persists to `agent_execution_logs` for real runs; supports `persist=False` for in-memory simulation later), and 3 runnable compiled Tier-1 LangGraph workflows:
  1. `onboard_syllabus_graph`: `[Agent 1 (profile)] -> [Agent 2 (parse PDF / seed)] -> END`
  2. `complete_diagnostic_graph`: `[Agent 1 (score baseline)] -> [Agent 4 (initial DAG plan)] -> END`
  3. `assessment_adapt_graph`: `[Agent 7 (grade)] -> [Agent 8 (weakness/decay)] -> (conditional edge -> [Agent 9 (remediate or advance)]) -> END`

- [ ] **Step 1: Deliver Tier-1 `orchestrator.py` in chat** with graph diagram & conditional-edge explanation. Wait for confirmation.
- [ ] **Step 2: Antigravity creates `backend/tests/test_orchestrator_tier1.py` and runs pytest**
  Execute `onboard_syllabus_graph`, `complete_diagnostic_graph`, and `assessment_adapt_graph` on weak vs strong submissions; assert conditional edges branch accurately and write ordered `agent_execution_logs` rows.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_orchestrator_tier1.py -v`
  Expected: PASS.

### Task 9: Core FastAPI Routers & Application Entrypoint

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create (User types): `backend/app/routers/students.py`, `syllabi.py`, `workflows.py`, `planner.py`, `assessments.py`, `traces.py`, `backend/app/main.py`
- Test Create (Antigravity): `backend/tests/test_api_tier1.py`

**Interfaces:**
- Produces Tier-1 REST endpoints (Auth, Profile, Syllabi list/activate/graph, Tier-1 Workflows `onboard-syllabus` & `complete-diagnostic`, Planner + Adaptation Diff, Assessments start/submit/history, Agent Traces) + CORS (`http://localhost:5173`) + startup DB creation & idempotent demo seeding.

- [ ] **Step 1: Deliver each router and `main.py` one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Guide user through Git Bash command to start FastAPI server** (`cd backend && uvicorn app.main:app --reload`) and verify `/docs` responds.
- [ ] **Step 3: Antigravity creates `backend/tests/test_api_tier1.py` and runs API integration suite via `TestClient`**
  Test demo login, multi-syllabus isolation (`403` on unowned syllabus), scanned PDF `422`, GATE CSE seed/switch, onboarding two-step flow, assessment submission triggering adaptive re-plan, and `/api/agents/traces`.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_api_tier1.py -v`
  Expected: PASS.

### Task 10: Tier 1 Frontend Foundation & Core Adaptive Loop UI

**Files Breakdown:**
- **Auto-Generated by CLI Setup Commands (User runs via Git Bash — NOT manually typed):**
  - `npm create vite@latest frontend -- --template react-ts`: generates `package.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, `src/vite-env.d.ts`, starter `src/main.tsx`, `src/index.css`, `src/App.tsx`.
  - Tailwind CSS + `npx shadcn@latest init` + `npx shadcn@latest add ...`: generates `components.json`, `src/lib/utils.ts`, and `src/components/ui/*.tsx`.
- **User Manually Updates / Types One File at a Time in Chat:**
  - Foundation tweaks: `frontend/index.html`, `frontend/vite.config.ts`, `frontend/src/index.css`, `frontend/src/main.tsx`
  - Tier-1 App Modules: `frontend/src/types/api.ts`, `src/lib/api.ts`, `src/context/AppContext.tsx`, `src/components/layout/AppShell.tsx`, `src/pages/AuthPage.tsx`, `src/pages/OnboardingPage.tsx`, `src/pages/PlannerPage.tsx`, `src/pages/AssessmentPage.tsx`, `src/pages/AgentTracePage.tsx`, `src/App.tsx`

- [ ] **Step 1: Guide user through Git Bash frontend scaffolding & dependency install** (`npm create vite@latest frontend -- --template react-ts`, install Tailwind, `shadcn/ui`, `lucide-react`, `framer-motion`, `@xyflow/react`, `recharts`).
- [ ] **Step 2: Deliver foundation updates and Tier-1 React files one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 3: Antigravity runs TypeScript & Vite build verification** (`npx tsc --noEmit && npm run build` inside `frontend/`).
  Expected: Zero TypeScript or Vite build errors.
- [ ] **Step 4: Quick user browser verification** of core Tier-1 loop (switch/upload syllabus → take assessment → see Adaptation Diff & Agent Execution Trace).

---

## Tier 2: Advanced Demonstration Features

### Task 11: Modular `RetrievalProvider` (Per-Syllabus FAISS + TF-IDF Fallback), Agent 3 & Orchestrator Hook

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create/Update (User types): `backend/app/services/retrieval.py`, `backend/app/agents/resource_agent.py`, extend `backend/app/agents/orchestrator.py` (hook Agent 3 into `onboard_syllabus_graph`)
- Test Create (Antigravity): `backend/tests/test_retrieval.py`

**Interfaces:**
- Produces: `RetrievalProvider` protocol, `APIFaissRetrievalProvider` (per-syllabus `faiss_indices/syllabus_{id}.index`), `LocalTfidfRetrievalProvider` (SVD + FAISS only when `n_docs >= 32 and n_features >= 32`; else sparse TF-IDF cosine similarity—no hashed projections), `run_resource_agent`.

- [ ] **Step 1: Deliver `retrieval.py`, `resource_agent.py`, and the clean `orchestrator.py` Agent-3 extension one file at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_retrieval.py` and runs pytest (Review Focus #5)**
  Verify 3-topic PDF bypasses SVD without error, returns `retrieval_mode="lexical_tfidf_fallback"`, and isolates queries strictly by `syllabus_id`.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_retrieval.py -v`
  Expected: PASS.

### Task 12: Agents 5, 6 & 10 (Teaching, Question Gen, Coaching), Tutor Router & Orchestrator Extension

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create/Update (User types): `backend/app/agents/teaching_agent.py`, `question_agent.py`, `coaching_agent.py`, `backend/app/routers/tutor.py`, extend `backend/app/agents/orchestrator.py` (add `study_session_graph` + Agent 6/10 nodes into onboarding & assessment flows) & `backend/app/main.py` (register `tutor.router`)
- Test Create (Antigravity): `backend/tests/test_agents_tier2.py`

**Interfaces:**
- Produces: Style-adapted lesson builder tagging `source_origin` (`llm_generated_summary` | `curated_dataset_note` | `extracted_pdf_excerpt`), difficulty-split question generator (`<50`: 60/30/10, `50-75`: 25/50/25, `>=75`: 10/40/50), coaching insight builder, `/api/tutor/*`, `/api/resources/*`, `/api/questions/*`, `study_session_graph`.

- [ ] **Step 1: Deliver each agent, `routers/tutor.py`, and orchestrator/`main.py` updates one at a time in chat**. Wait for confirmation on each.
- [ ] **Step 2: Antigravity creates `backend/tests/test_agents_tier2.py` and runs pytest**
  Verify offline `raw_excerpt` fallback lessons carry `source_origin="extracted_pdf_excerpt"`, question distributions follow mastery difficulty rules, and `study_session_graph` logs traces cleanly.
  Run: `.venv/Scripts/python -m pytest backend/tests/test_agents_tier2.py -v`
  Expected: PASS.

### Task 13: Non-Destructive Demo Simulation, Real Daily Check & Analytics / Parent Dashboards

**Files (Chat-only for `backend/app/`; Antigravity creates tests):**
- App Create/Update (User types): `backend/app/routers/analytics.py`, extend `backend/app/agents/orchestrator.py` (add persisted `daily_check_graph` + in-memory `demo_simulation_graph` with `persist=False` so ZERO `agent_execution_logs` or DB rows are written during simulation), extend `backend/app/routers/workflows.py` (`/daily-check`, `/daily-check/simulate`) & `backend/app/main.py`
- Test Create (Antigravity): `backend/tests/test_simulation_and_analytics.py`

**Interfaces:**
- Produces: `/api/workflows/daily-check` (persists check + `agent_execution_logs`), `/api/workflows/daily-check/simulate` (pure in-memory retention check + preview diff + in-memory trace return, `is_simulation=True`), `/api/analytics/student`, `/api/analytics/forgetting-curve`, `/api/analytics/parent-dashboard`.

- [ ] **Step 1: Deliver `routers/analytics.py` and workflow/orchestrator extensions one at a time in chat**. Wait for confirmation.
- [ ] **Step 2: Antigravity creates `backend/tests/test_simulation_and_analytics.py` and runs pytest (Review Focus #3 & #4)**
  Snapshot DB before `POST /api/workflows/daily-check/simulate` (`simulate_days_elapsed=14`), assert simulated alerts + in-memory trace return with `is_simulation=True`, and verify ZERO changes across `last_practiced_at`, `topic_mastery`, `study_plan_items`, `plan_adaptations`, and `agent_execution_logs`. Verify `parent_teacher` read access (`200`) and mutation rejection (`403`).
  Run: `.venv/Scripts/python -m pytest backend/tests/test_simulation_and_analytics.py -v`
  Expected: PASS.

### Task 14: Tier 2 Frontend Views (Dashboard, AI Tutor, React Flow KG, Resources, Analytics, Parent Dashboard)

**Files (Chat-only one view at a time):**
- Create (User types): `frontend/src/pages/DashboardPage.tsx`, `TutorPage.tsx`, `KnowledgeGraphPage.tsx`, `ResourcesPage.tsx`, `AnalyticsPage.tsx`, `ParentDashboardPage.tsx`, plus route wiring in `App.tsx` & `AppShell.tsx`

- [ ] **Step 1: Deliver each of the 6 React views one at a time in chat** (clearly labeling Estimated Predictive Scores out of configurable `max_score`, non-destructive Demo Simulation drawer, `source_origin` provenance badges, `needs_review` edge badges, and read-only Parent Dashboard without rank/percentile). Wait for confirmation on each.
- [ ] **Step 2: Antigravity runs `npx tsc --noEmit && npm run build` inside `frontend/`**.
  Expected: Clean TypeScript check and production Vite bundle.

---

## Tier 3: Optional Enhancements & Final Verification

### Task 15: Prerequisite Confirmation API/UI, Motion Polish & Full Regression Suite

**Files (Chat-only for app code; Antigravity adds regression test):**
- App Update (User types): `backend/app/routers/syllabi.py` (`PATCH /api/syllabi/{id}/prerequisites`), `KnowledgeGraphPage.tsx` (confirm/remove `needs_review` edges), Framer Motion transitions, exportable study summary.
- Test Create (Antigravity): `backend/tests/test_e2e_regression.py`

- [ ] **Step 1: Deliver prerequisite confirmation endpoint & UI polish one file at a time in chat**. Wait for confirmation.
- [ ] **Step 2: Antigravity runs complete `backend/tests/` regression suite + frontend build check**
  Run: `.venv/Scripts/python -m pytest backend/tests/ -v` and `npm run build` in `frontend/`.
  Expected: 100% pass across all Tier 1–3 tests, all 5 Review Focus scenarios, and clean frontend production build.

---

## Self-Review Check (Completed)

- **All 6 Refinements Incorporated:** Python 3.13.5 / `faiss-cpu` Windows wheel resolution verified via `pip --dry-run` (`PyJWT` + `bcrypt` replacing `passlib`/`python-jose`); simulation traces kept strictly in memory (`persist=False`); Tier-1 orchestrator imports only Tier-1 agents (zero unresolved imports/stubs); full Vite/shadcn file distinction mapped; durable `backend/tests/` suite owned by Antigravity; Phase 0 preserved and actual ZIP structure verified prior to Task 1 extraction command.
- **Review Focus Pinned:** Every failure mode maps directly to an explicit `backend/tests/` test module.
