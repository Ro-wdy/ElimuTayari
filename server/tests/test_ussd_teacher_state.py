"""Returning-teacher USSD state (issue #4), tested at the /ussd HTTP seam.

A teacher who has taught before dials back in and sees a home screen that
leads with "Continue: <last sub-strand>", plus "My coverage" (taught X of Y)
and the post-class "Upload questions" prompt that quotes the Q <code> <text>
SMS format. A first-time caller sees the original home screen unchanged.

Sessions are simulated the same way as test_ussd_browse: successive posts of
the accumulated text under one sessionId, asserting on the plain-text CON/END
body, database rows, and the recorded SMS outbox - never a live Africa's
Talking API.
"""

from typing import Iterator

import pytest

from sqlalchemy import select

from app.db import create_db_engine, create_session_factory
from app.models import TeachingSession
from app.seed import seed_placeholder_content

PHONE = "+254711223344"


@pytest.fixture
def seeded_client(client, migrated_database_url) -> Iterator:
    """The conftest client, with the placeholder Mathematics content seeded."""
    engine = create_db_engine(migrated_database_url)
    session = create_session_factory(engine)()
    try:
        seed_placeholder_content(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()
    yield client


def dial(client, text: str, session_id: str = "ATUid_1", phone: str = PHONE) -> str:
    response = client.post(
        "/ussd",
        data={
            "sessionId": session_id,
            "phoneNumber": phone,
            "networkCode": "63902",
            "serviceCode": "*384*1234#",
            "text": text,
        },
    )
    assert response.status_code == 200
    return response.text


def teach(client, text: str = "1*1*2", session_id: str = "ATUid_taught") -> None:
    """Complete one browse-and-select session so PHONE becomes a known teacher."""
    body = dial(client, text, session_id=session_id)
    assert body.startswith("END ")


def test_first_time_caller_sees_home_screen_without_continue(seeded_client):
    body = dial(seeded_client, "")

    assert body.startswith("CON ")
    assert "Continue" not in body
    assert "1. Mathematics" in body
    assert "code" in body.lower()


def test_known_teacher_home_leads_with_continue_and_shifts_options(seeded_client):
    teach(seeded_client)  # M-ALG-02 Formulae and Variations

    body = dial(seeded_client, "", session_id="ATUid_2")

    assert body.startswith("CON ")
    assert "1. Continue: Formulae and Variations" in body
    assert "2. Mathematics" in body
    assert "3. My coverage" in body
    assert "4. Upload questions" in body


def test_continue_reselects_last_substrand_and_resends_pack(
    seeded_client, session, sms_outbox
):
    teach(seeded_client)  # M-ALG-02
    sms_outbox.sent.clear()

    body = dial(seeded_client, "1", session_id="ATUid_2")

    assert body.startswith("END ")
    assert "M-ALG-02" in body
    teaching = session.scalars(select(TeachingSession)).all()
    assert [t.substrand_code for t in teaching] == ["M-ALG-02", "M-ALG-02"]
    assert sms_outbox.sent, "continue should resend the teaching pack"
    assert "M-ALG-02" in sms_outbox.sent[-1][1]


def test_browse_still_works_for_a_returning_teacher_with_shifted_numbers(
    seeded_client, session
):
    teach(seeded_client)  # M-ALG-02
    body = dial(seeded_client, "2*5*1", session_id="ATUid_2")  # Maths -> Numbers

    assert body.startswith("END ")
    assert "M-NUM-01" in body
    codes = [t.substrand_code for t in session.scalars(select(TeachingSession))]
    assert codes == ["M-ALG-02", "M-NUM-01"]
