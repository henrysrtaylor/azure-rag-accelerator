"""Content safety guardrails for user input and model output.

Implements content moderation (hate, violence, etc.), jailbreak detection,
and on-topic classification using Azure Content Safety and LLM-as-judge.
"""
import os

from azure.ai.contentsafety.models import AnalyzeTextOptions, AnalyzeTextOutputType, TextCategory
from azure.core.rest import HttpRequest

from raglib.azure_ai import send_llm_request
from raglib.config import get_content_safety_client
from raglib.prompts.markdown_loader import markdown_loader

prompt_guardrail_ontopic = markdown_loader(
    "prompt_guardrail_ontopic",
    allowed_topics=os.getenv("PARAMETER_ALLOWED_TOPICS", "Any topic")
)
response_inappropriate = markdown_loader("responses/response_inappropriate")
response_jailbreak = markdown_loader("responses/response_jailbreak")
response_offtopic = markdown_loader("responses/response_offtopic")

# Character substitutions for evasion detection (leetspeak, spacing tricks)
REPLACE_WORDS = [("     ", ""), ("    ", ""), ("   ", ""), ("  ", ""), (" ", ""), ("@", "a"), ("3", "e"), ("!", "i"), ("1", "l"), ("$", "s")]


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

    response = content_mod_client.analyze_text(AnalyzeTextOptions(
        text=text_final,
        output_type=AnalyzeTextOutputType.EIGHT_SEVERITY_LEVELS
    ))
        
    hate_result = next(item for item in response.categories_analysis if item.category == TextCategory.HATE)
    self_harm_result = next(item for item in response.categories_analysis if item.category == TextCategory.SELF_HARM)
    sexual_result = next(item for item in response.categories_analysis if item.category == TextCategory.SEXUAL)
    violence_result = next(item for item in response.categories_analysis if item.category == TextCategory.VIOLENCE)

    return {
        "hate": hate_result.severity,
        "self_harm": self_harm_result.severity,
        "sexual": sexual_result.severity,
        "violence": violence_result.severity
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
        json={
            "userPrompt": text,
            "documents": []
        }
    )
    
    response = content_mod_client.send_request(request)
    result = response.json()
    return result['userPromptAnalysis']['attackDetected']


def check_content_safety(user_query: str) -> dict[str, bool]:
    """
    Run content moderation and jailbreak detection on user input.

    Args:
        user_query: The user's query text.

    Returns:
        Dict with 'content_moderation_detected' and 'prompt_injection_detected' bools.
    """
    text_moderation_results = moderate_content(user_query)
    
    hate_guardrail_threshold = int(os.getenv("PARAMETER_HATE_GUARDRAIL_THRESHOLD", "4"))
    selfharm_guardrail_threshold = int(os.getenv("PARAMETER_SELFHARM_GUARDRAIL_THRESHOLD", "4"))
    sexual_guardrail_threshold = int(os.getenv("PARAMETER_SEXUAL_GUARDRAIL_THRESHOLD", "4"))
    violence_guardrail_threshold = int(os.getenv("PARAMETER_VIOLENCE_GUARDRAIL_THRESHOLD", "4"))
    
    content_moderation_detected =  (
        text_moderation_results['hate'] >= hate_guardrail_threshold or 
        text_moderation_results['self_harm'] >= selfharm_guardrail_threshold or 
        text_moderation_results['sexual'] >= sexual_guardrail_threshold or 
        text_moderation_results['violence'] >= violence_guardrail_threshold
    )
    
    prompt_injection_detected = detect_jailbreak(user_query)
                               
    return {
        "content_moderation_detected": content_moderation_detected,
        "prompt_injection_detected": prompt_injection_detected,
    }


def check_topic_relevance(user_query: str, deployment_name: str) -> str:
    """
    Use LLM-as-judge to classify if query is on-topic.

    Args:
        user_query: The user's query text.
        deployment_name: The LLM deployment to use.

    Returns:
        Lowercase classification string (e.g., 'true', 'false', 'off-topic').
    """ 
      
    guardrail_messages = [
        {"role": "system", "content": prompt_guardrail_ontopic},
        {"role": "user", "content": user_query}
    ]
    return send_llm_request(deployment_name, guardrail_messages).strip().lower()


def check_user_guardrails(user_query: str) -> dict[str, bool | str | None]:
    """
    Run all guardrail checks on user query.

    Args:
        user_query: The user's query text.

    Returns:
        Dict with 'guardrail_triggered' (bool), 'guardrail_type' (str|None),
        and 'guardrail_answer' (str|None).
    """   
    guardrail_results = check_content_safety(user_query)
    on_topic = check_topic_relevance(user_query, os.getenv("AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL"))
    
    if guardrail_results['content_moderation_detected']:
        guardrail_answer = response_inappropriate
        guardrail_type = "inappropriate_text"
        
    elif guardrail_results['prompt_injection_detected']:
        guardrail_answer = response_jailbreak
        guardrail_type = "jailbreak_attempt"
        
    elif on_topic in ("false", "no", "0", "off-topic", "off topic", "not relevant", "not related", "irrelevant"):
        guardrail_answer = response_offtopic
        guardrail_type = "off_topic_query"
        
    else:
        return {
            "guardrail_triggered": False,
            "guardrail_type": None,
            "guardrail_answer": None,
        }
        
    return {
        "guardrail_triggered": True,
        "guardrail_type": guardrail_type,
        "guardrail_answer": guardrail_answer,
    }


def check_model_guardrails(model_answer: str) -> dict[str, bool | str | None]:
    """
    Run guardrail checks on LLM model output.

    Args:
        model_answer: The model's response text.

    Returns:
        Dict with 'guardrail_triggered' (bool), 'guardrail_type' (str|None),
        and 'guardrail_answer' (str|None).
    """   
    guardrail_results = check_content_safety(model_answer)
    
    if guardrail_results['content_moderation_detected']:
        return {
            "guardrail_triggered": True,
            "guardrail_type": "inappropriate_text",
            "guardrail_answer": response_inappropriate,
        }
        
    return {
        "guardrail_triggered": False,
        "guardrail_type": None,
        "guardrail_answer": None,
    }
