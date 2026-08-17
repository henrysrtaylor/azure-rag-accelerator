"""Preloaded prompt templates used by RAG services."""

from raglib.config import app_config
from raglib.prompts.markdown_loader import markdown_loader

MAIN_AGENT_PROMPT = markdown_loader("prompt_main_agent")
QUERY_REFINEMENT_PROMPT = markdown_loader("prompt_query_refinement")
SUGGESTED_QUESTIONS_PROMPT = markdown_loader(
    "prompt_suggested_questions",
    number_suggested_questions=app_config.suggested_questions,
)
GUARDRAIL_ONTOPIC_PROMPT = markdown_loader("prompt_guardrail_ontopic")
VERBALISATION_IMAGE_PROMPT = markdown_loader("prompt_verbalisation_image")

EVAL_GROUNDEDNESS_PROMPT = markdown_loader("prompt_eval_groundedness")
EVAL_RELEVANCE_PROMPT = markdown_loader("prompt_eval_relevance")
EVAL_COHERENCE_PROMPT = markdown_loader("prompt_eval_coherence")
EVAL_FLUENCY_PROMPT = markdown_loader("prompt_eval_fluency")
