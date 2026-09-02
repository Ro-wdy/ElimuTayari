"""Seed reviewed wiki content into the database.

The Markdown wiki (wiki/) is the source of truth for served content. This
module loads it: substrands rows come from each learning area's graph.json
manifest plus the page frontmatter, and content_units rows come from the page
sections ("## SMS teaching pack" -> kind sms_pack, "## Teacher pack" -> kind
guidance).

Review gate: a page is served only once its frontmatter status is "reviewed"
(REVIEWED_STATUS). Every other status - today the wiki carries
draft-human-review throughout - is excluded by default; --include-drafts loads
unreviewed pages anyway for development and sandbox testing.

Frontmatter is parsed with the standard library (the same convention as
scripts/validate_wiki.py): the wiki's frontmatter is flat key: value lines,
and PyYAML is not a declared dependency of the server.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ContentUnit, Question, Substrand, TeachingSession

REVIEWED_STATUS = "reviewed"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SMS_LINE = re.compile(r"^\*\*SMS \d+/\d+:\*\*\s*(.+?)\s*$", re.MULTILINE)


def _section(text: str, heading: str) -> str | None:
    """The body of one "## heading" section, up to the next "## " or EOF."""
    match = re.search(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE
    )
    return match.group(1).strip() if match else None


def _sms_pack_body(text: str) -> str | None:
    """Join the "## SMS teaching pack" messages into one body, one message per
    line, with the Markdown markers stripped - the shape app.sms_pack.split_pack
    re-splits at send time (it prefers line breaks, so each message stays whole
    or is numbered cleanly)."""
    section = _section(text, "SMS teaching pack")
    if section is None:
        return None
    messages = [m.replace("`", "") for m in _SMS_LINE.findall(section)]
    if not messages:
        return None
    return "\n".join(messages)


def _frontmatter_value(metadata: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+?)\s*$", metadata, re.MULTILINE)
    return match.group(1) if match else None


@dataclass(frozen=True)
class ParsedPage:
    """A sub-strand page as written: frontmatter identity plus the extracted
    content bodies, before the manifest supplies strand/learning-area names."""

    code: str
    title: str
    strand_id: str
    status: str
    sms_pack: str | None
    guidance: str | None


def parse_page(text: str) -> ParsedPage:
    """Parse one sub-strand Markdown page.

    Raises ValueError when the page lacks frontmatter or a required key, so a
    malformed page fails the seed loudly instead of seeding partial rows.
    """
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError("page has no YAML frontmatter")
    metadata = match.group(1)

    values: dict[str, str] = {}
    for key in ("id", "title", "strand_id", "status"):
        value = _frontmatter_value(metadata, key)
        if value is None:
            raise ValueError(f"frontmatter is missing {key}")
        values[key] = value

    return ParsedPage(
        code=values["id"],
        title=values["title"],
        strand_id=values["strand_id"],
        status=values["status"],
        sms_pack=_sms_pack_body(text),
        guidance=_section(text, "Teacher pack"),
    )


@dataclass(frozen=True)
class WikiPage:
    """A sub-strand page joined with its manifest: everything the database
    rows need."""

    code: str
    title: str
    learning_area: str
    strand: str
    status: str
    sms_pack: str | None
    guidance: str | None


def _strand_names(graph: dict) -> dict[str, tuple[str, str]]:
    """strand id -> (learning-area title, strand title), resolved by following
    the strand's part-of edge to its learning-area node."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    names: dict[str, tuple[str, str]] = {}
    for edge in graph.get("edges", []):
        source = nodes.get(edge.get("from"))
        target = nodes.get(edge.get("to"))
        if (
            edge.get("type") == "part-of"
            and source is not None
            and target is not None
            and source.get("type") == "strand"
            and target.get("type") == "learning-area"
        ):
            names[source["id"]] = (target["title"], source["title"])
    return names


def load_wiki(wiki_root: Path) -> list[WikiPage]:
    """Read every learning area's graph.json manifest under wiki_root and parse
    the sub-strand pages it lists.

    The manifest drives discovery, so a page removed from the wiki (file or
    manifest entry) simply stops being loaded; frontmatter drives identity and
    status. A manifest entry whose page file is missing is skipped rather than
    failing the whole seed.
    """
    pages: list[WikiPage] = []
    for graph_path in sorted(wiki_root.glob("*/*/graph.json")):
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        strand_names = _strand_names(graph)
        for node in graph.get("nodes", []):
            if node.get("type") != "sub-strand" or not node.get("path"):
                continue
            page_path = graph_path.parent / node["path"]
            if not page_path.exists():
                continue
            parsed = parse_page(page_path.read_text(encoding="utf-8"))
            if parsed.strand_id not in strand_names:
                raise ValueError(
                    f"{page_path}: strand {parsed.strand_id} has no part-of edge "
                    "to a learning-area in graph.json"
                )
            learning_area, strand = strand_names[parsed.strand_id]
            pages.append(
                WikiPage(
                    code=parsed.code,
                    title=parsed.title,
                    learning_area=learning_area,
                    strand=strand,
                    status=parsed.status,
                    sms_pack=parsed.sms_pack,
                    guidance=parsed.guidance,
                )
            )
    return pages


@dataclass(frozen=True)
class WikiSeedResult:
    substrands_created: int = 0
    substrands_updated: int = 0
    substrands_removed: int = 0
    substrands_retained: int = 0
    content_units_created: int = 0
    content_units_unchanged: int = 0
    pages_excluded: int = 0
    pages_unservable: int = 0


