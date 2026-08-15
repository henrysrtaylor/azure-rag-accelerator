"""RAG evaluation script using custom LLM-as-judge functions.

Runs the RAG pipeline against a golden dataset and computes metrics:
groundedness, relevance, fluency, coherence, F1, and retrieval precision/recall.
"""

import json
import logging
import time
from pathlib import Path

import numpy as np
from tqdm import tqdm

from raglib.clients import load_env_vars
from raglib.eval import (
    f1_score,
    judge_coherence,
    judge_fluency,
    judge_groundedness,
    judge_relevance,
    normalize_score,
    precision_recall_at_k,
)
from raglib.config import eval_config
from raglib.log import configure_logging
from raglib.permissions import build_security_filter
from raglib.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

configure_logging()
load_env_vars()

OUTPUT_DIR = Path(__file__).parent / "results"

start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

# Load from local JSON file
LOCAL_DATASET_PATH = (
    Path(__file__).parent.parent / "data" / "evaluation" / "example_golden_dataset.json"
)
with open(LOCAL_DATASET_PATH, encoding="utf-8") as f:
    qna_set = json.load(f)

# Metrics we track (all normalized to 0-1)
aggregated_metrics = [
    "coherence",
    "f1_score",
    "fluency",
    "groundedness",
    "relevance",
    "retrieval_precision_at_1",
    "retrieval_precision_at_5",
    "retrieval_recall_at_1",
    "retrieval_recall_at_5",
]

results_individual: list[dict] = []
security_filter = build_security_filter(None)
rag_pipeline = RAGPipeline()

print(f"\nRunning RAG evaluation on {len(qna_set)} examples...\n")

for eval_example in tqdm(qna_set, desc="Evaluating", unit="query"):
    query = eval_example.get("query", "")
    ground_truth = eval_example.get("ground_truth", "")
    ground_truth_documents = eval_example.get("ground_truth_documents", [])

    chat_history = [
        {
            "role": "assistant",
            "content": "Hello! I'm your RAG assistant. How can I help you today?",
        },
        {"role": "user", "content": query},
    ]

    start_time = time.time()
    chat_response = rag_pipeline.run_evaluation(
        chat_history,
        security_filter=security_filter,
    )
    response = chat_response.get("assistant_message", {"content": ""}).get(
        "content", ""
    )
    context = chat_response.get("document_context", "")
    titles = [ref["text"] for ref in chat_response.get("references", [])]
    latency = time.time() - start_time

    # Retrieval metrics (no LLM)
    p1, r1 = precision_recall_at_k(
        list(set(titles)), list(set(ground_truth_documents)), 1
    )
    p5, r5 = precision_recall_at_k(
        list(set(titles)), list(set(ground_truth_documents)), 5
    )

    # F1 score (no LLM)
    f1 = f1_score(response, ground_truth)

    # LLM judges
    groundedness_result = judge_groundedness(query, context, response)
    relevance_result = judge_relevance(query, response)
    coherence_result = judge_coherence(query, response)
    fluency_result = judge_fluency(response)

    results_individual.append(
        {
            "query": query,
            "response": response,
            "ground_truth": ground_truth,
            "context": context,
            "retrieved_documents": titles,
            "latency_seconds": latency,
            # Normalized scores (0-1)
            "groundedness": normalize_score(groundedness_result["score"]),
            "relevance": normalize_score(relevance_result["score"]),
            "coherence": normalize_score(coherence_result["score"]),
            "fluency": normalize_score(fluency_result["score"]),
            "f1_score": f1,
            "retrieval_precision_at_1": p1,
            "retrieval_precision_at_5": p5,
            "retrieval_recall_at_1": r1,
            "retrieval_recall_at_5": r5,
            # Reasoning for debugging
            "groundedness_reason": groundedness_result["reasoning"],
            "relevance_reason": relevance_result["reasoning"],
            "coherence_reason": coherence_result["reasoning"],
            "fluency_reason": fluency_result["reasoning"],
        }
    )

# Calculate aggregated metrics
aggregated_eval_metrics = {
    k: float(np.mean([d[k] for d in results_individual if d.get(k) is not None]))
    for k in aggregated_metrics
}


def print_summary_table(metrics: dict) -> int:
    """Print a pass/fail summary table and return the passed metric count."""
    print("\n" + "=" * 65)
    print("                    EVALUATION SUMMARY")
    print("=" * 65)
    print(f"{'Metric':<30} {'Score':>8} {'Threshold':>10} {'Status':>10}")
    print("-" * 65)

    passed = 0
    friendly_names = {
        "groundedness": "Groundedness",
        "relevance": "Relevance",
        "fluency": "Fluency",
        "coherence": "Coherence",
        "f1_score": "F1 Score",
        "retrieval_precision_at_1": "Precision@1",
        "retrieval_precision_at_5": "Precision@5",
        "retrieval_recall_at_1": "Recall@1",
        "retrieval_recall_at_5": "Recall@5",
    }

    for metric_key in aggregated_metrics:
        score = metrics.get(metric_key, 0)
        threshold = eval_config.metric_thresholds.get(metric_key, 0.5)
        status = "PASS" if score >= threshold else "FAIL"
        if status == "PASS":
            passed += 1
        name = friendly_names.get(metric_key, metric_key)
        print(f"{name:<30} {score:>8.2f} {threshold:>10.2f} {status:>10}")

    print("-" * 65)
    total = len(aggregated_metrics)
    overall = "PASS" if passed == total else "FAIL"
    print(f"{'Overall:':<30} {'':<8} {'':<10} {f'{passed}/{total} {overall}':>10}")
    print("=" * 65)
    return passed


def save_results_json(results: list[dict], aggregated: dict, timestamp: str) -> Path:
    """Save detailed results and summary to timestamped directory as JSON."""
    dir_name = timestamp.replace(":", "-").replace(" ", "_")
    run_dir = OUTPUT_DIR / dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Full results - already has query/response/ground_truth + metrics
    with open(run_dir / "full_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Aggregated summary
    summary = {
        "timestamp": timestamp,
        "total_examples": len(results),
        "metrics": {},
        "passed": 0,
        "total": len(aggregated_metrics),
        "overall": "FAIL",
    }
    for metric_key in aggregated_metrics:
        score = aggregated.get(metric_key, 0)
        threshold = eval_config.metric_thresholds.get(metric_key, 0.5)
        status = "PASS" if score >= threshold else "FAIL"
        if status == "PASS":
            summary["passed"] += 1
        summary["metrics"][metric_key] = {
            "score": round(score, 4),
            "threshold": threshold,
            "status": status,
        }
    summary["overall"] = "PASS" if summary["passed"] == summary["total"] else "FAIL"

    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return run_dir


# Print summary table
passed_count = print_summary_table(aggregated_eval_metrics)

# Save to directory
results_dir = save_results_json(
    results_individual, aggregated_eval_metrics, start_timestamp
)
print(f"\nResults saved to: {results_dir}")
print("  - full_results.json (query, response, ground_truth + metrics)")
print("  - summary.json (aggregated metrics with pass/fail)")

logger.info(
    "Evaluation completed with %d examples; %d/%d metrics passed.",
    len(results_individual),
    passed_count,
    len(aggregated_metrics),
)
