"""Typed application and evaluation configuration."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GuardrailThresholds:
    """Content-safety severity thresholds. A category triggers at or above its value."""

    hate: int = 4
    self_harm: int = 4
    sexual: int = 4
    violence: int = 4


@dataclass(frozen=True)
class TaskModelConfig:
    """Per-task LLM generation parameters."""

    reasoning_effort: str = "low"
    max_tokens: int = 2000

    def as_model_parameters(self) -> dict:
        """Build the model-parameter dict consumed by send_llm_request."""
        return {
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_tokens,
        }


@dataclass(frozen=True)
class AppConfig:
    """Application defaults configured in code rather than environment variables.

    Chunking and retrieval values control Azure AI Search behavior. Guardrail
    values are minimum Content Safety severity scores that block content.
    Model values identify the Azure Foundry deployments used by the pipeline,
    evaluation, and embedding workflows, while the per-task ``TaskModelConfig``
    entries tune generation parameters for each LLM call.
    """

    # Azure Foundry deployment identity (non-secret model identifiers).
    large_deployed_model: str = "gpt-5.4"
    small_deployed_model: str = "gpt-5.4-mini"
    judge_model: str = "gpt-5.4-mini"
    embedding_deployed_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    large_model_version: str = "2026-03-05"
    small_model_version: str = "2026-03-17"
    embedding_model_version: str = "1"

    # Chunking and indexing.
    chunk_size: int = 1000
    chunk_overlap: int = 100
    # Documents per indexer batch; lower to throttle model calls during indexing.
    indexer_batch_size: int = 10

    # Retrieval.
    number_chunks_retrieve: int = 5
    number_documents_retrieve: int = 5
    # Candidate chunks the vector arm feeds into hybrid fusion/semantic re-ranking.
    k_nearest_neighbors: int = 5
    # Relative importance of vector results during hybrid-search result fusion.
    vector_weight: float = 1.0
    search_mode: Literal["any", "all"] = "any"

    # Generation and output.
    number_suggested_questions: int = 3

    # Content-safety thresholds.
    guardrails: GuardrailThresholds = field(default_factory=GuardrailThresholds)

    # Per-task LLM generation parameters.
    main_agent: TaskModelConfig = field(
        default_factory=lambda: TaskModelConfig(reasoning_effort="low", max_tokens=2000)
    )
    query_refinement: TaskModelConfig = field(
        default_factory=lambda: TaskModelConfig(reasoning_effort="low", max_tokens=200)
    )
    suggested_questions: TaskModelConfig = field(
        default_factory=lambda: TaskModelConfig(reasoning_effort="low", max_tokens=300)
    )
    topic_guardrail: TaskModelConfig = field(
        default_factory=lambda: TaskModelConfig(reasoning_effort="low", max_tokens=20)
    )
    judge: TaskModelConfig = field(
        default_factory=lambda: TaskModelConfig(reasoning_effort="low", max_tokens=800)
    )


@dataclass(frozen=True)
class EvalConfig:
    """Pass/fail thresholds for normalized evaluation metrics."""

    groundedness_threshold: float = 0.6
    relevance_threshold: float = 0.6
    fluency_threshold: float = 0.6
    coherence_threshold: float = 0.6
    similarity_threshold: float = 0.6
    f1_score_threshold: float = 0.5
    retrieval_precision_at_1_threshold: float = 0.5
    retrieval_precision_at_5_threshold: float = 0.5
    retrieval_recall_at_1_threshold: float = 0.5
    retrieval_recall_at_5_threshold: float = 0.7

    @property
    def metric_thresholds(self) -> dict[str, float]:
        """Map evaluation result keys to their pass/fail thresholds."""
        return {
            "groundedness": self.groundedness_threshold,
            "relevance": self.relevance_threshold,
            "fluency": self.fluency_threshold,
            "coherence": self.coherence_threshold,
            "similarity": self.similarity_threshold,
            "f1_score": self.f1_score_threshold,
            "retrieval_precision_at_1": self.retrieval_precision_at_1_threshold,
            "retrieval_precision_at_5": self.retrieval_precision_at_5_threshold,
            "retrieval_recall_at_1": self.retrieval_recall_at_1_threshold,
            "retrieval_recall_at_5": self.retrieval_recall_at_5_threshold,
        }


app_config = AppConfig()
eval_config = EvalConfig()
