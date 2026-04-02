"""Pydantic models for the data catalog."""

from typing import Any

from pydantic import BaseModel, field_validator


class ColumnEntry(BaseModel):
    name: str
    type: str
    description: str
    business_context: str | None = None
    disambiguation: str | None = None
    common_mistake: str | None = None
    values: list[str] | None = None

    @field_validator("values", mode="before")
    @classmethod
    def coerce_values(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        return [str(x) for x in v]


class QualityMetadata(BaseModel):
    status: str  # healthy, degraded, stale
    known_issues: list[dict[str, Any]] = []
    null_rates: dict[str, float] = {}

    @field_validator("known_issues", mode="before")
    @classmethod
    def coerce_known_issues(cls, v: Any) -> list[dict[str, Any]]:
        """Accept both strings and dicts in known_issues."""
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"issue": item, "severity": "medium", "workaround": None})
            elif isinstance(item, dict):
                result.append(item)
        return result


class Relationship(BaseModel):
    column: str
    references: str
    type: str = "many_to_one"


class SampleQuery(BaseModel):
    question: str
    sql: str
    notes: str | None = None


class TableCatalogEntry(BaseModel):
    table: str  # schema.table_name
    description: str
    owner: str | None = None
    primary_key: str | None = None
    row_count_approx: int | None = None
    refresh_cadence: str | None = None
    last_refreshed: str | None = None
    quality: QualityMetadata = QualityMetadata(status="healthy")
    relationships: list[Relationship] = []
    columns: list[ColumnEntry] = []
    sample_queries: list[SampleQuery] = []
    deprecated: bool = False
    deprecation_note: str | None = None

    @property
    def schema_name(self) -> str:
        return self.table.split(".")[0]

    @property
    def table_name(self) -> str:
        return self.table.split(".")[1]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> ColumnEntry | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def to_schema_text(self) -> str:
        """Return a text representation for embedding/prompting."""
        lines = [f"Table: {self.table}", f"Description: {self.description}"]
        if self.refresh_cadence:
            lines.append(f"Refresh: {self.refresh_cadence}")
        if self.quality.status != "healthy":
            lines.append(f"Quality: {self.quality.status}")
        lines.append("Columns:")
        for c in self.columns:
            col_line = f"  - {c.name} ({c.type}): {c.description}"
            if c.business_context:
                col_line += f" | Context: {c.business_context}"
            lines.append(col_line)
        return "\n".join(lines)


class MetricDefinition(BaseModel):
    id: str
    name: str
    description: str
    table: str | None = None
    tables: list[str] | None = None
    calculation: str
    filters: str | None = None
    grain: str | None = None
    refresh_cadence: str | None = None
    owner: str | None = None
    typical_users: list[str] = []
    known_issues: list[str] = []


class Metric(BaseModel):
    name: str
    disambiguation_required: bool = False
    prompt_to_user: str | None = None
    definitions: list[MetricDefinition] = []


class SchemaCatalogEntry(BaseModel):
    model_config = {"populate_by_name": True}

    schema_name: str = ""
    description: str = ""
    owner: str | None = None
    refresh_cadence: str | None = None
    notes: list[str] = []

    @field_validator("schema_name", mode="before")
    @classmethod
    def accept_schema_key(cls, v: Any) -> str:
        return v or ""
