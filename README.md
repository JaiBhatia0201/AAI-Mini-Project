# PS-03: Adaptive Exam Prep & Multi-Agent Tutoring System

A full-stack **11-Agent LangGraph** adaptive study platform that helps students plan, learn, practice, and retain **any course or competitive exam syllabus**. Brand-new users can upload any text-selectable syllabus PDF to generate an isolated prerequisite Knowledge Graph, study roadmap, AI lessons, calibrated quizzes, and forgetting-curve alerts—or explore the pre-seeded GATE CSE demo personas.

---

## Core Capabilities

- **Works for Any Student & Any Syllabus PDF**: Upload any text-selectable PDF (university courses, certifications, competitive exams) to extract structured topics, verbatim syllabus excerpts, study resources, and diagnostic questions. Scanned/image-only PDFs (`< 50` extractable chars/page) are rejected cleanly with `HTTP 422` before modifying the database.
- **11-Agent LangGraph Pipeline (`StateGraph`)**:
  - **LLM-Capable Cognitive Agents (with deterministic/excerpt fallbacks)**: Syllabus Understanding (`Agent 2`), Resource Synthesis (`Agent 3`), Style-Adapted Teaching (`Agent 5`), Question Selection/Generation (`Agent 6`), and Grounded Motivational Coaching (`Agent 10`).
  - **Deterministic Learning-Science Engines**: Student Profiling (`Agent 1`), Topological DAG Study Planner (`Agent 4`), Assessment Grader (`Agent 7`), Weakness & Ancestor-Blocker Detector (`Agent 8`), Adaptive Re-Scheduler (`Agent 9`), and LangGraph Master Orchestrator (`Agent 11`).
- **Interactive Knowledge Graph (`@xyflow/react`)**: Color-coded prerequisite DAG (`Red < 60%`, `Amber 60–79%`, `Green >= 80%`) with interactive verification (`Confirm` / `Remove`) for uncertain `needs_review` dependencies.
- **Closed-Loop Adaptive Assessment**: Submitting a quiz automatically evaluates topic mastery, locates upstream root-cause prerequisite blockers, inserts remedial revision tasks + `Day +1/+2` pull-forwards for weak topics, or schedules `Day +3/+7/+14/+30` spaced repetition checkpoints when on track.
- **Ebbinghaus Forgetting Curve & Non-Destructive Simulator**: Tracks retention decay $R = \exp(-t / S_{\text{mem}})$ and provides a read-only **Demo Simulator** (`+N` days) that previews future alerts and reschedules strictly in memory without mutating SQLite data.
- **Modular Per-Syllabus Retrieval**: Uses API embeddings (`Gemini` or `OpenAI`) + dedicated per-syllabus FAISS indices when keys are configured, or falls back transparently to local `scikit-learn` TF-IDF (with conditional `TruncatedSVD` + FAISS for larger corpora).
- **Read-Only Parent / Teacher Portal**: Guardians register using a student's unique `link_code` to view progress, coverage, readiness estimates, and weak/blocker topics while write operations remain blocked (`HTTP 403`).

---

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy ORM + SQLite (`PRAGMA foreign_keys=ON`), PyJWT + bcrypt, `pypdf`, `NetworkX`, `scikit-learn`, `faiss-cpu`, `LangGraph`.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, `@xyflow/react`, `Recharts`, `Framer Motion`, `Lucide React`.

---

## Project Structure

