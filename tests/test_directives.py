"""Directives → skill matcher tests."""

from __future__ import annotations

from qset_gen.models import SkillTaxonomyEntry
from qset_gen.session.directives import resolve_directive_skill_ids


def _tax(*pairs: tuple[str, str]) -> list[SkillTaxonomyEntry]:
    return [SkillTaxonomyEntry(skill_id=sid, name=name) for sid, name in pairs]


def test_full_substring_match():
    taxonomy = _tax(
        ("trig_unit_circle", "Unit circle"),
        ("alg_quadratics", "Quadratics"),
    )
    matched = resolve_directive_skill_ids(
        ["practice unit circle problems this week"],
        taxonomy,
    )
    assert matched == {"trig_unit_circle"}


def test_case_insensitive():
    taxonomy = _tax(("trig_unit_circle", "Unit Circle"))
    matched = resolve_directive_skill_ids(
        ["UNIT CIRCLE drills"],
        taxonomy,
    )
    assert matched == {"trig_unit_circle"}


def test_word_stem_fallback_matches_reordered():
    """'Circles unit' should match 'Unit Circle' via the word-stem fallback."""
    taxonomy = _tax(("trig_unit_circle", "Unit Circle"))
    matched = resolve_directive_skill_ids(
        ["work on circles unit drills"],
        taxonomy,
    )
    assert matched == {"trig_unit_circle"}


def test_no_match_when_keywords_absent():
    taxonomy = _tax(("trig_unit_circle", "Unit Circle"))
    matched = resolve_directive_skill_ids(
        ["practice fractions and decimals"],
        taxonomy,
    )
    assert matched == set()


def test_multiple_matches():
    taxonomy = _tax(
        ("trig_unit_circle", "Unit Circle"),
        ("alg_quadratics", "Quadratics"),
        ("geo_circles", "Circles"),
    )
    matched = resolve_directive_skill_ids(
        ["focus on quadratics and unit circle"],
        taxonomy,
    )
    # Both unit_circle and quadratics should match.
    # geo_circles ("Circles") also substring-matches "unit circle" — that's expected
    # behavior of the substring rule; smarter matching can disambiguate later.
    assert "alg_quadratics" in matched
    assert "trig_unit_circle" in matched


def test_short_words_ignored_in_stem_fallback():
    """Skills like 'of pi' shouldn't match every directive — 'of' is too short."""
    taxonomy = _tax(("special_pi", "Properties of pi"))
    matched = resolve_directive_skill_ids(
        ["graphing functions"],
        taxonomy,
    )
    assert matched == set()


def test_empty_inputs_return_empty_set():
    taxonomy = _tax(("a", "Algebra"))
    assert resolve_directive_skill_ids([], taxonomy) == set()
    assert resolve_directive_skill_ids(["practice algebra"], []) == set()
