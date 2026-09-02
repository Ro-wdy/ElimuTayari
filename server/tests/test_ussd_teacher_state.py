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


def test_coverage_counts_distinct_taught_substrands(seeded_client):
    teach(seeded_client, "1*1*2", session_id="ATUid_1")  # M-ALG-02
    teach(seeded_client, "1", session_id="ATUid_2")  # M-ALG-02 again
    teach(seeded_client, "2*5*1", session_id="ATUid_3")  # M-NUM-01

    body = dial(seeded_client, "3", session_id="ATUid_4")

    assert body == "END You have taught 2 of 15 Mathematics sub-strands."


def test_coverage_counts_another_teachers_sessions_separately(seeded_client):
    teach(seeded_client, "1*1*2", session_id="ATUid_1")  # PHONE: M-ALG-02
    dial(seeded_client, "m-num-01", session_id="ATUid_2", phone="+254700000001")

    body = dial(seeded_client, "3", session_id="ATUid_3")

    assert body == "END You have taught 1 of 15 Mathematics sub-strands."


def test_post_class_prompt_quotes_the_question_upload_sms_format(seeded_client):
    teach(seeded_client)  # a taught session makes the next dial-in offer upload

    body = dial(seeded_client, "4", session_id="ATUid_2")

    assert body.startswith("END ")
    assert "SMS" in body
    assert "shortcode" in body
    assert body.endswith("Q <code> <question>")


def test_invalid_choice_on_returning_home_re_prompts_with_continue(seeded_client):
    teach(seeded_client)

    body = dial(seeded_client, "5", session_id="ATUid_2")

    assert body.startswith("CON ")
    assert "Invalid" in body
    assert "1. Continue: Formulae and Variations" in body


def test_direct_code_entry_still_works_for_a_returning_teacher(
    seeded_client, session
):
    teach(seeded_client)  # M-ALG-02

    body = dial(seeded_client, "M-DAT-03", session_id="ATUid_2")

    assert body.startswith("END ")
    assert "M-DAT-03" in body
    codes = [t.substrand_code for t in session.scalars(select(TeachingSession))]
    assert codes == ["M-ALG-02", "M-DAT-03"]
