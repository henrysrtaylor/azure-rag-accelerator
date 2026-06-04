"""Markdown template loader with variable substitution.

Loads prompt and response templates from markdown/ directory, supporting
{variable_name} placeholders via Python's str.format().
"""
from pathlib import Path


def markdown_loader(name: str, **kwargs: str) -> str:
    """
    Load a markdown template and substitute variables.

    Args:
        name: Template name (without .md extension), e.g., "prompt_main_agent"
              or "responses/response_jailbreak".
        **kwargs: Variables to substitute in the template.

    Returns:
        Template content with variables substituted.

    Raises:
        FileNotFoundError: If template file doesn't exist.

    Example:
        >>> markdown_loader("prompt_main_agent", allowed_topics="Topic A, Topic B")
    """
    prompts_dir = Path(__file__).parent / "markdown"
    path = prompts_dir / f"{name}.md"
    
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    
    content = path.read_text(encoding="utf-8")
    
    if kwargs:
        content = content.format(**kwargs)
    
    return content
