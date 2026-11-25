"""Live internet search (Wikipedia + DuckDuckGo) with in-memory FAISS vector re-ranking."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable
from urllib.parse import quote

import faiss
import httpx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import get_settings

_USER_AGENT = "AdaptiveExamPrepTutor/1.0 (Academic Study Assistant; https://localhost)"

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "define", "describe",
    "did", "do", "does", "explain", "for", "from", "give", "how", "i", "in", "is", "it",
    "me", "my", "of", "on", "or", "please", "tell", "that", "the", "their", "this", "to",
    "what", "when", "where", "which", "who", "why", "with", "would", "you", "your", "about",
    "between", "compare", "difference", "example", "examples", "simple", "terms", "work",
    "works", "working", "mean", "means", "meaning", "used", "use", "using",
}

_GENERIC_FOLLOWUP_PHRASES = (
    "this topic",
    "this concept",
    "above topic",
    "step by step",
    "give me an example",
    "concrete example",
    "real world example",
    "real-world example",
    "explain simply",
    "summarize this",
    "why this concept matters",
    "explain why this",
    "key takeaways",
    "prerequisite",
)


@dataclass
class WebSourceHit:
    """Ranked live web chunk returned by in-memory FAISS similarity search."""

    title: str
    url: str
    snippet: str
    score: float
    provider: str = "wikipedia"


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return arr / norms


def _meaningful_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9+#.-]{2,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and not t.isdigit()}


def _split_into_chunks(text: str, max_chars: int = 420) -> list[str]:
    """Split a web article extract into clean, self-contained paragraphs for FAISS ranking."""
    raw_paras = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) >= 50]
    chunks: list[str] = []
    for para in raw_paras:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            buf = ""
            for sent in sentences:
                if len(buf) + len(sent) + 1 <= max_chars:
                    buf = f"{buf} {sent}".strip()
                else:
                    if len(buf) >= 50:
                        chunks.append(buf)
                    buf = sent
            if len(buf) >= 50:
                chunks.append(buf)
    return chunks[:8]


def _fetch_wikipedia_chunks(query: str, max_pages: int = 4, timeout: float = 8.0) -> list[dict[str, str]]:
    """Query Wikipedia's live search + plain-text extract API and return paragraph chunks."""
    headers = {"User-Agent": _USER_AGENT}
    chunks: list[dict[str, str]] = []
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            search_resp = client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_pages,
                    "format": "json",
                },
            )
            if search_resp.status_code != 200:
                return []
            search_items = search_resp.json().get("query", {}).get("search", [])
            if not search_items:
                return []

            titles = [str(item["title"]) for item in search_items if item.get("title")]
            if not titles:
                return []

            extract_resp = client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts",
                    "explaintext": "true",
                    "exintro": "true",
                    "exchars": "1800",
                    "titles": "|".join(titles),
                    "format": "json",
                },
            )
            if extract_resp.status_code != 200:
                return []

            pages = extract_resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                title = str(page.get("title") or "").strip()
                extract = str(page.get("extract") or "").strip()
                if not title or not extract:
                    continue
                url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                for para in _split_into_chunks(extract):
                    chunks.append(
                        {
                            "title": title,
                            "url": url,
                            "text": para,
                            "provider": "wikipedia",
                        }
                    )
    except Exception:  # noqa: BLE001
        return []
    return chunks


def _fetch_duckduckgo_chunks(query: str, max_items: int = 4, timeout: float = 6.0) -> list[dict[str, str]]:
    """Query DuckDuckGo's Instant Answer JSON API for concise web summaries."""
    headers = {"User-Agent": _USER_AGENT}
    chunks: list[dict[str, str]] = []
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1",
                },
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            abstract = str(data.get("AbstractText") or "").strip()
            abstract_url = str(data.get("AbstractURL") or "").strip()
            heading = str(data.get("Heading") or query).strip()
            if abstract and abstract_url:
                chunks.append(
                    {
                        "title": heading,
                        "url": abstract_url,
                        "text": abstract[:450],
                        "provider": "duckduckgo",
                    }
                )
            for rel in data.get("RelatedTopics") or []:
                if len(chunks) >= max_items:
                    break
                if isinstance(rel, dict) and rel.get("Text") and rel.get("FirstURL"):
                    chunks.append(
                        {
                            "title": str(rel.get("Text"))[:80],
                            "url": str(rel.get("FirstURL")),
                            "text": str(rel.get("Text"))[:420],
                            "provider": "duckduckgo",
                        }
                    )
    except Exception:  # noqa: BLE001
        return []
    return chunks


