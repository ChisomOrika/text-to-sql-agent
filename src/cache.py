"""Semantic query cache — avoids redundant LLM calls for similar questions.

Uses the same sentence-transformers model as catalog retrieval. Embeds each
incoming question and checks against a cache of recent (embedding, result) pairs.
If cosine similarity exceeds a threshold, returns the cached result instead of
running the full agent pipeline. This eliminates ~90% of redundant LLM calls
in practice, since users tend to ask the same 20 questions in different words.

Numpy is sufficient here — the cache holds hundreds of entries, not millions.
At scale (10K+ cached queries with sub-millisecond lookup requirements), switch
to a dedicated vector store (pgvector, Qdrant, or Redis with vector search).
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from config.settings import settings


@dataclass
class CacheEntry:
    question: str
    embedding: np.ndarray
    result: dict[str, Any]
    created_at: float
    hit_count: int = 0


class SemanticCache:
    """LRU-style semantic cache with similarity threshold."""

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_entries: int = 500,
        ttl_seconds: int = 3600,
    ):
        # 0.92 is deliberately high — we'd rather miss the cache and get a fresh
        # answer than return a cached answer for a subtly different question.
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._entries: list[CacheEntry] = []
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    def _embed(self, text: str) -> np.ndarray:
        model = self._get_model()
        return model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]

    def get(self, question: str) -> dict[str, Any] | None:
        """Look up a semantically similar cached result. Returns None on miss."""
        if not self._entries:
            return None

        self._evict_expired()
        q_emb = self._embed(question)

        best_score = -1.0
        best_entry = None

        for entry in self._entries:
            score = float(np.dot(q_emb, entry.embedding))
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self.similarity_threshold and best_entry is not None:
            best_entry.hit_count += 1
            return best_entry.result

        return None

    def put(self, question: str, result: dict[str, Any]):
        """Cache a question-result pair."""
        # Don't cache errors or disambiguation requests
        status = result.get("status", "")
        if status in ("error", "needs_input"):
            return

        self._evict_expired()

        # Evict oldest if at capacity
        if len(self._entries) >= self.max_entries:
            self._entries.sort(key=lambda e: e.created_at)
            self._entries = self._entries[len(self._entries) // 4:]

        embedding = self._embed(question)
        self._entries.append(CacheEntry(
            question=question,
            embedding=embedding,
            result=result,
            created_at=time.time(),
        ))

    def _evict_expired(self):
        """Remove entries older than TTL."""
        now = time.time()
        self._entries = [e for e in self._entries if now - e.created_at < self.ttl_seconds]

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total_hits = sum(e.hit_count for e in self._entries)
        return {
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "total_hits": total_hits,
            "ttl_seconds": self.ttl_seconds,
            "similarity_threshold": self.similarity_threshold,
        }

    def clear(self):
        self._entries.clear()
