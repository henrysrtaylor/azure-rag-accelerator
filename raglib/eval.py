"""RAG evaluation utilities and LLM-as-judge functions.

Provides:
- Retrieval metrics: precision@k, recall@k, f1_score
- LLM-judged metrics: groundedness, relevance, coherence, fluency

LLM judges load prompts from raglib/prompts/evaluation/ and return
structured scores (1-5) with reasoning.
"""

import json

from raglib.azure_ai import send_llm_request
from raglib.prompts.prompts import (
    EVAL_COHERENCE_PROMPT,
    EVAL_FLUENCY_PROMPT,
    EVAL_GROUNDEDNESS_PROMPT,
    EVAL_RELEVANCE_PROMPT,
)


# Evaluation metrics
def precision_recall_at_k(
    retrieved_documents: list[str], ground_truth_documents: list[str], k: int
) -> tuple[float, float]:
    """
    Calculate precision@k and recall@k for retrieval evaluation.

    Args:
        retrieved_documents: Retrieved document titles/identifiers.
        ground_truth_documents: Expected relevant document titles/identifiers.
        k: Number of top results to consider.

    Returns:
        Tuple of (precision@k, recall@k).

    Example:
        >>> precision_recall_at_k(['doc1', 'doc2', 'doc3'], ['doc1', 'doc4'], k=2)
        (0.5, 0.5)  # 1 of 2 retrieved is relevant, 1 of 2 ground truth found
    """
    if k == 0 or len(retrieved_documents) == 0:
        return 0.0, 0.0
    ground_truth_set = set(ground_truth_documents)
    top_k_retrieved = set(retrieved_documents[:k])
    precision = len(ground_truth_set & top_k_retrieved) / k
    recall = (
        len(ground_truth_set & top_k_retrieved) / len(ground_truth_set)
        if ground_truth_set
        else 1.0
    )
    return precision, recall


def f1_score(response: str, ground_truth: str) -> float:
    """
    Calculate token-overlap F1 score between response and ground_truth.

    Args:
        response: The AI-generated answer.
        ground_truth: The expected correct answer.

    Returns:
        F1 score (0-1), harmonic mean of precision and recall.
    """
    response_tokens = set(response.lower().split())
    truth_tokens = set(ground_truth.lower().split())

    if not response_tokens or not truth_tokens:
        return 0.0

    common = response_tokens & truth_tokens
    precision = len(common) / len(response_tokens)
    recall = len(common) / len(truth_tokens)

    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


class LLMJudge:
    """Evaluate RAG responses using an LLM judge model."""

    def __init__(self, deployment: str) -> None:
        self.deployment = deployment

    def groundedness(self, query: str, context: str, response: str) -> dict:
        """Score how well the response is grounded in the provided context."""
        user_content = f"""## Query
{query}

## Context
{context}

## Response
{response}"""
        return self._evaluate(EVAL_GROUNDEDNESS_PROMPT, user_content)

    def relevance(self, query: str, response: str) -> dict:
        """Score how relevant the response is to the query."""
        user_content = f"""## Query
{query}

## Response
{response}"""
        return self._evaluate(EVAL_RELEVANCE_PROMPT, user_content)

    def coherence(self, query: str, response: str) -> dict:
        """Score the logical consistency and flow of the response."""
        user_content = f"""## Query
{query}

## Response
{response}"""
        return self._evaluate(EVAL_COHERENCE_PROMPT, user_content)

    def fluency(self, response: str) -> dict:
        """Score the natural language quality of the response."""
        user_content = f"""## Response
{response}"""
        return self._evaluate(EVAL_FLUENCY_PROMPT, user_content)

    def _evaluate(self, system_prompt: str, user_content: str) -> dict:
        """Send a judge request and return parsed score and reasoning."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            response = send_llm_request(self.deployment, messages)
            response_text = self._parse_response(response)
            result = json.loads(response_text)
            return {
                "score": result.get("score"),
                "reasoning": result.get("reasoning", ""),
            }
        except json.JSONDecodeError as e:
            return {
                "score": None,
                "reasoning": f"JSON parse error: {e}. Raw: {response[:200]}",
            }
        except Exception as e:
            return {"score": None, "reasoning": f"Error: {e}"}

    def _parse_response(self, response: str) -> str:
        """Strip markdown code fences if present."""
        text = response.strip()
        if not text.startswith("```"):
            return text
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        return "\n".join(json_lines)


def normalize_score(score: int, scale: int = 5) -> float:
    """
    Normalize a 1-5 score to 0-1 scale.

    Args:
        score: Raw score (1-5).
        scale: Maximum score value (default 5).

    Returns:
        Normalized score (0-1).
    """
    if score is None:
        return None
    return score / scale
