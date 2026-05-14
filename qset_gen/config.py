"""Config loader — reads config.toml into a structured Config object.

Secrets stay in environment variables (loaded via python-dotenv); config.toml
only carries non-secret tunables (weights, thresholds, paths, model name).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .adapt.weak_strong import AdaptParams
from .selection.scoring import ScoringWeights


@dataclass
class PathsConfig:
    cache_db: Path
    output_dir: Path
    templates_dir: Path


@dataclass
class ExtractorConfig:
    model: str = "claude-opus-4-7"
    max_tokens: int = 4096
    transcript_excerpt_chars: int = 4000


@dataclass
class WebhookConfig:
    host: str = "0.0.0.0"
    port: int = 8787


@dataclass
class NotionDbIds:
    """Notion DB IDs sourced from env vars. None means the var is unset."""

    questions: str | None = None
    students: str | None = None
    q_history: str | None = None
    session_signals: str | None = None
    skill_taxonomy: str | None = None
    skill_status_history: str | None = None

    @classmethod
    def from_env(cls) -> NotionDbIds:
        return cls(
            questions=os.environ.get("NOTION_DB_QUESTIONS"),
            students=os.environ.get("NOTION_DB_STUDENTS"),
            q_history=os.environ.get("NOTION_DB_Q_HISTORY"),
            session_signals=os.environ.get("NOTION_DB_SESSION_SIGNALS"),
            skill_taxonomy=os.environ.get("NOTION_DB_SKILL_TAXONOMY"),
            skill_status_history=os.environ.get("NOTION_DB_SKILL_STATUS_HISTORY"),
        )

    def missing(self) -> list[str]:
        return [k for k, v in self.__dict__.items() if v is None]


@dataclass
class Config:
    paths: PathsConfig
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    adapt: AdaptParams = field(default_factory=AdaptParams)
    extractor: ExtractorConfig = field(default_factory=ExtractorConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    notion_dbs: NotionDbIds = field(default_factory=NotionDbIds.from_env)

    @property
    def webhook_base_url(self) -> str | None:
        return os.environ.get("WEBHOOK_BASE_URL")

    @property
    def webhook_secret(self) -> str | None:
        return os.environ.get("WEBHOOK_SECRET")

    @property
    def notion_token(self) -> str | None:
        return os.environ.get("NOTION_TOKEN")

    @property
    def anthropic_api_key(self) -> str | None:
        return os.environ.get("ANTHROPIC_API_KEY")


def load_config(path: Path | str = "config.toml", *, project_root: Path | None = None) -> Config:
    """Load and parse config.toml. Returns defaults if the file is missing
    (useful in tests). Relative paths are resolved against `project_root`
    (defaults to the cwd)."""
    project_root = project_root or Path.cwd()
    path = Path(path)
    if not path.is_absolute():
        path = project_root / path

    data: dict = {}
    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)

    paths_raw = data.get("paths", {})
    paths = PathsConfig(
        cache_db=_resolve(project_root, paths_raw.get("cache_db", "qset.db")),
        output_dir=_resolve(project_root, paths_raw.get("output_dir", "out")),
        templates_dir=_resolve(project_root, paths_raw.get("templates_dir", "templates")),
    )

    weights_raw = data.get("scoring", {}).get("weights", {})
    weights = ScoringWeights(**{k: float(v) for k, v in weights_raw.items()})

    adapt_raw = data.get("adapt", {})
    adapt = AdaptParams(**{k: v for k, v in adapt_raw.items() if k in AdaptParams.__dataclass_fields__})

    extractor_raw = data.get("extractor", {})
    extractor = ExtractorConfig(**{k: v for k, v in extractor_raw.items() if k in ExtractorConfig.__dataclass_fields__})

    webhook_raw = data.get("webhook", {})
    webhook = WebhookConfig(**{k: v for k, v in webhook_raw.items() if k in WebhookConfig.__dataclass_fields__})

    return Config(
        paths=paths,
        weights=weights,
        adapt=adapt,
        extractor=extractor,
        webhook=webhook,
        notion_dbs=NotionDbIds.from_env(),
    )


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else root / p
