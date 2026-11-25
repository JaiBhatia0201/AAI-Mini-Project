"""Unit tests for out-of-syllabus detection and in-memory FAISS web chunk ranking."""

from types import SimpleNamespace

from app.services.web_search import (
    is_question_out_of_syllabus,
    rank_web_chunks_with_faiss,
)


def test_rank_web_chunks_with_faiss_orders_best_matching_paragraph_first():
    chunks = [
        {
            "title": "Baking Sourdough Bread",
            "url": "https://example.com/bread",
            "text": "Sourdough fermentation uses wild yeast and lactic acid bacteria to leaven flour dough.",
            "provider": "wikipedia",
        },
        {
            "title": "Docker (software)",
            "url": "https://en.wikipedia.org/wiki/Docker_(software)",
            "text": "Docker is a platform that uses OS-level virtualization to deliver software in isolated packages called containers.",
            "provider": "wikipedia",
        },
        {
            "title": "Containerization",
            "url": "https://en.wikipedia.org/wiki/Containerization_(computing)",
            "text": "Containers share the host operating system kernel and isolate application dependencies cleanly.",
            "provider": "duckduckgo",
        },
    ]

    hits, mode = rank_web_chunks_with_faiss(
        query="How does Docker containerization isolate software?",
        chunks=chunks,
        top_k=2,
        embedder=None,
    )
    assert mode in {"web_faiss_embeddings", "web_tfidf_faiss"}
    assert len(hits) == 2
    assert "Docker" in hits[0].title or "Container" in hits[0].title
    assert hits[0].score >= hits[1].score


def test_is_question_out_of_syllabus_distinguishes_in_vs_out_of_syllabus():
    topics = [
        SimpleNamespace(
            title="Normalization & Functional Dependencies",
            subject="DBMS",
            unit="Unit 3",
            subtopics_json='["BCNF", "3NF", "Attribute Closure"]',
            raw_excerpt="Functional dependencies and BCNF decomposition.",
        ),
        SimpleNamespace(
            title="Deadlocks & Concurrency",
            subject="Operating Systems",
            unit="Unit 2",
            subtopics_json='["Banker Algorithm", "Mutual Exclusion"]',
            raw_excerpt="Coffman conditions and deadlock avoidance.",
        ),
    ]

    # Clearly outside syllabus + low FAISS score -> True
    low_hits = [SimpleNamespace(score=0.12, retrieval_mode="lexical_tfidf_fallback")]
    assert is_question_out_of_syllabus("What is Quantum Computing and qubits?", topics, low_hits) is True

    # Generic follow-up stays inside syllabus -> False
    assert is_question_out_of_syllabus("Give me a concrete example step by step", topics, low_hits) is False

    # Question mentioning syllabus topic stays inside syllabus -> False
    assert is_question_out_of_syllabus("How does BCNF differ from 3NF?", topics, low_hits) is False
