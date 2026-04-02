"""LangGraph state graph construction — wires all nodes together."""

from langgraph.graph import END, StateGraph

from src.agent.state import AgentState
from src.agent.nodes.parse_question import parse_question
from src.agent.nodes.retrieve_schema import retrieve_schema, set_retriever
from src.agent.nodes.check_freshness import check_freshness
from src.agent.nodes.generate_sql import generate_sql
from src.agent.nodes.validate_sql import validate_sql
from src.agent.nodes.execute_query import execute_query
from src.agent.nodes.format_response import format_response
from src.catalog.retriever import CatalogRetriever


def _ask_user(state: AgentState) -> dict:
    """Pause execution — return disambiguation options to the caller."""
    metrics = state.get("relevant_metrics", [])
    prompt = ""
    for m in metrics:
        if m.get("disambiguation_required"):
            prompt = m.get("prompt_to_user", "Which metric definition would you like?")
            break
    return {
        "final_response": prompt,
        "status": "needs_input",
    }


def _route_after_retrieval(state: AgentState) -> str:
    if state.get("needs_disambiguation", False):
        return "disambiguate"
    return "continue"


def _route_after_validation(state: AgentState) -> str:
    if state.get("validation_passed", False):
        return "execute"
    retry = state.get("retry_count", 0)
    if retry < 2:
        return "retry"
    return "fail"


def _increment_retry(state: AgentState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1}


def _route_after_execution(state: AgentState) -> str:
    if state.get("execution_error"):
        retry = state.get("retry_count", 0)
        if retry < 2:
            return "retry"
        return "fail"
    return "success"


def build_graph(retriever: CatalogRetriever) -> StateGraph:
    """Build and compile the agent graph."""
    set_retriever(retriever)

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("parse_question", parse_question)
    graph.add_node("retrieve_schema", retrieve_schema)
    graph.add_node("ask_user", _ask_user)
    graph.add_node("check_freshness", check_freshness)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("validate_sql", validate_sql)
    graph.add_node("increment_retry", _increment_retry)
    graph.add_node("execute_query", execute_query)
    graph.add_node("format_response", format_response)

    # Wire edges
    graph.set_entry_point("parse_question")
    graph.add_edge("parse_question", "retrieve_schema")

    # Disambiguation happens AFTER schema retrieval, not during parsing — we need
    # catalog context to know which metrics have multiple definitions. Parsing alone
    # can't tell us whether "revenue" is ambiguous in this specific warehouse.
    graph.add_conditional_edges(
        "retrieve_schema",
        _route_after_retrieval,
        {"disambiguate": "ask_user", "continue": "check_freshness"},
    )
    # Routes to END, not back into the graph — disambiguation requires user input,
    # so we break execution and re-invoke with the user's choice (LangGraph human-in-the-loop).
    graph.add_edge("ask_user", END)

    graph.add_edge("check_freshness", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")

    graph.add_conditional_edges(
        "validate_sql",
        _route_after_validation,
        {"execute": "execute_query", "retry": "increment_retry", "fail": "format_response"},
    )
    graph.add_edge("increment_retry", "generate_sql")

    graph.add_conditional_edges(
        "execute_query",
        _route_after_execution,
        {"success": "format_response", "retry": "increment_retry", "fail": "format_response"},
    )
    graph.add_edge("format_response", END)

    return graph.compile()
