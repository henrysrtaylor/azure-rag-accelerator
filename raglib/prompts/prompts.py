"""Preloaded prompt templates used by RAG services."""

import re

from raglib.config import app_config
from raglib.prompts.markdown_loader import markdown_loader

# Editable use-case background context, shared by the main agent and query
# refinement. Strip HTML editor comments so only the bullets reach the model.
SHARED_CONTEXT_PROMPT = re.sub(
    r"<!--.*?-->", "", markdown_loader("prompt_shared_context"), flags=re.DOTALL
).strip()
MAIN_AGENT_PROMPT = markdown_loader(
    "prompt_main_agent",
    additional_context=SHARED_CONTEXT_PROMPT,
)
QUERY_REFINEMENT_PROMPT = markdown_loader(
    "prompt_query_refinement",
    additional_context=SHARED_CONTEXT_PROMPT,
)
SUGGESTED_QUESTIONS_PROMPT = markdown_loader(
    "prompt_suggested_questions",
    number_suggested_questions=app_config.number_suggested_questions,
)
GUARDRAIL_ONTOPIC_PROMPT = markdown_loader("prompt_guardrail_ontopic")
VERBALISATION_IMAGE_PROMPT = markdown_loader("prompt_verbalisation_image")

EVAL_GROUNDEDNESS_PROMPT = markdown_loader("prompt_eval_groundedness")
EVAL_RELEVANCE_PROMPT = markdown_loader("prompt_eval_relevance")
EVAL_COHERENCE_PROMPT = markdown_loader("prompt_eval_coherence")
EVAL_FLUENCY_PROMPT = markdown_loader("prompt_eval_fluency")
EVAL_SIMILARITY_PROMPT = markdown_loader("prompt_eval_similarity")