def _servable(page: WikiPage, include_drafts: bool) -> tuple[bool, str | None]:
    """Whether a page is served, and if not, why: "excluded" (review gate) or
    "unservable" (no SMS pack to send)."""
    if page.status != REVIEWED_STATUS and not include_drafts:
        return False, "excluded"
    if not page.sms_pack:
        return False, "unservable"
    return True, None


def seed_wiki_content(
    session: Session, pages: list[WikiPage], include_drafts: bool = False
) -> WikiSeedResult:
    """Insert or refresh the database rows for the servable wiki pages.

    Substrands are matched on code and updated in place. Content units are
    append-only: an edited body is inserted as a new version (the serving query
    takes the highest), an unchanged body is left alone, so re-seeding an
    unedited wiki is a no-op.

    The substrands table is then a mirror of the servable wiki: any row whose
    code is no longer servable - a page removed, demoted below the review gate,
    or left over from the placeholder seeder - is deleted, which removes it from
    the USSD menus and (via ON DELETE CASCADE) drops its content units.

    Exception: a stale sub-strand with recorded questions or teaching sessions
    is RETAINED, not deleted - deleting it would cascade those rows away, and a
    page demoted for revision (or a habitual run without --include-drafts while
    the wiki is still all drafts) must never erase what teachers already sent.
    A retained sub-strand keeps serving its last content until the page returns.
    """
    servable: list[WikiPage] = []
    excluded = unservable = 0
    for page in pages:
        ok, reason = _servable(page, include_drafts)
        if ok:
            servable.append(page)
        elif reason == "excluded":
            excluded += 1
        else:
            unservable += 1

    created = updated = 0
    for page in servable:
        substrand = session.get(Substrand, page.code)
        if substrand is None:
            session.add(
                Substrand(
                    code=page.code,
                    learning_area=page.learning_area,
                    strand=page.strand,
                    title=page.title,
                )
            )
            created += 1
        else:
            substrand.learning_area = page.learning_area
            substrand.strand = page.strand
            substrand.title = page.title
            updated += 1
    session.flush()

    servable_codes = {page.code for page in servable}
    stale = session.scalars(
        select(Substrand.code).where(Substrand.code.not_in(servable_codes))
    ).all()
    with_data = set(
        session.scalars(
            select(Question.substrand_code)
            .where(Question.substrand_code.in_(stale))
            .distinct()
        )
    ) | set(
        session.scalars(
            select(TeachingSession.substrand_code)
            .where(TeachingSession.substrand_code.in_(stale))
            .distinct()
        )
    )
    prunable = [code for code in stale if code not in with_data]
    if prunable:
        # A core DELETE so the database's ON DELETE rules apply (content units
        # cascade away; a teacher's last_substrand is set NULL). Only rows with
        # no questions and no teaching sessions reach this delete.
        session.execute(delete(Substrand).where(Substrand.code.in_(prunable)))
        session.expire_all()
    removed = len(prunable)
    retained = len(stale) - removed

    units_created = units_unchanged = 0
    for page in servable:
        for kind, body in (("sms_pack", page.sms_pack), ("guidance", page.guidance)):
            if not body:
                continue
            latest = session.scalars(
                select(ContentUnit)
                .where(
                    ContentUnit.substrand_code == page.code,
                    ContentUnit.kind == kind,
                )
                .order_by(ContentUnit.version.desc())
                .limit(1)
            ).one_or_none()
            if latest is not None and latest.body == body:
                units_unchanged += 1
                continue
            version = 1 if latest is None else latest.version + 1
            session.add(
                ContentUnit(
                    substrand_code=page.code, kind=kind, body=body, version=version
                )
            )
            units_created += 1
    session.flush()

    return WikiSeedResult(
        substrands_created=created,
        substrands_updated=updated,
        substrands_removed=removed,
        substrands_retained=retained,
        content_units_created=units_created,
        content_units_unchanged=units_unchanged,
        pages_excluded=excluded,
        pages_unservable=unservable,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WIKI_ROOT = REPO_ROOT / "wiki"


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m app.wiki_seed",
        description="Seed reviewed wiki content into the database.",
    )
    parser.add_argument(
        "--wiki-root",
        type=Path,
        default=DEFAULT_WIKI_ROOT,
        help=f"wiki directory to load (default: {DEFAULT_WIKI_ROOT})",
    )
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help=(
            "also load pages whose status is not "
            f'"{REVIEWED_STATUS}" (development/sandbox only)'
        ),
    )
    args = parser.parse_args(argv)

    from app.config import get_settings
    from app.db import create_db_engine, create_session_factory

    pages = load_wiki(args.wiki_root)

    engine = create_db_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        result = seed_wiki_content(session, pages, include_drafts=args.include_drafts)
        session.commit()
    finally:
        session.close()
        engine.dispose()

    print(
        f"Seeded wiki from {args.wiki_root}: "
        f"{result.substrands_created} sub-strands created, "
        f"{result.substrands_updated} updated, "
        f"{result.substrands_removed} removed, "
        f"{result.substrands_retained} retained (teacher data recorded); "
        f"{result.content_units_created} content units created, "
        f"{result.content_units_unchanged} unchanged; "
        f"{result.pages_excluded} pages excluded (not {REVIEWED_STATUS}), "
        f"{result.pages_unservable} unservable (no SMS pack)."
    )
    if result.pages_excluded and not args.include_drafts:
        print("Pass --include-drafts to load unreviewed pages in development.")


if __name__ == "__main__":
    main()
