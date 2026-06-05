"""RAG evaluation script using Azure AI Evaluation SDK.

Runs the RAG pipeline against a golden dataset and computes metrics:
groundedness, relevance, fluency, coherence, F1, and retrieval precision/recall.
"""
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np
from tqdm import tqdm
from azure.ai.evaluation import (
    CoherenceEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    evaluate,
)

from eval_config import SDK_LLM_THRESHOLD, METRIC_THRESHOLDS
from raglib.config import load_env_vars
from raglib.eval import precision_recall_at_k
from raglib.log import log_message
from raglib.permissions import build_security_filter
from raglib.pipeline import evaluation_chat_logic

load_env_vars()

OUTPUT_DIR = Path(__file__).parent / "output"

log_enabled = True
print_log_enabled = True
log_tag = "evaluation_metrics"
start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

# Load from local JSON file
LOCAL_DATASET_PATH = Path(__file__).parent.parent / "data" / "evaluation" / "example_golden_dataset.json"
with open(LOCAL_DATASET_PATH, 'r', encoding='utf-8') as f:
    qna_set = json.load(f)

model_config = {
    "type": "azure_openai",
    "azure_endpoint": os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    "azure_deployment": os.getenv("AZURE_FOUNDRY_JUDGE_MODEL"),
    "api_version": os.getenv("AZURE_FOUNDRY_API_VERSION"),
}
evaluators = {
    "groundedness": {
        "evaluator": GroundednessEvaluator(model_config, threshold=SDK_LLM_THRESHOLD),
        "column_mapping": {"response": "${data.response}", "context": "${data.context}"}
    },
    "f1_score": {
        "evaluator": F1ScoreEvaluator(),
        "column_mapping": {"response": "${data.response}", "ground_truth": "${data.ground_truth}"}
    },
    "relevance": {
        "evaluator": RelevanceEvaluator(model_config, threshold=SDK_LLM_THRESHOLD),
        "column_mapping": {"query": "${data.query}", "response": "${data.response}"}
    },
    "fluency": {
        "evaluator": FluencyEvaluator(model_config, threshold=SDK_LLM_THRESHOLD),
        "column_mapping": {"response": "${data.response}"}
    },
    "coherence": {
        "evaluator": CoherenceEvaluator(model_config, threshold=SDK_LLM_THRESHOLD),
        "column_mapping": {"response": "${data.response}"}
    }
}


latency_results: list[float] = []
retrieval_results: list[list[float]] = []
eval_golden_dataset_enhanced: list[dict] = []
security_filter = build_security_filter(None)

print(f"\nRunning RAG evaluation on {len(qna_set)} examples...\n")

for eval_example in tqdm(qna_set, desc="Evaluating", unit="query"):
    query = eval_example.get("query", "")
    ground_truth_documents = eval_example.get("ground_truth_documents", [])

    chat_history = [
        {"role": "assistant", "content": "Hello! I'm your RAG assistant. How can I help you today?"},
        {"role": "user", "content": query}
    ]

    start_time = time.time()
    chat_response = evaluation_chat_logic(
        chat_history,
        security_filter=security_filter
    )
    answer = chat_response.get("assistant_message", {"content": ""}).get("content", "")
    context = chat_response.get("document_context", "")
    titles = [ref['text'] for ref in chat_response.get("references", [])]
    end_time = time.time()

    latency_results.append(end_time - start_time)

    precision_at_1, recall_at_1 = precision_recall_at_k(list(set(titles)), list(set(ground_truth_documents)), 1)
    precision_at_5, recall_at_5 = precision_recall_at_k(list(set(titles)), list(set(ground_truth_documents)), 5)
    retrieval_results.append([precision_at_1, precision_at_5, recall_at_1, recall_at_5])

    eval_example["response"] = answer
    eval_example["context"] = context
    eval_example["retrieved_documents"] = titles
    eval_golden_dataset_enhanced.append(eval_example)

with tempfile.NamedTemporaryFile(mode="w+", suffix=".jsonl", delete=False) as tmp_file:
    for item in eval_golden_dataset_enhanced:
        tmp_file.write(json.dumps(item) + "\n")

    print(f"\n\nStarting evaluation using temp file: {tmp_file.name}\n\n")
    results = evaluate(
        data=tmp_file.name,
        evaluators={k: v["evaluator"] for k, v in evaluators.items()},
        evaluator_config={k: v["column_mapping"] for k, v in evaluators.items()},
    )
os.remove(tmp_file.name)

results_individual = results.get("rows", [])
results_individual = [
    {k.replace("outputs.", "", 1) if k.startswith("outputs.") else k: v for k, v in d.items()}
    for d in results_individual
]
for i, d in enumerate(results_individual):
    d["latency_seconds"] = latency_results[i]
    d["retrieval_precision_at_1"] = retrieval_results[i][0]
    d["retrieval_precision_at_5"] = retrieval_results[i][1]
    d["retrieval_recall_at_1"] = retrieval_results[i][2]
    d["retrieval_recall_at_5"] = retrieval_results[i][3]

