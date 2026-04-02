"""Streamlit chat UI for the text-to-SQL agent."""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from src.catalog.loader import CatalogLoader
from src.catalog.index import CatalogIndex
from src.catalog.retriever import CatalogRetriever
from src.agent.graph import build_graph


# Example questions organized by what they demonstrate
EXAMPLE_QUESTIONS = {
    "Metric Disambiguation": {
        "icon": "🔀",
        "description": "These questions involve 'revenue' — which has 3 competing definitions. The agent asks which one you mean instead of guessing.",
        "questions": [
            "What was our revenue last quarter?",
            "Compare billed vs recognized revenue for 2025",
            "Show me GAAP revenue by quarter for fiscal year 2025",
        ],
    },
    "Data Quality Awareness": {
        "icon": "⚠️",
        "description": "These hit tables with known issues. The agent warns you about stale data, null rates, and deprecated tables.",
        "questions": [
            "What is the recognized revenue for March 2026?",
            "What's the average NPS score for Q1 2025?",
            "Show me the current client list from the legacy system",
            "What's the utilization rate by department for Q1 2026?",
        ],
    },
    "Cross-Schema Joins": {
        "icon": "🔗",
        "description": "Questions that require joining across finance, operations, and client_services schemas.",
        "questions": [
            "Which clients have overdue invoices and active engagements?",
            "Show me the top 5 consultants by billable hours with their department",
            "What's the budget variance by department for Q1 2026?",
        ],
    },
    "Simple Lookups": {
        "icon": "🔍",
        "description": "Straightforward queries to see the basic flow — parse, retrieve, generate, execute.",
        "questions": [
            "How many active clients do we have?",
            "List all employees currently on leave",
            "What's the total contract value by contract type?",
            "Show the top 10 largest invoices",
        ],
    },
    "Ambiguity Resolution": {
        "icon": "🤔",
        "description": "'Status' means 9 different things across 9 tables. Watch how the agent picks the right one.",
        "questions": [
            "Show me all pending items",
            "Which engagements are at risk or over budget?",
            "What's the completion rate for work orders this year?",
        ],
    },
    "Guardrails": {
        "icon": "🛡️",
        "description": "The agent refuses destructive queries and redirects away from deprecated tables.",
        "questions": [
            "DROP TABLE clients",
            "DELETE FROM finance.gl_transactions WHERE amount > 0",
        ],
    },
}


@st.cache_resource
def init_agent():
    """Initialize catalog, index, agent graph, and cache.

    Auto-creates the warehouse and catalog index on first run (needed for
    Streamlit Cloud where setup scripts don't run automatically).
    """
    import os
    from src.cache import SemanticCache
    from src.logging_config import setup_logging
    from config.settings import settings

    setup_logging()

    # Auto-seed warehouse if it doesn't exist
    if not os.path.exists(settings.duckdb_path):
        from src.warehouse.seed import seed_warehouse
        os.makedirs(os.path.dirname(settings.duckdb_path), exist_ok=True)
        seed_warehouse()

    catalog = CatalogLoader().load()

    # Auto-build index if it doesn't exist
    index_path = os.path.join(settings.catalog_dir, ".index", "embeddings.npy")
    index = CatalogIndex(catalog)
    if not os.path.exists(index_path):
        index.build()
        index.save()
    else:
        index.load()

    retriever = CatalogRetriever(catalog, index)
    graph = build_graph(retriever)
    cache = SemanticCache()
    return graph, catalog, cache


