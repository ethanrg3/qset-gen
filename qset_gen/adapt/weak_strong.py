"""Adaptive weak/strong skill recompute — plan §6.4.

Triggered after every Session Signals insert AND every Q-History batch insert.

weakness_score(skill, s) =
      α * (1 − rolling_accuracy(skill, s))            # last 20 attempts, exp-decayed
    + β * session_struggle_density(skill, s)          # struggled / total recent sessions
    − γ * session_mastery_density(skill, s)
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Attempt, SessionSignals, SkillTaxonomyEntry, Student


@dataclass(frozen=True)
class AdaptParams:
    alpha: float = 0.5
    beta: float = 0.4
    gamma: float = 0.2
    theta_weak: float = 0.55
    theta_strong: float = 0.20
    min_evidence_points: int = 5
    rolling_window_attempts: int = 20
    session_decay_halflife_days: int = 14


@dataclass
class SkillStatusChange:
    skill_id: str
    prior_status: str   # "weak" | "neutral" | "strong"
    new_status: str
    weakness_score: float


def recompute_weak_strong(
    *,
    student: Student,
    history: list[Attempt],
    sessions: list[SessionSignals],
    taxonomy: list[SkillTaxonomyEntry],
    params: AdaptParams,
) -> tuple[list[str], list[str], list[SkillStatusChange]]:
    """Returns (new_weak_skill_ids, new_strong_skill_ids, changes).

    Caller is responsible for persisting the result via NotionGateway.update_student_skills
    and NotionGateway.append_skill_status_history.
    """
    raise NotImplementedError


def weakness_score(
    *,
    skill_id: str,
    history: list[Attempt],
    sessions: list[SessionSignals],
    params: AdaptParams,
) -> tuple[float, int]:
    """Returns (score, evidence_points)."""
    raise NotImplementedError
