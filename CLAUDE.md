# Atlas — CLAUDE.md

Personal AI agent for athlete physiological intelligence.
Single user. MVP v0.1.

---

## Project layout

```
atlas/
├── app/
│   ├── api/              # FastAPI route handlers
│   │   ├── __init__.py
│   │   └── ask.py        # POST /ask endpoint
│   ├── agent/            # LLM agent + tool definitions
│   │   ├── __init__.py
│   │   ├── agent.py      # Ollama chat loop + tool dispatch
│   │   └── tools.py      # All agent tools (DB query functions)
│   ├── ingestion/        # All parsing lives here
│   │   ├── __init__.py
│   │   ├── fit_parser.py      # FIT file parsing via fitparse
│   │   ├── ndjson_parser.py   # Activity/sleep/recovery NDJSON
│   │   └── pipeline.py        # Orchestrates full ingest run
│   ├── models/           # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── workout.py
│   │   ├── sleep.py
│   │   ├── activity.py
│   │   └── recovery.py
│   └── core/
│       ├── __init__.py
│       ├── config.py     # Settings loaded from .env
│       └── database.py   # SQLAlchemy engine + session factory
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── suunto-data-03042026/ # Suunto export (gitignored)
├── synthetic_wearable_data/ # Synthetic dev/test data (same structure as real export)
├── tests/
│   ├── conftest.py
│   ├── test_ingestion/
│   │   └── __init__.py
│   └── test_agent/
│       └── __init__.py
├── CLAUDE.md
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## Hard rules

1. **No raw SQL in routes.** All queries go through SQLAlchemy ORM (`app/models/`).
2. **All parsing in `app/ingestion/`.** FIT files via `fit_parser.py`, NDJSON via `ndjson_parser.py`.
3. **No hardcoded secrets.** Use `.env` + `app/core/config.py`. Never commit `.env`.
4. **Every schema change needs an Alembic migration.** Never edit the DB manually.
5. **Run tests after every change.** Fix failures before stopping or committing.
6. **Commit after each meaningful step.**
7. **Skip `.gpx` files silently** in the ingestion pipeline — FIT files are the source of truth.
8. **No computed/derived metrics in MVP.** Agent queries raw DB data directly. `processing/` is post-MVP.
9. **`activity/` aggregation happens at query time**, not on ingest. Store raw 30-min slots in the DB.
10. **Skip `gears.json` gracefully** — out of scope for MVP.

---

## Data on disk

Real export directory: `suunto-data-03042026/` (repo root, gitignored)
Synthetic dev/test data: `synthetic_wearable_data/` (same folder structure, safe to commit)

| Folder | Format | Content |
|---|---|---|
| `workouts/` | `.fit` + `.gpx` | 333 FIT files, named `YYYY-MM-DD_HH.MM.SS-sport_type.fit`. Skip `.gpx`. |
| `activity/` | NDJSON by month | 30-min slots: stepCount, energyConsumption |
| `sleep/` | NDJSON by month | Per-session: deep/light/REM durations, HRV, SpO2, quality |
| `sleep_stages/` | NDJSON by month | Granular stage rows (stage enum + duration in seconds) |
| `recovery/` | NDJSON by month | balance (0–1), stressState (int) |
| `user/` | JSON | user.json (profile), gears.json (skip) |

**NDJSON shape:** each line is `{ "timestamp": "ISO8601", "entryData": { ... } }`.

**hr fields in sleep NDJSON** are stored as fractions (e.g. `1.07`), not bpm — normalize on ingest (multiply by hrMax from user profile, hrMax = 198).

---

## Agent tools (MVP — 5 tools)

| Tool | Description |
|---|---|
| `get_workout_summary` | Recent workouts, filterable by sport/date range |
| `get_sleep_summary` | Sleep metrics over a date range |
| `get_activity_summary` | Daily steps + energy over a date range (aggregate at query time) |
| `get_recovery_summary` | Recovery balance + stress over a date range |
| `get_user_profile` | Static profile data (hrMax, hrRest, weight, etc.) |

---

## Environment variables

```
DATABASE_URL=postgresql://atlas:atlas@localhost:5432/atlas
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:32b
```

---

## Local dev setup

```bash
ollama pull qwen2.5:72b        # Pull model (once)
docker compose up -d           # Start Postgres
alembic upgrade head           # Apply migrations
python -m app.ingestion.pipeline synthetic_wearable_data  # or suunto-data-03042026 for real data
uvicorn app.main:app --reload
```

---

## Known data quirks to handle

- `sleep.hrAvg` / `sleep.hrMin` are normalized fractions, not bpm. Multiply by hr_rest on ingest.
- `activity/` only starts from 2024-12; `sleep/` and `recovery/` start from 2025-09 — gaps are expected.
- Workout sport types use underscore slugs (e.g. `cross_country_skiing`, `ski_touring`).
- Timestamps include timezone offset (`+01:00`). Normalize to UTC on ingest.
- Some sport types (gym, pilates, yoga) produce FIT files with minimal sensor data — don't crash on missing fields.
- `sleep_stages/` has a separate granular table linked by `sleepId` from `sleep/`.
