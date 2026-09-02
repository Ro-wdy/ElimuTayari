"""The wiki seed: loading reviewed wiki pages into the database.

Parsing is tested against the real wiki pages in wiki/ (the worktree carries
them) so the parser is held to the format that actually ships, plus synthetic
pages for the edge cases the real wiki does not currently exhibit (a signed-off
status, a missing SMS section, a re-seed after an edit).
"""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import create_db_engine, create_session_factory

from app.models import ContentUnit, Substrand
from app.seed import seed_placeholder_content
from app.wiki_seed import WikiPage, load_wiki, main, parse_page, seed_wiki_content

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_ROOT = REPO_ROOT / "wiki"
MATHS = WIKI_ROOT / "grade-10" / "core-mathematics"


def test_parse_page_reads_frontmatter_from_a_real_wiki_page():
    text = (MATHS / "sub-strands" / "M-ALG-02-indices-and-logarithms.md").read_text(
        encoding="utf-8"
    )

    page = parse_page(text)

    assert page.code == "M-ALG-02"
    assert page.title == "Indices and Logarithms"
    assert page.strand_id == "M-ALG"
    assert page.status == "draft-human-review"


def test_parse_page_joins_the_sms_messages_into_one_pack_body():
    """The stored body is what app.sms_pack.split_pack re-splits at send time:
    one message per line, the "**SMS i/n:**" markers and backticks gone."""
    text = (MATHS / "sub-strands" / "M-ALG-02-indices-and-logarithms.md").read_text(
        encoding="utf-8"
    )

    page = parse_page(text)

    lines = page.sms_pack.split("\n")
    assert len(lines) == 3
    assert lines[0].startswith("M-ALG-02 Index laws:")
    assert "**SMS" not in page.sms_pack
    assert "`" not in page.sms_pack
    assert all(len(line) <= 160 for line in lines)


def test_parse_page_extracts_the_teacher_pack_as_guidance():
    text = (MATHS / "sub-strands" / "M-ALG-02-indices-and-logarithms.md").read_text(
        encoding="utf-8"
    )

    page = parse_page(text)

    assert page.guidance.startswith("### Learning sequence")
    assert "Common misconceptions" in page.guidance
    # The section ends where the next "## " heading begins.
    assert "Worked example" not in page.guidance


def synthetic_page(
    code: str = "M-TST-01",
    status: str = "reviewed",
    sms_section: str = (
        "## SMS teaching pack\n\n"
        "**SMS 1/2:** `M-TST-01` First message.\n\n"
        "**SMS 2/2:** Second message.\n"
    ),
) -> str:
    return (
        "---\n"
        f"id: {code}\n"
        "curriculum_ref: 9.9\n"
        "type: sub-strand\n"
        "title: Test Sub-strand\n"
        "strand_id: M-TST\n"
        f"status: {status}\n"
        "---\n\n"
        f"# {code}: Test Sub-strand\n\n"
        "## Teacher pack\n\n"
        "### Learning sequence\n\n"
        "1. Teach the thing.\n\n"
        f"{sms_section}"
    )


def test_parse_page_without_an_sms_section_has_no_pack():
    page = parse_page(synthetic_page(sms_section=""))

    assert page.sms_pack is None


def test_load_wiki_reads_every_manifest_page_with_names_from_the_graph():
    pages = load_wiki(WIKI_ROOT)

    assert len(pages) == 14
    by_code = {page.code: page for page in pages}
    algebra = by_code["M-ALG-02"]
    assert algebra.learning_area == "Core Mathematics"
    assert algebra.strand == "Numbers and Algebra"
    assert algebra.title == "Indices and Logarithms"
    assert by_code["M-STA-02"].strand == "Statistics and Probability"
    assert all(page.sms_pack for page in pages)


def wiki_page(
    code: str = "M-TST-01",
    status: str = "reviewed",
    sms_pack: str | None = "M-TST-01 First message.\nSecond message.",
    guidance: str | None = "### Learning sequence\n\n1. Teach the thing.",
    title: str = "Test Sub-strand",
) -> WikiPage:
    return WikiPage(
        code=code,
        title=title,
        learning_area="Core Mathematics",
        strand="Testing",
        status=status,
        sms_pack=sms_pack,
        guidance=guidance,
    )


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_loads_reviewed_pages_and_skips_unreviewed_ones(session: Session):
    pages = [
        wiki_page(code="M-TST-01", status="reviewed"),
        wiki_page(code="M-TST-02", status="draft-human-review"),
    ]

    result = seed_wiki_content(session, pages)

    assert session.get(Substrand, "M-TST-01") is not None
    assert session.get(Substrand, "M-TST-02") is None
    assert result.pages_excluded == 1


def test_include_drafts_loads_the_real_wiki_before_sign_off(session: Session):
    """Today every wiki page is draft-human-review; the development flag loads
    them anyway so the sandbox can serve real content before review."""
    pages = load_wiki(WIKI_ROOT)

    gated = seed_wiki_content(session, pages)
    included = seed_wiki_content(session, pages, include_drafts=True)

    assert gated.substrands_created == 0
    assert gated.pages_excluded == 14
    assert included.substrands_created == 14
    assert count(session, Substrand) == 14
    packs = session.scalars(
        select(ContentUnit).where(ContentUnit.kind == "sms_pack")
    ).all()
    assert len(packs) == 14
    guidance = session.scalars(
        select(ContentUnit).where(ContentUnit.kind == "guidance")
    ).all()
    assert len(guidance) == 14