def main():
    st.set_page_config(page_title="Text-to-SQL Agent", layout="wide")

    graph, catalog, cache = init_agent()

    # --- Sidebar: Catalog Browser & Quality Status ---
    with st.sidebar:
        st.header("Data Catalog")

        # Quality summary
        healthy = sum(1 for t in catalog.tables.values() if t.quality.status == "healthy")
        degraded = sum(1 for t in catalog.tables.values() if t.quality.status == "degraded")
        stale = sum(1 for t in catalog.tables.values() if t.quality.status == "stale")
        col1, col2, col3 = st.columns(3)
        col1.metric("Healthy", healthy)
        col2.metric("Degraded", degraded)
        col3.metric("Stale", stale)

        st.divider()

        # Schema browser
        for schema_name in sorted(catalog.schemas.keys()):
            tables = catalog.get_tables_for_schema(schema_name)
            with st.expander(f"{schema_name} ({len(tables)} tables)"):
                for t in tables:
                    icon = {"healthy": "🟢", "degraded": "🟡", "stale": "🔴"}.get(
                        t.quality.status, "⚪"
                    )
                    dep = " ⚠️ DEPRECATED" if t.deprecated else ""
                    st.markdown(f"{icon} **{t.table_name}**{dep}")
                    st.caption(t.description[:100] + "..." if len(t.description) > 100 else t.description)

        st.divider()
        st.header("Metrics")
        for m in catalog.metrics:
            with st.expander(f"{m.name} {'⚠️' if m.disambiguation_required else ''}"):
                for d in m.definitions:
                    st.markdown(f"**{d.name}**: {d.description[:80]}...")

    # --- Main Area ---
    title_col, btn_col = st.columns([6, 1])
    with title_col:
        st.title("Text-to-SQL Agent")
    with btn_col:
        st.markdown("")  # spacing
        if st.button("New Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_disambiguation = None
            st.rerun()

    st.caption(
        "Ask questions about an enterprise data warehouse with 15 tables across 3 schemas. "
        "The agent uses a data catalog to understand business context, disambiguate metrics, "
        "and warn about data quality issues."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_disambiguation" not in st.session_state:
        st.session_state.pending_disambiguation = None

    # --- Example Questions (shown when chat is empty) ---
    if not st.session_state.messages and not st.session_state.pending_disambiguation:
        st.markdown("### Try these examples")
        st.markdown(
            "Each category demonstrates a different capability. "
            "Click any question to run it."
        )

        for category, info in EXAMPLE_QUESTIONS.items():
            with st.expander(f"{info['icon']}  **{category}** — {info['description']}", expanded=False):
                for q in info["questions"]:
                    if st.button(q, key=f"example_{hash(q)}", use_container_width=True):
                        st.session_state.messages.append({"role": "user", "content": q})
                        _run_query(graph, cache, q)
                        st.rerun()

        st.divider()

    # --- Chat History ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sql"):
                with st.expander("Generated SQL"):
                    st.code(msg["sql"], language="sql")
            if msg.get("warnings"):
                for w in msg["warnings"]:
                    st.warning(w)
            if msg.get("results"):
                import pandas as pd
                df = pd.DataFrame(msg["results"])
                st.dataframe(df, use_container_width=True)

    # --- Disambiguation Handler ---
    if st.session_state.pending_disambiguation:
        disambig = st.session_state.pending_disambiguation
        st.info(disambig["prompt"])
        options = disambig["options"]
        cols = st.columns(len(options))
        for i, opt in enumerate(options):
            if cols[i].button(opt["name"], key=f"disambig_{i}"):
                st.session_state.pending_disambiguation = None
                _run_query(graph, cache, disambig["question"], disambiguation_choice=opt["id"])
                st.rerun()

    # --- Chat Input ---
    if question := st.chat_input("Ask a question about your data..."):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        _run_query(graph, cache, question)
        st.rerun()


def _run_query(graph, cache, question: str, disambiguation_choice: str | None = None):
    """Run a query through the agent with caching and input sanitization."""
    from src.guardrails import sanitize_input

    # Sanitize input
    cleaned_question, injection_warnings = sanitize_input(question)

    # Check cache first (skip if disambiguation)
    if not disambiguation_choice:
        cached = cache.get(cleaned_question)
        if cached is not None:
            msg = {
                "role": "assistant",
                "content": cached.get("final_response", "") + "\n\n*⚡ Served from cache*",
                "sql": cached.get("generated_sql"),
                "warnings": cached.get("warnings", []),
                "results": cached.get("query_results"),
            }
            st.session_state.messages.append(msg)
            return

    with st.spinner("Thinking..."):
        result = graph.invoke({
            "user_question": cleaned_question,
            "conversation_history": [],
            "disambiguation_choice": disambiguation_choice,
        })

    status = result.get("status", "error")

    if status == "needs_input":
        st.session_state.pending_disambiguation = {
            "prompt": result.get("final_response", ""),
            "options": result.get("disambiguation_options", []),
            "question": question,
        }
        return

    # Cache the result
    cache.put(cleaned_question, result)

    msg = {
        "role": "assistant",
        "content": result.get("final_response", "Something went wrong."),
        "sql": result.get("generated_sql"),
        "warnings": result.get("warnings", []),
        "results": result.get("query_results"),
    }
    st.session_state.messages.append(msg)


if __name__ == "__main__":
    main()
