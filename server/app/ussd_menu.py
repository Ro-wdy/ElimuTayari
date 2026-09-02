"""USSD menu state machine and screen rendering.

Africa's Talking gives the callback no per-session storage: the whole history
of the caller's inputs arrives on every request as one accumulated text field
("1*2*1"). The menu is therefore a pure function of that text plus the
database - each request replays the tokens from the home screen forward, so
no server-side session state exists to lose.

Constraints honoured here:

- every rendered screen fits within MAX_SCREEN_CHARS (~160), enforced by test;
- an invalid token leaves the caller on the same screen with a short error
  line (CON re-prompt) instead of ending the session, and later tokens still
  apply, so a mis-key does not strand the caller;
- menu entries come from the substrands table (seeded from the wiki), never
  from hardcoded lists;
- a sub-strand code (e.g. M-ALG-02, case-insensitive) typed at the home
  screen jumps straight to that sub-strand.

Navigation resolves to either a Screen (rendered as a CON reply) or a
Selection (the route records the teaching session, sends the pack and replies
END): the side effects stay in the route, keeping this module read-only
against the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Substrand

MAX_SCREEN_CHARS = 160

INVALID_LINE = "Invalid choice."


@dataclass(frozen=True)
class Screen:
    """A CON reply: the menu lines to show, re-prompting if the last input
    was invalid."""

    lines: tuple[str, ...]
    invalid: bool = False

    def render(self) -> str:
        lines = (INVALID_LINE, *self.lines) if self.invalid else self.lines
        return "CON " + "\n".join(lines)


@dataclass(frozen=True)
class Selection:
    """The caller picked a sub-strand: the route turns this into side effects
    and an END reply."""

    substrand: Substrand


def learning_areas(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(Substrand.learning_area).distinct().order_by(Substrand.learning_area)
        )
    )


def strands(db: Session, learning_area: str) -> list[str]:
    return list(
        db.scalars(
            select(Substrand.strand)
            .where(Substrand.learning_area == learning_area)
            .distinct()
            .order_by(Substrand.strand)
        )
    )


def substrands(db: Session, learning_area: str, strand: str) -> list[Substrand]:
    return list(
        db.scalars(
            select(Substrand)
            .where(
                Substrand.learning_area == learning_area, Substrand.strand == strand
            )
            .order_by(Substrand.code)
        )
    )


def home_screen(db: Session, invalid: bool = False) -> Screen:
    lines = ["Welcome to ElimuTayari"]
    lines += [f"{i}. {area}" for i, area in enumerate(learning_areas(db), start=1)]
    lines.append("Or enter a sub-strand code e.g. M-ALG-02")
    return Screen(tuple(lines), invalid=invalid)


def strands_screen(db: Session, learning_area: str, invalid: bool = False) -> Screen:
    lines = [f"{learning_area} strands"]
    lines += [f"{i}. {s}" for i, s in enumerate(strands(db, learning_area), start=1)]
    return Screen(tuple(lines), invalid=invalid)


def substrands_screen(
    db: Session, learning_area: str, strand: str, invalid: bool = False
) -> Screen:
    lines = [strand]
    lines += [
        f"{i}. {s.title}"
        for i, s in enumerate(substrands(db, learning_area, strand), start=1)
    ]
    return Screen(tuple(lines), invalid=invalid)


def _pick(options: list[str], token: str) -> str | None:
    """The option a numeric menu token selects, or None if out of range."""
    if token.isdigit() and 1 <= int(token) <= len(options):
        return options[int(token) - 1]
    return None


@dataclass
class _State:
    """Where the replayed tokens have navigated to so far."""

    learning_area: str | None = None
    strand: str | None = None


def navigate(db: Session, text: str) -> Screen | Selection:
    """Replay the accumulated USSD text into the current screen or selection.

    Each request re-derives the caller's position from the full text, one
    token at a time. A token that matches nothing is skipped with the invalid
    flag set, so the caller is re-prompted on the same screen and their next
    input still lands where they expect.
    """
    state = _State()
    invalid = False
    tokens = [t.strip() for t in text.split("*") if t.strip()]
    for token in tokens:
        invalid = not _apply(db, state, token)
    return _screen_for(db, state, invalid)


def _apply(db: Session, state: _State, token: str) -> bool:
    """Advance state by one token; False if the token matched nothing."""
    if state.learning_area is None:
        area = _pick(learning_areas(db), token)
        if area is not None:
            state.learning_area = area
            return True
        return False
    if state.strand is None:
        strand = _pick(strands(db, state.learning_area), token)
        if strand is not None:
            state.strand = strand
            return True
        return False
    return False


def _screen_for(db: Session, state: _State, invalid: bool) -> Screen:
    if state.learning_area is None:
        return home_screen(db, invalid=invalid)
    if state.strand is None:
        return strands_screen(db, state.learning_area, invalid=invalid)
    return substrands_screen(db, state.learning_area, state.strand, invalid=invalid)
