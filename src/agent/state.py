"""LangGraph agent state definition."""

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    # Input
    user_question: str
    conversation_history: list[dict[str, str]]
    disambiguation_choice: str | None

    # Step 1: Parse
    parsed_intent: str  # metric_query, exploration, comparison, trend, lookup
    entities_extracted: list[str]
    time_range: dict[str, str] | None

    # Step 2: Schema retrieval
    relevant_tables: list[dict[str, Any]]  # Serialized catalog entries
    relevant_metrics: list[dict[str, Any]]

    # Step 3: Freshness
    freshness_warnings: list[str]
    quality_warnings: list[str]

    # Step 4: SQL generation
    generated_sql: str
    sql_explanation: str

    # Step 5: Validation
    validation_passed: bool
    validation_errors: list[str]
    retry_count: int

    # Step 6: Execution
    query_results: list[dict[str, Any]] | None
    row_count: int
    execution_error: str | None

    # Step 7: Response
    final_response: str
    warnings: list[str]

    # Control flow
    needs_disambiguation: bool
    disambiguation_options: list[dict[str, str]]
    status: Literal["in_progress", "needs_input", "completed", "error"]
