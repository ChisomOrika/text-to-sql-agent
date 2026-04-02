"""FastAPI route handlers."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from src.api.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    TableSummary,
)
from src.auth import verify_api_key
from src.guardrails import sanitize_input
from src.logging_config import logger

router = APIRouter()

# In-memory session store: session_id -> conversation_history
_sessions: dict[str, list[dict]] = {}

# These are set during app startup
_graph = None
_catalog = None
_cache = None


def set_dependencies(graph, catalog, cache=None):
    global _graph, _catalog, _cache
    _graph = graph
    _catalog = catalog
    _cache = cache


@router.post("/api/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    user: dict[str, Any] = Depends(verify_api_key),
) -> QueryResponse:
    """Execute a natural language query against the warehouse."""
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = []

    # Sanitize input for prompt injection
    cleaned_question, injection_warnings = sanitize_input(req.question)
    if injection_warnings:
        logger.warning(
            f"Injection patterns stripped from query by user={user.get('user')}",
            extra={"extra_data": {"warnings": injection_warnings}},
        )

    # Check semantic cache first (skip if disambiguation choice is provided)
    if _cache and not req.disambiguation_choice:
        cached = _cache.get(cleaned_question)
        if cached is not None:
            logger.info(
                "Cache hit",
                extra={"extra_data": {"event": "cache_hit", "question": cleaned_question[:100]}},
            )
            return QueryResponse(
                status="completed",
                answer=cached.get("final_response"),
                sql=cached.get("generated_sql"),
                results=cached.get("query_results"),
                row_count=cached.get("row_count", 0),
                warnings=cached.get("warnings", []),
                session_id=session_id,
                cached=True,
            )

    # Build agent input
    agent_input = {
        "user_question": cleaned_question,
        "conversation_history": _sessions[session_id],
        "disambiguation_choice": req.disambiguation_choice,
    }

    # Run the graph
    result = _graph.invoke(agent_input)

    # Store in session
    _sessions[session_id].append({"role": "user", "content": cleaned_question})

    status = result.get("status", "error")

    if status == "needs_input":
        return QueryResponse(
            status="needs_clarification",
            clarification_prompt=result.get("final_response", ""),
            clarification_options=result.get("disambiguation_options", []),
            session_id=session_id,
        )

    # Cache the result
    if _cache:
        _cache.put(cleaned_question, result)

    # Store assistant response
    _sessions[session_id].append(
        {"role": "assistant", "content": result.get("final_response", "")}
    )

    return QueryResponse(
        status="completed" if status == "completed" else "error",
        answer=result.get("final_response"),
        sql=result.get("generated_sql"),
        results=result.get("query_results"),
        row_count=result.get("row_count", 0),
        warnings=result.get("warnings", []),
        session_id=session_id,
    )


@router.get("/api/catalog/tables", response_model=list[TableSummary])
async def list_tables() -> list[TableSummary]:
    """List all tables in the catalog with quality status."""
    if _catalog is None:
        return []
    return [
        TableSummary(
            table=entry.table,
            description=entry.description,
            quality_status=entry.quality.status,
            refresh_cadence=entry.refresh_cadence,
            last_refreshed=entry.last_refreshed,
            column_count=len(entry.columns),
            deprecated=entry.deprecated,
        )
        for entry in _catalog.tables.values()
    ]


@router.get("/api/catalog/table/{schema_name}/{table_name}")
async def get_table(schema_name: str, table_name: str):
    """Get full catalog entry for a table."""
    if _catalog is None:
        return {"error": "Catalog not loaded"}
    full_name = f"{schema_name}.{table_name}"
    entry = _catalog.get_table(full_name)
    if not entry:
        return {"error": f"Table {full_name} not found"}
    return entry.model_dump()


@router.get("/api/catalog/metrics")
async def list_metrics():
    """List all metric definitions."""
    if _catalog is None:
        return []
    return [m.model_dump() for m in _catalog.metrics]


@router.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check."""
    warehouse_ok = False
    try:
        from src.warehouse.connection import execute_query
        execute_query("SELECT 1")
        warehouse_ok = True
    except Exception:
        pass

    catalog_ok = _catalog is not None and len(_catalog.tables) > 0
    cache_stats = _cache.stats() if _cache else {}

    return HealthResponse(
        status="ok" if warehouse_ok and catalog_ok else "degraded",
        warehouse_connected=warehouse_ok,
        catalog_loaded=catalog_ok,
        tables_count=len(_catalog.tables) if _catalog else 0,
        cache_stats=cache_stats,
    )
