"""
Prompt package initializer.

Expose shared prompt builders for LLM interactions so Lambda handlers can
import them with a stable path.
"""

from .medical_search import (  # noqa: F401
    MEDICAL_SEARCH_SYSTEM_PROMPT,
    MEDICAL_SEARCH_USER_TEMPLATE,
    build_medical_search_prompts,
)


