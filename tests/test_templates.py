"""All shipped TOML templates must load and validate."""

from __future__ import annotations

from rgprep.selection.templates import list_templates, load_template


def test_all_templates_load(templates_dir):
    names = list_templates(templates_dir)
    assert names, "no templates found"
    for name in names:
        t = load_template(name, templates_dir)
        assert t.size > 0
        assert sum(t.sections.values()) == 1.0


def test_post_session_template_has_high_session_tie_floor(templates_dir):
    t = load_template("act_math_post_session_15", templates_dir)
    assert t.session_tie_floor >= 0.5
    assert t.resurface_floor == 0.0


def test_pre_test_template_is_resurface_heavy(templates_dir):
    t = load_template("act_math_pre_test_30", templates_dir)
    assert t.resurface_floor >= 0.5
