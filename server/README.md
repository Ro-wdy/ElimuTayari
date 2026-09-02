# server

FastAPI application for ElimuTayari: the Africa's Talking USSD callback, the
inbound-SMS webhook, and the database behind them.

## Setup

```bash
cd server
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt  # macOS/Linux
```

Copy `../.env.example` to `../.env` and fill in credentials. Everything has a
working default except the API keys, so the server runs against local SQLite
with no configuration.

## Database

Migrations are Alembic, and read `DATABASE_URL` from the environment (default:
local SQLite at `server/elimutayari.db`), so the same history runs on SQLite in
development and Postgres in production.

```bash
.venv/Scripts/python.exe -m alembic upgrade head   # create/update the schema
.venv/Scripts/python.exe -m app.seed               # load placeholder Maths content
```

The seed is idempotent: it matches rows on their natural keys and refreshes them,
so it is safe to run on every deploy.

## Run

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

- `GET /health` — liveness, returns `{"status": "ok"}`
- `POST /ussd` — Africa's Talking USSD callback (form-encoded in, `CON`/`END` plain text out)
- `POST /sms/inbound` — Africa's Talking inbound-SMS webhook (form-encoded in)

USSD and SMS are stubs at this stage; tickets #2 and #3 give them real behaviour.

## Tests

```bash
.venv/Scripts/python.exe -m pytest
```

## Schema

| Table | Purpose |
| --- | --- |
| `substrands` | CBC sub-strands, keyed by code (`M-ALG-02`) — the shared identifier across wiki, DB, USSD and SMS |
| `teachers` | One row per phone number, with the sub-strand they last browsed |
| `content_units` | Wiki content per sub-strand, by `kind` (`guidance`/`activity`/`materials`/`sms_pack`) and `version` |
| `teaching_sessions` | That a teacher taught a sub-strand — the denominator for hotspot analytics |
| `questions` | Post-class uploads, from a `student` or the `teacher` |
| `tests` | Generated tests, spanning one or more sub-strands |

Enumerated columns are `String` + `CHECK` rather than native enums, and
structured columns use the portable `JSON` type, to keep SQLite and Postgres
behaving identically.