```text
Mini-Project/
├── .env.example                 # Environment & API provider template
├── backend/
│   ├── requirements.txt         # Python dependencies
│   ├── app/
│   │   ├── main.py              # FastAPI app, startup DB init & seeding, /api/health
│   │   ├── config.py            # REPO_ROOT-anchored settings loader
│   │   ├── database.py          # SQLite engine & session setup
│   │   ├── models.py            # 13 SQLAlchemy models w/ multi-syllabus isolation
│   │   ├── schemas.py           # Pydantic v2 request/response schemas
│   │   ├── agents/              # Agents 1-10 + Agent 11 LangGraph orchestrator
│   │   ├── engines/             # DAG, EMA mastery, Ebbinghaus, spaced rep, predictor
│   │   ├── routers/             # Auth, students, syllabi, workflows, planner, tutor, etc.
│   │   └── services/            # JWT/RBAC auth, LLM client, retrieval, GATE seeder
│   └── tests/                   # Pytest unit, orchestrator, and API E2E test suite
├── frontend/
│   ├── package.json             # Frontend scripts & dependencies
│   ├── vite.config.ts           # Vite server & /api proxy to 127.0.0.1:8000
│   └── src/
│       ├── context/AppContext.tsx
│       ├── lib/api.ts           # Typed REST client with JWT persistence
│       ├── types/api.ts         # Shared TypeScript API contracts
│       ├── components/          # AppShell workspace chrome & UI primitives
│       └── pages/               # Auth, Onboarding, Dashboard, Graph, Tutor, Planner, etc.
├── data/gate_cse/               # Extracted GATE CSE flagship dataset & sample syllabus PDF
└── docs/                        # System design specification & implementation plan
```

---

## Setup & Installation

### 1. Configure Environment Variables
Copy `.env.example` to `.env` in the repository root if `.env` does not already exist:
- Leave API keys blank to run **100% offline** using deterministic rules, PDF excerpts, and local TF-IDF retrieval.
- Set `GROQ_API_KEY` (default model `openai/gpt-oss-120b`), `GEMINI_API_KEY`, or `OPENAI_API_KEY` (with `LLM_PROVIDER=auto` or explicit provider name) to enable live LLM tutoring/parsing.

### 2. Backend Setup (Python Virtual Environment)
From the repository root (`Mini-Project/`):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 3. Frontend Setup (Node.js)
```powershell
cd frontend
npm install
cd ..
```

---

## Running the Application

Open **two terminals** in the repository root:

**Terminal 1 — FastAPI Backend (`http://127.0.0.1:8000`):**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```
- Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`
- Health & active mode check: `http://127.0.0.1:8000/api/health`

**Terminal 2 — Vite React Frontend (`http://localhost:5173`):**
```powershell
cd frontend
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## Quick UI Walkthrough (New User Flow)

1. **Register a Student Account**: Open `http://localhost:5173`, select **Create Brand-New Account** → **Student**, enter any name/email/password, and submit. Your personal **Parent Link Code** appears in the top bar.
2. **Upload a Syllabus PDF**: Select **Upload Your Own Syllabus PDF**, choose any text-selectable PDF (for testing, `data/gate_cse/sample_syllabi/gate_cse_syllabus.pdf` is included in the repo), configure your target score & learning style, and click **Build Knowledge Graph & Diagnostic**.
3. **Calibrate Baseline**: Answer or skip the generated diagnostic check to personalize your initial DAG roadmap.
4. **Explore & Trigger Adaptation**:
   - Inspect topic mastery colors and confirm/remove `needs_review` links in **Knowledge Graph**.
   - Generate style-adapted lessons & flashcards in **AI Study Tutor**.
   - Take a quiz in **Quizzes & Exams** (deliberately missing a topic triggers **Agents 7 → 8 → 9 → 10** and inserts remedial tasks into **Study Planner**).
   - Preview future memory decay safely using **Non-Destructive Demo Simulator** on **Dashboard**, and inspect step-by-step runs in **Agent Trace**.
5. **Test Linked Guardian View**: Sign out, choose **Create Brand-New Account** → **Parent / Teacher**, and paste the student's **Parent Link Code** to inspect the read-only progress portal.

*(Optional: Seeded demo personas **Aarav**, **Priya**, **Rohan**, and **Kavita (Parent)** are also available via quick demo buttons on the login screen.)*

---

## Verification Commands

**Run Backend Test Suite:**
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

**Typecheck & Build Frontend:**
```powershell
cd frontend
npx tsc -b --noEmit
npm run build
```
