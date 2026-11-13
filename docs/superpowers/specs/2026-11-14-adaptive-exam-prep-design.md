# Design Specification: Autonomous Adaptive Exam Prep Agent (PS-03)

**Date:** 2026-11-14  
**Subject:** Agentic AI & Enterprise Automation Lab — Mini-Project  
**Project Size:** Full Project (Multi-Agent Backend + Modern Web Frontend + Problem Definition `.docx` + Flagship Dataset `.zip`)  
**Status:** Approved (With Workflow Clarification Incorporated)

---

## 1. Intent & Why

Students preparing for competitive exams (such as GATE CSE) typically rely on static timetables and passive question banks that treat every learner identically, fail to detect prerequisite knowledge gaps, and allow previously studied topics to decay before exam day.

This project builds an **Autonomous AI Learning Coach** that behaves like a personal adaptive tutor: it parses a student's syllabus into a prerequisite-aware knowledge graph, curates multi-modal resources, teaches concepts according to the learner's style, assesses understanding with adaptive difficulty, detects root-cause weak areas and retention decay, and dynamically rewrites future study plans in real time.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
1. **Immediate Milestone Deliverables (Phase 0):**
   - `Problem_Definition_and_Scope.docx`: Formal lab submission document specifying the problem definition, objectives, full 11-agent architecture, 6 advanced features, dataset specification, tech stack, and scope boundaries.
   - `gate_cse_adaptive_dataset.zip`: Self-contained, schema-validated flagship dataset covering GATE CSE CS Core (DBMS, OS, Computer Networks, TOC) and Engineering Mathematics (Discrete Math, Linear Algebra, Calculus, Probability & Statistics), complete with a sample syllabus PDF, prerequisite DAG, curated multi-modal resources, Easy/Medium/Hard question bank, and realistic multi-week synthetic student profiles and attempt logs.
2. **Full 11-Agent Multi-Agent Architecture:** Implement all 10 domain agents plus Agent 11 (Master Orchestrator) using LangGraph with observable state transitions and conditional routing.
3. **All 6 Advanced Features:**
   - Interactive Student Knowledge Graph (syllabus hierarchy + mastery & prerequisite edges)
   - Spaced Repetition Engine (Day 3, Day 7, Day 14, Day 30 schedules)
   - Predictive Exam Score (data-backed estimated current readiness + projected exam-day score out of configurable `max_score`, e.g., `100` for GATE CSE)
   - Forgetting Curve Detection (Ebbinghaus retention decay alerts & automatic revision insertion, plus non-destructive Demo Simulation)
   - Multi-Modal Learning (Notes, Videos, Flashcards, Quizzes tailored to learning style)
   - Read-Only Parent/Teacher Analytics Dashboard
4. **Domain-Independent Multi-Syllabus Core:** Keep the seeded GATE CSE flagship dataset permanently available while allowing students to upload and switch across multiple custom PDF syllabi with backend-enforced isolation of plans, mastery, assessments, spaced repetition schedules, resources, and analytics.
5. **Production-Grade Educational SaaS UI/UX & Reliability:** Decoupled React + TypeScript frontend and FastAPI backend with LLM-backed intelligence, deterministic learning-science math, honest lexical/PDF-excerpt offline fallbacks, and live Agent Execution Trace observability.
6. **Learn-by-Typing Codebase:** Clean, modular, beginner-friendly implementation delivered incrementally in chat so the author personally types, understands, and confidently defends every file during the lab demonstration.

### Non-Goals
- Proctoring, webcam monitoring, or anti-cheat browser lockdown during assessments.
- Live multi-user real-time video streaming, peer chatrooms, or payment/subscription billing.
- Hosting local GPU/transformer embedding or LLM models (API embeddings/LLMs are used when configured; offline retrieval falls back to lightweight TF-IDF lexical similarity).
- OCR on scanned/image-only PDFs or audio/video transcription (image-only PDFs without selectable text are explicitly detected and rejected with a clear message).
- Official nationwide exam rank or percentile prediction (removed from initial scope because nationwide candidate score distributions are not present in the dataset).
- Mandatory paid YouTube Data API or external Web Search API keys in the initial release (architecture keeps the retrieval provider modular for future extension).

### Anti-Goals (What Would Make This a Failure)
- **Static Timetable Generator:** Simply producing a fixed calendar from a PDF without real assessment-driven re-planning.
- **Stubbed Agents:** Having 11 names in documentation while collapsing the actual code into 1–2 generic prompts.
- **Hallucinated Scores/Prerequisites:** Letting an LLM invent numerical mastery percentages, test scores, or forgetting-curve intervals—or silently fabricating fake prerequisites offline.
- **Destructive Demo Shortcuts:** Letting a time-lapse demo simulation corrupt or overwrite real student timestamps, attempt history, or study schedules.
- **Overengineered "Magic" Code:** Heavy design-pattern indirection (meta-factories, excessive generics, opaque wrappers) that prevents the student author from understanding and manually typing the project.
- **Direct Code Writing Overriding User Typing:** Writing application source code directly into workspace files instead of presenting it incrementally in chat.

---

## 3. Constraints

