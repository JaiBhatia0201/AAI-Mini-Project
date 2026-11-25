"""Modular per-syllabus retrieval: online API FAISS or honest offline TF-IDF/SVD fallback."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Protocol
import faiss
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_settings

SVD_DIM = 32
_EMBED_COOLDOWN_UNTIL: dict[tuple[str, str], float] = {}


@dataclass
class RetrievalDocument:
    """Indexable chunk bound strictly to one syllabus_id and topic_id."""

    doc_id: str
    syllabus_id: str
    topic_id: str
    title: str
    text: str
    source_origin: str = "curated_dataset_note"


@dataclass
class RetrievalHit:
    """Ranked search match annotated with retrieval_mode for honest provenance."""

    doc_id: str
    syllabus_id: str
    topic_id: str
    title: str
    text: str
    score: float
    source_origin: str
    retrieval_mode: str


class RetrievalProvider(Protocol):
    """Protocol decoupling search callers from online FAISS vs offline TF-IDF backends."""

    def has_index(self, syllabus_id: str) -> str | None:
        """Return active retrieval mode if an index already exists for syllabus_id, else None."""

    def index_syllabus_documents(
        self,
        syllabus_id: str,
        documents: list[RetrievalDocument],
    ) -> str:
        """Index documents for a single syllabus and return the active retrieval mode."""

    def search(
        self,
        syllabus_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        """Search documents strictly isolated within syllabus_id."""


def _safe_syllabus_slug(syllabus_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in syllabus_id)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return arr / norms


class LocalTfidfRetrievalProvider:
    """Honest offline lexical retrieval using TF-IDF (plus SVD+FAISS only when >=32 docs & features)."""

    def __init__(self, index_dir: Path | None = None, svd_dim: int = SVD_DIM) -> None:
        self.index_dir = index_dir or get_settings().faiss_index_path
        self.svd_dim = svd_dim
        self._stores: dict[str, dict[str, Any]] = {}

    def _meta_path(self, syllabus_id: str) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        return self.index_dir / f"local_corpus_{_safe_syllabus_slug(syllabus_id)}.json"

    def _faiss_path(self, syllabus_id: str) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        return self.index_dir / f"local_svd_{_safe_syllabus_slug(syllabus_id)}.index"

    def has_index(self, syllabus_id: str) -> str | None:
        if syllabus_id in self._stores and self._stores[syllabus_id].get("docs"):
            return str(self._stores[syllabus_id].get("mode", "lexical_tfidf_fallback"))
        if self._meta_path(syllabus_id).exists():
            return "svd_tfidf_faiss_fallback" if self._faiss_path(syllabus_id).exists() else "lexical_tfidf_fallback"
        return None

    def index_syllabus_documents(
        self,
        syllabus_id: str,
        documents: list[RetrievalDocument],
    ) -> str:
        scoped_docs = [d for d in documents if d.syllabus_id == syllabus_id and d.text.strip()]
        if not scoped_docs:
            self._stores[syllabus_id] = {"docs": [], "mode": "lexical_tfidf_fallback"}
            return "lexical_tfidf_fallback"

        corpus = [f"{d.title}\n{d.text}" for d in scoped_docs]
        vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
        except ValueError:
            # Occurs if corpus only contained stop words; fall back without stopword filter
            vectorizer = TfidfVectorizer(max_features=4096)
            tfidf_matrix = vectorizer.fit_transform(corpus)

        n_docs, n_features = tfidf_matrix.shape
        payload = [
            {
                "doc_id": d.doc_id,
                "syllabus_id": d.syllabus_id,
                "topic_id": d.topic_id,
                "title": d.title,
                "text": d.text,
                "source_origin": d.source_origin,
            }
            for d in scoped_docs
        ]
        self._meta_path(syllabus_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if n_docs >= self.svd_dim and n_features >= self.svd_dim:
            svd = TruncatedSVD(n_components=self.svd_dim, random_state=42)
            reduced = _normalize_rows(svd.fit_transform(tfidf_matrix))
            index = faiss.IndexFlatIP(self.svd_dim)
            index.add(reduced)
            faiss.write_index(index, str(self._faiss_path(syllabus_id)))
            mode = "svd_tfidf_faiss_fallback"
            self._stores[syllabus_id] = {
                "docs": scoped_docs,
                "vectorizer": vectorizer,
                "matrix": tfidf_matrix,
                "svd": svd,
                "faiss_index": index,
                "mode": mode,
            }
            return mode

        mode = "lexical_tfidf_fallback"
        self._stores[syllabus_id] = {
            "docs": scoped_docs,
            "vectorizer": vectorizer,
            "matrix": tfidf_matrix,
            "svd": None,
            "faiss_index": None,
            "mode": mode,
        }
        return mode

    def _ensure_loaded(self, syllabus_id: str) -> dict[str, Any] | None:
        if syllabus_id in self._stores:
            return self._stores[syllabus_id]
        meta_file = self._meta_path(syllabus_id)
        if not meta_file.exists():
            return None
        raw = json.loads(meta_file.read_text(encoding="utf-8"))
        docs = [RetrievalDocument(**item) for item in raw]
        self.index_syllabus_documents(syllabus_id, docs)
        return self._stores.get(syllabus_id)

    def search(
        self,
        syllabus_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        store = self._ensure_loaded(syllabus_id)
        if not store or not store["docs"] or not query.strip():
            return []

        docs: list[RetrievalDocument] = store["docs"]
        vectorizer: TfidfVectorizer = store["vectorizer"]
        q_vec = vectorizer.transform([query])
        k = min(max(1, top_k), len(docs))

        if store.get("svd") is not None and store.get("faiss_index") is not None:
            reduced_q = _normalize_rows(store["svd"].transform(q_vec))
            scores, indices = store["faiss_index"].search(reduced_q, k)
            hits: list[RetrievalHit] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(docs):
                    continue
                doc = docs[idx]
                hits.append(
                    RetrievalHit(
                        doc_id=doc.doc_id,
                        syllabus_id=doc.syllabus_id,
                        topic_id=doc.topic_id,
                        title=doc.title,
                        text=doc.text,
                        score=round(float(score), 4),
                        source_origin=doc.source_origin,
                        retrieval_mode=store["mode"],
                    )
                )
            return hits

        sims = cosine_similarity(q_vec, store["matrix"]).ravel()
        top_indices = np.argsort(-sims)[:k]
        return [
            RetrievalHit(
                doc_id=docs[i].doc_id,
                syllabus_id=docs[i].syllabus_id,
                topic_id=docs[i].topic_id,
                title=docs[i].title,
                text=docs[i].text,
                score=round(float(sims[i]), 4),
                source_origin=docs[i].source_origin,
                retrieval_mode=store["mode"],
            )
            for i in top_indices
        ]


class APIFaissRetrievalProvider:
    """Online embedding provider writing isolated per-syllabus FAISS indices with fallback."""

    def __init__(
        self,
        provider_name: str,
        index_dir: Path | None = None,
        embedder: Any | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.index_dir = index_dir or get_settings().faiss_index_path
        self._embedder = embedder
        self._fallback = LocalTfidfRetrievalProvider(index_dir=self.index_dir)
        self._cache: dict[str, tuple[faiss.IndexFlatIP, list[RetrievalDocument]]] = {}

    def _cooldown_key(self) -> tuple[str, str]:
        settings = get_settings()
        secret = settings.gemini_api_key if self.provider_name == "gemini" else settings.openai_api_key
        return (self.provider_name, hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12])

    def _in_cooldown(self) -> bool:
        if self._embedder is not None:
            return False
        return time.monotonic() < _EMBED_COOLDOWN_UNTIL.get(self._cooldown_key(), 0.0)

    def _trip_cooldown(self) -> None:
        if self._embedder is None:
            _EMBED_COOLDOWN_UNTIL[self._cooldown_key()] = time.monotonic() + 120.0

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        if self._in_cooldown():
            return None
        settings = get_settings()
        if self.provider_name == "gemini":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            self._embedder = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=settings.gemini_api_key,
            )
            return self._embedder
        if self.provider_name == "openai":
            from langchain_openai import OpenAIEmbeddings

            self._embedder = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.openai_api_key,
            )
            return self._embedder
        return None

    def _index_path(self, syllabus_id: str) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        return self.index_dir / f"syllabus_{_safe_syllabus_slug(syllabus_id)}.index"

    def _meta_path(self, syllabus_id: str) -> Path:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        return self.index_dir / f"syllabus_{_safe_syllabus_slug(syllabus_id)}_meta.json"

    def has_index(self, syllabus_id: str) -> str | None:
        if syllabus_id in self._cache:
            return "api_embeddings_faiss"
        if self._index_path(syllabus_id).exists() and self._meta_path(syllabus_id).exists():
            return "api_embeddings_faiss"
        return self._fallback.has_index(syllabus_id)

    def index_syllabus_documents(
        self,
        syllabus_id: str,
        documents: list[RetrievalDocument],
    ) -> str:
        scoped_docs = [d for d in documents if d.syllabus_id == syllabus_id and d.text.strip()]
        if not scoped_docs:
            return "api_embeddings_faiss"
        try:
            embedder = self._get_embedder()
            if embedder is None:
                return self._fallback.index_syllabus_documents(syllabus_id, scoped_docs)
            vectors = _normalize_rows(
                np.array(embedder.embed_documents([f"{d.title}\n{d.text}" for d in scoped_docs]))
            )
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(self._index_path(syllabus_id)))
            self._meta_path(syllabus_id).write_text(
                json.dumps([d.__dict__ for d in scoped_docs], indent=2),
                encoding="utf-8",
            )
            self._cache[syllabus_id] = (index, scoped_docs)
            return "api_embeddings_faiss"
        except Exception:  # noqa: BLE001
            self._trip_cooldown()
            return self._fallback.index_syllabus_documents(syllabus_id, scoped_docs)

    def search(
        self,
        syllabus_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        if not query.strip():
            return []
        try:
            embedder = self._get_embedder()
            if embedder is None:
                return self._fallback.search(syllabus_id, query, top_k=top_k)
            if syllabus_id not in self._cache:
                idx_file = self._index_path(syllabus_id)
                meta_file = self._meta_path(syllabus_id)
                if not idx_file.exists() or not meta_file.exists():
                    return self._fallback.search(syllabus_id, query, top_k=top_k)
                index = faiss.read_index(str(idx_file))
                docs = [RetrievalDocument(**d) for d in json.loads(meta_file.read_text(encoding="utf-8"))]
                self._cache[syllabus_id] = (index, docs)

            index, docs = self._cache[syllabus_id]
            q_vec = _normalize_rows(np.array([embedder.embed_query(query)]))
            k = min(max(1, top_k), len(docs))
            scores, indices = index.search(q_vec, k)
            return [
                RetrievalHit(
                    doc_id=docs[i].doc_id,
                    syllabus_id=docs[i].syllabus_id,
                    topic_id=docs[i].topic_id,
                    title=docs[i].title,
                    text=docs[i].text,
                    score=round(float(score), 4),
                    source_origin=docs[i].source_origin,
                    retrieval_mode="api_embeddings_faiss",
                )
                for score, i in zip(scores[0], indices[0])
                if 0 <= i < len(docs)
            ]
        except Exception:  # noqa: BLE001
            self._trip_cooldown()
            return self._fallback.search(syllabus_id, query, top_k=top_k)


def get_retrieval_provider(index_dir: Path | None = None) -> RetrievalProvider:
    """Build active modular retrieval provider based on configured embedding keys."""
    settings = get_settings()
    provider = settings.effective_embedding_provider
    if provider in {"gemini", "openai"}:
        return APIFaissRetrievalProvider(provider_name=provider, index_dir=index_dir)
    return LocalTfidfRetrievalProvider(index_dir=index_dir)
