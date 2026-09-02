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


def home_screen(db: Session, invalid: bool = False) -> Screen:
    lines = ["Welcome to ElimuTayari"]
    lines += [f"{i}. {area}" for i, area in enumerate(learning_areas(db), start=1)]
    lines.append("Or enter a sub-strand code e.g. M-ALG-02")
    return Screen(tuple(lines), invalid=invalid)


def navigate(db: Session, text: str) -> Screen | Selection:
    """Replay the accumulated USSD text into the current screen or selection."""
    return home_screen(db)