1. **Code Delivery, Terminal Commands & Testing Responsibilities (Critical):**
   - **Phase 0 Authorization:** Antigravity is authorized to generate `Problem_Definition_and_Scope.docx` and `gate_cse_adaptive_dataset.zip` directly in the workspace (these are documentation and dataset deliverables, not application source code).
   - **Chat-Only Delivery for Application Code:** For all Backend, Agents, Frontend, Config, and Test source files, Antigravity must **never** directly create, edit, overwrite, or modify files in the workspace.
   - **File-by-File Cadence:** Present one complete file (or small logical component) at a time in chat. Before each code block, explain the file's purpose, exact path, important imports, classes, functions, variables, FastAPI/React communication or LangGraph orchestration mechanics in beginner-friendly language without assuming prior library knowledge. Wait for the author's confirmation before proceeding to the next file. For debugging, explain the root cause first and provide the smallest targeted fix.
   - **User-Executed Development Commands (Git Bash):** The author executes environment, Git, virtual environment (`.venv`), `pip`, `npm`, database setup, and dev server start/stop commands themselves. Antigravity provides Git Bash-compatible commands (for Windows) and explains each command's purpose, what it changes, and the expected output before asking the author to run it.
   - **Antigravity-Executed Automated Testing:** The author does **not** manually type or run standalone test scripts solely to verify the app. Antigravity owns automated validation (`pytest`, API checks, dataset schema checks, DB integrity checks, frontend build checks) via its terminal and temporary scratch test artifacts without modifying the author's application source code, reporting what was tested, results, and any discovered issues. Manual browser/UI checks are requested only when genuine user interaction is needed.
2. **Environment Isolation:** Backend Python dependencies live in an isolated `.venv` in the project root. Verified host baseline: Python 3.13.5, Node v22.18.0, npm 11.7.0, Git 2.51.0.
3. **Offline / Rate-Limit Resilience:** Every LLM-backed agent must gracefully fall back to deterministic/dataset/PDF-excerpt behavior if no API key is configured or an API call fails, while all deterministic learning-science engines operate 100% independently of LLM availability.
4. **Local-First Persistence:** Single-node SQLite database via SQLAlchemy + per-syllabus local FAISS/TF-IDF indices + NetworkX in-memory DAG reconstructed from persisted tables.

---

## 4. Approaches Considered & Selected Architecture

### Dropped Weak Alternatives
- **Pure rule-based scripts (no LLM):** Cannot parse arbitrary unseen PDF syllabi, generate tailored explanations/examples, or synthesize fresh exam questions across domains.
- **Single monolithic LLM prompt:** Breaks modular 11-agent observability and produces unreliable numerical tracking and schedule adaptation.

### Viable Approaches Evaluated
1. **Hybrid LangGraph + Deterministic Engine + Streamlit UI:** Fast single-process Python prototype, deterministic math, reliable demo—*but* constrained by Streamlit's layout/interactivity limits for rich interactive graphs and SaaS-grade UX.
2. **Decoupled FastAPI Backend + Separate React/TypeScript SPA:** Clean separation of UI, API, orchestration, and data layers with rich UI/UX libraries (`React Flow`, `Recharts`, `shadcn/ui`, `Framer Motion`)—*trades off* managing two processes (`uvicorn` + `vite`) for superior product quality.
3. **Pure Autonomous LLM Tool-Calling Swarm:** Every calculation delegated to LLM agents—*rejected* due to high latency, token cost, and non-deterministic mastery/retention numbers.

### Selected Approach: **Modified Option 2 + Option 1's Hybrid Agentic Intelligence**
Combines **Approach 2's decoupled FastAPI + React/TypeScript SaaS architecture** with **Approach 1's Hybrid Multi-Agent Intelligence** (LangGraph orchestrating 5 LLM-backed cognitive agents + 5 deterministic learning-science engines backed by SQLite, NetworkX, and modular FAISS/TF-IDF retrieval).

---

## 5. System Architecture & Component Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   FRONTEND (React + TypeScript + Vite)                  │
│  Tailwind CSS · shadcn/ui · Framer Motion · React Flow · Recharts       │
│  Global Top-Bar: Active Syllabus Switcher (GATE CSE | Custom PDFs)      │
│  Views: Dashboard | AI Tutor | Syllabus & KG | Planner | Resources |    │
│         Practice & Tests | Analytics | Parent/Teacher | Agent Trace     │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ REST JSON (?syllabus_id=...) + JWT
┌──────────────────────────────────▼──────────────────────────────────────┐
│                        BACKEND (FastAPI + Python)                       │
│  JWT Auth & RBAC (Student / Read-Only Parent-Teacher) · Ownership Check │
│  Multi-Syllabus PDF Ingestion · Assessment · Analytics · Trace Viewer   │
│  Persistence: SQLite + SQLAlchemy | Graph: NetworkX | Index: FAISS/TFIDF│
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Invokes Sub-Workflow + Logs Traces
┌──────────────────────────────────▼──────────────────────────────────────┐
│           AGENT 11: MASTER ORCHESTRATOR (LangGraph StateGraph)          │
│                                                                         │
│  LLM Cognitive Agents (w/ Fallback)     Deterministic Engines           │
│  ├─ 2. Syllabus Understanding (+PDF)    ├─ 1. Student Profiling         │
│  ├─ 3. Resource Discovery (Modular)     ├─ 4. Study Planner (DAG)       │
│  ├─ 5. Teaching Agent                   ├─ 7. Assessment Grader         │
│  ├─ 6. Practice Question Generator      ├─ 8. Weakness Detection        │
│  └─ 10. Motivation & Coaching           └─ 9. Adaptive Planning         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Immediate Phase-0 Deliverables (Authorized Direct Generation)

