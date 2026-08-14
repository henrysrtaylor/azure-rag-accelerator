"""Content safety guardrails for user input and model output.

Implements content moderation (hate, violence, etc.), jailbreak detection,
and on-topic classification using Azure Content Safety and LLM-as-judge.
"""

import os

from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    AnalyzeTextOutputType,
    TextCategory,
)
from azure.core.rest import HttpRequest

from raglib.azure_ai import send_llm_request
from raglib.clients import get_content_safety_client
from raglib.config import config
from raglib.prompts.markdown_loader import markdown_loader

prompt_guardrail_ontopic = markdown_loader("prompt_guardrail_ontopic")

# Character substitutions for evasion detection (leetspeak, spacing tricks)
REPLACE_WORDS = [
    ("     ", ""),
    ("    ", ""),
    ("   ", ""),
    ("  ", ""),
    (" ", ""),
    ("@", "a"),
    ("3", "e"),
    ("!", "i"),
    ("1", "l"),
    ("$", "s"),
]


def moderate_content(text: str) -> dict[str, int]:
    """
    Analyze text for harmful content using Azure Content Safety.

    Args:
        text: The text to analyze.

    Returns:
        Dict with severity scores (0-7) for 'hate', 'self_harm', 'sexual', 'violence'.
    """
    content_mod_client = get_content_safety_client()

    text_replaced = text.lower().strip()
    for old, new in REPLACE_WORDS:
        text_replaced = text_replaced.replace(old, new)
    text_final = f"{text} {text_replaced}"

    response = content_mod_client.analyze_text(
        AnalyzeTextOptions(
            text=text_final, output_type=AnalyzeTextOutputType.EIGHT_SEVERITY_LEVELS
        )
    )

    hate_result = next(
        item
        for item in response.categories_analysis
        if item.category == TextCategory.HATE
    )
    self_harm_result = next(
        item
        for item in response.categories_analysis
        if item.category == TextCategory.SELF_HARM
    )
    sexual_result = next(
        item
        for item in response.categories_analysis
        if item.category == TextCategory.SEXUAL
    )
    violence_result = next(
        item
        for item in response.categories_analysis
        if item.category == TextCategory.VIOLENCE
    )

    return {
        "hate": hate_result.severity,
        "self_harm": self_harm_result.severity,
        "sexual": sexual_result.severity,
        "violence": violence_result.severity,
    }


def detect_jailbreak(text: str) -> bool:
    """
    Detect prompt injection or jailbreak attempts using Azure Content Safety.

    Args:
        text: The text to analyze.

    Returns:
        True if an attack was detected, False otherwise.
    """
    content_mod_client = get_content_safety_client()
    content_mod_endpoint = os.getenv("AZURE_CONTENT_MODERATOR_ENDPOINT")
    api_version = os.getenv("AZURE_CONTENT_MODERATOR_API_VERSION", "2024-09-01")

    request = HttpRequest(
        method="POST",
        url=f"{content_mod_endpoint}/contentsafety/text:shieldPrompt?api-version={api_version}",
        json={"userPrompt": text, "documents": []},
    )

    response = content_mod_client.send_request(request)
    result = response.json()
    return result["userPromptAnalysis"]["attackDetected"]


def _is_content_moderation_detected(text: str) -> bool:
    """
    Check whether text crosses content moderation thresholds.

    Args:
        text: Input text.

    Returns:
        True when any category meets or exceeds configured thresholds.
    """
    text_moderation_results = moderate_content(text)

    return (
        text_moderation_results["hate"] >= config.hate_guardrail_threshold
        or text_moderation_results["self_harm"] >= config.self_harm_guardrail_threshold
        or text_moderation_results["sexual"] >= config.sexual_guardrail_threshold
        or text_moderation_results["violence"] >= config.violence_guardrail_threshold
    )


def _is_off_topic(user_query: str, deployment_name: str) -> bool:
    """
    Use LLM-as-judge to classify if query is off-topic.

    Args:
        user_query: The user's query text.
        deployment_name: The LLM deployment to use.

    Returns:
        True when the query is classified as off-topic.
    """

    guardrail_messages = [
        {"role": "system", "content": prompt_guardrail_ontopic},
        {"role": "user", "content": user_query},
    ]
    on_topic = send_llm_request(deployment_name, guardrail_messages).strip().lower()
    return on_topic in (
        "false",
        "no",
        "0",
        "off-topic",
        "off topic",
        "not relevant",
        "not related",
        "irrelevant",
    )


def _run_guardrails(query: str, check_prompt_and_topic: bool) -> dict[str, bool]:
    """Run guardrail checks and return detection flags."""
    content_moderation_detected = _is_content_moderation_detected(query)

    if not check_prompt_and_topic:
        return {
            "content_moderation_detected": content_moderation_detected,
        }

    prompt_injection_detected = detect_jailbreak(query)
    off_topic_detected = _is_off_topic(query, config.large_deployed_model)

    return {
        "content_moderation_detected": content_moderation_detected,
        "prompt_injection_detected": prompt_injection_detected,
        "off_topic_detected": off_topic_detected,
    }


def guardrails(query: str, model: bool = False) -> dict[str, bool | str | None]:
    """
    Run guardrail checks for user input or model output.

    Args:
        query: Text to evaluate.
        model: When True, run model-output checks only.

    Returns:
        Dict with 'guardrail_triggered' (bool) and 'guardrail_type' (str|None).
    """
    guardrail_results = _run_guardrails(query, check_prompt_and_topic=not model)

    if guardrail_results["content_moderation_detected"]:
        guardrail_type = "inappropriate_text"

    elif not model and guardrail_results["prompt_injection_detected"]:
        guardrail_type = "jailbreak_attempt"

    elif not model and guardrail_results["off_topic_detected"]:
        guardrail_type = "off_topic_query"

    else:
        return {
            "guardrail_triggered": False,
            "guardrail_type": None,
        }

    return {
        "guardrail_triggered": True,
        "guardrail_type": guardrail_type,
    }
