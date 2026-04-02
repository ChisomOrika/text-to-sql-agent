"""Build and query a vector index over catalog entries for schema retrieval.

Uses sentence-transformers (local) instead of Claude embeddings. Catalog retrieval
runs on every query — using Claude embeddings here would double API costs and add
200ms+ latency per query. Local embeddings are fast (~5ms) and good enough for
matching questions to table descriptions.
"""

import os
import pickle
from pathlib import Path

import numpy as np

from config.settings import settings
from src.catalog.loader import CatalogLoader
from src.catalog.models import TableCatalogEntry


class CatalogIndex:
    """Lightweight vector index over catalog table descriptions."""

    def __init__(self, catalog: CatalogLoader | None = None):
        self.catalog = catalog
        self._embeddings: np.ndarray | None = None
        self._table_keys: list[str] = []
        self._texts: list[str] = []
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    def build(self, catalog: CatalogLoader | None = None):
        """Build the vector index from catalog entries."""
        cat = catalog or self.catalog
        if cat is None:
            raise ValueError("No catalog provided")
        self.catalog = cat

        texts = []
        keys = []
        for table_name, entry in cat.tables.items():
            text = entry.to_schema_text()
            # Also include sample queries for richer matching
            for sq in entry.sample_queries:
                text += f"\nSample Q: {sq.question}"
            texts.append(text)
            keys.append(table_name)

        model = self._get_model()
        # Embeddings are normalized so dot product = cosine similarity but faster (no per-query normalization).
        self._embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        self._table_keys = keys
        self._texts = texts

    def save(self, path: str | None = None):
        """Save index to disk."""
        save_dir = Path(path or os.path.join(settings.catalog_dir, ".index"))
        save_dir.mkdir(parents=True, exist_ok=True)
        np.save(save_dir / "embeddings.npy", self._embeddings)
        with open(save_dir / "metadata.pkl", "wb") as f:
            pickle.dump({"keys": self._table_keys, "texts": self._texts}, f)

    def load(self, path: str | None = None):
        """Load index from disk."""
        load_dir = Path(path or os.path.join(settings.catalog_dir, ".index"))
        self._embeddings = np.load(load_dir / "embeddings.npy")
        with open(load_dir / "metadata.pkl", "rb") as f:
            meta = pickle.load(f)
        self._table_keys = meta["keys"]
        self._texts = meta["texts"]

    def search(self, query: str, top_k: int | None = None) -> list[tuple[str, float]]:
        """Return top-k (table_name, score) pairs for a query."""
        if self._embeddings is None:
            raise RuntimeError("Index not built or loaded")
        k = top_k or settings.catalog_top_k
        model = self._get_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        scores = (q_emb @ self._embeddings.T).flatten()
        top_indices = np.argsort(scores)[::-1][:k]
        return [(self._table_keys[i], float(scores[i])) for i in top_indices]
