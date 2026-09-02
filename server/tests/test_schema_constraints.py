"""Schema constraints, observed through a session against the migrated schema.

The seam here is the schema itself, so these tests drive it the way application
code will - adding objects and flushing - and assert on what the database
accepts and rejects.
"""

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ContentUnit,
    GeneratedTest,
    Question,
    Substrand,
    Teacher,
    TeachingSession,
)

PHONE = "+254711223344"
CODE = "M-ALG-02"


def add_substrand(session: Session, code: str = CODE) -> Substrand:
    substrand = Substrand(
        code=code,
        learning_area="Mathematics",
        strand="Algebra",
        title="Formulae and Variations",
    )
    session.add(substrand)
    session.flush()
    return substrand


def add_teacher(session: Session, phone: str = PHONE) -> Teacher:
    teacher = Teacher(phone=phone)
    session.add(teacher)
    session.flush()
    return teacher


def test_valid_rows_are_accepted(session: Session):
    """Positive control: the constraints below reject bad data, not all data."""
    add_substrand(session)
    add_teacher(session)
    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="pack", version=1))
    session.add(Question(teacher_phone=PHONE, substrand_code=CODE, text="why?", source="student"))
    session.add(TeachingSession(teacher_phone=PHONE, substrand_code=CODE))
    session.flush()

    assert session.scalars(select(Question)).one().text == "why?"


def test_substrand_code_is_unique(session: Session):
    add_substrand(session, code="M-NUM-01")

    session.add(
        Substrand(
            code="M-NUM-01",
            learning_area="Mathematics",
            strand="Numbers",
            title="A different title, the same code",
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_substrand_requires_a_title(session: Session):
    session.add(Substrand(code="M-NUM-02", learning_area="Mathematics", strand="Numbers"))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("kind", ["guidance", "activity", "materials", "sms_pack"])
def test_content_unit_accepts_each_documented_kind(session: Session, kind: str):
    add_substrand(session)

    session.add(ContentUnit(substrand_code=CODE, kind=kind, body="body", version=1))
    session.flush()

    assert session.scalars(select(ContentUnit)).one().kind == kind


def test_content_unit_rejects_an_undocumented_kind(session: Session):
    add_substrand(session)

    session.add(ContentUnit(substrand_code=CODE, kind="lesson_plan", body="body", version=1))

    with pytest.raises(IntegrityError):
        session.flush()


def test_content_unit_is_unique_per_substrand_kind_and_version(session: Session):
    add_substrand(session)
    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="first", version=1))
    session.flush()

    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="second", version=1))

    with pytest.raises(IntegrityError):
        session.flush()


def test_content_unit_allows_the_same_kind_at_a_new_version(session: Session):
    """A revised wiki page is seeded alongside the version already sent out."""
    add_substrand(session)
    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="v1", version=1))
    session.flush()

    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="v2", version=2))
    session.flush()

    bodies = set(session.scalars(select(ContentUnit.body)))
    assert bodies == {"v1", "v2"}


@pytest.mark.parametrize("source", ["student", "teacher"])
def test_question_accepts_each_documented_source(session: Session, source: str):
    add_substrand(session)
    add_teacher(session)

    session.add(Question(teacher_phone=PHONE, substrand_code=CODE, text="q", source=source))
    session.flush()

    assert session.scalars(select(Question)).one().source == source


def test_question_rejects_an_undocumented_source(session: Session):
    add_substrand(session)
    add_teacher(session)

    session.add(Question(teacher_phone=PHONE, substrand_code=CODE, text="q", source="parent"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_question_requires_a_substrand_that_exists(session: Session):
    add_teacher(session)

    session.add(
        Question(teacher_phone=PHONE, substrand_code="M-NOPE-99", text="q", source="student")
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_question_requires_a_teacher_that_exists(session: Session):
    """Ticket #3 must create the teacher before storing their question."""
    add_substrand(session)

    session.add(
        Question(teacher_phone="+254700000000", substrand_code=CODE, text="q", source="student")
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_teaching_session_requires_a_teacher_that_exists(session: Session):
    add_substrand(session)

    session.add(TeachingSession(teacher_phone="+254700000000", substrand_code=CODE))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_substrand_removes_its_content_units(session: Session):
    """ON DELETE CASCADE, asserted at the database level: the delete is issued
    as SQL rather than through the ORM, so the DDL is what is under test."""
    add_substrand(session)
    session.add(ContentUnit(substrand_code=CODE, kind="sms_pack", body="pack", version=1))
    session.flush()
    session.expunge_all()

    session.execute(delete(Substrand).where(Substrand.code == CODE))
    session.flush()

    assert session.scalars(select(ContentUnit)).all() == []


def test_deleting_a_substrand_clears_it_from_teachers_last_position(session: Session):
    """ON DELETE SET NULL: a teacher outlives the sub-strand they last browsed."""
    add_substrand(session)
    session.add(Teacher(phone=PHONE, last_substrand=CODE))
    session.flush()
    session.expunge_all()

    session.execute(delete(Substrand).where(Substrand.code == CODE))
    session.flush()

    assert session.scalars(select(Teacher.last_substrand)).one() is None


def test_generated_test_stores_substrand_codes_and_items_as_structured_data(session: Session):
    """The portable JSON columns must survive a round-trip as lists and dicts,
    not as the strings SQLite stores underneath."""
    add_teacher(session)
    add_substrand(session, code="M-ALG-01")
    add_substrand(session, code="M-GEO-03")
    session.add(
        GeneratedTest(
            teacher_phone=PHONE,
            substrand_codes=["M-ALG-01", "M-GEO-03"],
            items_json={"items": [{"q": "Expand (x+2)(x-3)", "marks": 3}]},
        )
    )
    session.flush()
    session.expunge_all()

    stored = session.scalars(select(GeneratedTest)).one()
    assert stored.substrand_codes == ["M-ALG-01", "M-GEO-03"]
    assert stored.items_json["items"][0]["marks"] == 3


def test_foreign_keys_are_enforced_on_sqlite(session: Session):
    """Guards the pragma itself: SQLite silently ignores foreign keys without
    it, which would let development accept rows Postgres rejects."""
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
