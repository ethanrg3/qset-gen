"""Adaptive weak/strong skill recompute — plan §6.4.

Triggered after every Session Signals insert AND every Q-History batch insert.

weakness_score(skill, s) =
      α * (1 − rolling_accuracy(skill, s))            # last N attempts, exp-decayed by age
    + β * session_struggle_density(skill, s)          # struggled-count / total recent sessions
    − γ * session_mastery_density(skill, s)

Promotion / demotion gating:
- weakness_score ≥ θ_weak AND evidence ≥ min_evidence_points → weak
- weakness_score ≤ θ_strong AND evidence ≥ min_evidence_points → strong
- otherwise → neutral

Evidence points = (recent attempts on the skill) + (recent sessions mentioning the
skill in any list). This prevents flipping a skill's status on one data point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..models import Attempt, SessionSignals, SkillTaxonomyEntry, Student

# Skill status constants — used in SkillStatusChange.prior_status / new_status.
STATUS_WEAK = "weak"
STATUS_STRONG = "strong"
STATUS_NEUTRAL = "neutral"


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
    session_cutoff_days: int = 60          # ignore sessions older than this entirely
    attempt_decay_halflife_days: int = 14  # weight on recent attempts in rolling accuracy


@dataclass
class SkillStatusChange:
    skill_id: str
    prior_status: str   # STATUS_WEAK | STATUS_NEUTRAL | STATUS_STRONG
    new_status: str
    weakness_score: float


def recompute_weak_strong(
    *,
    student: Student,
    history: list[Attempt],
    sessions: list[SessionSignals],
    taxonomy: list[SkillTaxonomyEntry],
    params: AdaptParams,
    question_skill_map: dict[str, str] | None = None,
    today: date | None = None,
) -> tuple[list[str], list[str], list[SkillStatusChange]]:
    """Recompute weak/strong status for every skill in the taxonomy.

    Returns (new_weak_skill_ids, new_strong_skill_ids, changes). Caller persists
    via NotionGateway.update_student_skills and append_skill_status_history.
    """
    if today is None:
        today = date.today()
    qmap = question_skill_map or {}

    prior_weak = set(student.weak_skills)
    prior_strong = set(student.strong_skills)

    new_weak: list[str] = []
    new_strong: list[str] = []
    changes: list[SkillStatusChange] = []

    for entry in taxonomy:
        skill_id = entry.skill_id
        score, evidence = weakness_score(
            skill_id=skill_id,
            history=history,
            sessions=sessions,
            params=params,
            question_skill_map=qmap,
            today=today,
        )

        prior_status = (
            STATUS_WEAK if skill_id in prior_weak
            else STATUS_STRONG if skill_id in prior_strong
            else STATUS_NEUTRAL
        )

        if evidence < params.min_evidence_points:
            new_status = STATUS_NEUTRAL
        elif score >= params.theta_weak:
            new_status = STATUS_WEAK
            new_weak.append(skill_id)
        elif score <= params.theta_strong:
            new_status = STATUS_STRONG
            new_strong.append(skill_id)
        else:
            new_status = STATUS_NEUTRAL

        if new_status != prior_status:
            changes.append(SkillStatusChange(
                skill_id=skill_id,
                prior_status=prior_status,
                new_status=new_status,
                weakness_score=score,
            ))

    return new_weak, new_strong, changes


def weakness_score(
    *,
    skill_id: str,
    history: list[Attempt],
    sessions: list[SessionSignals],
    params: AdaptParams,
    question_skill_map: dict[str, str] | None = None,
    today: date | None = None,
) -> tuple[float, int]:
    """Returns (score, evidence_points). See module docstring for the formula."""
    if today is None:
        today = date.today()
    qmap = question_skill_map or {}

    accuracy, attempt_evidence = rolling_accuracy(
        skill_id=skill_id, history=history, question_skill_map=qmap, today=today, params=params
    )
    struggle_density, _ = _session_density(
        skill_id=skill_id, sessions=sessions, today=today, list_name="skills_struggled", params=params
    )
    mastery_density, _ = _session_density(
        skill_id=skill_id, sessions=sessions, today=today, list_name="skills_mastered_today", params=params
    )

    score = (
        params.alpha * (1.0 - accuracy)
        + params.beta * struggle_density
        - params.gamma * mastery_density
    )

    session_evidence = _count_session_appearances(skill_id=skill_id, sessions=sessions, today=today, params=params)
    total_evidence = attempt_evidence + session_evidence
    return score, total_evidence


def rolling_accuracy(
    *,
    skill_id: str,
    history: list[Attempt],
    question_skill_map: dict[str, str],
    today: date,
    params: AdaptParams,
) -> tuple[float, int]:
    """Exp-decayed accuracy over the last `rolling_window_attempts` attempts on this skill.

    Returns (accuracy, attempt_count). Cold-start (no attempts): (0.5, 0) — neutral.
    """
    skill_attempts = [a for a in history if question_skill_map.get(a.question_id) == skill_id]
    if not skill_attempts:
        return 0.5, 0

    skill_attempts.sort(key=lambda a: a.attempted_at, reverse=True)
    recent = skill_attempts[: params.rolling_window_attempts]

    weighted_correct = 0.0
    weight_total = 0.0
    for a in recent:
        age_days = max(0, (today - a.attempted_at.date()).days)
        w = 0.5 ** (age_days / params.attempt_decay_halflife_days)
        weight_total += w
        if a.correct:
            weighted_correct += w

    accuracy = weighted_correct / weight_total if weight_total > 0 else 0.5
    return accuracy, len(recent)


def _session_density(
    *,
    skill_id: str,
    sessions: list[SessionSignals],
    today: date,
    list_name: str,
    params: AdaptParams,
) -> tuple[float, int]:
    """Density of sessions where `skill_id` appears in `list_name`, exp-decayed by session age.

    density = Σ(w_i * I[skill ∈ list_i]) / Σ(w_i), where w_i = 0.5^(age_i / halflife).
    Sessions older than `session_cutoff_days` are excluded entirely.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    mention_count = 0
    for s in sessions:
        age = (today - s.session_date).days
        if age < 0 or age > params.session_cutoff_days:
            continue
        w = 0.5 ** (age / params.session_decay_halflife_days)
        weight_total += w
        if skill_id in getattr(s, list_name):
            weighted_sum += w
            mention_count += 1
    density = weighted_sum / weight_total if weight_total > 0 else 0.0
    return density, mention_count


def _count_session_appearances(
    *,
    skill_id: str,
    sessions: list[SessionSignals],
    today: date,
    params: AdaptParams,
) -> int:
    """Number of recent sessions where this skill appears in any list."""
    count = 0
    for s in sessions:
        age = (today - s.session_date).days
        if age < 0 or age > params.session_cutoff_days:
            continue
        if (
            skill_id in s.skills_struggled
            or skill_id in s.skills_practiced
            or skill_id in s.skills_introduced
            or skill_id in s.skills_mastered_today
        ):
            count += 1
    return count
