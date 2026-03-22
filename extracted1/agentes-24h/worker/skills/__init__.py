"""Skills disponíveis para os agentes."""
from .firecrawl import FirecrawlSkill
from .notebooklm import GeminiNotebookSkill, NotebookLMSkill

__all__ = ["FirecrawlSkill", "GeminiNotebookSkill", "NotebookLMSkill"]
