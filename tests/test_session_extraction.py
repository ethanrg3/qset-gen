"""Plan §11. Snapshot tests on canned Fathom transcripts — locks the prompt."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs canned Fathom transcripts in fixtures/sample_transcripts/")
def test_extraction_snapshot_basic_session():
    pass


@pytest.mark.skip(reason="needs canned Fathom transcripts in fixtures/sample_transcripts/")
def test_extraction_skips_topics_not_in_taxonomy():
    pass


@pytest.mark.skip(reason="needs canned Fathom transcripts in fixtures/sample_transcripts/")
def test_extraction_struggled_requires_clear_evidence():
    pass
