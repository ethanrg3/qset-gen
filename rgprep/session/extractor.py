"""Claude session extractor — plan §6.

Calls claude-opus-4-7 with the extraction prompt + transcript, validates the JSON
response against SessionExtraction, and returns the structured object.

Reuse: this same function backs both `rgprep ingest-session` and the existing
Fathom progress-report generator (plan §6.3) — one LLM call, two artifacts.
"""

from __future__ import annotations

from ..models import SessionExtraction, SkillTaxonomyEntry


class SessionExtractor:
    def __init__(self, *, api_key: str, model: str = "claude-opus-4-7", max_tokens: int = 4096) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def extract(self, transcript: str, taxonomy: list[SkillTaxonomyEntry]) -> SessionExtraction:
        """Returns a validated SessionExtraction. Raises pydantic.ValidationError on bad JSON."""
        raise NotImplementedError
