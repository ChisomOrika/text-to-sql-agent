"""Structured logging with per-node timing for observability.

Every agent node logs: node name, duration, input/output sizes, and any errors.
This makes it possible to diagnose slow queries, identify which step failed,
and track LLM call costs over time. In production, pipe these JSON logs to
Datadog/Grafana/CloudWatch for dashboards and alerting.
"""

import json
import logging
import time
from functools import wraps
from typing import Any, Callable

# Configure structured JSON logging
logger = logging.getLogger("text_to_sql_agent")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO"):
    """Configure the agent logger with JSON formatting."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))


def log_node(node_name: str):
    """Decorator that logs timing and metadata for each agent node."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            start = time.time()
            question = state.get("user_question", "")[:100]

            logger.info(
                f"Node started: {node_name}",
                extra={"extra_data": {
                    "node": node_name,
                    "event": "node_start",
                    "question_preview": question,
                }},
            )

            try:
                result = func(state)
                elapsed = time.time() - start

                # Build metadata about what happened
                meta: dict[str, Any] = {
                    "node": node_name,
                    "event": "node_complete",
                    "duration_ms": round(elapsed * 1000, 1),
                }

                # Node-specific metrics
                if node_name == "retrieve_schema":
                    meta["tables_retrieved"] = len(result.get("relevant_tables", []))
                    meta["needs_disambiguation"] = result.get("needs_disambiguation", False)
                elif node_name == "generate_sql":
                    sql = result.get("generated_sql", "")
                    meta["sql_length"] = len(sql)
                elif node_name == "validate_sql":
                    meta["validation_passed"] = result.get("validation_passed", False)
                    meta["validation_errors"] = result.get("validation_errors", [])
                elif node_name == "execute_query":
                    meta["row_count"] = result.get("row_count", 0)
                    meta["execution_error"] = result.get("execution_error")

                logger.info(
                    f"Node completed: {node_name} ({elapsed:.2f}s)",
                    extra={"extra_data": meta},
                )
                return result

            except Exception as e:
                elapsed = time.time() - start
                logger.error(
                    f"Node failed: {node_name} ({elapsed:.2f}s) - {e}",
                    extra={"extra_data": {
                        "node": node_name,
                        "event": "node_error",
                        "duration_ms": round(elapsed * 1000, 1),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }},
                )
                raise

        return wrapper
    return decorator
