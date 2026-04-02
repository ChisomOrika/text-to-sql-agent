#!/usr/bin/env python3
"""One-shot script to create and seed the DuckDB warehouse."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.warehouse.seed import seed_warehouse

if __name__ == "__main__":
    seed_warehouse()
    print("Done! Warehouse is ready.")
