"""Retrieve relevant catalog entries for a natural language question."""

from src.catalog.index import CatalogIndex
from src.catalog.loader import CatalogLoader
from src.catalog.models import Metric, TableCatalogEntry


# Keyword matching is deterministic and free — we don't want the LLM deciding
# whether "revenue" means revenue; that's exactly the silent decision that causes wrong answers.
METRIC_KEYWORDS = {
    "revenue": "revenue",
    "sales": "revenue",
    "income": "revenue",
    "utilization": "utilization_rate",
    "utilisation": "utilization_rate",
    "nps": "client_satisfaction",
    "net promoter": "client_satisfaction",
    "csat": "client_satisfaction",
    "satisfaction": "client_satisfaction",
}


class CatalogRetriever:
    """Retrieves relevant catalog entries given a natural language question."""

    def __init__(self, catalog: CatalogLoader, index: CatalogIndex):
        self.catalog = catalog
        self.index = index

    def retrieve(
        self, question: str, top_k: int | None = None
    ) -> tuple[list[TableCatalogEntry], list[Metric]]:
        """Return relevant tables and any matching metric definitions."""
        # Vector search for relevant tables
        results = self.index.search(question, top_k=top_k)
        tables = []
        for table_name, score in results:
            entry = self.catalog.get_table(table_name)
            # Deprecated tables should never reach the SQL generation step.
            if entry and not entry.deprecated:
                tables.append(entry)

        # Keyword match for metrics
        metrics = self._match_metrics(question)

        return tables, metrics

    def _match_metrics(self, question: str) -> list[Metric]:
        """Check if the question references any known metrics."""
        q_lower = question.lower()
        matched = set()
        for keyword, metric_name in METRIC_KEYWORDS.items():
            if keyword in q_lower:
                matched.add(metric_name)

        metrics = []
        for name in matched:
            m = self.catalog.get_metric(name)
            if m:
                metrics.append(m)
        return metrics
