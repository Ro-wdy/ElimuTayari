"""The placeholder-content seed.

The seed runs on every deploy and in tests, so idempotency is a property worth
holding it to: running it again must converge on the same rows rather than
duplicating or drifting.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ContentUnit, Substrand
from app.seed import PLACEHOLDER_SUBSTRANDS, seed_placeholder_content

EXPECTED_SUBSTRAND_COUNT = 15


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_loads_every_placeholder_substrand(session: Session):
    seed_placeholder_content(session)

    assert count(session, Substrand) == EXPECTED_SUBSTRAND_COUNT


def test_seed_gives_every_substrand_one_sms_pack(session: Session):
    seed_placeholder_content(session)

    packs = session.scalars(
        select(func.count()).select_from(ContentUnit).where(ContentUnit.kind == "sms_pack")
    ).one()
    assert packs == EXPECTED_SUBSTRAND_COUNT


def test_seeded_substrands_are_retrievable_by_code(session: Session):
    seed_placeholder_content(session)

    substrand = session.get(Substrand, "M-ALG-02")
    assert substrand is not None
    assert substrand.learning_area == "Mathematics"
    assert substrand.strand == "Algebra"
    assert substrand.title == "Formulae and Variations"


def test_seeded_substrand_codes_are_unique(session: Session):
    codes = [entry.code for entry in PLACEHOLDER_SUBSTRANDS]

    assert len(set(codes)) == len(codes)


def test_seeding_twice_does_not_duplicate_rows(session: Session):
    seed_placeholder_content(session)

    seed_placeholder_content(session)

    assert count(session, Substrand) == EXPECTED_SUBSTRAND_COUNT
    assert count(session, ContentUnit) == EXPECTED_SUBSTRAND_COUNT


def test_seeding_reports_creations_first_then_updates(session: Session):
    first = seed_placeholder_content(session)

    second = seed_placeholder_content(session)

    assert (first.substrands_created, first.substrands_updated) == (15, 0)
    assert (second.substrands_created, second.substrands_updated) == (0, 15)
    assert (first.content_units_created, first.content_units_updated) == (15, 0)
    assert (second.content_units_created, second.content_units_updated) == (0, 15)


def test_reseeding_restores_content_that_drifted(session: Session):
    """The seed is the source of truth for placeholder content, so a row edited
    out of band must be brought back into line rather than left alone."""
    seed_placeholder_content(session)
    pack = session.scalars(
        select(ContentUnit).where(ContentUnit.substrand_code == "M-ALG-02")
    ).one()
    original_body = pack.body
    pack.body = "edited out of band"
    session.flush()

    seed_placeholder_content(session)

    refreshed = session.scalars(
        select(ContentUnit).where(ContentUnit.substrand_code == "M-ALG-02")
    ).one()
    assert refreshed.body == original_body


def test_every_seeded_pack_names_its_substrand(session: Session):
    """A teacher receiving a pack by SMS needs to know which sub-strand it is."""
    seed_placeholder_content(session)

    units = session.scalars(select(ContentUnit)).all()
    assert len(units) == EXPECTED_SUBSTRAND_COUNT
    for unit in units:
        assert unit.substrand_code in unit.body
