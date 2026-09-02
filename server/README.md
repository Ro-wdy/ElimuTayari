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
.venv/Scripts/python.exe -m app.wiki_seed          # load reviewed wiki content
.venv/Scripts/python.exe -m app.seed               # or: placeholder Maths content
```

Both seeds are idempotent and safe to run on every deploy. `app.wiki_seed` is
the real one: it loads the Markdown wiki (`../wiki/`) into `substrands` and
`content_units`, driven by each learning area's `graph.json` manifest and the
page frontmatter.

- **Review gate** — only pages whose frontmatter `status` is `reviewed` are
  loaded. Anything else (today the whole wiki is `draft-human-review`) is
  excluded; `--include-drafts` loads unreviewed pages anyway for development
  and sandbox testing.
- **Re-runnable** — an edited page is stored as a new `content_units` version
  (serving picks the highest); an unedited wiki re-seeds as a no-op.
- **Mirror semantics** — sub-strands no longer servable (page removed, demoted
  below the gate, or left over from the placeholder seeder) are deleted, which
  removes them from the USSD menus. Note this means a gated seed of an
  all-draft wiki empties the served content: that is the review gate doing its
  job, and the CLI prints the `--include-drafts` hint when it happens.

`app.seed` keeps its placeholder role for tests and for bootstrapping before
wiki content lands.

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
