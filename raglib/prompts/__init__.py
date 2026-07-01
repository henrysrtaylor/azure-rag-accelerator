"""Prompts package for raglib.

This package provides utilities for loading and formatting markdown prompt templates.
Prompts are stored in raglib/prompts/agent/ and support variable substitution.

Usage:
    from raglib.prompts import markdown_loader
    
    # Simple load
    prompt = markdown_loader("prompt_main_agent")
    
    # Load response template
    response = markdown_loader("responses/response_jailbreak")
"""
from raglib.prompts.markdown_loader import markdown_loader

__all__ = ["markdown_loader"]
