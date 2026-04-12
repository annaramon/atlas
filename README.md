# Atlas

Personal AI agent for athlete physiological intelligence. Ask natural-language questions about your training, sleep, recovery, and activity data — Atlas queries your database and answers with real numbers.

```
POST /ask  {"question": "How was my sleep last week compared to the week before?"}
           {"answer": "Last week you averaged 7.4h with 22% deep sleep and HRV of 61ms.
                       The prior week averaged 6.9h, 18% deep, HRV 54ms — a clear improvement."}
```

---

## How it works

```
User question
     │
     ▼
POST /ask  (FastAPI)
     │
     ▼
Agent loop  (Ollama — qwen2.5:32b)
     │
     ├─ model decides which tools to call
     │
     ├─ tool call → SQLAlchemy query → Postgres
     │
     ├─ result injected back into context
     │
     └─ model produces final answer
     │
     ▼
{"answer": "..."}
```

The model receives five tool schemas describing what data is available and what each tool returns. It selects the right tools, fills in the date arguments, and synthesises an answer from the results. No routing logic is hardcoded — the LLM drives all of it.

---

## Data sources

Atlas ingests exports from Suunto watches. The pipeline handles four data domains:

| Source | Format | Content |
|---|---|---|
| `workouts/` | `.fit` files | One file per session — sport type, duration, distance, ascent, calories, HR, HR zones |
| `sleep/` | NDJSON by month | Per-session deep/light/REM durations, HRV, SpO2, quality score |
| `sleep_stages/` | NDJSON by month | Granular stage rows linked to each sleep session |
| `activity/` | NDJSON by month | 30-minute slots of step count and energy consumption |
| `recovery/` | NDJSON by month | Daily balance score (0–1) and stress state |

NDJSON shape: each line is `{ "timestamp": "ISO8601", "entryData": { ... } }`.

---

## Agent tools

| Tool | What it does |
|---|---|
| `get_workout_summary` | Workouts over a date range, optionally filtered by sport type |
| `get_sleep_summary` | Sleep metrics over a date range |
| `get_activity_summary` | Daily steps and energy (aggregated from 30-min slots at query time) |
| `get_recovery_summary` | Recovery balance and stress over a date range |
| `get_user_profile` | Static profile — hrMax, hrRest, weight, height, DOB |

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Agent | Ollama (qwen2.5:32b) |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2 + Alembic |
| Ingestion | fitparse (FIT files), custom NDJSON parsers |
| Tests | pytest (43 tests) |

---

## Setup

**Prerequisites:** Python 3.11+, Docker, [Ollama](https://ollama.com)

### 1. Clone and install

```bash
git clone https://github.com/youruser/atlas.git
cd atlas
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```
DATABASE_URL=postgresql://atlas:atlas@localhost:5432/atlas
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:32b
```

### 3. Start Postgres

```bash
docker compose up -d
```

### 4. Apply migrations

```bash
alembic upgrade head
```

### 5. Pull the model

```bash
ollama pull qwen2.5:32b
```

### 6. Ingest data

```bash
# Using the included synthetic dataset (safe to run immediately):
python -m app.ingestion.pipeline synthetic_wearable_data

# Or point at your own Suunto export:
python -m app.ingestion.pipeline /path/to/your/suunto-export
```

The pipeline is idempotent — re-running it will not create duplicate records.

### 7. Start the server

```bash
uvicorn app.main:app --reload
```

---

## Usage

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What sports did I train most this month?"}'
```

```json
{"answer": "This month you logged 8 sessions: 3 running, 2 cycling, 2 gym, 1 ski touring."}
```

---

## Project structure

```
atlas/
├── app/
│   ├── api/
│   │   └── ask.py                # POST /ask endpoint
│   ├── agent/
│   │   ├── agent.py              # Ollama chat loop + tool dispatch
│   │   └── tools.py              # Tool implementations (DB queries)
│   ├── ingestion/
│   │   ├── fit_parser.py         # FIT file parsing
│   │   ├── ndjson_parser.py      # Sleep / activity / recovery parsing
│   │   └── pipeline.py           # Orchestrates full ingest run
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── workout.py
│   │   ├── sleep.py              # Sleep + SleepStage (cascade)
│   │   ├── activity.py
│   │   └── recovery.py
│   └── core/
│       ├── config.py             # Settings from .env
│       └── database.py           # Engine + session factory
├── alembic/                      # Migration history
├── synthetic_wearable_data/      # Synthetic dataset for dev/testing
├── tests/
│   ├── test_agent/
│   └── test_ingestion/
├── docker-compose.yml
└── requirements.txt
```

---

## Running tests

```bash
pytest
```

43 tests covering the ingestion parsers, all five agent tools, and the agent loop.

---

## Synthetic data

`synthetic_wearable_data/` mirrors the real Suunto export structure and is safe to commit. It contains generated workouts, sleep sessions, activity slots, and recovery records. Use it to develop and test without needing a real watch export.

---

## Roadmap

- [ ] Dashboard UI — sleep trends, training load, recovery timeline
- [ ] `GET` endpoints for direct data access (needed for dashboard)
- [ ] Computed metrics (TSS, ATL/CTL, HRV baseline)
- [ ] Multi-session conversation memory
