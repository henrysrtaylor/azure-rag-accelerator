"""Preloaded response templates."""

from raglib.prompts.markdown_loader import markdown_loader

EMPTY_QUERY_RESPONSE = markdown_loader("responses/response_empty_query")
FAILURE_RESPONSE = markdown_loader("responses/response_failure")
GUARDRAIL_RESPONSE = markdown_loader("responses/response_guardrail")
