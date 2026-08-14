"""Typed configuration for RAG behavior and model selection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Application defaults configured in code rather than environment variables.

    Chunking and retrieval values control Azure AI Search behavior. Guardrail
    values are minimum Content Safety severity scores that block content.
    Model values identify the Azure Foundry deployments used by the pipeline,
    evaluation, and embedding workflows.
    """

    chunk_size: int = 1000
    chunk_overlap: int = 100
    number_documents_retrieve: int = 5
    k_nearest_neighbors: int = 3
    suggested_questions: int = 3
    hate_guardrail_threshold: int = 4
    self_harm_guardrail_threshold: int = 4
    sexual_guardrail_threshold: int = 4
    violence_guardrail_threshold: int = 4
    large_deployed_model: str = "gpt-5.4"
    small_deployed_model: str = "gpt-5.4-mini"
    judge_model: str = "gpt-5.4-mini"
    embedding_deployed_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    large_model_version: str = "2026-03-05"
    small_model_version: str = "2026-03-17"
    embedding_model_version: str = "1"
    reasoning_effort: str = "low"


config = Config()