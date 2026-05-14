"""Config loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from qset_gen.config import Config, NotionDbIds, load_config


def test_load_config_with_missing_file_returns_defaults(tmp_path):
    cfg = load_config("nonexistent.toml", project_root=tmp_path)
    assert isinstance(cfg, Config)
    assert cfg.paths.cache_db == tmp_path / "qset.db"
    assert cfg.weights.W_DIFF == 1.0  # default
    assert cfg.extractor.model == "claude-opus-4-7"


def test_load_config_parses_weights_section(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[scoring.weights]\n'
        'W_DIFF = 2.0\n'
        'W_RESURFACE = 3.0\n'
    )
    cfg = load_config("config.toml", project_root=tmp_path)
    assert cfg.weights.W_DIFF == 2.0
    assert cfg.weights.W_RESURFACE == 3.0
    # Unspecified fields keep defaults
    assert cfg.weights.W_PRIORITY == 0.8


def test_load_config_resolves_relative_paths_against_project_root(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[paths]\n'
        'cache_db = "data/qset.db"\n'
        'output_dir = "renders"\n'
    )
    cfg = load_config("config.toml", project_root=tmp_path)
    assert cfg.paths.cache_db == tmp_path / "data" / "qset.db"
    assert cfg.paths.output_dir == tmp_path / "renders"


def test_load_config_absolute_paths_preserved(tmp_path):
    (tmp_path / "config.toml").write_text(
        f'[paths]\n'
        f'cache_db = "/tmp/abs.db"\n'
    )
    cfg = load_config("config.toml", project_root=tmp_path)
    assert cfg.paths.cache_db == Path("/tmp/abs.db")


def test_load_config_parses_adapt_section(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[adapt]\n'
        'alpha = 0.7\n'
        'theta_weak = 0.6\n'
    )
    cfg = load_config("config.toml", project_root=tmp_path)
    assert cfg.adapt.alpha == 0.7
    assert cfg.adapt.theta_weak == 0.6


def test_notion_db_ids_missing_when_env_unset(monkeypatch):
    for var in (
        "NOTION_DB_QUESTIONS", "NOTION_DB_STUDENTS", "NOTION_DB_Q_HISTORY",
        "NOTION_DB_SESSION_SIGNALS", "NOTION_DB_SKILL_TAXONOMY", "NOTION_DB_SKILL_STATUS_HISTORY",
    ):
        monkeypatch.delenv(var, raising=False)
    ids = NotionDbIds.from_env()
    assert set(ids.missing()) == {
        "questions", "students", "q_history", "session_signals", "skill_taxonomy", "skill_status_history"
    }


def test_notion_db_ids_loaded_from_env(monkeypatch):
    monkeypatch.setenv("NOTION_DB_QUESTIONS", "abc123")
    monkeypatch.setenv("NOTION_DB_STUDENTS", "def456")
    ids = NotionDbIds.from_env()
    assert ids.questions == "abc123"
    assert ids.students == "def456"
    assert "questions" not in ids.missing()
    assert "students" not in ids.missing()


def test_config_exposes_secrets_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTION_TOKEN", "secret_xxx")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    monkeypatch.setenv("WEBHOOK_SECRET", "wh_secret")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    cfg = load_config("nonexistent.toml", project_root=tmp_path)
    assert cfg.notion_token == "secret_xxx"
    assert cfg.anthropic_api_key == "sk-ant-xxx"
    assert cfg.webhook_secret == "wh_secret"
    assert cfg.webhook_base_url == "https://example.com"