normalise_llm_judgement = [
    'groundedness.gpt_groundedness',
    'relevance.gpt_relevance',
    'fluency.gpt_fluency',
    'coherence.gpt_coherence',
]

aggregated_metrics = sorted(normalise_llm_judgement + [
    'f1_score.f1_score',
    'retrieval_precision_at_1',
    'retrieval_precision_at_5',
    'retrieval_recall_at_1',
    'retrieval_recall_at_5'
])

tracked_metrics = sorted(aggregated_metrics + [
    "groundedness.groundedness_result",
    "groundedness.groundedness_reason",
    "f1_score.f1_result",
    "relevance.relevance_result",
    "relevance.relevance_reason",
    "fluency.fluency_result",
    "fluency.fluency_reason",
    "coherence.coherence_result",
    "coherence.coherence_reason",
])

eval_metrics = [
    {key: d.get(key, None) / 5.0 if key in normalise_llm_judgement and d.get(key) is not None 
     else d.get(key, None) for key in tracked_metrics}
    for d in results_individual
]

aggregated_eval_metrics = {
    k: float(np.mean([d[k] for d in eval_metrics if k in d and d[k] is not None]))
    for k in aggregated_metrics
}


def print_summary_table(metrics: dict) -> int:
    """Print a formatted summary table with pass/fail status. Returns count of passed metrics."""
    print("\n" + "=" * 65)
    print("                    EVALUATION SUMMARY")
    print("=" * 65)
    print(f"{'Metric':<30} {'Score':>8} {'Threshold':>10} {'Status':>10}")
    print("-" * 65)

    passed = 0
    friendly_names = {
        'groundedness.gpt_groundedness': 'Groundedness',
        'relevance.gpt_relevance': 'Relevance',
        'fluency.gpt_fluency': 'Fluency',
        'coherence.gpt_coherence': 'Coherence',
        'f1_score.f1_score': 'F1 Score',
        'retrieval_precision_at_1': 'Precision@1',
        'retrieval_precision_at_5': 'Precision@5',
        'retrieval_recall_at_1': 'Recall@1',
        'retrieval_recall_at_5': 'Recall@5',
    }

    for metric_key in aggregated_metrics:
        score = metrics.get(metric_key, 0)
        threshold = METRIC_THRESHOLDS.get(metric_key, 0.5)
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


def save_results_json(metrics_list: list[dict], aggregated: dict, dataset: list[dict], timestamp: str) -> Path:
    """Save detailed results and summary to timestamped directory as JSON."""
    dir_name = timestamp.replace(':', '-').replace(' ', '_')
    run_dir = OUTPUT_DIR / dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Full results with query/response/ground_truth + all metrics
    full_results = []
    for i, metrics in enumerate(metrics_list):
        result = {
            'query': dataset[i].get('query', ''),
            'response': dataset[i].get('response', ''),
            'ground_truth': dataset[i].get('ground_truth', ''),
            'context': dataset[i].get('context', ''),
            'retrieved_documents': dataset[i].get('retrieved_documents', []),
            'latency_seconds': results_individual[i].get('latency_seconds', 0),
            'metrics': metrics
        }
        full_results.append(result)

    with open(run_dir / "full_results.json", 'w', encoding='utf-8') as f:
        json.dump(full_results, f, indent=2)

    # Aggregated summary
    summary = {
        'timestamp': timestamp,
        'total_examples': len(metrics_list),
        'metrics': {},
        'passed': 0,
        'total': len(aggregated_metrics),
        'overall': 'FAIL'
    }
    for metric_key in aggregated_metrics:
        score = aggregated.get(metric_key, 0)
        threshold = METRIC_THRESHOLDS.get(metric_key, 0.5)
        status = 'PASS' if score >= threshold else 'FAIL'
        if status == 'PASS':
            summary['passed'] += 1
        summary['metrics'][metric_key] = {
            'score': round(score, 4),
            'threshold': threshold,
            'status': status
        }
    summary['overall'] = 'PASS' if summary['passed'] == summary['total'] else 'FAIL'

    with open(run_dir / "summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return run_dir


# Print summary table
passed_count = print_summary_table(aggregated_eval_metrics)

# Save to directory
results_dir = save_results_json(eval_metrics, aggregated_eval_metrics, eval_golden_dataset_enhanced, start_timestamp)
print(f"\nResults saved to: {results_dir}")
print(f"  - full_results.json (query, response, ground_truth + metrics)")
print(f"  - summary.json (aggregated metrics with pass/fail)")

# Log to Application Insights
properties = {
    'tag': log_tag,
    'start_timestamp': start_timestamp,
    'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    'passed_metrics': passed_count,
    'total_metrics': len(aggregated_metrics),
    **aggregated_eval_metrics
}
log_message(
    should_log=log_enabled,
    print_message=print_log_enabled,
    message=f"Evaluation completed with {len(eval_metrics)} examples.",
    level=20,
    additional_properties=properties
)