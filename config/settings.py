"""Central configuration using Pydantic BaseSettings."""

from pydantic_settings import BaseSettings


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


settings = Settings()
