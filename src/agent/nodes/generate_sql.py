"""Step 4: Generate SQL using Claude."""

from src.agent.state import AgentState
from src.agent.prompts import GENERATE_SQL_SYSTEM, GENERATE_SQL_USER
from src.catalog.models import TableCatalogEntry
from src.llm.claude import chat_json


def generate_sql(state: AgentState) -> dict:
    """Generate SQL query using Claude with catalog context."""
    question = state["user_question"]

    # Build catalog context from relevant tables
    catalog_parts = []
    for table_data in state.get("relevant_tables", []):
        entry = TableCatalogEntry(**table_data)
        catalog_parts.append(entry.to_schema_text())

        # Few-shot examples from the catalog's sample_queries dramatically reduce
        # hallucination — the LLM sees correct patterns for this specific warehouse.
        for sq in entry.sample_queries:
            catalog_parts.append(f"\nExample for {entry.table}:")
            catalog_parts.append(f"  Q: {sq.question}")
            catalog_parts.append(f"  SQL: {sq.sql}")

    catalog_context = "DATA CATALOG CONTEXT:\n" + "\n\n".join(catalog_parts)

    # Add metric context if disambiguation was resolved
    choice = state.get("disambiguation_choice")
    if choice:
        for metric_data in state.get("relevant_metrics", []):
            for defn in metric_data.get("definitions", []):
                if defn.get("id") == choice or defn.get("name", "").lower() in choice.lower():
                    catalog_context += (
                        f"\n\nSELECTED METRIC DEFINITION:\n"
                        f"Name: {defn['name']}\n"
                        f"Table: {defn.get('table', 'N/A')}\n"
                        f"Calculation: {defn['calculation']}\n"
                        f"Filters: {defn.get('filters', 'None')}"
                    )

    # Build warnings context
    warnings = state.get("freshness_warnings", []) + state.get("quality_warnings", [])
    warnings_context = ""
    if warnings:
        warnings_context = "DATA QUALITY WARNINGS (inform the query if relevant):\n" + "\n".join(
            f"- {w}" for w in warnings
        )

    # Retry context includes the previous SQL AND the error — without seeing what
    # failed, the LLM tends to regenerate the same broken query.
    retry_context = ""
    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        prev_sql = state.get("generated_sql", "")
        errors = state.get("validation_errors", []) or []
        exec_error = state.get("execution_error")
        if exec_error:
            errors.append(f"Execution error: {exec_error}")
        retry_context = (
            f"PREVIOUS ATTEMPT FAILED (attempt {retry_count}):\n"
            f"Previous SQL: {prev_sql}\n"
            f"Errors: {'; '.join(errors)}\n"
            f"Fix these issues in the new query."
        )

    user_msg = GENERATE_SQL_USER.format(
        question=question,
        catalog_context=catalog_context,
        warnings_context=warnings_context,
        retry_context=retry_context,
    )

    result = chat_json(system=GENERATE_SQL_SYSTEM, user_message=user_msg)

    return {
        "generated_sql": result.get("sql", ""),
        "sql_explanation": result.get("explanation", ""),
    }
