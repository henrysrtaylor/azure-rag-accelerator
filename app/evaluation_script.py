"""RAG evaluation script using Azure AI Evaluation SDK.

Runs the RAG pipeline against a golden dataset and computes metrics:
groundedness, similarity, relevance, fluency, coherence, F1, and retrieval precision/recall.
"""
import json
import os
import re
import tempfile
import time

import numpy as np
from azure.ai.evaluation import (
    CoherenceEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    SimilarityEvaluator,
    evaluate,
)

from raglib.config import get_blob_container_client, load_env_vars
from raglib.log import log_message
from raglib.permissions import build_security_filter
from raglib.pipeline import evaluation_chat_logic

load_env_vars()

log_enabled = True
print_log_enabled = True
log_tag = "evaluation_metrics"
start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

container_client = get_blob_container_client(os.getenv("BLOB_CONTAINER_NAME_EVAL"))
blob_client = container_client.get_blob_client(os.getenv("BLOB_DOCUMENT_NAME_EVAL"))
streamdownloader = blob_client.download_blob()
re_pattern = r'\{[^{}]*\}'
download_ = streamdownloader.readall().decode('utf-8').replace("\r", " ").replace("\n", " ")
qna_set = [json.loads(line) for line in re.findall(re_pattern, download_)]

threshold = 3
model_config = {
    "type": "azure_openai",
    "azure_endpoint": os.getenv("AZURE_FOUNDRY_ENDPOINT"),
    "azure_deployment": os.getenv("AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL"),
    "api_version": os.getenv("AZURE_FOUNDRY_API_VERSION"),
}
evaluators = {
    "groundedness": {
        "evaluator": GroundednessEvaluator(model_config, threshold=threshold),
        "column_mapping": {"response": "${data.response}", "context": "${data.context}"}
    },
    "similarity": {
        "evaluator": SimilarityEvaluator(model_config, threshold=threshold),
        "column_mapping": {"response": "${data.response}", "ground_truth": "${data.ground_truth}"}
    },
    "f1_score": {
        "evaluator": F1ScoreEvaluator(),
        "column_mapping": {"response": "${data.response}", "ground_truth": "${data.ground_truth}"}
    },
    "relevance": {
        "evaluator": RelevanceEvaluator(model_config, threshold=threshold),
        "column_mapping": {"query": "${data.query}", "response": "${data.response}"}
    },
    "fluency": {
        "evaluator": FluencyEvaluator(model_config, threshold=threshold),
        "column_mapping": {"response": "${data.response}"}
    },
    "coherence": {
        "evaluator": CoherenceEvaluator(model_config, threshold=threshold),
        "column_mapping": {"response": "${data.response}"}
    }
}


def precision_recall_at_k(
    response_documents: list[str],
    ground_truth_documents: list[str],
    k: int
) -> tuple[float, float]:
    """
    Calculate precision@k and recall@k for retrieval evaluation.

    Args:
        response_documents: Retrieved document titles.
        ground_truth_documents: Expected relevant document titles.
        k: Number of top results to consider.

    Returns:
        Tuple of (precision@k, recall@k).
    """
    if k == 0 or len(response_documents) == 0:
        return 0.0, 0.0
    ground_truth_set = set(ground_truth_documents)
    top_k_responses = set(response_documents[:k])
    precision = len(ground_truth_set & top_k_responses) / k
    recall = len(ground_truth_set & top_k_responses) / len(ground_truth_set)
    return precision, recall


latency_results: list[float] = []
retrieval_results: list[list[float]] = []
eval_golden_dataset_enhanced: list[dict] = []
security_filter = build_security_filter(None)

for eval_example in qna_set:
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
    'similarity.gpt_similarity',
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
    "similarity.similarity_result",
    "f1_score.f1_result",
    "relevance.relevance_result",
    "relevance.relevance_reason",
    "fluency.fluency_result",
    "fluency.fluency_reason",
    "coherence.coherence_result",
    "coherence.coherence_reason",
])

eval_metrics = [
    {key: d[key] / 5.0 if key in normalise_llm_judgement else d[key] for key in tracked_metrics}
    for d in results_individual
]

aggregated_eval_metrics = {
    k: float(np.mean([d[k] for d in eval_metrics if k in d and d[k] is not None]))
    for k in aggregated_metrics
}

for idx, metrics in enumerate(eval_metrics):
    print(f"\nExample {idx + 1} metrics:")
    for metric, value in metrics.items():
        print(f"{metric}: {value}")

properties = {
    'tag': log_tag,
    'start_timestamp': start_timestamp,
    'end_timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    **aggregated_eval_metrics
}
log_message(
    should_log=log_enabled,
    print_message=print_log_enabled,
    message=f"Evaluation completed with {len(eval_metrics)} examples.",
    level=20,
    additional_properties=properties
)