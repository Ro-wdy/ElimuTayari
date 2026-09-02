"""Database schema.

Written for SQLite (local development) and Postgres (production) from one set
of models, so:

- enumerated columns are String + CHECK constraints, not native ENUM types,
  which SQLite has no equivalent for and which Postgres cannot alter in place;
- list/structured columns use the portable JSON type (JSON on Postgres,
  TEXT on SQLite);
- timestamps are timezone-aware and defaulted in Python, since server-side
  now() spellings differ between the two backends;
- every constraint and index is named by convention, because Alembic cannot
  emit an ALTER for an unnamed constraint on either backend.

Parent-to-child relationships are declared rather than left implicit in the
foreign-key columns: the ORM derives flush ordering from relationships, so
without them a single session that adds a parent and its child can emit the
child INSERT first and trip the foreign key.

Sub-strand codes (e.g. M-ALG-02) are the shared identifier across the wiki,
USSD navigation and SMS commands, so substrands.code is the natural primary key
and every other table references it rather than a surrogate id.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

CONTENT_KINDS = ("guidance", "activity", "materials", "sms_pack")
QUESTION_SOURCES = ("student", "teacher")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    allowed = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({allowed})"


class Substrand(Base):
    """A CBC sub-strand: the unit a teacher browses to and teaches from."""

    __tablename__ = "substrands"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    learning_area: Mapped[str] = mapped_column(String(64), nullable=False)
    strand: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)

    content_units: Mapped[list["ContentUnit"]] = relationship(
        back_populates="substrand", cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(back_populates="substrand")
    teaching_sessions: Mapped[list["TeachingSession"]] = relationship(
        back_populates="substrand"
    )


class Teacher(Base):
    """A teacher, identified by the phone number they call and text from."""

    __tablename__ = "teachers"

    phone: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_substrand: Mapped[str | None] = mapped_column(
        ForeignKey("substrands.code", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    questions: Mapped[list["Question"]] = relationship(back_populates="teacher")
    teaching_sessions: Mapped[list["TeachingSession"]] = relationship(
        back_populates="teacher"
    )
    tests: Mapped[list["Test"]] = relationship(back_populates="teacher")


class ContentUnit(Base):
    """One piece of wiki content for a sub-strand, seeded from the Markdown wiki.

    Versioned so a revised wiki page can be seeded alongside the version already
    sent to teachers. One row per (sub-strand, kind, version).
    """

    __tablename__ = "content_units"
    __table_args__ = (
        CheckConstraint(_in_list("kind", CONTENT_KINDS), name="kind_valid"),
        UniqueConstraint("substrand_code", "kind", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    substrand_code: Mapped[str] = mapped_column(
        ForeignKey("substrands.code", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    substrand: Mapped["Substrand"] = relationship(back_populates="content_units")


class TeachingSession(Base):
    """A record that a teacher taught a sub-strand: the denominator for hotspot
    analytics, where questions are weighted per teaching session."""

    __tablename__ = "teaching_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_phone: Mapped[str] = mapped_column(
        ForeignKey("teachers.phone", ondelete="CASCADE"), nullable=False, index=True
    )
    substrand_code: Mapped[str] = mapped_column(
        ForeignKey("substrands.code", ondelete="CASCADE"), nullable=False, index=True
    )
    taught_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    teacher: Mapped["Teacher"] = relationship(back_populates="teaching_sessions")
    substrand: Mapped["Substrand"] = relationship(back_populates="teaching_sessions")


class Question(Base):
    """A question uploaded after class, from a student or the teacher.

    Feeds test generation and topic-difficulty analytics.
    """

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(_in_list("source", QUESTION_SOURCES), name="source_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_phone: Mapped[str] = mapped_column(
        ForeignKey("teachers.phone", ondelete="CASCADE"), nullable=False, index=True
    )
    substrand_code: Mapped[str] = mapped_column(
        ForeignKey("substrands.code", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    teacher: Mapped["Teacher"] = relationship(back_populates="questions")
    substrand: Mapped["Substrand"] = relationship(back_populates="questions")


class Test(Base):
    """A generated test sent to a teacher.

    Spans one or more sub-strands, so substrand_codes is a JSON list rather than
    a single foreign key; items_json holds the generated items as produced.
    """

    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_phone: Mapped[str] = mapped_column(
        ForeignKey("teachers.phone", ondelete="CASCADE"), nullable=False, index=True
    )
    substrand_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    items_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    teacher: Mapped["Teacher"] = relationship(back_populates="tests")
