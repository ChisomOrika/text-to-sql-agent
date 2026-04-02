"""Load and validate YAML catalog files into Pydantic models."""

import os
from pathlib import Path

import yaml

from config.settings import settings
from src.catalog.models import (
    Metric,
    SchemaCatalogEntry,
    TableCatalogEntry,
)


class CatalogLoader:
    """Loads the full data catalog from YAML files."""

    def __init__(self, catalog_dir: str | None = None):
        self.catalog_dir = Path(catalog_dir or settings.catalog_dir)
        self.tables: dict[str, TableCatalogEntry] = {}
        self.schemas: dict[str, SchemaCatalogEntry] = {}
        self.metrics: list[Metric] = []

    def load(self) -> "CatalogLoader":
        """Load all catalog files. Returns self for chaining."""
        self._load_metrics()
        for schema_dir in self.catalog_dir.iterdir():
            if schema_dir.is_dir() and not schema_dir.name.startswith("."):
                self._load_schema(schema_dir)
        return self

    def _load_metrics(self):
        metrics_file = self.catalog_dir / "_metrics.yaml"
        if metrics_file.exists():
            with open(metrics_file) as f:
                data = yaml.safe_load(f)
            for m in data.get("metrics", []):
                self.metrics.append(Metric(**m))

    def _load_schema(self, schema_dir: Path):
        schema_file = schema_dir / "_schema.yaml"
        if schema_file.exists():
            with open(schema_file) as f:
                data = yaml.safe_load(f)
            # YAML uses 'schema' key, model uses 'schema_name'
            if "schema" in data and "schema_name" not in data:
                data["schema_name"] = data.pop("schema")
            entry = SchemaCatalogEntry(**data)
            self.schemas[entry.schema_name] = entry

        for yaml_file in sorted(schema_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and "table" in data:
                entry = TableCatalogEntry(**data)
                self.tables[entry.table] = entry

    def get_table(self, full_name: str) -> TableCatalogEntry | None:
        return self.tables.get(full_name)

    def get_tables_for_schema(self, schema: str) -> list[TableCatalogEntry]:
        return [t for t in self.tables.values() if t.schema_name == schema]

    def get_metric(self, name: str) -> Metric | None:
        for m in self.metrics:
            if m.name.lower() == name.lower():
                return m
        return None

    def get_all_table_names(self) -> list[str]:
        return list(self.tables.keys())

    def get_non_deprecated_tables(self) -> list[TableCatalogEntry]:
        return [t for t in self.tables.values() if not t.deprecated]
