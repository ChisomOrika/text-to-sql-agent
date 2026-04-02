"""Step 7: Format results into a human-readable response."""

import json

from src.agent.state import AgentState
from src.agent.prompts import FORMAT_RESPONSE_SYSTEM, FORMAT_RESPONSE_USER
from src.llm.claude import chat


def format_response(state: AgentState) -> dict:
    """Format query results and warnings into a final response."""
    warnings = state.get("freshness_warnings", []) + state.get("quality_warnings", [])
    results = state.get("query_results")
    row_count = state.get("row_count", 0)
    sql = state.get("generated_sql", "")
    explanation = state.get("sql_explanation", "")
    question = state["user_question"]
    exec_error = state.get("execution_error")

    # Handle error case
    if exec_error:
        return {
            "final_response": (
                f"I wasn't able to execute the query successfully.\n\n"
                f"**Error:** {exec_error}\n\n"
                f"**SQL attempted:**\n```sql\n{sql}\n```"
            ),
            "warnings": warnings,
            "status": "error",
        }

    # Handle validation failure after max retries
    if not state.get("validation_passed", True) and state.get("retry_count", 0) >= 2:
        errors = state.get("validation_errors", [])
        return {
            "final_response": (
                f"I couldn't generate a valid SQL query for your question after multiple attempts.\n\n"
                f"**Issues:** {'; '.join(errors)}\n\n"
                f"Try rephrasing your question or being more specific about which tables or metrics you need."
            ),
            "warnings": warnings,
            "status": "error",
        }

    # Format results
    if results:
        # Truncate large result sets for the prompt
        display_results = results[:50]
        results_str = json.dumps(display_results, indent=2, default=str)
    else:
        results_str = "No results returned."

    warnings_str = "\n".join(f"- {w}" for w in warnings) if warnings else "None"

    user_msg = FORMAT_RESPONSE_USER.format(
        question=question,
        sql=sql,
        explanation=explanation,
        row_count=row_count,
        results=results_str,
        warnings=warnings_str,
    )

    response_text = chat(
        system=FORMAT_RESPONSE_SYSTEM,
        user_message=user_msg,
        max_tokens=2048,
    )

    return {
        "final_response": response_text,
        "warnings": warnings,
        "status": "completed",
    }
