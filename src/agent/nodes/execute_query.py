"""Step 6: Execute SQL on DuckDB."""

from src.agent.state import AgentState
from src.warehouse.connection import execute_query as run_sql


def execute_query(state: AgentState) -> dict:
    """Execute the validated SQL against DuckDB."""
    sql = state.get("generated_sql", "")

    try:
        results = run_sql(sql)
        return {
            "query_results": results,
            "row_count": len(results),
            "execution_error": None,
        }
    except Exception as e:
        return {
            "query_results": None,
            "row_count": 0,
            "execution_error": str(e),
        }
