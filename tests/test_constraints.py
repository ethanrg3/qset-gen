"""Plan §11. Constraint-aware sampler tests."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="constraint sampler not yet implemented (Phase 1)")
def test_no_streak_constraint():
    """Sampler never produces 3+ same-skill in a row when alternation is possible."""
    pass


@pytest.mark.skip(reason="constraint sampler not yet implemented (Phase 1)")
def test_resurface_floor_honored():
    """Set contains ≥floor_resurface eligible misses when student has enough miss history."""
    pass


@pytest.mark.skip(reason="constraint sampler not yet implemented (Phase 1)")
def test_session_tie_floor_honored():
    """Set respects session_tie_floor when a recent session has struggled/introduced skills."""
    pass
