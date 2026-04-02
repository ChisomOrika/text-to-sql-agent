"""Step 5: Validate generated SQL against the catalog (programmatic, no LLM).

Validation is programmatic (sqlparse), not LLM-based. LLM validation would add
latency and cost, and would itself be probabilistic — you'd be using a probabilistic
system to validate another probabilistic system. Programmatic validation is deterministic
and catches the most common failure modes: wrong table name and destructive SQL.

Column-level validation was removed after it produced too many false positives — regex
can't reliably distinguish table names from column names in arbitrary SQL (e.g.,
"client_services.client_feedback" would flag "client_feedback" as a missing column).
Instead, we let DuckDB catch column errors on execution and retry with the error message.
"""

import re

import sqlparse

from src.agent.state import AgentState
from src.catalog.models import TableCatalogEntry
from src.guardrails import validate_generated_sql
from src.logging_config import log_node


@log_node("validate_sql")
def validate_sql(state: AgentState) -> dict:
    """Validate SQL against the catalog. Returns validation result."""
    sql = state.get("generated_sql", "")
    errors = []

    if not sql.strip():
        return {"validation_passed": False, "validation_errors": ["Empty SQL generated"]}

    # Parse SQL
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            errors.append("Failed to parse SQL")
            return {"validation_passed": False, "validation_errors": errors}
    except Exception as e:
        errors.append(f"SQL parse error: {e}")
        return {"validation_passed": False, "validation_errors": errors}

    # Check for destructive operations
    sql_upper = sql.upper().strip()
    for forbidden in ("DROP ", "DELETE ", "INSERT ", "UPDATE ", "ALTER ", "CREATE ", "TRUNCATE "):
        if sql_upper.startswith(forbidden):
            errors.append(f"Destructive SQL detected: {forbidden.strip()}")
            return {"validation_passed": False, "validation_errors": errors}

    # Check for injection patterns (piggyback queries, system catalog access, etc.)
    safe, guardrail_errors = validate_generated_sql(sql)
    if not safe:
        errors.extend(guardrail_errors)
        return {"validation_passed": False, "validation_errors": errors}

    # Extract table references from SQL
    referenced_tables = _extract_table_refs(sql)
    all_catalog_table_names = {
        t["table"] for t in state.get("relevant_tables", [])
    }

    # Check that referenced tables exist in the catalog
    for ref in referenced_tables:
        if ref not in all_catalog_table_names:
            # Maybe it's partially qualified — check just table name
            short_matches = [t for t in all_catalog_table_names if t.endswith(f".{ref}")]
            if not short_matches:
                errors.append(f"Table '{ref}' not found in retrieved catalog entries")

    return {
        "validation_passed": len(errors) == 0,
        "validation_errors": errors,
    }


def _extract_table_refs(sql: str) -> set[str]:
    """Extract table references from SQL using regex."""
    refs = set()
    # Match schema.table patterns
    for match in re.finditer(r'(?:FROM|JOIN)\s+([\w]+\.[\w]+)', sql, re.IGNORECASE):
        refs.add(match.group(1))
    # Match standalone table names after FROM/JOIN
    for match in re.finditer(r'(?:FROM|JOIN)\s+([\w]+)(?:\s|$|,)', sql, re.IGNORECASE):
        val = match.group(1)
        if "." not in val and val.upper() not in ("SELECT", "WHERE", "GROUP", "ORDER", "HAVING"):
            refs.add(val)
    return refs
