"""USSD menu state machine and screen rendering.

Africa's Talking gives the callback no per-session storage: the whole history
of the caller's inputs arrives on every request as one accumulated text field
("1*2*1"). The menu is therefore a pure function of that text, the caller's
phone number (also on every request), and the database - each request replays
the tokens from the home screen forward, so no server-side session state
exists to lose.

Constraints honoured here:

- every rendered screen fits within MAX_SCREEN_CHARS (~160), enforced by test;
- an invalid token leaves the caller on the same screen with a short error
  line (CON re-prompt) instead of ending the session, and later tokens still
  apply, so a mis-key does not strand the caller;
- menu entries come from the substrands table (seeded from the wiki), never
  from hardcoded lists;
- a sub-strand code (e.g. M-ALG-02, case-insensitive) typed at the home
  screen jumps straight to that sub-strand;
- a returning teacher (a teachers row with last_substrand) gets a home screen
  that leads with "1. Continue: <last sub-strand>" and appends "My coverage"
  and "Upload questions"; the extra lines are paid for by dropping the code
  hint, which the returning teacher has already seen (and every pack SMS ends
  with its code). A first-time caller's home screen is unchanged.

Navigation resolves to either a Screen (rendered as a CON reply) or a
Selection (the route records the teaching session, sends the pack and replies
END): the side effects stay in the route, keeping this module read-only
against the database.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Substrand, Teacher, TeachingSession

MAX_SCREEN_CHARS = 160

INVALID_LINE = "Invalid choice."


@dataclass(frozen=True)
class Screen:
    """A menu reply: CON to keep the session open (re-prompting if the last
    input was invalid), or END for a terminal information screen."""

    lines: tuple[str, ...]
    invalid: bool = False
    end: bool = False

    def render(self) -> str:
        lines = (INVALID_LINE, *self.lines) if self.invalid else self.lines
        return ("END " if self.end else "CON ") + "\n".join(lines)


@dataclass(frozen=True)
class Selection:
    """The caller picked a sub-strand to teach: the route turns this into
    side effects (teaching session, pack SMS) and an END reply."""

    substrand: Substrand


@dataclass(frozen=True)
class TestSelection:
    """The caller picked a sub-strand under Get a test: the route generates
    and sends the test, then replies END."""

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


def continue_substrand(db: Session, phone: str) -> Substrand | None:
    """The sub-strand the caller taught last, or None for a first-time caller."""
    if not phone:
        return None
    teacher = db.get(Teacher, phone)
    if teacher is None or teacher.last_substrand is None:
        return None
    return db.get(Substrand, teacher.last_substrand)


def home_screen(
    db: Session, cont: Substrand | None = None, invalid: bool = False
) -> Screen:
    lines = ["Welcome to ElimuTayari"]
    if cont is None:
        areas = learning_areas(db)
        lines += [f"{i}. {area}" for i, area in enumerate(areas, start=1)]
        lines.append(f"{len(areas) + 1}. Get a test")
        lines.append("Or enter a sub-strand code e.g. M-ALG-02")
        return Screen(tuple(lines), invalid=invalid)
    lines.append(f"1. Continue: {cont.title}")
    areas = learning_areas(db)
    lines += [f"{i}. {area}" for i, area in enumerate(areas, start=2)]
    lines.append(f"{len(areas) + 2}. My coverage")
    lines.append(f"{len(areas) + 3}. Upload questions")
    lines.append(f"{len(areas) + 4}. Get a test")
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


def coverage_screen(db: Session, phone: str) -> Screen:
    """Taught-so-far progress: distinct sub-strands from teaching_sessions
    against the seeded total, one line per learning area."""
    lines = []
    for area in learning_areas(db):
        taught = db.scalar(
            select(func.count(func.distinct(TeachingSession.substrand_code)))
            .join(Substrand, Substrand.code == TeachingSession.substrand_code)
            .where(
                TeachingSession.teacher_phone == phone,
                Substrand.learning_area == area,
            )
        )
        total = db.scalar(
            select(func.count())
            .select_from(Substrand)
            .where(Substrand.learning_area == area)
        )
        lines.append(f"You have taught {taught} of {total} {area} sub-strands.")
    return Screen(tuple(lines), end=True)


def test_areas_screen(db: Session, invalid: bool = False) -> Screen:
    """The Get a test entry point: pick a learning area (or type a code)."""
    lines = ["Get a test for which sub-strand?"]
    lines += [f"{i}. {area}" for i, area in enumerate(learning_areas(db), start=1)]
    return Screen(tuple(lines), invalid=invalid)


def upload_screen() -> Screen:
    """The post-class prompt: how to upload student questions, ending with the
    SMS format so the teacher never has to memorise it."""
    return Screen(
        (
            "After class, SMS your students' questions to this same shortcode.",
            "Format: Q <code> <question>",
        ),
        end=True,
    )


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
    selected: Substrand | None = None
    info: str | None = None  # "coverage" | "upload": terminal info screens
    mode: str = "pack"  # "pack" | "test": what selecting a sub-strand means


def navigate(db: Session, text: str, phone: str = "") -> Screen | Selection | TestSelection:
    """Replay the accumulated USSD text into the current screen or selection.

    Each request re-derives the caller's position from the full text, one
    token at a time. A token that matches nothing is skipped with the invalid
    flag set, so the caller is re-prompted on the same screen and their next
    input still lands where they expect. The phone number picks the home
    screen variant: a returning teacher gets Continue/coverage/upload options.
    """
    cont = continue_substrand(db, phone)
    state = _State()
    invalid = False
    tokens = [t.strip() for t in text.split("*") if t.strip()]
    for token in tokens:
        invalid = not _apply(db, state, token, cont)
    return _screen_for(db, state, invalid, cont, phone)


def _apply_returning_home(
    db: Session, state: _State, token: str, cont: Substrand
) -> bool:
    """One token on the returning-teacher home screen: 1 continues the last
    sub-strand, learning areas shift down one, then coverage and upload."""
    if token == "1":
        state.selected = cont
        return True
    areas = learning_areas(db)
    if token.isdigit() and 2 <= int(token) <= len(areas) + 1:
        state.learning_area = areas[int(token) - 2]
        return True
    if token == str(len(areas) + 2):
        state.info = "coverage"
        return True
    if token == str(len(areas) + 3):
        state.info = "upload"
        return True
    if token == str(len(areas) + 4):
        state.mode = "test"
        return True
    direct = db.get(Substrand, token.upper())
    if direct is not None:
        state.selected = direct
        return True
    return False


def _apply_area_or_code(db: Session, state: _State, token: str) -> bool:
    """One token on a plain learning-areas screen: a numbered area, or a
    sub-strand code jumping straight to that sub-strand."""
    area = _pick(learning_areas(db), token)
    if area is not None:
        state.learning_area = area
        return True
    direct = db.get(Substrand, token.upper())
    if direct is not None:
        state.selected = direct
        return True
    return False


def _apply(db: Session, state: _State, token: str, cont: Substrand | None) -> bool:
    """Advance state by one token; False if the token matched nothing."""
    if state.selected is not None or state.info is not None:
        return False
    if state.learning_area is None:
        if state.mode == "test":
            return _apply_area_or_code(db, state, token)
        if cont is not None:
            return _apply_returning_home(db, state, token, cont)
        if token == str(len(learning_areas(db)) + 1):
            state.mode = "test"
            return True
        return _apply_area_or_code(db, state, token)
    if state.strand is None:
        strand = _pick(strands(db, state.learning_area), token)
        if strand is not None:
            state.strand = strand
            return True
        return False
    if state.selected is None:
        options = substrands(db, state.learning_area, state.strand)
        if token.isdigit() and 1 <= int(token) <= len(options):
            state.selected = options[int(token) - 1]
            return True
        return False
    return False


def _screen_for(
    db: Session, state: _State, invalid: bool, cont: Substrand | None, phone: str
) -> Screen | Selection | TestSelection:
    if state.selected is not None:
        if state.mode == "test":
            return TestSelection(state.selected)
        return Selection(state.selected)
    if state.info == "coverage":
        return coverage_screen(db, phone)
    if state.info == "upload":
        return upload_screen()
    if state.learning_area is None:
        if state.mode == "test":
            return test_areas_screen(db, invalid=invalid)
        return home_screen(db, cont=cont, invalid=invalid)
    if state.strand is None:
        return strands_screen(db, state.learning_area, invalid=invalid)
    return substrands_screen(db, state.learning_area, state.strand, invalid=invalid)
