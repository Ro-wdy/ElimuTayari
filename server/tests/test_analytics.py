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

import json
from datetime import datetime, timezone

from app.analytics import cluster_questions, compute_hotspots, write_digest
from app.llm_client import StubLlmClient
from app.models import Question, Substrand, Teacher, TeachingSession

TEACHER_PHONE = "+254711223344"

SIGN_QUESTIONS = [
    "Why do we swap the sign when dividing by a negative?",
    "What happens to the inequality when I multiply by -1?",
    "How do I make y the subject of x = 2y + 1?",
]

CANNED_CLUSTERS = json.dumps(
    [
        {"theme": "Sign changes with negatives", "question_indexes": [1, 2]},
        {"theme": "Changing the subject of a formula", "question_indexes": [3]},
    ]
)


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


def test_cluster_questions_names_themes_from_json_reply():
    llm = StubLlmClient(replies=[CANNED_CLUSTERS])

    result = cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    assert result.raw_reply is None
    assert [t.theme for t in result.themes] == [
        "Sign changes with negatives",
        "Changing the subject of a formula",
    ]
    assert result.themes[0].questions == SIGN_QUESTIONS[:2]
    assert result.themes[1].questions == [SIGN_QUESTIONS[2]]


def test_cluster_prompt_numbers_questions_and_names_the_substrand():
    llm = StubLlmClient(replies=[CANNED_CLUSTERS])

    cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    (system, prompt) = llm.calls[0]
    assert "Formulae and Variations" in prompt
    for i, text in enumerate(SIGN_QUESTIONS, start=1):
        assert f"{i}. {text}" in prompt
    assert "JSON" in system or "JSON" in prompt


def test_cluster_reply_wrapped_in_code_fence_still_parses():
    llm = StubLlmClient(replies=[f"```json\n{CANNED_CLUSTERS}\n```"])

    result = cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    assert result.raw_reply is None
    assert len(result.themes) == 2


def test_malformed_cluster_reply_falls_back_to_raw_text():
    reply = "Students seem confused about signs, mostly."
    llm = StubLlmClient(replies=[reply])

    result = cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    assert result.themes == []
    assert result.raw_reply == reply


def test_wrong_shape_json_reply_falls_back_to_raw_text():
    reply = json.dumps({"themes": ["signs"]})
    llm = StubLlmClient(replies=[reply])

    result = cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    assert result.themes == []
    assert result.raw_reply == reply


def test_out_of_range_question_indexes_are_ignored():
    reply = json.dumps(
        [{"theme": "Sign changes", "question_indexes": [1, 99, 0, -2]}]
    )
    llm = StubLlmClient(replies=[reply])

    result = cluster_questions(llm, "Formulae and Variations", SIGN_QUESTIONS)

    assert result.raw_reply is None
    assert result.themes[0].questions == [SIGN_QUESTIONS[0]]


def seed_two_hotspots_and_one_unrated(session) -> None:
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    seed_substrand(session, "M-ALG-02", "Formulae and Variations")
    seed_substrand(session, "M-NUM-01", "Indices and Logarithms")
    session.flush()
    # M-ALG-02: 3 questions / 1 session = 3.0 -> hottest.
    seed_activity(session, "M-ALG-02", sessions=1, question_texts=SIGN_QUESTIONS)
    # M-ALG-01: 2 questions / 2 sessions = 1.0.
    seed_activity(
        session,
        "M-ALG-01",
        sessions=2,
        question_texts=["What is a determinant?", "Why can't I divide matrices?"],
    )
    # M-NUM-01: questions but no recorded session -> unrated.
    seed_activity(
        session, "M-NUM-01", question_texts=["What is a logarithm even for?"]
    )
    session.flush()


def test_digest_file_ranks_hotspots_and_names_themes(session, tmp_path):
    seed_two_hotspots_and_one_unrated(session)
    llm = StubLlmClient(
        replies=[
            CANNED_CLUSTERS,
            json.dumps(
                [{"theme": "Matrix operations", "question_indexes": [1, 2]}]
            ),
            json.dumps(
                [{"theme": "Purpose of logarithms", "question_indexes": [1]}]
            ),
        ]
    )
    out_path = tmp_path / "reports" / "confusion-digest.md"

    written = write_digest(session, llm, out_path)

    assert written == out_path
    text = out_path.read_text(encoding="utf-8")
    # Ranked by ratio: M-ALG-02 (3.0) before M-ALG-01 (1.0).
    assert text.index("M-ALG-02") < text.index("M-ALG-01")
    assert "3 student questions over 1 teaching session" in text
    assert "3.0 questions/session" in text
    assert "Sign changes with negatives" in text
    assert SIGN_QUESTIONS[0] in text
    assert "Matrix operations" in text
    # The unrated sub-strand is surfaced, not ranked or dropped.
    assert "M-NUM-01" in text
    assert "no recorded teaching sessions" in text
    assert "Purpose of logarithms" in text


def test_digest_with_no_questions_says_so_and_never_calls_claude(session, tmp_path):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-01", "Matrices")
    session.flush()
    seed_activity(session, "M-ALG-01", sessions=2)
    session.flush()
    llm = StubLlmClient()
    out_path = tmp_path / "confusion-digest.md"

    write_digest(session, llm, out_path)

    text = out_path.read_text(encoding="utf-8")
    assert "No student questions" in text
    assert llm.calls == []


def test_digest_includes_raw_reply_when_clustering_is_unparseable(
    session, tmp_path
):
    seed_teacher(session)
    seed_substrand(session, "M-ALG-02", "Formulae and Variations")
    session.flush()
    seed_activity(session, "M-ALG-02", sessions=1, question_texts=SIGN_QUESTIONS)
    session.flush()
    llm = StubLlmClient(replies=["Mostly sign confusion, I'd say."])
    out_path = tmp_path / "confusion-digest.md"

    write_digest(session, llm, out_path)

    text = out_path.read_text(encoding="utf-8")
    assert "could not be parsed" in text
    assert "Mostly sign confusion, I'd say." in text


def test_digest_is_rerunnable_and_overwrites_in_place(session, tmp_path):
    seed_two_hotspots_and_one_unrated(session)
    llm = StubLlmClient(replies=[CANNED_CLUSTERS])
    out_path = tmp_path / "confusion-digest.md"

    write_digest(session, llm, out_path)
    first = out_path.read_text(encoding="utf-8")
    write_digest(session, llm, out_path)
    second = out_path.read_text(encoding="utf-8")

    assert second == first  # overwritten, not appended
    assert second.count("## Hotspots") == 1
