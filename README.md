# ElimuTayari

**A teaching companion for Grade 10 teachers in Kenya that works on any phone, with no internet.**

ElimuTayari puts an LLM-generated, KICD-aligned teaching wiki within reach of a teacher whose
only tool is a basic GSM phone. The teacher dials a USSD code, picks the sub-strand they are
about to teach, and the guidance arrives by SMS — how to teach it, activities that need no
special materials, and common misconceptions. After class, they text back the questions their
students asked. Those questions become the raw material for generated tests and for analytics
that reveal which topics confuse students most — which in turn drives revision of the wiki
itself.

The pilot covers **Core Mathematics, Grade 10** (the first CBC senior-school cohort), with the
wiki as ground truth; verification against the official KICD curriculum designs is planned for
a future iteration.

## How it works without internet

The teacher needs **no internet, no smartphone, and no app** — only GSM signal:

- **USSD** (`*XXX#`-style dialing) works on every phone and every network without a data
  bundle. It carries the interactive part: menus, choices, short status screens.
- **SMS** carries the content. Teaching packs, confirmations, and generated tests arrive as
  ordinary text messages — and an SMS **persists on the phone**, so the teacher can re-read
  the pack in a classroom with no signal at all. The SMS inbox is the offline cache.
- The **server** is the only online component. USSD and SMS traffic travels over the GSM
  network to Africa's Talking, which forwards it to the server over HTTPS. All intelligence —
  the wiki content, the database, the Claude API calls — lives server-side, where compute and
  connectivity are cheap. The phone is just a terminal.

## What the teacher can do

| Action | Channel | What happens |
|---|---|---|
| Browse strands / enter a code (e.g. `M-ALG-02`) | USSD | Teaching pack arrives as 2–3 SMS; a teaching session is logged |
| Continue where they left off | USSD | Home screen leads with the last-taught sub-strand |
| My coverage | USSD | "You have taught X of Y Mathematics sub-strands" |
| Upload student questions | SMS `Q M-ALG-02 <question>` | Stored as a confusion signal; confirmation SMS |
| Upload their own test items | SMS `T M-ALG-02 <item>` | Stored in the question bank; confirmation SMS |
| Get a test | USSD | Claude composes ~5 questions from the sub-strand's outcomes plus the uploaded question bank; delivered by SMS |

For the maintainer, a weekly **confusion-hotspot digest** ranks sub-strands by student
questions per teaching session and clusters the question texts into named themes — the signal
for which wiki pages need revising.

## Architecture

```
Teacher's phone (any GSM phone — no internet)
   │  USSD dialing / SMS
   ▼
GSM network → Africa's Talking gateway
   │  HTTPS webhooks (form-encoded callbacks)
   ▼
FastAPI server
   ├── POST /ussd          stateless menu state machine (replays the session's
   │                       accumulated input; no server-side session state)
   ├── POST /sms/inbound   Q/T command parser → question bank
   ├── SMS client seam ───→ Africa's Talking SMS API (packs, confirmations, tests)
   ├── LLM client seam ───→ Claude API (test generation, question clustering)
   └── Database: SQLite (dev) / Postgres (prod)
         teachers · substrands · content_units · teaching_sessions
         questions · tests
   ▲
   │  seed (python -m app.wiki_seed)
Markdown wiki (wiki/) — the source of truth
   git-versioned pages per sub-strand, generated with Claude from the KICD
   curriculum designs, carrying explicit review status and provenance
```

Design principles:

- **Pre-reviewed content, narrowly-scoped live LLM.** The wiki is generated ahead of time and
  human-reviewable; the live Claude calls are confined to test generation and question
  clustering, where a wobble is low-stakes. Curriculum guidance is never generated on the fly.
- **The wiki is the source of truth.** Content lives as Markdown in `wiki/` (browsable in
  GitHub/Obsidian), keyed by stable sub-strand codes (`M-ALG-02`) shared across pages,
  database rows, USSD navigation, and SMS commands. A seed script loads it into the database;
  editing a page and re-seeding updates what teachers receive.
- **Stateless USSD.** Africa's Talking resends the whole input history on every request, so
  the menu is a pure function of that text plus the database — nothing to lose when a session
  drops.
- **Seams everywhere.** Outbound SMS and Claude calls go through injectable client seams, so
  the entire test suite runs with no network and no credentials.
- **Phone number is identity.** No registration, no PINs — the number that dials is the
  teacher record.

## Repository layout

- `server/` — FastAPI application: webhooks, menu logic, SMS/LLM clients, seeders, analytics,
  migrations, tests. See `server/README.md` for setup, commands, and schema.
- `wiki/` — the LLM wiki: per-sub-strand Markdown pages with frontmatter (code, status,
  prerequisites), a machine-readable manifest (`graph.json`), and source provenance.
- `docs/` — agent workflow configuration and (future) ADRs.
- `.claude/skills/` — the engineering skills that define how work happens in this repo.

## Running it (sandbox)

```bash
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.wiki_seed --include-drafts   # load the wiki (drafts allowed pre-review)
.venv/bin/python -m uvicorn app.main:app --port 8000
```

Expose the server with a tunnel (e.g. `ngrok http 8000`), then in the Africa's Talking
**sandbox** dashboard point your USSD channel at `<public-url>/ussd` and your shortcode's
*Incoming Messages* callback at `<public-url>/sms/inbound`. Test the whole loop in the AT
simulator. Configuration lives in `.env` (see `.env.example`); sandbox SMS only appear inside
the simulator, and replies thread correctly when the sender ID is set to the shortcode itself.

Tests: `cd server && .venv/bin/python -m pytest`.

### Sandbox configuration (current pilot)

| Setting | Value |
|---|---|
| Africa's Talking app | Sandbox (`AFRICASTALKING_USERNAME=sandbox`) |
| USSD service code | _fill in from the AT sandbox USSD channel (looks like `*384*NNNN#`)_ |
| Two-way SMS shortcode | `13302` (teachers text `Q`/`T` uploads here) |
| SMS sender ID | `13302` — replies from the shortcode itself, so they thread with the teacher's messages in one conversation. (`Elimu` is registered for production branding; note replies to an alphanumeric sender are impossible.) |
| USSD callback | `<public-url>/ussd` |
| Incoming-SMS callback | `<public-url>/sms/inbound` (SMS → SMS Callback URLs → Incoming Messages) |

Sandbox quirks worth knowing: outbound SMS are delivered only inside the launched simulator
(never to real phones), and only for numbers registered there; messages from an alphanumeric
sender ID appear as a separate conversation thread from the shortcode's.

## Status

Feature-complete MVP, verified end-to-end in the Africa's Talking sandbox. Open work:
educator verification of wiki content against the official KICD designs, a content pipeline
for further learning areas, and production deployment (hosted server, Postgres, live USSD
service code and shortcode).
