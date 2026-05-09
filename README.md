# rgprep-generator

Notion-backed personalized ACT/SAT homework generator. Produces self-contained interactive HTML question sets per student, scored by a multi-signal algorithm grounded in cognitive-science evidence (interleaving, retrieval, spacing). Fed by Fathom session signals so homework reflects what just happened in the live tutoring session.

Single-tutor system, ~5–15 concurrent students. v1 covers ACT Math; architecture is test-agnostic so other sections land as TOML config + content additions.

## Quickstart

```bash
# Requires Python 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp config.example.toml config.toml
cp .env.example .env
# fill in NOTION_TOKEN, ANTHROPIC_API_KEY, NOTION_DB_*, WEBHOOK_* in .env

rgprep --help
```

## CLI

```bash
# Pull a fresh snapshot from Notion into the local SQLite cache
rgprep refresh-cache

# Generate a homework set
rgprep generate --student "Hank" --template act_math_mixed_20

# Ingest a Fathom transcript (writes Session Signals, recomputes weak/strong)
rgprep ingest-session --transcript ./fathom_2026-05-08_hank.txt --student "Hank" --session-date 2026-05-08

# Run the submission webhook locally
rgprep webhook
```

## How it works

Three loops:

1. **Session loop.** Tutoring session → Fathom transcript → Claude extractor → `Session Signals` Notion DB → recompute `weak_skills`/`strong_skills` on the Student record.
2. **Generation loop.** Pull from Notion → score candidates → constrain (no-streak, resurface floor, session-tie floor) → render single-file HTML.
3. **Submission loop.** Student submits → FastAPI webhook → `Q-History` rows → recompute weak/strong.

Both recompute paths converge on the same `weak_skills`/`strong_skills` properties.

## Pedagogical traceability

Weights and rules are not arbitrary — each maps to a finding in the literature. Preserve this table when tuning, so the *why* survives turnover.

| Signal / mechanism | Backed by |
|---|---|
| `resurface_signal` 1–6 day window | Adesope et al. 2017 — g = 0.82 effect at 1–6 day gap |
| `resurface_signal` weight | Same meta-analysis — g = 0.93 vs no-activity, g = 0.83 in secondary populations |
| `session_signal` weight (high) and 1–6 day decay on `skills_introduced` | Adesope et al. — same retrieval-window finding applied to *just-taught* content |
| Constraint-aware sampler / no-streak rule | Rohrer, Dedrick & Stershic 2015 — d = 0.79 at 30-day delay; Brunmair & Richter 2019 — g = 0.42 |
| `spacing_signal` 10–30% gap | Donovan & Radosevich — d = 0.46 |
| Sets are 100% retrieval-based; no re-reading or highlighting in the UX | Dunlosky et al. 2013 — both rated low utility |
| Mixed format exploration (future) | Adesope et al. — mixed formats produced largest gains |

## Project layout

See `rgprep_question_generator_plan.md` (v2 plan) for full specification — schema (§4), scoring (§5), session ingestion (§6), templates (§7), rendering + webhook (§8), phasing (§9).

```
rgprep/
├── cli.py              # Typer commands
├── notion_client.py    # Notion read/write
├── cache.py            # SQLite mirror
├── models.py           # pydantic Question, Student, Attempt, SessionExtraction
├── selection/          # scoring, constraints, templates
├── render/             # Jinja2 shell + render
├── session/            # extractor, prompt, ingest
├── adapt/              # weak/strong recompute
└── webhook/            # FastAPI app + auth
templates/              # set TOML templates
tests/                  # unit + snapshot tests
```

## Status

**Phase 1 (MVP) — scaffold.** Module skeletons in place; implementation in progress.
