# ElimuTayari

An LLM-wiki teaching companion for Grade 10 teachers in Kenya (CBC curriculum), accessed
from any GSM phone via USSD and SMS (Africa's Talking). Teachers pick a strand, receive a
teaching pack by SMS, and upload student questions after class; those questions feed test
generation and topic-difficulty analytics. Wiki content is pre-generated with Claude from
the official KICD Grade 10 curriculum designs and human-reviewed; the live LLM only
generates tests and clusters questions.

## Monorepo layout

This is a monorepo. Planned packages (create them as work begins, don't scaffold ahead of
need):

- `server/` — FastAPI app: USSD callback, inbound-SMS webhook, outbound SMS, DB (SQLite dev / Postgres prod)
- `wiki/` — the Markdown LLM wiki: curriculum content by learning area → strand → sub-strand, source of truth for `server/` content (seeded into the DB)
- `scripts/` — content pipeline: KICD PDF extraction, Claude generation, DB seeding

Sub-strand codes (e.g. `M-ALG-02`) are the shared identifier across wiki pages, DB rows,
USSD navigation, and SMS commands.

## Working standard

The engineering skills in `.claude/skills/` are the standard for how work happens in this
repo. When beginning a piece of work, reach for the matching skill rather than improvising:

- Building a feature from a spec or tickets: `/implement` (drives `/tdd`, closes with a review)
- Writing or fixing code with tests: `/tdd`
- Designing modules or APIs: consult `codebase-design` and `domain-modeling`
- Hard bugs or performance regressions: `diagnosing-bugs`
- Turning a plan or conversation into tickets: `/to-tickets`; into a spec: `/to-spec`
- Unsure which flow fits: `/ask-matt`

Note: this repo's `code-review` skill (standards + spec review) coexists with Claude
Code's built-in `/code-review` (bug hunting). If a skill invocation is ambiguous, the
repo-local skill is the one the `implement` flow refers to.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `Ro-wdy/ElimuTayari`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root (created lazily by `/domain-modeling`; proceed silently if absent). See `docs/agents/domain.md`.
