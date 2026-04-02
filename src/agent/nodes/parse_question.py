"""Step 1: Parse the user's natural language question."""

from src.agent.state import AgentState
from src.agent.prompts import PARSE_QUESTION_SYSTEM
from src.llm.claude import chat_json
from src.logging_config import log_node


@log_node("parse_question")
def parse_question(state: AgentState) -> dict:
    """Extract intent, entities, and time range from the user question."""
    question = state["user_question"]

    result = chat_json(
        system=PARSE_QUESTION_SYSTEM,
        user_message=question,
    )

    return {
        "parsed_intent": result.get("intent", "lookup"),
        "entities_extracted": result.get("entities", []),
        "time_range": result.get("time_range"),
        "retry_count": 0,
        "status": "in_progress",
    }
