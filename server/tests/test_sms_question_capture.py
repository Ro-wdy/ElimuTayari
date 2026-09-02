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
from sqlalchemy import select

from app.models import Question
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


def test_q_upload_sends_confirmation_sms(seeded_client, sms_outbox):
    seeded_client.post(
        "/sms/inbound", data=at_payload("Q M-ALG-02 Why do we swap the sign?")
    )

    assert len(sms_outbox.sent) == 1
    to, message = sms_outbox.sent[0]
    assert to == TEACHER_PHONE
    assert "M-ALG-02" in message
