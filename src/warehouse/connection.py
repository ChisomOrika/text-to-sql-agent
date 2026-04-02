"""DuckDB connection manager."""

import duckdb
from config.settings import settings

_connection: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a singleton DuckDB connection."""
    global _connection
    if _connection is None:
        _connection = duckdb.connect(settings.duckdb_path)
    return _connection


def execute_query(sql: str, timeout_seconds: int | None = None) -> list[dict]:
    """Execute a SQL query and return results as list of dicts."""
    conn = get_connection()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def close_connection():
    """Close the DuckDB connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
