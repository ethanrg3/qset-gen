"""Plan §11. Full pipeline produces a file that opens and renders all questions."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="renderer not yet implemented (Phase 1)")
def test_render_smoke_produces_self_contained_html(tmp_path):
    pass


@pytest.mark.skip(reason="renderer not yet implemented (Phase 1)")
def test_rendered_html_embeds_webhook_url_and_secret(tmp_path):
    pass
