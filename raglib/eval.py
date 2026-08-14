"""RAG evaluation utilities and LLM-as-judge functions.

Provides:
- Retrieval metrics: precision@k, recall@k, f1_score
- LLM-judged metrics: groundedness, relevance, coherence, fluency

LLM judges load prompts from raglib/prompts/evaluation/ and return
structured scores (1-5) with reasoning.
"""
import json
from typing import Optional

from raglib.azure_ai import send_llm_request
from raglib.config import config
from raglib.prompts.markdown_loader import markdown_loader

# Evaluation metrics
def precision_recall_at_k(
    retrieved_documents: list[str],
    ground_truth_documents: list[str],
    k: int
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
    recall = len(ground_truth_set & top_k_retrieved) / len(ground_truth_set) if ground_truth_set else 1.0
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


# LLM Judge Helpers
# Note: _call_judge exists to handle JSON response parsing in one place.
# LLMs may wrap JSON in markdown code blocks (```json...```) which must be stripped,
# and we need consistent error handling when parsing fails. Without this helper,
# we'd duplicate ~25 lines of parsing logic in each judge function.
def _call_judge(system_prompt: str, user_content: str) -> dict:
    """
    Call the LLM judge and parse the JSON response.
    
    Args:
        system_prompt: The evaluation criteria and instructions.
        user_content: The content to evaluate (query, response, context, etc.).
        
    Returns:
        Dict with 'score' (1-5) and 'reasoning' keys.
        Returns {'score': None, 'reasoning': 'Error: ...'} on failure.
    """
    deployment = config.judge_model
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        response = send_llm_request(deployment, messages)
        
        # Try to parse JSON from response
        # Handle potential markdown code blocks
        response_text = response.strip()
        if response_text.startswith("```"):
            # Extract content between code fences
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)
        
        result = json.loads(response_text)
        return {
            "score": result.get("score"),
            "reasoning": result.get("reasoning", "")
        }
    except json.JSONDecodeError as e:
        return {"score": None, "reasoning": f"JSON parse error: {e}. Raw: {response[:200]}"}
    except Exception as e:
        return {"score": None, "reasoning": f"Error: {e}"}


# LLM Judge Functions
def judge_groundedness(
    query: str,
    context: str,
    response: str
) -> dict:
    """
    Evaluate whether the response is grounded in the provided context.
    
    Args:
        query: The user's question.
        context: The retrieved context/documents.
        response: The AI-generated answer.
        
    Returns:
        Dict with 'score' (1-5, where 5=fully grounded) and 'reasoning'.
    """
    system_prompt = markdown_loader("prompt_eval_groundedness")
    
    user_content = f"""## Query
{query}

## Context
{context}

## Response
{response}"""
    
    return _call_judge(system_prompt, user_content)


def judge_relevance(
    query: str,
    response: str
) -> dict:
    """
    Evaluate whether the response is relevant to the user's query.
    
    Args:
        query: The user's question.
        response: The AI-generated answer.
        
    Returns:
        Dict with 'score' (1-5, where 5=highly relevant) and 'reasoning'.
    """
    system_prompt = markdown_loader("prompt_eval_relevance")
    
    user_content = f"""## Query
{query}

## Response
{response}"""
    
    return _call_judge(system_prompt, user_content)


def judge_coherence(
    query: str,
    response: str
) -> dict:
    """
    Evaluate the logical consistency and flow of the response.
    
    Args:
        query: The user's question (for context).
        response: The AI-generated answer.
        
    Returns:
        Dict with 'score' (1-5, where 5=perfectly coherent) and 'reasoning'.
    """
    system_prompt = markdown_loader("prompt_eval_coherence")
    
    user_content = f"""## Query
{query}

## Response
{response}"""
    
    return _call_judge(system_prompt, user_content)


def judge_fluency(
    response: str
) -> dict:
    """
    Evaluate the natural language quality of the response.
    
    Args:
        response: The AI-generated answer.
        
    Returns:
        Dict with 'score' (1-5, where 5=excellent fluency) and 'reasoning'.
    """
    system_prompt = markdown_loader("prompt_eval_fluency")
    
    user_content = f"""## Response
{response}"""
    
    return _call_judge(system_prompt, user_content)


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
