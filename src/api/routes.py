"""FastAPI route handlers."""

import uuid
from fastapi import APIRouter

from src.api.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    TableSummary,
)

router = APIRouter()

# In-memory session store: session_id -> conversation_history
_sessions: dict[str, list[dict]] = {}

# These are set during app startup
_graph = None
_catalog = None


def set_dependencies(graph, catalog):
    global _graph, _catalog
    _graph = graph
    _catalog = catalog


@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Execute a natural language query against the warehouse."""
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = []

    # Build agent input
    agent_input = {
        "user_question": req.question,
        "conversation_history": _sessions[session_id],
        "disambiguation_choice": req.disambiguation_choice,
    }

    # Run the graph
    result = _graph.invoke(agent_input)

    # Store in session
    _sessions[session_id].append({"role": "user", "content": req.question})

    status = result.get("status", "error")

    if status == "needs_input":
        return QueryResponse(
            status="needs_clarification",
            clarification_prompt=result.get("final_response", ""),
            clarification_options=result.get("disambiguation_options", []),
            session_id=session_id,
        )

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
        from src.warehouse.connection import get_connection
        conn = get_connection()
        conn.execute("SELECT 1")
        warehouse_ok = True
    except Exception:
        pass

    catalog_ok = _catalog is not None and len(_catalog.tables) > 0

    return HealthResponse(
        status="ok" if warehouse_ok and catalog_ok else "degraded",
        warehouse_connected=warehouse_ok,
        catalog_loaded=catalog_ok,
        tables_count=len(_catalog.tables) if _catalog else 0,
    )
