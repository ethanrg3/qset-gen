"""Pydantic models mirroring the Notion schema (plan §4) and the extraction schema (§6.2)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["guess", "unsure", "confident"]
Test = Literal["ACT", "SAT"]
Section = Literal["Math", "English", "Reading", "Science", "RW"]


class SkillTaxonomyEntry(BaseModel):
    skill_id: str
    name: str
    description: str | None = None


class Question(BaseModel):
    """Plan §4.1. `skill_tag` is the primary skill; if Notion returns multiple, take the first."""

    question_id: str
    test: Test
    section: Section
    skill_tag: str
    difficulty_low: float
    difficulty_high: float
    html_render: str
    answer_key: str
    explanation_html: str
    time_target_sec: int = 60
    active: bool = True

    @property
    def difficulty_mid(self) -> float:
        return (self.difficulty_low + self.difficulty_high) / 2.0


class Student(BaseModel):
    """Plan §4.4. weak_skills/strong_skills auto-managed after v1 ships (§6.4)."""

    student_id: str
    name: str
    current_act_math: float | None = None
    target_act_math: float | None = None
    test_date: date | None = None
    weak_skills: list[str] = Field(default_factory=list)
    strong_skills: list[str] = Field(default_factory=list)
    last_set_generated_at: datetime | None = None
    last_session_at: datetime | None = None


class Attempt(BaseModel):
    """Plan §4.2 Q-History row."""

    student_id: str
    question_id: str
    attempted_at: datetime
    correct: bool
    time_spent_sec: int
    set_id: str
    confidence: Confidence | None = None


class SessionExtraction(BaseModel):
    """Strict schema for the Claude extractor output (plan §6.2)."""

    skills_practiced: list[str] = Field(default_factory=list)
    skills_struggled: list[str] = Field(default_factory=list)
    skills_introduced: list[str] = Field(default_factory=list)
    skills_mastered_today: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    homework_directives: list[str] = Field(default_factory=list)


class SessionSignals(BaseModel):
    """Plan §4.3. One row per tutoring session."""

    session_id: str
    student_id: str
    session_date: date
    duration_min: int | None = None
    skills_practiced: list[str] = Field(default_factory=list)
    skills_struggled: list[str] = Field(default_factory=list)
    skills_introduced: list[str] = Field(default_factory=list)
    skills_mastered_today: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    homework_directives: list[str] = Field(default_factory=list)
    raw_transcript_excerpt: str | None = None
    extraction_model: str | None = None


class SetTemplate(BaseModel):
    """Plan §7."""

    name: str
    test: str
    size: int
    sections: dict[str, float]
    skill_distribution: dict[str, float] = Field(
        default_factory=lambda: {"weak": 0.6, "neutral": 0.3, "strong": 0.1}
    )
    resurface_floor: float = 0.20
    session_tie_floor: float = 0.25
    new_question_floor: float = 0.40
    time_limit_min: int = 30
    allow_calculator: bool = True
    no_streak_max: int = 2
    ordering: Literal["interleaved", "sequential"] = "interleaved"

    @field_validator("sections", "skill_distribution")
    @classmethod
    def _proportions_sum_to_one(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"proportions must sum to 1.0, got {total}")
        return v


class SubmitPayload(BaseModel):
    """Plan §8.3. Body of POST /submit."""

    student_id: str
    set_id: str
    attempts: list[Attempt]
