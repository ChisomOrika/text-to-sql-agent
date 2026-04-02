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


@st.cache_resource
def init_agent():
    """Initialize catalog, index, and agent graph (cached)."""
    catalog = CatalogLoader().load()
    index = CatalogIndex(catalog)
    index.load()
    retriever = CatalogRetriever(catalog, index)
    graph = build_graph(retriever)
    return graph, catalog


def main():
    st.set_page_config(page_title="Text-to-SQL Agent", layout="wide")
    st.title("Text-to-SQL Agent")

    graph, catalog = init_agent()

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

    # --- Main Area: Chat Interface ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_disambiguation" not in st.session_state:
        st.session_state.pending_disambiguation = None

    # Display chat history
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

    # Handle disambiguation
    if st.session_state.pending_disambiguation:
        disambig = st.session_state.pending_disambiguation
        st.info(disambig["prompt"])
        options = disambig["options"]
        cols = st.columns(len(options))
        for i, opt in enumerate(options):
            if cols[i].button(opt["name"], key=f"disambig_{i}"):
                st.session_state.pending_disambiguation = None
                _run_query(graph, disambig["question"], disambiguation_choice=opt["id"])
                st.rerun()

    # Chat input
    if question := st.chat_input("Ask a question about your data..."):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        _run_query(graph, question)
        st.rerun()


def _run_query(graph, question: str, disambiguation_choice: str | None = None):
    """Run a query through the agent and update session state."""
    with st.spinner("Thinking..."):
        result = graph.invoke({
            "user_question": question,
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
