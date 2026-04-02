"""Central configuration using Pydantic BaseSettings.

Reads from .env locally. On Streamlit Cloud, reads from st.secrets
(configured in the Streamlit Cloud dashboard).
"""

import os

from pydantic_settings import BaseSettings


def _get_streamlit_secret(key: str) -> str | None:
    """Try to read a secret from Streamlit Cloud's secrets manager."""
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


class Settings(BaseSettings):
    # Warehouse
    duckdb_path: str = "./data/warehouse.duckdb"

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Catalog
    catalog_dir: str = "./catalog"

    # Retrieval
    catalog_top_k: int = 5
    embedding_model: str = "all-MiniLM-L6-v2"

    # Agent
    max_sql_retries: int = 2
    query_timeout_seconds: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# On Streamlit Cloud, secrets come from the dashboard, not .env
_cloud_key = _get_streamlit_secret("ANTHROPIC_API_KEY")
if _cloud_key:
    os.environ["ANTHROPIC_API_KEY"] = _cloud_key

settings = Settings()