#### A. `Problem_Definition_and_Scope.docx`
Generated via `python-docx` in the workspace root:
1. Title Page & Lab Metadata (Agentic AI & Enterprise Automation Lab — PS-03)
2. Problem Definition & Background (why static schedules fail; need for closed-loop adaptive tutoring)
3. Objectives & Measurable Success Criteria
4. Proposed Multi-Agent Solution (all 11 agents, LangGraph orchestration, hybrid LLM + deterministic model)
5. Scope of All 6 Advanced Features (including honest scope boundaries for predictive estimates and read-only Parent/Teacher monitoring)
6. Dataset Specification (GATE CSE flagship scope scored out of 100 + multi-syllabus generic PDF upload capability)
7. System Architecture & Technology Stack
8. Reliability, Offline PDF-Text/TF-IDF Fallbacks, Non-Destructive Demo Simulation & Agent Trace Observability
9. Constraints, Assumptions & Out-of-Scope Boundaries

#### B. `gate_cse_adaptive_dataset.zip`
Generated in the workspace root (and later extracted into `data/gate_cse/` for backend seeding) with verified schema integrity:
- `README.md` & `dataset_manifest.json` — Version, record counts, schema guide, provenance (curated canonical textbook/course references + synthetic learner trajectories).
- `sample_syllabi/gate_cse_syllabus.pdf` — Structured multi-unit text-selectable GATE CSE syllabus PDF (DBMS, OS, Computer Networks, TOC, Discrete Mathematics, Linear Algebra, Calculus, Probability & Statistics) usable directly to test Agent 2 PDF ingestion.
- `syllabus_graph.json` — Hierarchical tree + prerequisite DAG across all 8 subjects (~40–48 topics, ~120+ subtopics), each with `topic_id`, `subject`, `unit`, `title`, `subtopics`, `raw_excerpt`, `difficulty` (1–5), `exam_weightage`, `estimated_hours`, `prerequisite_confidence` (`verified_seed`), and acyclic `prerequisites` (validated via NetworkX).
- `learning_resources.json` — Curated multi-modal resources per topic across 4 modalities: `video` (canonical NPTEL / MIT OCW / classic university course references), `textbook` (standard authors & chapters like Silberschatz, Korth, Kurose-Ross, Sipser, Rosen, Strang, Sheldon Ross), `notes` (concise markdown study notes tagged `source_origin="curated_dataset_note"`), and `flashcards` (concept Q&A pairs).
- `question_bank.json` — ~240+ Easy / Medium / Hard conceptual & GATE-style questions tagged with `topic_id`, `subtopic`, `difficulty`, `question_type`, `prompt`, `options`, `correct_answer`, `explanation`, and `expected_time_sec`.
- `student_profiles.json` — 4 realistic student personas (including the flagship PDF scenario: `GATE CSE`, `max_score=100`, `target_score=75`, `days_remaining=90`, `daily_hours=4`, strong in DBMS/OS, weak in Computer Networks/TOC; plus Visual, Reading, and Practice-Oriented learner profiles, plus a linked `parent_teacher` demo account).
- `assessment_attempts.json` & `mastery_history.json` — Multi-week historical diagnostic, topic quiz, and weekly mock test attempts (scaled to GATE CSE's 100-mark format) with per-question `is_correct`, `time_taken_sec`, timestamps, computed `mastery_score`, `retention_score`, and logged schedule adaptations for immediate trend visualization.

---

### 5.2 Hybrid Multi-Agent Specification (All 11 Agents in LangGraph)

LangGraph maintains a typed `TutorState` dictionary scoped by `student_id` and `syllabus_id`, persisted across real runs via SQLite checkpoints and `agent_execution_logs`.

| # | Agent Name | Type | Core Responsibility | Inputs → Outputs |
|---|---|---|---|---|
| 1 | **Student Profiling Agent** | Deterministic | Captures availability (`daily_hours`), learning style (`visual` / `reading` / `practice`), syllabus target (`exam_name`, `target_score`, `max_score`, `days_remaining`); deterministically scores diagnostic quiz (or converts self-reported strength ratings) into baseline per-topic mastery. | Form + diagnostic/self-ratings → `StudentProfile` + baseline `TopicMastery[]` |
| 2 | **Syllabus Understanding Agent** | LLM + `pypdf`/PyMuPDF + NetworkX (w/ Heading/Numbering Fallback) | Extracts raw text per page; rejects scanned/image-only PDFs lacking extractable text (`422`); parses units, topics, subtopics, and verbatim `raw_excerpt` blocks. Uses LLM for candidate prerequisite edges when online (flagged `llm_extracted` / `needs_review` if uncertain); offline fallback parses headings/numbering cleanly without inventing non-obvious cross-unit prerequisites. Validates DAG acyclicity via NetworkX. | Uploaded PDF bytes → `SyllabusGraph` (nodes w/ `raw_excerpt` + tagged prerequisite edges) |
| 3 | **Resource Discovery Agent** | Modular `RetrievalProvider` (API Embeddings + FAISS online; TF-IDF fallback offline) + LLM Synthesis | Ranks local library resources scoped strictly to `syllabus_id`; when LLM is available, synthesizes contextual study notes (`source_origin="llm_generated_summary"`), flashcards, textbook references, and curated search queries; offline falls back to local TF-IDF matches and raw extracted PDF excerpts (`source_origin="extracted_pdf_excerpt"`). | `syllabus_id` + `topic_id` + `learning_style` → ranked `LearningResource[]` w/ provenance tags |
| 4 | **Study Planner Agent** | Deterministic (DAG + Constraint Scheduler) | Performs prerequisite-respecting topological sort weighted by difficulty, baseline weakness, exam weightage, and `daily_hours`; allocates daily learn/practice blocks, assessment checkpoints, and initial Day 3/7/14/30 spaced repetition slots. | `SyllabusGraph` + `SyllabusConfig` + `TopicMastery[]` → `StudyPlanItems[]` |
| 5 | **Teaching Agent** | LLM (w/ Curated Notes & `raw_excerpt` Fallback) | Explains concepts adapted to `learning_style`, generates real-world examples, builds prerequisite dependency paths, and produces flashcards (`llm_generated_summary`); offline fallback presents curated dataset notes or cleanly labeled PDF `extracted_pdf_excerpt` sections without pretending they are AI-generated summaries. | `topic` + `raw_excerpt` + `mastery` + `learning_style` → `LessonPackage` w/ `source_origin` |
| 6 | **Practice Question Generator** | Hybrid (Question Bank + LLM + `raw_excerpt` Fallback) | Selects difficulty-calibrated questions from `question_bank` and generates fresh Easy/Medium/Hard questions via LLM; offline on custom PDFs creates structured concept-check prompts directly from persisted `raw_excerpt` definitions and subtopics. | `topic_id` + `raw_excerpt` + `target_difficulty` → `Question[]` |
| 7 | **Assessment Agent** | Deterministic | Conducts Diagnostic, Topic Quizzes, Weekly Tests (20 Qs), and Mock Exams scoped to `syllabus_id`; grades responses deterministically and outputs `{score, max_score, accuracy, time_taken_sec, per_topic_breakdown}`. | `AssessmentSubmission` → `AssessmentResult` + `QuestionAttempt[]` |
| 8 | **Weakness Detection Agent** | Deterministic Learning-Science Engine | Updates topic mastery (EMA + difficulty weighting), computes Ebbinghaus retention `R(t)` (at real `now` or a temporary simulated evaluation date during non-destructive demos), detects weak topics (`mastery < 60%` or consecutive misses), identifies overdue tasks, and traces root-cause prerequisite blockers in NetworkX. | `AssessmentResult` / `eval_date` + `AttemptHistory` + `SyllabusGraph` → `WeaknessReport` + `RetentionAlerts[]` |
| 9 | **Adaptive Planning Agent** | Deterministic Re-Scheduler | Reacts to Weakness & Retention Alerts: injects immediate revision, extra practice, and re-tests; reschedules overdue pending tasks; pulls forward Day 3/7/14/30 spaced repetition reviews; re-balances remaining days before exam date. *(Skipped from DB writes during non-destructive Demo Simulation—returns preview diff only.)* | `WeaknessReport` + `RetentionAlerts[]` + `StudyPlan` → `UpdatedStudyPlan` / `PreviewDiff` |
| 10 | **Motivation & Coaching Agent** | Deterministic Metrics + LLM Narrative | Computes study streak, hours completed, week-over-week accuracy deltas, and **Estimated Predictive Exam Score** per syllabus; generates grounded coaching feedback referencing real numbers (with deterministic template fallback). | `ProgressMetrics` + `PredictiveScoreEstimate` → `CoachingSummary` |
| 11 | **Master Orchestrator** | LangGraph `StateGraph` | Coordinates 5 sub-workflows (`onboard_syllabus_flow`, `complete_diagnostic_flow`, `study_session_flow`, `assessment_adapt_flow`, `daily_check_flow`) plus a read-only `demo_simulation_flow`, logging traces for observability. | `WorkflowTrigger` + `TutorState` → updated state + `ExecutionTrace[]` |

#### LangGraph Sub-Workflows & Conditional Transitions
1. **Onboarding Part A — Syllabus Ingestion (`POST /api/workflows/onboard-syllabus`):**
   `[1: Student Profiler (save goals & learning style)]` → `[2: Syllabus Understanding (extract text; reject scanned PDFs; parse nodes/raw_excerpts/DAG)]` → `[3: Resource Discovery (index syllabus_id & match/synthesize)]` → `[6: Question Generator (prepare 8–12 baseline diagnostic questions)]` → `END`
2. **Onboarding Part B — Baseline & Plan (`POST /api/workflows/complete-diagnostic`):**
   `[1: Student Profiler (score diagnostic OR convert self-reported strengths/weaknesses)]` → `[4: Study Planner (topological DAG schedule + Day 3/7/14/30 milestones)]` → `[10: Motivation Coach (initial estimated readiness score)]` → `END`
3. **Study & Practice Flow (`POST /api/workflows/teach-and-practice`):**
   `[3: Resource Discovery (if uncached)]` → `[5: Teaching Agent]` → `[6: Question Generator (calibrated to topic mastery)]` → `END`
4. **Closed Adaptive Loop (`POST /api/assessments/{id}/submit`):**
   `[7: Assessment Agent]` → `[8: Weakness Detection]` → *(conditional edge)*:
   - **Weakness OR Retention Decay Detected:** → `[9: Adaptive Planner (insert revision + practice + retest)]` → `[6: Question Generator (pre-stage targeted practice)]` → `[10: Motivation Coach]` → `END`
   - **Target Mastery Met (`M >= 75%` and `R(t) >= 0.65`):** → `[9: Adaptive Planner (schedule Day +3/+7/+14/+30 spaced review & advance schedule)]` → `[10: Motivation Coach]` → `END`
5. **Real Daily Retention & Overdue Check (`POST /api/workflows/daily-check` + auto-run on Dashboard load once per 24h):**
   `[8: Weakness & Retention Scan (real timestamp now; checks R(t) < 0.65 & overdue study_plan_items)]` → *(conditional edge)*:
   - **If alerts or overdue items exist:** → `[9: Adaptive Planner (persists rescheduled overdue items & priority revision)]` → `[10: Motivation Coach]` → `END`
   - **Otherwise:** → `[10: Motivation Coach (streak & daily summary)]` → `END`
6. **Non-Destructive Demo Simulation (`POST /api/workflows/daily-check/simulate`):**
   `[8: Read-Only Retention Scan using temporary eval_date = now + simulate_days_elapsed]` → `[9: Compute Preview Adaptation Diff in Memory (NO DB WRITES)]` → `END`  
   *Guarantees:* Never alters `last_practiced_at`, `assessment_attempts`, `topic_mastery`, `study_plan_items`, or `plan_adaptations`. All outputs are explicitly tagged `is_simulation: true` and labeled **Demo Simulation** in the UI.

---

### 5.3 Deterministic Learning-Science Algorithms (Exact Specifications)

1. **Topic Mastery Estimation (Recency-Weighted EMA + Difficulty Calibration):**
   - Each attempt gets weight $w_i$ by difficulty (`Easy = 0.8`, `Medium = 1.0`, `Hard = 1.25`) multiplied by pacing factor (`1.05` if solved accurately within `1.2 * expected_time_sec`, `0.95` if $> 1.8 \times \text{expected\_time\_sec}$, else `1.0`).
   - Session score for topic $k$: $S_k = \text{clamp}\left(100 \times \frac{\sum c_i w_i}{\sum w_i}, 0, 100\right)$ where $c_i \in \{0, 1\}$.
   - Updated mastery: $M_{\text{new}} = \text{clamp}(0.65 \cdot M_{\text{old}} + 0.35 \cdot S_k, 0, 100)$.
   - Initial diagnostic sets $M_0$ directly from diagnostic accuracy (or self-reported ratings: Strong=`78`, Moderate=`55`, Weak=`35`; default prior=`40` for untested topics).

2. **Weakness & Prerequisite Bottleneck Detection:**
   - Topic flagged `weak` if $M_{\text{new}} < 60$, OR accuracy drops $> 15$ points across the last 2 assessments, OR $\ge 2$ consecutive misses occur on the same subtopic.
   - Using `NetworkX` (`nx.ancestors(G, topic_id)`), if a weak topic has an upstream prerequisite with $M < 65$, that ancestor is flagged as a **Root-Cause Prerequisite Blocker** and scheduled ahead of the dependent topic.

3. **Ebbinghaus Forgetting Curve Detection:**
   - Retention estimate:
     $$R_k(t) = \exp\left(-\frac{t}{S_k^{\text{mem}}}\right)$$
     where $t$ is days elapsed between `last_practiced_at` and the evaluation date (`now` for real checks, or `now + simulate_days_elapsed` in memory for Demo Simulation), and stability $S_k^{\text{mem}} = 4.0 \times (1 + 0.55 \cdot n_{\text{rev}}) \times \left(0.5 + \frac{M_k}{100}\right)$ days ($n_{\text{rev}}$ = completed spaced-repetition reviews).
   - If $R_k(t) < 0.65$, the topic triggers a **Retention Falling Alert**.

4. **Spaced Repetition Engine (Day 3 / 7 / 14 / 30):**
   - Completing a topic schedules review checkpoints at offsets `+3`, `+7`, `+14`, `+30` days.
   - If assessment drops $M < 60$ or real retention falls below `0.65`, the review pulls forward to `Day +1 / +2` remedial revision before resuming the `3/7/14/30` sequence.

5. **Predictive Exam Score Estimate (Scoped & Configured per Exam):**
   - **Current Estimated Score:**
     $$\text{Score}_{\text{curr}} = \text{MaxScore} \times \frac{\sum_k W_k \cdot (M_k / 100) \cdot (0.7 + 0.3 R_k)}{\sum_k W_k}$$
   - **Projected Exam-Day Estimate:** Uses linear regression slope of weekly average mastery velocity $\hat{v}$ over remaining weeks $w_{\text{rem}}$ (with diminishing-returns damping as mastery approaches 95%)—for example, on **GATE CSE (`max_score = 100`)**, showing **Current Estimated Score: `62.5 / 100`** and **Projected Exam-Day Estimate: `76.0 / 100`**.
   - **Honest Labeling:** All API payloads and UI components explicitly label these values as **Estimated Readiness Projections** based on internal mastery/retention trends, not guaranteed official exam scores. Configurable `max_score` supports other exams (e.g., `100`, `200`, `300`) cleanly.

6. **Question Difficulty Adaptation:**
   - `M < 50`: 60% Easy, 30% Medium, 10% Hard
   - `50 <= M < 75`: 25% Easy, 50% Medium, 25% Hard
   - `M >= 75`: 10% Easy, 40% Medium, 50% Hard

---

### 5.4 Persistence, Isolation, Permissions & Retrieval

#### Multi-Syllabus Isolation & Ownership Enforcement
- **Backend Ownership Guard (Never Trust Frontend State):** Every protected route resolves `authenticated_user` from the JWT token. Any request accessing or modifying a `syllabus_id` (or its child topics, plans, assessments, or resources) verifies `syllabus.student_id == effective_student_id` at the service/API boundary, returning `403 Forbidden` / `404 Not Found` on mismatch.
- **Database-Level Cross-Syllabus Integrity:**
  - All syllabus-dependent tables (`syllabus_topics`, `topic_prerequisites`, `topic_mastery`, `learning_resources`, `questions`, `study_plan_items`, `assessments`, `question_attempts`, `plan_adaptations`, `agent_execution_logs`) carry `syllabus_id` with cascading/indexed foreign keys.
  - `syllabus_topics` includes a unique constraint on `(syllabus_id, id)`. `topic_prerequisites` enforces composite foreign keys `(syllabus_id, prerequisite_topic_id)` and `(syllabus_id, dependent_topic_id)` referencing `syllabus_topics(syllabus_id, id)` (with SQLite `PRAGMA foreign_keys=ON`), making cross-syllabus prerequisite edges impossible at the database layer as well as in application logic.
  - `topic_mastery`, `study_plan_items`, `assessments`, `question_attempts`, and `plan_adaptations` additionally enforce `student_id` + `syllabus_id` alignment.

#### Parent/Teacher Account Association & Read-Only Authorization
- **Controlled Association:** `users` includes `role` (`"student"` | `"parent_teacher"`) and `linked_student_id` (nullable FK to `student_profiles.id`). Each `student_profiles` row holds a unique `link_code` (e.g., `"GATE-DEMO-8421"`). A `parent_teacher` account links to one student either via the seeded demo association or by supplying the student's `link_code` at registration/linking time.
- **Strict Read-Only Access:** Backend dependency guards (`require_student_role` vs `require_parent_or_student_read`) enforce that `parent_teacher` accounts can **only** call read-only monitoring endpoints (`GET /api/analytics/parent-dashboard`, `GET /api/syllabi` for the linked student) scoped strictly to `current_user.linked_student_id`. Any mutation route (uploading syllabi, updating profile, starting/submitting assessments, triggering re-planning, editing prerequisites) returns `403 Forbidden` for `parent_teacher` tokens.

#### Core Relational Tables
- `users` (`id`, `name`, `email`, `password_hash`, `role` [`student` | `parent_teacher`], `linked_student_id`, `created_at`)
- `student_profiles` (`id`, `user_id`, `active_syllabus_id`, `link_code`, `current_grade`, `daily_hours`, `learning_style`, `study_streak`, `total_hours_logged`, `last_active_date`)
- `syllabi` (`id`, `student_id`, `title`, `exam_name`, `target_score`, `max_score`, `days_remaining`, `source_type` [`seeded` | `pdf_upload`], `raw_filename`, `last_daily_check_at`, `created_at`)
- `syllabus_topics` (`id`, `syllabus_id`, `topic_code`, `subject`, `unit`, `title`, `subtopics_json`, `raw_excerpt`, `source_origin` [`curated_dataset_note` | `extracted_pdf_excerpt`], `difficulty`, `exam_weightage`, `estimated_hours`) + `UNIQUE(syllabus_id, id)`
- `topic_prerequisites` (`id`, `syllabus_id`, `prerequisite_topic_id`, `dependent_topic_id`, `confidence_status` [`verified_seed` | `llm_extracted` | `needs_review` | `user_confirmed`]) + composite FKs to `syllabus_topics(syllabus_id, id)`
- `topic_mastery` (`id`, `student_id`, `syllabus_id`, `topic_id`, `mastery_score`, `retention_score`, `stability_days`, `review_count`, `status` [`unstarted` | `learning` | `weak` | `mastered`], `last_practiced_at`)
- `learning_resources` (`id`, `syllabus_id`, `topic_id`, `modality` [`video` | `textbook` | `notes` | `flashcard` | `search_query`], `title`, `source_ref`, `url_or_content`, `summary`, `source_origin` [`curated_dataset_note` | `extracted_pdf_excerpt` | `llm_generated_summary`], `created_by_agent`)
- `questions` (`id`, `syllabus_id`, `topic_id`, `subtopic`, `difficulty` [`easy` | `medium` | `hard`], `question_type`, `prompt`, `options_json`, `correct_answer`, `explanation`, `expected_time_sec`, `source_origin`, `is_generated`)
- `study_plan_items` (`id`, `student_id`, `syllabus_id`, `topic_id`, `scheduled_date`, `day_number`, `task_type` [`learn` | `practice` | `revision` | `spaced_rep` | `assessment`], `duration_hours`, `status` [`pending` | `completed` | `rescheduled`], `adaptation_reason`)
- `assessments` (`id`, `student_id`, `syllabus_id`, `title`, `assessment_type` [`diagnostic` | `topic_quiz` | `weekly_test` | `mock_exam`], `score`, `max_score`, `accuracy`, `time_taken_sec`, `created_at`)
- `question_attempts` (`id`, `assessment_id`, `student_id`, `syllabus_id`, `topic_id`, `question_id`, `selected_answer`, `is_correct`, `time_taken_sec`, `created_at`)
- `plan_adaptations` (`id`, `student_id`, `syllabus_id`, `trigger_assessment_id`, `weak_topics_json`, `summary`, `changes_json`, `created_at`)
- `agent_execution_logs` (`id`, `run_id`, `student_id`, `syllabus_id`, `workflow_name`, `agent_number`, `agent_name`, `execution_mode` [`llm` | `fallback` | `deterministic` | `simulation`], `status`, `latency_ms`, `input_summary`, `output_summary`, `error_message`, `created_at`)

#### Modular Retrieval Strategy (Per-Syllabus FAISS Online + Honest TF-IDF Fallback Offline)
- **Provider Abstraction (`RetrievalProvider`):** Keeps search decoupled so the caller only passes `(syllabus_id, query, top_k)`.
- **Online Mode (Embedding API Configured):** Calls the configured API embedding model (`GOOGLE_API_KEY` or `OPENAI_API_KEY`) to build and query a **dedicated per-syllabus FAISS index** (`faiss_indices/syllabus_{syllabus_id}.index` + metadata map), guaranteeing zero cross-syllabus results.
- **Offline Fallback Mode (No Embedding API):** Explicitly documented as **lightweight lexical / approximate vector similarity** (not transformer-equivalent semantic understanding):
  - Uses `scikit-learn` **TF-IDF cosine similarity** scoped strictly to documents within `syllabus_id`.
  - Applies `TruncatedSVD` + per-syllabus FAISS indexing **only** when the syllabus corpus has sufficient documents and vocabulary terms (`n_docs >= svd_dim` and `n_features >= svd_dim`, e.g., `>= 32`).
  - For small corpora (such as a newly uploaded single-subject PDF), skips SVD and falls back directly to **sparse TF-IDF cosine similarity** (`TfidfVectorizer` dot product).
  - Never uses hashed NumPy random projections and never labels TF-IDF/SVD matches as deep semantic embeddings.

---

### 5.5 Frontend Architecture & Page Map (React + TypeScript + Vite)

- **Stack:** React 18+, TypeScript, Vite, Tailwind CSS, `shadcn/ui`, `Framer Motion`, `React Flow`, `Recharts`, `Lucide` icons.
- **Global Top Bar:** Persistent **Active Syllabus Switcher** (`GATE CSE (Flagship)` ↔ Custom Uploaded PDFs + `+ Upload Syllabus PDF`), Demo Persona Switcher (`GATE CSE Student`, `Parent / Teacher (Read-Only)`), and Execution Mode indicator (`LLM Active` / `Offline Fallback`).
- **9 Core Views:**
  1. **Student Dashboard:** Today's adaptive tasks, study streak, **Estimated Predictive Score** card (`62.5 / 100 Current Estimate` → `76.0 / 100 Projected Estimate`, clearly labeled as estimates), real forgetting-curve alerts, a clearly marked **Demo Simulation** drawer/button (*"Simulate +N Days (Non-Destructive)"*), and quick actions.
  2. **AI Study Assistant (Teaching Agent 5):** Concept tutor adapted to learning style—structured explanation, real-world analogy, prerequisite dependency path breadcrumbs, interactive flashcards, and follow-up Q&A—with explicit badge showing whether content is `LLM Generated`, `Curated Dataset Note`, or `Extracted PDF Excerpt`.
  3. **Syllabus Explorer & Interactive Knowledge Graph (`React Flow`):** Inspect GATE CSE or upload any text-selectable custom PDF (clear warning/error on scanned image-only PDFs); zoomable prerequisite DAG color-coded by mastery (`Red < 60%`, `Amber 60–79%`, `Green >= 80%`) with dashed/badge indicators on `needs_review` prerequisite edges so students can confirm or remove uncertain dependencies.
  4. **Personalized Study Planner & Adaptive Timeline:** Day-by-day / Week-by-week schedule distinguishing `Learn`, `Practice`, `Spaced Repetition (Day 3/7/14/30)`, and `Assessment` blocks, plus an **"Adaptation Diff"** panel explaining real persisted plan changes (separate from any non-destructive Demo Simulation preview).
  5. **Learning Resources Library:** Filterable by subject, topic, and modality (`Videos`, `Textbooks`, `Notes`, `Flashcards`, `Curated Queries`) with per-syllabus retrieval search (`API Embeddings + FAISS` or `TF-IDF Lexical Fallback` badge) and on-demand Agent 3 synthesis.
  6. **Practice Questions & Assessments:** Adaptive topic quizzes, 20-question weekly tests, and full mock exams with timer, per-question pacing, immediate diagnostic breakdown, and instant trigger of the closed adaptive loop (`Assessment → Weakness → Re-plan`).
  7. **Student Progress & Performance Analytics (`Recharts`):** Mastery trends over time, subject breakdown, Ebbinghaus retention decay curve, accuracy vs. speed scatter, and estimated predictive score trajectory.
  8. **Parent / Teacher Dashboard (Read-Only):** Accessible via linked `parent_teacher` account (or read-only demo view): displays hours studied, streak consistency, flagged weak topics & prerequisite blockers, week-over-week mastery trends, **Syllabus Coverage %**, **Estimated Score (`X / MaxScore`)**, **Target Gap**, and **Readiness Band** (no ungrounded rank/percentile claims).
  9. **Agent Execution Trace:** Live/historical timeline of LangGraph runs for the active syllabus showing `run_id`, workflow name, invoked agents (`1–11`), execution mode badge (`LLM`, `Deterministic`, `Fallback`, `Demo Simulation`), latency in ms, and expandable state diff payloads.

---

### 5.6 Reliability, Fallbacks & Core REST API Surface

- **LLM Provider Abstraction:** Supports Gemini (`langchain-google-genai`) or OpenAI (`langchain-openai`) via `.env` (`LLM_PROVIDER`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`).
- **Core REST Endpoints (All syllabus-scoped APIs enforce backend ownership + RBAC):**
  - `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/demo-login`, `GET /api/auth/me`
  - `GET / PUT /api/students/profile` (student write; parent read-only summary)
  - `GET /api/syllabi`, `POST /api/syllabi/{id}/activate`, `GET /api/syllabi/{id}/graph`, `PATCH /api/syllabi/{id}/prerequisites` (confirm/remove `needs_review` edges; student only)
  - `POST /api/workflows/onboard-syllabus` (PDF upload w/ scanned-PDF `422` check or GATE CSE seed → Agents 1, 2, 3, 6)
  - `POST /api/workflows/complete-diagnostic` (Diagnostic or self-ratings → Agents 1, 4, 10)
  - `POST /api/workflows/teach-and-practice` (Agents 3, 5, 6)
  - `POST /api/workflows/daily-check` (Real persistence check → Agents 8, 9, 10)
  - `POST /api/workflows/daily-check/simulate` (Read-only non-destructive Demo Simulation w/ `simulate_days_elapsed`)
  - `GET /api/resources`, `POST /api/resources/discover`
  - `GET /api/planner`, `POST /api/planner/adapt`
  - `POST /api/tutor/ask`
  - `POST /api/assessments/start`, `POST /api/assessments/{id}/submit`, `GET /api/assessments/history`
  - `GET /api/analytics/student`, `GET /api/analytics/parent-dashboard`, `GET /api/analytics/forgetting-curve`
  - `GET /api/agents/traces`, `GET /api/agents/traces/{run_id}`

---

## 6. Implementation Priorities (Tiered Build Plan)

All 11 agents and all 6 advanced features remain in scope, organized into three build priorities so a rock-solid end-to-end adaptive learning cycle works before secondary polish:

### Tier 1 — Core Implementation (Must Work End-to-End First)
- **Foundation & Isolation:** SQLite + SQLAlchemy schema with `syllabus_id` composite integrity, JWT auth + ownership guards, GATE CSE `.zip` seed loader.
- **Core Agents & Orchestrator:** Agent 1 (Student Profiler), Agent 2 (Syllabus Understanding w/ PDF fallback & scanned-PDF rejection), Agent 4 (DAG Study Planner), Agent 7 (Assessment Grader), Agent 8 (Weakness Detection), Agent 9 (Adaptive Planner), Agent 11 (LangGraph `StateGraph` + `agent_execution_logs`).
- **Core Frontend Loop:** Auth + Top-Bar Syllabus Switcher, Onboarding/PDF Upload, Interactive Study Planner w/ Adaptation Diff, Practice Quiz & Assessment Submission triggering live re-planning, and Agent Execution Trace view.

### Tier 2 — Advanced Demonstration Features (Built Once Core Loop Is Stable)
- **Remaining Cognitive Agents:** Agent 3 (Modular `RetrievalProvider`: API FAISS + TF-IDF offline fallback + LLM synthesis), Agent 5 (Teaching Agent w/ `source_origin` provenance), Agent 6 (Adaptive Practice Question Generator), Agent 10 (Motivation Coach + Estimated Predictive Score).
- **Advanced Features & Dashboards:** Interactive React Flow Knowledge Graph (mastery color-coding + `needs_review` edge flags), Ebbinghaus Forgetting Curve + Day 3/7/14/30 Spaced Repetition + Non-Destructive Demo Simulation (`daily-check/simulate`), Multi-Modal Resources Library, Recharts Student Analytics, and Read-Only Parent/Teacher Dashboard (`link_code` association).

### Tier 3 — Optional Enhancements (Must Not Block a Working Project)
- Framer Motion transition polish and micro-interactions.
- Interactive drag/add UI for manually editing prerequisite DAG edges inside React Flow.
- Exportable study plan / progress summary report (PDF/Markdown).
- Future live external YouTube Data API / Web Search `RetrievalProvider` plugins.

---

## 7. What Is Left to the Builder (Planning & Implementation Freedom)

- Exact visual palette, typography pairing, and shadcn/ui component styling within the SaaS quality bar.
- Exact LLM prompt templates and structured output schemas for Agents 2, 3, 5, 6, and 10.
- Exact step-by-step milestone ordering inside the `writing-plans` implementation plan (Phase 0 direct generation first, then Tier 1 → Tier 2 → Tier 3 incremental chat-only file delivery with verification steps).
- Specific pytest/unit tests covering deterministic mastery/forgetting math, cross-syllabus DB/API isolation, parent/teacher read-only RBAC, scanned-PDF rejection, non-destructive demo simulation invariants, and dataset schema checks.
