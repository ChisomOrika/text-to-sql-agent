#!/usr/bin/env python3
"""Build the catalog vector index."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalog.loader import CatalogLoader
from src.catalog.index import CatalogIndex


def main():
    print("Loading catalog...")
    catalog = CatalogLoader().load()
    print(f"  Found {len(catalog.tables)} tables, {len(catalog.metrics)} metrics")

    print("Building vector index...")
    index = CatalogIndex(catalog)
    index.build()
    index.save()
    print("Done! Index saved to catalog/.index/")


if __name__ == "__main__":
    main()
