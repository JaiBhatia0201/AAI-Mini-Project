# GATE CSE Flagship Adaptive Dataset (PS-03)

Self-contained benchmark dataset for **PS-03: Adaptive Exam Prep Agent**.

## Contents
- `sample_syllabi/gate_cse_syllabus.pdf` — Text-selectable multi-page GATE CSE syllabus PDF covering 8 subjects (4 CS Core + 4 Engineering Mathematics) for testing live Agent 2 ingestion.
- `syllabus_graph.json` — 40 topics, 160 subtopics, verbatim `raw_excerpt` descriptions, difficulty/weightage metadata, and verified acyclic prerequisite edges.
- `learning_resources.json` — 160 curated multi-modal resources (`video`, `textbook`, `notes`, `flashcard`) tagged with `source_origin="curated_dataset_note"`.
- `question_bank.json` — 240 GATE-style questions (2 Easy, 2 Medium, 2 Hard per topic) with options, correct answers, explanations, and `expected_time_sec`.
- `student_profiles.json` — 4 synthetic student personas (led by `stu_aarav`, 90 days remaining, 4 hrs/day, strong DBMS/OS, weak CN/TOC) plus 1 read-only linked `parent_teacher` demo account (`link_code="GATE-DEMO-2026"`).
- `assessment_attempts.json` & `mastery_history.json` — Multi-week attempt histories scaled to GATE CSE (`max_score=100`), mastery snapshots, Ebbinghaus retention trajectories, and sample adaptive re-planning logs.
