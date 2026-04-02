"""Evaluation harness — runs test questions through the agent and scores results."""

import json
import time
from pathlib import Path

import yaml

from src.catalog.loader import CatalogLoader
from src.catalog.index import CatalogIndex
from src.catalog.retriever import CatalogRetriever
from src.agent.graph import build_graph
from eval.metrics import (
    compute_summary,
    score_disambiguation,
    score_safety,
    score_sql_validity,
    score_table_selection,
    score_warnings,
)


def load_questions(path: str = "eval/questions.yaml") -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("questions", [])


def run_evaluation(
    questions: list[dict] | None = None,
    output_path: str = "eval/results.json",
    category_filter: str | None = None,
) -> dict:
    """Run all evaluation questions and return scored results."""
    # Initialize components
    print("Initializing...")
    catalog = CatalogLoader().load()
    index = CatalogIndex(catalog)
    index.load()
    retriever = CatalogRetriever(catalog, index)
    graph = build_graph(retriever)

    if questions is None:
        questions = load_questions()

    if category_filter:
        questions = [q for q in questions if q.get("category") == category_filter]

    results = []
    print(f"Running {len(questions)} questions...\n")

    for i, q in enumerate(questions):
        qid = q.get("id", f"Q{i+1}")
        question_text = q["question"]
        print(f"  [{qid}] {question_text[:60]}...", end=" ", flush=True)

        start = time.time()
        try:
            state = graph.invoke({
                "user_question": question_text,
                "conversation_history": [],
                "disambiguation_choice": None,
            })
        except Exception as e:
            state = {"status": "error", "execution_error": str(e)}
        elapsed = time.time() - start

        # Score
        result = {
            "id": qid,
            "category": q.get("category"),
            "difficulty": q.get("difficulty"),
            "question": question_text,
            "elapsed_seconds": round(elapsed, 2),
            "status": state.get("status", "error"),
            "generated_sql": state.get("generated_sql"),
            "row_count": state.get("row_count", 0),
        }

        result["table_selection"] = score_table_selection(
            q.get("expected_tables", []),
            state.get("relevant_tables", []),
        )

        result["sql_valid"] = score_sql_validity(state.get("execution_error"))

        result["disambiguation"] = score_disambiguation(
            q.get("expects_disambiguation", False),
            state.get("needs_disambiguation", False),
        )

        result["warnings_score"] = score_warnings(
            q.get("expects_warning", False),
            q.get("expected_warning_keywords", []),
            state.get("freshness_warnings", []) + state.get("quality_warnings", []),
        )

        result["safety"] = score_safety(
            state.get("status", ""),
            state.get("generated_sql"),
        )

        status_icon = "✓" if result["sql_valid"] else "✗"
        print(f"{status_icon} ({elapsed:.1f}s)")
        results.append(result)

    # Summary
    summary = compute_summary(results)
    output = {"summary": summary, "results": results}

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Print summary
    print(f"\n{'='*50}")
    print(f"EVALUATION SUMMARY ({len(results)} questions)")
    print(f"{'='*50}")
    print(f"SQL Validity:           {summary.get('sql_validity_rate', 0):.1%}")
    print(f"Disambiguation Accuracy:{summary.get('disambiguation_accuracy', 0):.1%}")
    print(f"Warning Accuracy:       {summary.get('warning_accuracy', 0):.1%}")
    print(f"Safety Rate:            {summary.get('safety_rate', 0):.1%}")
    print(f"Avg Table Precision:    {summary.get('avg_table_precision', 0):.2f}")
    print(f"Avg Table Recall:       {summary.get('avg_table_recall', 0):.2f}")
    print(f"Results saved to: {output_path}")

    return output
