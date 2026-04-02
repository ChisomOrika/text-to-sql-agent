"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router, set_dependencies
from src.catalog.loader import CatalogLoader
from src.catalog.index import CatalogIndex
from src.catalog.retriever import CatalogRetriever
from src.agent.graph import build_graph
from src.cache import SemanticCache
from src.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize catalog, index, agent graph, and cache on startup."""
    setup_logging()

    print("Loading catalog...")
    catalog = CatalogLoader().load()
    print(f"  {len(catalog.tables)} tables, {len(catalog.metrics)} metrics")

    print("Loading catalog index...")
    index = CatalogIndex(catalog)
    index.load()

    retriever = CatalogRetriever(catalog, index)

    print("Building agent graph...")
    graph = build_graph(retriever)

    print("Initializing semantic cache...")
    cache = SemanticCache()

    set_dependencies(graph, catalog, cache)
    print("Ready!")

    yield

    from src.warehouse.connection import close_connection
    close_connection()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Text-to-SQL Agent",
        description="Enterprise text-to-SQL with data catalog and quality awareness",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
