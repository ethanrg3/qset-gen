"""Match free-text `homework_directives` to skill_ids in the taxonomy.

The session extractor stores directives like "practice unit-circle problems
this week". The scorer needs them as a set of skill_ids so it can apply the
+0.4 directive bonus. That mapping is a small NLP problem; v1 does a
case-insensitive substring match on the taxonomy skill name and a "soft"
multi-word fallback (every word in the skill name appears in the directive).

If accuracy becomes a problem, swap in embeddings or an LLM call here — the
caller doesn't care about the implementation, only the resolved set.
"""

from __future__ import annotations

import re

from ..models import SkillTaxonomyEntry


def resolve_directive_skill_ids(
    directives: list[str],
    taxonomy: list[SkillTaxonomyEntry],
) -> set[str]:
    """Return the set of skill_ids whose taxonomy name matches at least one directive.

    Matching strategy (in order of preference per skill):
      1. The full skill name appears as a case-insensitive substring of any directive.
      2. All word stems in the skill name appear (in any order) in the same directive.

    No partial-credit scoring; either a skill matches or it doesn't.
    """
    if not directives or not taxonomy:
        return set()

    normalized_directives = [_normalize(d) for d in directives]
    matched: set[str] = set()

    for entry in taxonomy:
        name = entry.name.lower().strip()
        if not name:
            continue

        if any(name in d for d in normalized_directives):
            matched.add(entry.skill_id)
            continue

        # Fallback: every meaningful word in the name appears in some directive,
        # tolerating short inflectional suffixes ("circle" vs "circles").
        words = [w for w in _tokenize(name) if w]
        if not words:
            continue
        for d in normalized_directives:
            d_words = _tokenize(d)
            if all(any(_token_matches(w, dw) for dw in d_words) for w in words):
                matched.add(entry.skill_id)
                break

    return matched


def _token_matches(skill_tok: str, directive_tok: str) -> bool:
    """Equal, or one is a short-prefix inflection of the other (≤2 char suffix)."""
    if skill_tok == directive_tok:
        return True
    if directive_tok.startswith(skill_tok) and len(directive_tok) - len(skill_tok) <= 2:
        return True
    if skill_tok.startswith(directive_tok) and len(skill_tok) - len(directive_tok) <= 2:
        return True
    return False


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(s: str) -> str:
    return s.lower().strip()


def _tokenize(s: str) -> list[str]:
    """Lowercase alphanumeric tokens. Drops short tokens (≤2 chars) to avoid
    matching on words like 'of', 'in', 'a'."""
    return [t for t in _TOKEN_RE.findall(s.lower()) if len(t) > 2]
