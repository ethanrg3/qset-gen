"""Session extractor tests — uses a fake Anthropic client so no API calls happen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from qset_gen.models import SessionExtraction, SkillTaxonomyEntry
from qset_gen.session.extractor import ExtractionError, SessionExtractor


@dataclass
class _Block:
    text: str


@dataclass
class _Response:
    content: list[_Block]


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.last_call: dict[str, Any] | None = None

    def create(self, **kwargs) -> _Response:
        self.last_call = kwargs
        return _Response(content=[_Block(text=self.response_text)])


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeMessages(response_text)


TAXONOMY = [
    SkillTaxonomyEntry(skill_id="geo_circles", name="Circles"),
    SkillTaxonomyEntry(skill_id="alg_quadratics", name="Quadratics"),
]


def _extractor(response_text: str) -> tuple[SessionExtractor, _FakeClient]:
    client = _FakeClient(response_text)
    return SessionExtractor(model="claude-opus-4-7", client=client), client


def test_extract_returns_valid_pydantic_model():
    payload = {
        "skills_practiced": ["geo_circles"],
        "skills_struggled": ["geo_circles"],
        "skills_introduced": [],
        "skills_mastered_today": [],
        "misconceptions": ["confuses radius with diameter in area formula"],
        "homework_directives": ["practice 10 circle problems this week"],
    }
    extractor, _ = _extractor(json.dumps(payload))
    result = extractor.extract("transcript text", TAXONOMY)
    assert isinstance(result, SessionExtraction)
    assert result.skills_struggled == ["geo_circles"]
    assert "diameter" in result.misconceptions[0]


def test_extract_tolerates_fenced_code_block():
    payload = {"skills_practiced": ["alg_quadratics"], "skills_struggled": [],
               "skills_introduced": [], "skills_mastered_today": [],
               "misconceptions": [], "homework_directives": []}
    wrapped = f"Here's the result:\n```json\n{json.dumps(payload)}\n```\n"
    extractor, _ = _extractor(wrapped)
    result = extractor.extract("transcript", TAXONOMY)
    assert result.skills_practiced == ["alg_quadratics"]


def test_extract_tolerates_surrounding_prose():
    payload = {"skills_practiced": [], "skills_struggled": ["geo_circles"],
               "skills_introduced": [], "skills_mastered_today": [],
               "misconceptions": [], "homework_directives": []}
    text = f"Sure, here you go: {json.dumps(payload)} — let me know if you need more."
    extractor, _ = _extractor(text)
    result = extractor.extract("transcript", TAXONOMY)
    assert result.skills_struggled == ["geo_circles"]


def test_extract_empty_lists_for_silent_categories():
    payload = {"skills_practiced": [], "skills_struggled": [], "skills_introduced": [],
               "skills_mastered_today": [], "misconceptions": [], "homework_directives": []}
    extractor, _ = _extractor(json.dumps(payload))
    result = extractor.extract("transcript", TAXONOMY)
    assert result.skills_practiced == []
    assert result.misconceptions == []


def test_extract_raises_on_invalid_json():
    extractor, _ = _extractor("this is not json at all")
    with pytest.raises(ExtractionError):
        extractor.extract("transcript", TAXONOMY)


def test_extract_raises_on_schema_violation():
    """Model returned JSON but missing/wrong-typed fields → ExtractionError."""
    bad_payload = {"skills_practiced": "not a list", "skills_struggled": []}
    extractor, _ = _extractor(json.dumps(bad_payload))
    with pytest.raises(ExtractionError):
        extractor.extract("transcript", TAXONOMY)


def test_extract_passes_taxonomy_into_system_message():
    payload = {"skills_practiced": [], "skills_struggled": [], "skills_introduced": [],
               "skills_mastered_today": [], "misconceptions": [], "homework_directives": []}
    extractor, client = _extractor(json.dumps(payload))
    extractor.extract("some transcript", TAXONOMY)

    assert client.messages.last_call is not None
    system = client.messages.last_call["system"]
    # Each taxonomy entry's skill_id should be present in the system message.
    for entry in TAXONOMY:
        assert entry.skill_id in system
        assert entry.name in system


def test_extract_uses_transcript_as_user_message():
    payload = {"skills_practiced": [], "skills_struggled": [], "skills_introduced": [],
               "skills_mastered_today": [], "misconceptions": [], "homework_directives": []}
    extractor, client = _extractor(json.dumps(payload))
    extractor.extract("MY_UNIQUE_TRANSCRIPT_MARKER", TAXONOMY)
    msgs = client.messages.last_call["messages"]
    assert any("MY_UNIQUE_TRANSCRIPT_MARKER" in m["content"] for m in msgs)