def rank_web_chunks_with_faiss(
    query: str,
    chunks: list[dict[str, str]],
    top_k: int = 4,
    embedder: Any | None = None,
) -> tuple[list[WebSourceHit], str]:
    """Rank live web paragraphs in memory using FAISS inner-product cosine similarity."""
    if not chunks or not query.strip():
        return [], "none"

    texts = [f"{c['title']}\n{c['text']}" for c in chunks]
    mode = "web_tfidf_faiss"
    vectors: np.ndarray | None = None
    q_vec: np.ndarray | None = None

    # Prefer configured API embeddings + FAISS when available; fall back cleanly to TF-IDF + FAISS
    settings = get_settings()
    emb_provider = settings.effective_embedding_provider
    active_embedder = embedder
    if active_embedder is None and emb_provider in {"gemini", "openai"}:
        try:
            if emb_provider == "gemini":
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                active_embedder = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=settings.gemini_api_key,
                )
            elif emb_provider == "openai":
                from langchain_openai import OpenAIEmbeddings

                active_embedder = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=settings.openai_api_key,
                )
        except Exception:  # noqa: BLE001
            active_embedder = None

    if active_embedder is not None:
        try:
            doc_embs = active_embedder.embed_documents(texts)
            query_emb = active_embedder.embed_query(query)
            vectors = _normalize_rows(np.array(doc_embs, dtype=np.float32))
            q_vec = _normalize_rows(np.array([query_emb], dtype=np.float32))
            mode = "web_faiss_embeddings"
        except Exception:  # noqa: BLE001
            vectors = None
            q_vec = None

    if vectors is None or q_vec is None:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=2048)
        try:
            mat = vectorizer.fit_transform(texts)
        except ValueError:
            vectorizer = TfidfVectorizer(max_features=2048)
            mat = vectorizer.fit_transform(texts)
        vectors = _normalize_rows(mat.toarray())
        q_vec = _normalize_rows(vectorizer.transform([query]).toarray())
        mode = "web_tfidf_faiss"

    dim = int(vectors.shape[1])
    if dim == 0:
        return [], mode

    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    search_k = min(len(chunks), max(top_k * 2, top_k))
    scores, indices = index.search(q_vec, search_k)

    hits: list[WebSourceHit] = []
    seen_urls: set[str] = set()
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        item = chunks[int(idx)]
        url = item["url"]
        # Prefer diverse top sources first, allowing a second chunk only if few unique URLs exist
        if url in seen_urls and len(seen_urls) >= 2:
            continue
        seen_urls.add(url)
        hits.append(
            WebSourceHit(
                title=item["title"],
                url=url,
                snippet=item["text"][:380],
                score=round(float(score), 4),
                provider=item.get("provider", "web"),
            )
        )
        if len(hits) >= top_k:
            break

    return hits, mode


def search_web_with_faiss(query: str, top_k: int = 4) -> tuple[list[WebSourceHit], str]:
    """Fetch live internet snippets (Wikipedia + DuckDuckGo) and rank them with in-memory FAISS."""
    cleaned = query.strip()
    if not cleaned:
        return [], "none"

    chunks = _fetch_wikipedia_chunks(cleaned, max_pages=4)
    chunks.extend(_fetch_duckduckgo_chunks(cleaned, max_items=3))
    if not chunks:
        return [], "web_unavailable"

    return rank_web_chunks_with_faiss(cleaned, chunks, top_k=top_k)


def is_question_out_of_syllabus(
    question: str,
    syllabus_topics: Iterable[Any],
    question_only_hits: Iterable[Any],
    selected_topic: Any | None = None,
) -> bool:
    """Decide deterministically whether a student's question falls outside their active syllabus."""
    cleaned = (question or "").strip()
    if len(cleaned) < 8:
        return False

    lower_q = cleaned.lower()
    if any(phrase in lower_q for phrase in _GENERIC_FOLLOWUP_PHRASES):
        return False

    q_tokens = _meaningful_tokens(cleaned)
    if not q_tokens:
        return False

    # Build vocabulary of active syllabus titles, subjects, subtopics, and selected topic excerpt
    syllabus_vocab: set[str] = set()
    for t in syllabus_topics:
        syllabus_vocab.update(_meaningful_tokens(getattr(t, "title", "")))
        syllabus_vocab.update(_meaningful_tokens(getattr(t, "subject", "")))
        syllabus_vocab.update(_meaningful_tokens(getattr(t, "unit", "")))
        raw_sub = getattr(t, "subtopics_json", "") or ""
        syllabus_vocab.update(_meaningful_tokens(raw_sub))
    if selected_topic is not None:
        syllabus_vocab.update(_meaningful_tokens(getattr(selected_topic, "raw_excerpt", "")))

    overlap = q_tokens.intersection(syllabus_vocab)
    if overlap:
        return False

    # No direct syllabus vocabulary overlap — check FAISS / TF-IDF semantic similarity score
    hits = list(question_only_hits)
    if not hits:
        return True

    top_hit = hits[0]
    top_score = float(getattr(top_hit, "score", 0.0))
    mode = str(getattr(top_hit, "retrieval_mode", ""))
    if mode == "api_embeddings_faiss":
        return top_score < 0.62
    return top_score < 0.22
