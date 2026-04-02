"""Step 2: Retrieve relevant catalog entries using RAG."""

from src.agent.state import AgentState
from src.catalog.retriever import CatalogRetriever
from src.logging_config import log_node


# Module-level retriever set during graph construction
_retriever: CatalogRetriever | None = None


def set_retriever(retriever: CatalogRetriever):
    global _retriever
    _retriever = retriever


@log_node("retrieve_schema")
def retrieve_schema(state: AgentState) -> dict:
    """Retrieve relevant tables and metrics from the catalog."""
    if _retriever is None:
        raise RuntimeError("Catalog retriever not initialized. Call set_retriever() first.")

    question = state["user_question"]
    tables, metrics = _retriever.retrieve(question)

    # Check if disambiguation is needed
    needs_disambig = False
    disambig_options = []

    # If user already made a disambiguation choice, filter metrics
    choice = state.get("disambiguation_choice")
    if choice:
        needs_disambig = False
    else:
        for m in metrics:
            if m.disambiguation_required:
                needs_disambig = True
                disambig_options = [
                    {"id": d.id, "name": d.name, "description": d.description}
                    for d in m.definitions
                ]
                break

    return {
        "relevant_tables": [t.model_dump() for t in tables],
        "relevant_metrics": [m.model_dump() for m in metrics],
        "needs_disambiguation": needs_disambig,
        "disambiguation_options": disambig_options,
    }
