"""Claude session extractor — plan §6.

Calls claude-opus-4-7 with the extraction prompt + transcript, validates the JSON
response against SessionExtraction, and returns the structured object.

The Anthropic client is injectable: pass `client=` to the constructor (any
object with a `.messages.create(...)` method returning an object with
`.content[0].text`). Tests pass a fake; runtime passes `anthropic.Anthropic`.

Reuse: this same function backs both `qset-gen ingest-session` and the existing
Fathom progress-report generator (plan §6.3) — one LLM call, two artifacts.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..models import SessionExtraction, SkillTaxonomyEntry
from .prompt import build_system_message


class ExtractionError(Exception):
    """Raised when the model output can't be parsed as the expected schema."""


class SessionExtractor:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-opus-4-7",
        max_tokens: int = 4096,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            from anthropic import Anthropic  # local import — avoid eager dep at module load

            if not api_key:
                raise ValueError("api_key is required when no client is provided")
            self._client = Anthropic(api_key=api_key)

    def extract(self, transcript: str, taxonomy: list[SkillTaxonomyEntry]) -> SessionExtraction:
        """Returns a validated SessionExtraction.

        Raises ExtractionError if the model output can't be parsed as valid JSON
        matching the SessionExtraction schema.
        """
        system = build_system_message(taxonomy)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": transcript}],
        )

        text = _extract_text(response)
        json_payload = _extract_json_object(text)

        try:
            data = json.loads(json_payload)
        except json.JSONDecodeError as e:
            raise ExtractionError(f"Model output was not valid JSON: {e}\n\n--- raw ---\n{text}") from e

        try:
            return SessionExtraction(**data)
        except Exception as e:
            raise ExtractionError(f"Model output didn't match SessionExtraction schema: {e}\n\n--- parsed ---\n{data}") from e


# ----- helpers -----

def _extract_text(response: Any) -> str:
    """Pull plain text out of an Anthropic-style response. The model may return
    multiple content blocks; we concatenate text blocks in order."""
    content = getattr(response, "content", None)
    if content is None:
        raise ExtractionError("Response has no .content")
    pieces: list[str] = []
    for block in content:
        # SDK shape: block.type == "text", block.text == "..."
        text = getattr(block, "text", None)
        if text is not None:
            pieces.append(text)
    if not pieces:
        raise ExtractionError("Response contained no text blocks")
    return "\n".join(pieces).strip()


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> str:
    """Pull the JSON object out of the model's response. Strict prompt asks for
    JSON only, but we tolerate a fenced code block or surrounding prose."""
    fence = _FENCE_RE.search(text)
    if fence:
        return fence.group(1)
    obj = _OBJECT_RE.search(text)
    if obj:
        return obj.group(0)
    return text