def latest_pack(session: Session, code: str) -> ContentUnit:
    """The pack the USSD route serves: highest version wins."""
    return session.scalars(
        select(ContentUnit)
        .where(ContentUnit.substrand_code == code, ContentUnit.kind == "sms_pack")
        .order_by(ContentUnit.version.desc())
        .limit(1)
    ).one()


def test_reseeding_an_unedited_wiki_changes_nothing(session: Session):
    pages = [wiki_page()]
    seed_wiki_content(session, pages)

    second = seed_wiki_content(session, pages)

    assert second.content_units_created == 0
    assert second.content_units_unchanged == 2
    assert count(session, ContentUnit) == 2
    assert latest_pack(session, "M-TST-01").version == 1


def test_reseeding_an_edited_page_bumps_the_version_and_serves_the_new_body(
    session: Session,
):
    seed_wiki_content(session, [wiki_page()])

    seed_wiki_content(
        session, [wiki_page(sms_pack="M-TST-01 Revised message after review.")]
    )

    served = latest_pack(session, "M-TST-01")
    assert served.version == 2
    assert served.body == "M-TST-01 Revised message after review."


def test_demoting_a_page_removes_it_from_serving_on_the_next_seed(session: Session):
    seed_wiki_content(
        session,
        [wiki_page(code="M-TST-01"), wiki_page(code="M-TST-02")],
    )

    result = seed_wiki_content(
        session,
        [
            wiki_page(code="M-TST-01"),
            wiki_page(code="M-TST-02", status="draft-human-review"),
        ],
    )

    assert result.substrands_removed == 1
    assert session.get(Substrand, "M-TST-02") is None
    assert count(session, Substrand) == 1
    units = session.scalars(select(ContentUnit.substrand_code).distinct()).all()
    assert units == ["M-TST-01"]


def test_removing_a_page_from_the_wiki_removes_it_from_serving(session: Session):
    seed_wiki_content(
        session,
        [wiki_page(code="M-TST-01"), wiki_page(code="M-TST-02")],
    )

    seed_wiki_content(session, [wiki_page(code="M-TST-01")])

    assert session.get(Substrand, "M-TST-02") is None
    assert count(session, Substrand) == 1


def test_wiki_seed_replaces_placeholder_content_without_duplicating(session: Session):
    """A database seeded with app.seed placeholders converges on the wiki:
    placeholder-only codes disappear, shared codes are updated in place, and
    the pack served for a shared code is the wiki's, not the placeholder."""
    seed_placeholder_content(session)

    seed_wiki_content(session, load_wiki(WIKI_ROOT), include_drafts=True)

    assert count(session, Substrand) == 14
    assert session.get(Substrand, "M-NUM-01") is None  # placeholder-only code
    algebra = session.get(Substrand, "M-ALG-02")  # code shared with placeholder
    assert algebra.title == "Indices and Logarithms"
    assert algebra.learning_area == "Core Mathematics"
    served = latest_pack(session, "M-ALG-02")
    assert served.version == 2  # bumped past the placeholder's version 1
    assert "[PLACEHOLDER]" not in served.body


def test_a_page_without_an_sms_pack_is_not_seeded(session: Session):
    """A sub-strand the teacher can browse to but never receive a pack for is
    worse than one that is absent, so a page missing its SMS section stays out."""
    result = seed_wiki_content(session, [wiki_page(sms_pack=None)])

    assert result.pages_unservable == 1
    assert count(session, Substrand) == 0


def test_ussd_selection_delivers_the_real_wiki_pack_not_placeholder(
    client, migrated_database_url, sms_outbox
):
    """The end-to-end check at the /ussd HTTP seam: after the wiki seed has
    replaced the placeholders, picking a sub-strand sends the wiki's SMS pack."""
    engine = create_db_engine(migrated_database_url)
    seed_session = create_session_factory(engine)()
    try:
        seed_placeholder_content(seed_session)
        seed_wiki_content(seed_session, load_wiki(WIKI_ROOT), include_drafts=True)
        seed_session.commit()
    finally:
        seed_session.close()
        engine.dispose()

    response = client.post(
        "/ussd",
        data={
            "sessionId": "ATUid_wiki",
            "phoneNumber": "+254700000001",
            "networkCode": "63902",
            "serviceCode": "*384*1234#",
            "text": "M-ALG-02",
        },
    )

    assert response.status_code == 200
    assert response.text.startswith("END M-ALG-02")
    sent = "\n".join(message for _, message in sms_outbox.sent)
    assert "Index laws" in sent
    assert "[PLACEHOLDER]" not in sent


def test_cli_seeds_the_configured_database(
    migrated_database_url, monkeypatch, capsys, session: Session
):
    """python -m app.wiki_seed, as a deploy runs it: no web server, database
    from DATABASE_URL, drafts only behind the flag."""
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)

    main(["--include-drafts", "--wiki-root", str(WIKI_ROOT)])

    assert count(session, Substrand) == 14
    out = capsys.readouterr().out
    assert "14 sub-strands created" in out
