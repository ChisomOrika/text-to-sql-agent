"""DuckDB connection manager with thread-safe connection pooling.

DuckDB is single-writer but supports concurrent readers. For a multi-user
web app, each request needs its own cursor. We use a single shared connection
with Python's threading lock to serialize writes, and create per-thread
cursors for reads. This handles the Streamlit/FastAPI concurrency model.

At higher scale (100+ concurrent users), switch to a client-server database
(Postgres + pgvector, ClickHouse) that handles connection pooling natively.
"""

import threading

import duckdb
from config.settings import settings

_connection: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the shared DuckDB connection (thread-safe initialization)."""
    global _connection
    if _connection is None:
        with _lock:
            # Double-check after acquiring lock
            if _connection is None:
                _connection = duckdb.connect(settings.duckdb_path, read_only=True)
    return _connection


def execute_query(sql: str, timeout_seconds: int | None = None) -> list[dict]:
    """Execute a read query using a thread-local cursor.

    Each call gets its own cursor from the shared connection, so multiple
    Streamlit/FastAPI requests can run queries concurrently without blocking.
    """
    conn = get_connection()
    # cursor() creates a thread-safe handle for concurrent reads
    with _lock:
        cursor = conn.cursor()
    try:
        result = cursor.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()


def close_connection():
    """Close the DuckDB connection."""
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
            _connection = None
