"""Tests for modular per-syllabus retrieval (online FAISS and offline TF-IDF fallback)."""

from pathlib import Path
import numpy as np

from app.services.retrieval import (
    APIFaissRetrievalProvider,
    LocalTfidfRetrievalProvider,
    RetrievalDocument,
)


def test_small_corpus_offline_tfidf_bypasses_svd_cleanly(tmp_path: Path) -> None:
    """Review Focus #5: 3-topic custom PDF (<32 docs) skips SVD and returns lexical TF-IDF hits."""
    provider = LocalTfidfRetrievalProvider(index_dir=tmp_path)
    docs_s1 = [
        RetrievalDocument(
            doc_id="d1",
            syllabus_id="syl_custom_1",
            topic_id="t1",
            title="TCP Congestion Control",
            text="Slow start, congestion window cwnd, AIMD, and fast retransmit thresholds.",
            source_origin="extracted_pdf_excerpt",
        ),
        RetrievalDocument(
            doc_id="d2",
            syllabus_id="syl_custom_1",
            topic_id="t2",
            title="Relational Normalization",
            text="Third normal form 3NF and BCNF dependency preservation.",
            source_origin="extracted_pdf_excerpt",
        ),
        RetrievalDocument(
            doc_id="d3",
            syllabus_id="syl_custom_1",
            topic_id="t3",
            title="Process Deadlocks",
            text="Coffman conditions, banker algorithm, resource allocation graphs.",
            source_origin="extracted_pdf_excerpt",
        ),
    ]
    docs_s2 = [
        RetrievalDocument(
            doc_id="other1",
            syllabus_id="syl_other_2",
            topic_id="o1",
            title="TCP Other Syllabus",
            text="This unrelated syllabus mentions TCP congestion window too.",
            source_origin="extracted_pdf_excerpt",
        )
    ]

    mode = provider.index_syllabus_documents("syl_custom_1", docs_s1 + docs_s2)
    provider.index_syllabus_documents("syl_other_2", docs_s2)
    assert mode == "lexical_tfidf_fallback"

    hits = provider.search("syl_custom_1", "congestion window fast retransmit", top_k=2)
    assert len(hits) == 2
    assert hits[0].doc_id == "d1"
    assert hits[0].retrieval_mode == "lexical_tfidf_fallback"
    assert all(h.syllabus_id == "syl_custom_1" for h in hits)


def test_large_corpus_offline_enables_svd_and_faiss(tmp_path: Path) -> None:
    """When corpus >= 32 docs and >= 32 features, SVD + per-syllabus FAISS activates cleanly."""
    provider = LocalTfidfRetrievalProvider(index_dir=tmp_path)
    vocab_topics = [
        "database relational algebra btree normalization transaction isolation locking",
        "operating systems process thread scheduling semaphore mutex deadlock paging",
        "computer networks ethernet subnetting cidr routing ospf bgp tcp udp",
        "automata finite state machine regular grammar pumping lemma turing machine",
    ]
    docs = [
        RetrievalDocument(
            doc_id=f"doc_{i}",
            syllabus_id="syl_large",
            topic_id=f"topic_{i}",
            title=f"Module {i} " + vocab_topics[i % len(vocab_topics)].split()[0],
            text=f"{vocab_topics[i % len(vocab_topics)]} concept_token_{i} detail_token_{i}",
        )
        for i in range(40)
    ]
    mode = provider.index_syllabus_documents("syl_large", docs)
    assert mode == "svd_tfidf_faiss_fallback"
    hits = provider.search("syl_large", "deadlock semaphore scheduling", top_k=3)
    assert len(hits) == 3
    assert hits[0].retrieval_mode == "svd_tfidf_faiss_fallback"


def test_api_faiss_provider_isolates_per_syllabus(tmp_path: Path) -> None:
    """Online FAISS provider builds dedicated per-syllabus indices using mock embedder."""

    class _DummyEmbedder:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            vecs = []
            for t in texts:
                low = t.lower()
                vecs.append([1.0 if "graph" in low else 0.1, 1.0 if "sql" in low else 0.1, 0.2, 0.3])
            return vecs

        def embed_query(self, text: str) -> list[float]:
            low = text.lower()
            return [1.0 if "graph" in low else 0.0, 1.0 if "sql" in low else 0.0, 0.1, 0.1]

    provider = APIFaissRetrievalProvider("openai", index_dir=tmp_path, embedder=_DummyEmbedder())
    docs_a = [
        RetrievalDocument("a1", "syl_a", "ta1", "Graph Traversals", "BFS and DFS graph traversal"),
        RetrievalDocument("a2", "syl_a", "ta2", "SQL Joins", "Inner and outer SQL joins"),
    ]
    docs_b = [
        RetrievalDocument("b1", "syl_b", "tb1", "Hidden Graph", "Graph from another syllabus"),
    ]
    assert provider.index_syllabus_documents("syl_a", docs_a) == "api_embeddings_faiss"
    assert provider.index_syllabus_documents("syl_b", docs_b) == "api_embeddings_faiss"
    assert (tmp_path / "syllabus_syl_a.index").exists()
    assert (tmp_path / "syllabus_syl_b.index").exists()

    hits_a = provider.search("syl_a", "graph traversal", top_k=2)
    assert hits_a[0].doc_id == "a1"
    assert hits_a[0].retrieval_mode == "api_embeddings_faiss"
    assert all(h.syllabus_id == "syl_a" for h in hits_a)
