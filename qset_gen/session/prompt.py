"""Extraction prompt — plan §6.2. Locked by snapshot tests in tests/test_session_extraction_snapshot."""

from __future__ import annotations

from ..models import SkillTaxonomyEntry

SYSTEM_TEMPLATE = """\
You are extracting structured pedagogical signals from a 1:1 ACT math tutoring session transcript. \
You must use ONLY the skill IDs provided in the taxonomy below. Do not invent skill names. \
If a topic in the transcript doesn't clearly map to a taxonomy skill, omit it rather than guessing.

[TAXONOMY]
{taxonomy}

Output strict JSON matching this schema:
{{
  "skills_practiced":      [skill_id, ...],
  "skills_struggled":      [skill_id, ...],
  "skills_introduced":     [skill_id, ...],
  "skills_mastered_today": [skill_id, ...],
  "misconceptions":        ["string", ...],
  "homework_directives":   ["string", ...]
}}

Rules:
- Conservative extraction. A skill is "struggled" only if there's clear evidence (multiple errors, explicit confusion, explicit tutor reteaching). One miss is not enough.
- "Introduced" means new this session — the student has not worked the topic before with you.
- "Mastered today" requires explicit evidence of correct independent execution after teaching.
- Misconceptions are short, specific phrases ("treats negative exponents as negative numbers"), not generic ("struggles with exponents").
- Homework directives are statements the tutor makes about what should be practiced this week. Quote them faithfully but compress to single phrases.
- If the transcript is silent on a category, return an empty list. Do not pad.

Return ONLY the JSON object, no surrounding prose.
"""


def build_system_message(taxonomy: list[SkillTaxonomyEntry]) -> str:
    """Inject the skill taxonomy into the system prompt."""
    lines = [
        f"- {entry.skill_id} | {entry.name}"
        + (f" — {entry.description}" if entry.description else "")
        for entry in taxonomy
    ]
    return SYSTEM_TEMPLATE.format(taxonomy="\n".join(lines))
