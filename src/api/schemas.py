"""Pydantic request/response models for the API."""

from typing import Any
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    disambiguation_choice: str | None = None


class QueryResponse(BaseModel):
    status: str  # completed, needs_clarification, error
    answer: str | None = None
    sql: str | None = None
    results: list[dict[str, Any]] | None = None
    row_count: int = 0
    warnings: list[str] = []
    clarification_prompt: str | None = None
    clarification_options: list[dict[str, str]] | None = None
    session_id: str = ""
    cached: bool = False


class TableSummary(BaseModel):
    table: str
    description: str
    quality_status: str
    refresh_cadence: str | None = None
    last_refreshed: str | None = None
    column_count: int = 0
    deprecated: bool = False


class HealthResponse(BaseModel):
    status: str
    warehouse_connected: bool
    catalog_loaded: bool
    tables_count: int
    cache_stats: dict[str, Any] = {}
