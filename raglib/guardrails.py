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
from raglib.config import AppConfig, app_config
from raglib.prompts.prompts import GUARDRAIL_ONTOPIC_PROMPT


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


class GuardrailEvaluator:
    """Evaluate user input and model output against configured guardrails."""

    def __init__(self, config: AppConfig = app_config) -> None:
        self.config = config

    def moderate_content(self, text: str) -> dict[str, int]:
        """Analyze text for harmful content using Azure Content Safety."""
        content_mod_client = get_content_safety_client()

        text_replaced = text.lower().strip()
        for old, new in REPLACE_WORDS:
            text_replaced = text_replaced.replace(old, new)
        text_final = f"{text} {text_replaced}"

        response = content_mod_client.analyze_text(
            AnalyzeTextOptions(
                text=text_final,
                output_type=AnalyzeTextOutputType.EIGHT_SEVERITY_LEVELS,
            )
        )

        severities = {
            item.category: item.severity for item in response.categories_analysis
        }
        return {
            "hate": severities[TextCategory.HATE],
            "self_harm": severities[TextCategory.SELF_HARM],
            "sexual": severities[TextCategory.SEXUAL],
            "violence": severities[TextCategory.VIOLENCE],
        }

    def detect_jailbreak(self, text: str) -> bool:
        """Detect prompt injection or jailbreak attempts."""
        content_mod_client = get_content_safety_client()
        content_mod_endpoint = os.getenv("AZURE_CONTENT_MODERATOR_ENDPOINT")
        api_version = os.getenv(
            "AZURE_CONTENT_MODERATOR_API_VERSION",
            "2024-09-01",
        )

        request = HttpRequest(
            method="POST",
            url=(
                f"{content_mod_endpoint}/contentsafety/text:shieldPrompt"
                f"?api-version={api_version}"
            ),
            json={"userPrompt": text, "documents": []},
        )

        response = content_mod_client.send_request(request)
        return response.json()["userPromptAnalysis"]["attackDetected"]

    def _is_content_moderation_detected(self, text: str) -> bool:
        """Check whether text crosses configured moderation thresholds."""
        results = self.moderate_content(text)
        return (
            results["hate"] >= self.config.hate_guardrail_threshold
            or results["self_harm"] >= self.config.self_harm_guardrail_threshold
            or results["sexual"] >= self.config.sexual_guardrail_threshold
            or results["violence"] >= self.config.violence_guardrail_threshold
        )

    def _is_off_topic(self, user_query: str) -> bool:
        """Use the configured LLM to classify whether a query is off-topic."""
        messages = [
            {"role": "system", "content": GUARDRAIL_ONTOPIC_PROMPT},
            {"role": "user", "content": user_query},
        ]
        on_topic = send_llm_request(
            self.config.large_deployed_model,
            messages,
        ).strip().lower()
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

    def _run_checks(
        self,
        query: str,
        check_prompt_and_topic: bool,
    ) -> dict[str, bool]:
        """Run applicable checks and return their detection flags."""
        results = {
            "content_moderation_detected": self._is_content_moderation_detected(
                query
            )
        }
        if check_prompt_and_topic:
            results["prompt_injection_detected"] = self.detect_jailbreak(query)
            results["off_topic_detected"] = self._is_off_topic(query)
        return results

    def check_input(self, query: str) -> dict[str, bool | str | None]:
        """Run content, jailbreak, and topic checks for user input."""
        results = self._run_checks(query, check_prompt_and_topic=True)
        return self._to_result(results, include_input_checks=True)

    def check_output(self, query: str) -> dict[str, bool | str | None]:
        """Run content moderation checks for model output."""
        results = self._run_checks(query, check_prompt_and_topic=False)
        return self._to_result(results, include_input_checks=False)

    def _to_result(
        self,
        results: dict[str, bool],
        include_input_checks: bool,
    ) -> dict[str, bool | str | None]:
        if results["content_moderation_detected"]:
            guardrail_type = "inappropriate_text"
        elif include_input_checks and results["prompt_injection_detected"]:
            guardrail_type = "jailbreak_attempt"
        elif include_input_checks and results["off_topic_detected"]:
            guardrail_type = "off_topic_query"
        else:
            return {"guardrail_triggered": False, "guardrail_type": None}

        return {"guardrail_triggered": True, "guardrail_type": guardrail_type}
