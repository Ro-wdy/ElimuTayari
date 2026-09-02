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

Test databases are built by running the real Alembic migrations, not
`Base.metadata.create_all`, so the schema under test is the one that ships.

Postgres compatibility is checked without a server by rendering the migration
as static SQL for the Postgres dialect and asserting on the types it produces.
The one test that needs a live database is skipped unless `POSTGRES_TEST_URL`
is set:

```bash
POSTGRES_TEST_URL=postgresql+psycopg://user:password@localhost:5432/elimutayari_test   .venv/Scripts/python.exe -m pytest
```

## Confusion-hotspot digest

A Markdown digest of where students are confused, for revising wiki pages:
sub-strands ranked by student questions per teaching session (not raw counts),
with each hotspot's questions clustered into named themes by Claude. Needs
`ANTHROPIC_API_KEY` in `.env`.

```bash
.venv/Scripts/python.exe -m app.analytics                       # default: ../reports/confusion-digest.md
.venv/Scripts/python.exe -m app.analytics --out weekly.md       # custom path
```

The report defaults to `reports/confusion-digest.md` at the repo root and is
rewritten in place on every run, so re-running is safe; the file is not
gitignored, so the maintainer can commit a digest to keep history. There is no
scheduler dependency - for a weekly run, add a cron line on the host:

```cron
0 6 * * 1 cd /path/to/ElimuTayari/server && .venv/bin/python -m app.analytics
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
