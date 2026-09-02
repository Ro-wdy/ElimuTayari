"""Inbound SMS question capture (issue #3).

Seams under test:
- POST /sms/inbound (the Africa's Talking webhook) via the TestClient fixture;
- stored rows observed through the session fixture (questions/teachers tables);
- outbound SMS observed through the sms_outbox recording client.

The client and session fixtures share one throwaway SQLite file, so tests seed
the placeholder sub-strands through the session and the webhook sees them.
Africa's Talking is never contacted: confirmations and help messages are
asserted against sms_outbox.sent.
"""

import pytest
from sqlalchemy import func, select

from app.models import Question, Teacher
from app.seed import seed_placeholder_content

TEACHER_PHONE = "+254711223344"


def at_payload(text: str, sender: str = TEACHER_PHONE) -> dict[str, str]:
    return {
        "from": sender,
        "to": "12345",
        "text": text,
        "date": "2026-09-02 11:04:00",
        "id": "aa4f8b12",
        "linkId": "SomeLinkId",
    }


@pytest.fixture
def seeded_client(client, session):
    """The webhook client, with the placeholder sub-strands seeded."""
    seed_placeholder_content(session)
    session.commit()
    return client


def stored_questions(session) -> list[Question]:
    return list(session.scalars(select(Question)))


def test_q_upload_stores_student_question(seeded_client, session):
    response = seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )

    assert response.status_code == 200
    questions = stored_questions(session)
    assert len(questions) == 1
    question = questions[0]
    assert question.substrand_code == "M-ALG-02"
    assert question.teacher_phone == TEACHER_PHONE
    assert question.text == "Why do we swap the sign?"
    assert question.source == "student"
    assert question.created_at is not None


def test_t_upload_stores_teacher_test_item(seeded_client, session):
    response = seeded_client.post(
        "/sms/inbound", data=at_payload("T M-ALG-02 Make y the subject of x=2y+1")
    )

    assert response.status_code == 200
    questions = stored_questions(session)
    assert len(questions) == 1
    question = questions[0]
    assert question.substrand_code == "M-ALG-02"
    assert question.text == "Make y the subject of x=2y+1"
    assert question.source == "teacher"


def test_lowercase_prefix_and_code_with_whitespace_still_parse(seeded_client, session):
    response = seeded_client.post(
        "/sms/inbound", data=at_payload("  q m-alg-02   Why do we swap the sign?  ")
    )

    assert response.status_code == 200
    questions = stored_questions(session)
    assert len(questions) == 1
    assert questions[0].substrand_code == "M-ALG-02"
    assert questions[0].source == "student"
    assert questions[0].text == "Why do we swap the sign?"


def test_q_upload_sends_confirmation_sms(seeded_client, sms_outbox):
    seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )

    assert len(sms_outbox.sent) == 1
    to, message = sms_outbox.sent[0]
    assert to == TEACHER_PHONE
    assert "M-ALG-02" in message


def test_student_question_reply_carries_a_grounded_answer(
    seeded_client, sms_outbox, llm_stub
):
    """A Q upload answers the question for the teacher, not just 'Saved'."""
    llm_stub._replies = ["A negative exponent means divide: 2^-1 is 1/2."]

    seeded_client.post(
        "/sms/inbound",
        data=at_payload("Q M-ALG-02 Why does a negative exponent give a fraction?"),
    )

    assert len(llm_stub.calls) == 1
    _, prompt = llm_stub.calls[0]
    assert "Why does a negative exponent give a fraction?" in prompt
    assert "M-ALG-02" in prompt
    joined = "\n".join(message for _, message in sms_outbox.sent)
    assert "A negative exponent means divide: 2^-1 is 1/2." in joined
    assert all(len(message) <= 160 for _, message in sms_outbox.sent)


def test_teacher_test_item_gets_plain_confirmation_and_no_llm_call(
    seeded_client, sms_outbox, llm_stub
):
    seeded_client.post(
        "/sms/inbound", data=at_payload("T M-ALG-02 Simplify 2^3 x 2^-1")
    )

    assert llm_stub.calls == []
    assert len(sms_outbox.sent) == 1
    assert "Saved: test item" in sms_outbox.sent[0][1]


def test_llm_failure_falls_back_to_plain_confirmation(
    seeded_client, sms_outbox, llm_stub, session
):
    def explode(system, prompt, max_tokens=16000):
        raise RuntimeError("api unreachable")

    llm_stub.complete = explode

    seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )

    # The question is saved and the teacher still hears back.
    assert len(stored_questions(session)) == 1
    assert len(sms_outbox.sent) == 1
    assert "Saved: student question" in sms_outbox.sent[0][1]


def test_first_contact_creates_teacher_row(seeded_client, session):
    assert session.get(Teacher, TEACHER_PHONE) is None

    seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )

    teacher = session.get(Teacher, TEACHER_PHONE)
    assert teacher is not None
    assert teacher.created_at is not None


def test_repeat_uploads_reuse_the_teacher_row(seeded_client, session):
    seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )
    response = seeded_client.post(
        "/sms/inbound", data=at_payload("T M-NUM-01 Simplify 2^3 x 2^4")
    )

    assert response.status_code == 200
    assert len(stored_questions(session)) == 2
    assert session.scalar(select(func.count()).select_from(Teacher)) == 1


def test_unknown_code_gets_explanatory_sms_and_stores_nothing(
    seeded_client, session, sms_outbox
):
    response = seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-XYZ-99 Why do we swap the sign?")
    )

    assert response.status_code == 200
    assert stored_questions(session) == []
    assert len(sms_outbox.sent) == 1
    to, message = sms_outbox.sent[0]
    assert to == TEACHER_PHONE
    assert "M-XYZ-99" in message
    assert "M-ALG-02" in message  # shows what a valid code looks like


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Q Why do we swap the sign?", id="missing-code"),
        pytest.param("Q M-ALG-02", id="empty-question-text"),
        pytest.param("Q M-ALG-02   ", id="whitespace-question-text"),
        pytest.param("Hello, when is the next pack?", id="non-command"),
        pytest.param("", id="empty-message"),
    ],
)
def test_malformed_message_gets_format_help_and_stores_nothing(
    seeded_client, session, sms_outbox, text
):
    response = seeded_client.post("/sms/inbound", data=at_payload(text))

    assert response.status_code == 200
    assert stored_questions(session) == []
    assert len(sms_outbox.sent) == 1
    to, message = sms_outbox.sent[0]
    assert to == TEACHER_PHONE
    assert "Q <code> <question>" in message
