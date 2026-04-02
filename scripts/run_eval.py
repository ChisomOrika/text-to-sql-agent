#!/usr/bin/env python3
"""Run the evaluation suite."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.runner import run_evaluation

if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else None
    if category:
        print(f"Running category: {category}")
    run_evaluation(category_filter=category)
