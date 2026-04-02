"""Step 3: Check data freshness and quality for selected tables."""

from datetime import datetime, timezone

from src.agent.state import AgentState
from src.catalog.models import TableCatalogEntry


def check_freshness(state: AgentState) -> dict:
    """Check freshness and quality metadata for relevant tables."""
    freshness_warnings = []
    quality_warnings = []
    now = datetime.now(timezone.utc)

    for table_data in state.get("relevant_tables", []):
        entry = TableCatalogEntry(**table_data)
        table_name = entry.table

        # Freshness check
        if entry.last_refreshed:
            try:
                refreshed = datetime.fromisoformat(entry.last_refreshed.replace("Z", "+00:00"))
                age_hours = (now - refreshed).total_seconds() / 3600
                age_days = age_hours / 24

                # Thresholds differ per cadence: a daily table 2 days stale is a problem,
                # but a monthly table 2 days past refresh is normal. Thresholds are
                # intentionally generous (2x the cadence) to avoid false alarms.
                if entry.refresh_cadence == "daily" and age_days > 2:
                    freshness_warnings.append(
                        f"WARNING: {table_name} is {age_days:.0f} days since last refresh "
                        f"(expected daily). Last refreshed: {entry.last_refreshed}"
                    )
                elif entry.refresh_cadence == "weekly" and age_days > 10:
                    freshness_warnings.append(
                        f"WARNING: {table_name} is {age_days:.0f} days since last refresh "
                        f"(expected weekly). Last refreshed: {entry.last_refreshed}"
                    )
                elif entry.refresh_cadence == "monthly" and age_days > 45:
                    freshness_warnings.append(
                        f"WARNING: {table_name} is {age_days:.0f} days since last refresh "
                        f"(expected monthly). Last refreshed: {entry.last_refreshed}"
                    )
            except (ValueError, TypeError):
                pass

        # Quality status
        if entry.quality.status == "stale":
            quality_warnings.append(
                f"STALE DATA: {table_name} is marked as stale. Results may be incomplete or outdated."
            )
        elif entry.quality.status == "degraded":
            quality_warnings.append(
                f"DEGRADED: {table_name} has known data quality issues."
            )

        # Specific known issues
        for issue in entry.quality.known_issues:
            issue_text = issue.get("issue", "")
            severity = issue.get("severity", "medium")
            workaround = issue.get("workaround", "")
            if issue_text:
                warning = f"{table_name}: {issue_text}"
                if workaround:
                    warning += f" Workaround: {workaround}"
                quality_warnings.append(warning)

        # Deprecated table warning
        if entry.deprecated:
            quality_warnings.append(
                f"DEPRECATED: {table_name} should not be used. "
                f"{entry.deprecation_note or 'Use the current version of this table instead.'}"
            )

    return {
        "freshness_warnings": freshness_warnings,
        "quality_warnings": quality_warnings,
    }
