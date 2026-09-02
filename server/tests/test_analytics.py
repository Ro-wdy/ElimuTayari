"""Confusion-hotspot analytics digest (issue #9).

Seams under test:
- compute_hotspots(session): the ranking math, observed on seeded rows through
  the session fixture;
- cluster_questions(llm, ...): theme clustering through the LlmClient seam,
  driven by StubLlmClient canned replies;
- write_digest(...): the Markdown report on disk, re-runnable.

No network, no credentials: Claude is always the stub, the database is the
migrated throwaway SQLite file from conftest.
"""

from datetime import datetime, timezone

from app.analytics import compute_hotspots
from app.models import Question, Substrand, Teacher, TeachingSession

TEACHER_PHONE = "+254711223344"


def seed_substrand(session, code: str, title: str) -> None:
    session.add(
        Substrand(
            code=code,
            learning_area="Mathematics",
            strand="Algebra",
            title=title,
        )
    )


def seed_activity(
    session,
    code: str,
    *,
    student_questions: int = 0,
    teacher_questions: int = 0,
    sessions: int = 0,
    question_texts: list[str] | None = None,
) -> None:
    """Attach questions and teaching sessions to an existing sub-strand."""
    taught_at = datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc)
    for _ in range(sessions):
        session.add(
            TeachingSession(
                teacher_phone=TEACHER_PHONE,
                substrand_code=code,
                taught_at=taught_at,
            )
        )
    if question_texts is None:
        question_texts = [
            f"Question {i} about {code}" for i in range(student_questions)
        ]
    for text in question_texts:
        session.add(
            Question(
                teacher_phone=TEACHER_PHONE,
                substrand_code=code,
                text=text,
                source="student",
            )
        )
    for i in range(teacher_questions):
        session.add(
            Question(
                teacher_phone=TEACHER_PHONE,
                substrand_code=code,
                text=f"Teacher item {i} for {code}",
                source="teacher",
            )
        )


def seed_teacher(session) -> None:
    session.add(Teacher(phone=TEACHER_PHONE))
    session.flush()


def test_hotspots_rank_by_questions_per_session_not_raw_counts(session):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    seed_substrand(session, "M-ALG-02", "Formulae and Variations")
    session.flush()
    # M-ALG-01: more questions in total, but taught often -> lower ratio.
    seed_activity(session, "M-ALG-01", student_questions=6, sessions=3)  # 2.0
    seed_activity(session, "M-ALG-02", student_questions=4, sessions=1)  # 4.0
    session.flush()

    ranking = compute_hotspots(session)

    assert [h.substrand_code for h in ranking.rated] == ["M-ALG-02", "M-ALG-01"]
    top = ranking.rated[0]
    assert top.title == "Formulae and Variations"
    assert top.student_questions == 4
    assert top.teaching_sessions == 1
    assert top.questions_per_session == 4.0
    assert ranking.rated[1].questions_per_session == 2.0


def test_teacher_questions_do_not_count_as_confusion(session):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    session.flush()
    seed_activity(
        session, "M-ALG-01", student_questions=1, teacher_questions=5, sessions=1
    )
    session.flush()

    ranking = compute_hotspots(session)

    assert ranking.rated[0].student_questions == 1


def test_zero_question_substrands_are_not_hotspots(session):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    session.flush()
    seed_activity(session, "M-ALG-01", student_questions=0, sessions=2)
    session.flush()

    ranking = compute_hotspots(session)

    assert ranking.rated == []
    assert ranking.unrated == []


def test_zero_session_substrand_with_questions_is_reported_separately(session):
    # Questions arrived without any recorded teaching session: the ratio is
    # undefined, so the sub-strand is surfaced in an unrated list rather than
    # ranked (or silently dropped).
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    seed_substrand(session, "M-ALG-02", "Formulae and Variations")
    session.flush()
    seed_activity(session, "M-ALG-01", student_questions=3, sessions=0)
    seed_activity(session, "M-ALG-02", student_questions=2, sessions=1)
    session.flush()

    ranking = compute_hotspots(session)

    assert [h.substrand_code for h in ranking.rated] == ["M-ALG-02"]
    assert [h.substrand_code for h in ranking.unrated] == ["M-ALG-01"]
    unrated = ranking.unrated[0]
    assert unrated.student_questions == 3
    assert unrated.teaching_sessions == 0
    assert unrated.questions_per_session is None


def test_equal_ratios_break_ties_by_question_count_then_code(session):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    seed_substrand(session, "M-ALG-02", "Formulae and Variations")
    seed_substrand(session, "M-ALG-03", "Quadratics")
    session.flush()
    seed_activity(session, "M-ALG-01", student_questions=2, sessions=1)  # 2.0
    seed_activity(session, "M-ALG-02", student_questions=4, sessions=2)  # 2.0
    seed_activity(session, "M-ALG-03", student_questions=2, sessions=1)  # 2.0
    session.flush()

    ranking = compute_hotspots(session)

    assert [h.substrand_code for h in ranking.rated] == [
        "M-ALG-02",  # same ratio, more evidence
        "M-ALG-01",  # ties with M-ALG-03, earlier code
        "M-ALG-03",
    ]
