"""Seed placeholder Grade 10 Mathematics content.

Downstream tickets need sub-strand codes and one SMS pack per code to work
against before the real wiki exists. The titles and codes here follow the KICD
Grade 10 Mathematics strands so the codes are stable, but every body is
placeholder text: ticket #6 generates real content and ticket #7 seeds it.

Seeding is idempotent - it is run on every deploy and by tests - so rows are
matched on their natural keys (substrands.code, and the
(substrand_code, kind, version) unique constraint on content_units) and updated
in place rather than inserted again.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentUnit, Substrand

LEARNING_AREA = "Mathematics"
SMS_PACK_VERSION = 1


@dataclass(frozen=True)
class SeedSubstrand:
    code: str
    strand: str
    title: str


PLACEHOLDER_SUBSTRANDS: tuple[SeedSubstrand, ...] = (
    SeedSubstrand("M-NUM-01", "Numbers", "Indices and Logarithms"),
    SeedSubstrand("M-NUM-02", "Numbers", "Compound Proportions and Rates of Work"),
    SeedSubstrand("M-NUM-03", "Numbers", "Approximations and Errors"),
    SeedSubstrand("M-ALG-01", "Algebra", "Matrices"),
    SeedSubstrand("M-ALG-02", "Algebra", "Formulae and Variations"),
    SeedSubstrand("M-ALG-03", "Algebra", "Quadratic Equations and Expressions"),
    SeedSubstrand("M-MEA-01", "Measurements", "Area of a Triangle"),
    SeedSubstrand("M-MEA-02", "Measurements", "Area of Part of a Circle"),
    SeedSubstrand("M-MEA-03", "Measurements", "Surface Area of Solids"),
    SeedSubstrand("M-GEO-01", "Geometry", "Coordinates and Graphs"),
    SeedSubstrand("M-GEO-02", "Geometry", "Scale Drawing"),
    SeedSubstrand("M-GEO-03", "Geometry", "Trigonometric Ratios"),
    SeedSubstrand("M-DAT-01", "Data Handling and Probability", "Data Presentation"),
    SeedSubstrand("M-DAT-02", "Data Handling and Probability", "Measures of Central Tendency"),
    SeedSubstrand("M-DAT-03", "Data Handling and Probability", "Probability"),
)


def placeholder_sms_pack(substrand: SeedSubstrand) -> str:
    return (
        f"[PLACEHOLDER] {substrand.code} {substrand.title}\n"
        f"1. Outcome: learners can work with {substrand.title.lower()}.\n"
        "2. Activity: worked example on the board, then pairs.\n"
        "3. Materials: exercise books, chalkboard.\n"
        "Reply Q <code> <question> after class."
    )


@dataclass(frozen=True)
class SeedResult:
    substrands_created: int
    substrands_updated: int
    content_units_created: int
    content_units_updated: int


def seed_placeholder_content(session: Session) -> SeedResult:
    """Insert or refresh the placeholder Mathematics sub-strands and SMS packs.

    Sub-strands are flushed before their content units so the rows the foreign
    key points at exist by the time the content-unit INSERTs are emitted.
    """
    created = updated = 0
    for entry in PLACEHOLDER_SUBSTRANDS:
        substrand = session.get(Substrand, entry.code)
        if substrand is None:
            session.add(
                Substrand(
                    code=entry.code,
                    learning_area=LEARNING_AREA,
                    strand=entry.strand,
                    title=entry.title,
                )
            )
            created += 1
        else:
            substrand.learning_area = LEARNING_AREA
            substrand.strand = entry.strand
            substrand.title = entry.title
            updated += 1
    session.flush()

    units_created = units_updated = 0
    for entry in PLACEHOLDER_SUBSTRANDS:
        body = placeholder_sms_pack(entry)
        unit = session.scalars(
            select(ContentUnit).where(
                ContentUnit.substrand_code == entry.code,
                ContentUnit.kind == "sms_pack",
                ContentUnit.version == SMS_PACK_VERSION,
            )
        ).one_or_none()
        if unit is None:
            session.add(
                ContentUnit(
                    substrand_code=entry.code,
                    kind="sms_pack",
                    body=body,
                    version=SMS_PACK_VERSION,
                )
            )
            units_created += 1
        else:
            unit.body = body
            units_updated += 1
    session.flush()

    return SeedResult(created, updated, units_created, units_updated)


def main() -> None:
    from app.config import get_settings
    from app.db import create_db_engine, create_session_factory

    engine = create_db_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        result = seed_placeholder_content(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()

    print(
        f"Seeded {LEARNING_AREA}: "
        f"{result.substrands_created} sub-strands created, "
        f"{result.substrands_updated} updated; "
        f"{result.content_units_created} SMS packs created, "
        f"{result.content_units_updated} updated."
    )


if __name__ == "__main__":
    main()
