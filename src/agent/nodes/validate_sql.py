"""Step 5: Validate generated SQL against the catalog (programmatic, no LLM).

Validation is programmatic (sqlparse), not LLM-based. LLM validation would add
latency and cost, and would itself be probabilistic — you'd be using a probabilistic
system to validate another probabilistic system. Programmatic validation is deterministic
and catches the most common failure modes (wrong table, wrong column, destructive SQL).
"""

import re

import sqlparse

from src.agent.state import AgentState
from src.catalog.models import TableCatalogEntry


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

    # Extract table references from SQL
    referenced_tables = _extract_table_refs(sql)
    catalog_tables = {
        t["table"]: TableCatalogEntry(**t)
        for t in state.get("relevant_tables", [])
    }
    all_catalog_table_names = set(catalog_tables.keys())

    # Check that referenced tables exist in the catalog
    for ref in referenced_tables:
        if ref not in all_catalog_table_names:
            # Maybe it's partially qualified — check just table name
            short_matches = [t for t in all_catalog_table_names if t.endswith(f".{ref}")]
            if not short_matches:
                errors.append(f"Table '{ref}' not found in retrieved catalog entries")

    # Check column references against catalog
    referenced_columns = _extract_column_refs(sql)
    for col in referenced_columns:
        found = False
        for entry in catalog_tables.values():
            if col.lower() in [c.name.lower() for c in entry.columns]:
                found = True
                break
        if not found:
            # Common SQL functions/aliases — don't flag these
            if col.lower() not in (
                "count", "sum", "avg", "min", "max", "coalesce", "extract",
                "date_trunc", "case", "when", "then", "else", "end", "as",
                "null", "true", "false", "distinct", "quarter", "year", "month",
            ):
                errors.append(f"Column '{col}' not found in any retrieved catalog table")

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


def _extract_column_refs(sql: str) -> set[str]:
    # Intentionally loose/best-effort: over-strict column validation causes more
    # false positives than it prevents real errors.
    """Extract potential column references from SQL. Best-effort."""
    cols = set()
    # Strip string literals and comments
    cleaned = re.sub(r"'[^']*'", "", sql)
    cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)

    # Look for identifiers after SELECT, WHERE, ON, BY, HAVING
    for match in re.finditer(r'(?:\.)([\w]+)', cleaned):
        cols.add(match.group(1))
    return cols
