"""USSD browse flow (issue #2), tested at the /ussd HTTP seam.

Africa's Talking accumulates the caller's inputs into one text field joined
with "*", so a multi-step session is simulated by posting successive requests
with text "", "1", "1*2", ... under one sessionId. Assertions read the
plain-text CON/END body, the database rows the flow writes, and the recorded
SMS outbox - never a live Africa's Talking API.
"""

from typing import Iterator

import pytest

from sqlalchemy import select

from app.db import create_db_engine, create_session_factory
from app.models import Teacher, TeachingSession
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


def test_home_screen_lists_learning_areas_and_invites_code_entry(seeded_client):
    body = dial(seeded_client, "")

    assert body.startswith("CON ")
    assert "1. Mathematics" in body
    assert "code" in body.lower()


def test_choosing_mathematics_lists_its_strands(seeded_client):
    body = dial(seeded_client, "1")

    assert body.startswith("CON ")
    assert "1. Algebra" in body
    assert "2. Data Handling and Probability" in body
    assert "3. Geometry" in body
    assert "4. Measurements" in body
    assert "5. Numbers" in body


def test_choosing_a_strand_lists_its_substrands(seeded_client):
    body = dial(seeded_client, "1*1")  # Mathematics -> Algebra

    assert body.startswith("CON ")
    assert "1. Matrices" in body
    assert "2. Formulae and Variations" in body
    assert "3. Quadratic Equations and Expressions" in body


def test_selecting_a_substrand_ends_session_and_records_teaching(
    seeded_client, session
):
    # Mathematics -> Algebra -> Formulae and Variations (M-ALG-02)
    body = dial(seeded_client, "1*1*2")

    assert body.startswith("END ")
    assert "SMS" in body

    teaching = session.scalars(select(TeachingSession)).all()
    assert [(t.teacher_phone, t.substrand_code) for t in teaching] == [
        (PHONE, "M-ALG-02")
    ]
    teacher = session.get(Teacher, PHONE)
    assert teacher is not None
    assert teacher.last_substrand == "M-ALG-02"


def test_selection_sends_the_teaching_pack_by_sms(seeded_client, sms_outbox):
    dial(seeded_client, "1*1*2")  # M-ALG-02

    assert len(sms_outbox.sent) >= 2
    recipients = {to for to, _ in sms_outbox.sent}
    assert recipients == {PHONE}
    messages = [message for _, message in sms_outbox.sent]
    assert all(len(message) <= 160 for message in messages)
    assert "M-ALG-02" in messages[-1]
    joined = " ".join(messages)
    assert "Formulae and Variations" in joined
    assert "Outcome" in joined


def test_second_selection_updates_last_substrand_without_duplicate_teacher(
    seeded_client, session
):
    dial(seeded_client, "1*1*2", session_id="ATUid_1")
    # The second dial is a returning teacher (issue #4): Continue takes slot 1,
    # so Mathematics is option 2.
    dial(seeded_client, "2*5*1", session_id="ATUid_2")  # Numbers -> M-NUM-01

    teachers = session.scalars(select(Teacher)).all()
    assert len(teachers) == 1
    assert teachers[0].last_substrand == "M-NUM-01"
    assert len(session.scalars(select(TeachingSession)).all()) == 2


def test_direct_code_entry_at_home_screen_selects_the_substrand(
    seeded_client, session, sms_outbox
):
    body = dial(seeded_client, "m-alg-02")

    assert body.startswith("END ")
    assert "M-ALG-02" in body
    teaching = session.scalars(select(TeachingSession)).all()
    assert [t.substrand_code for t in teaching] == ["M-ALG-02"]
    assert sms_outbox.sent, "pack should be sent for direct code entry"
    assert "M-ALG-02" in sms_outbox.sent[-1][1]


def test_invalid_input_at_home_re_prompts_instead_of_ending(seeded_client):
    body = dial(seeded_client, "9")

    assert body.startswith("CON ")
    assert "Invalid" in body
    assert "1. Mathematics" in body


def test_invalid_choice_deeper_in_the_menu_re_prompts_the_same_screen(seeded_client):
    body = dial(seeded_client, "1*7")

    assert body.startswith("CON ")
    assert "Invalid" in body
    assert "1. Algebra" in body  # still on the strands screen


def test_session_recovers_after_an_invalid_input(seeded_client):
    body = dial(seeded_client, "9*1")  # bad key, then Mathematics

    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "1. Algebra" in body


def test_every_screen_fits_within_the_ussd_character_limit(seeded_client):
    """Walk every reachable menu screen, valid and re-prompted, and check the
    ~160-character USSD limit holds for each rendered body."""
    texts = ["", "9"]  # home, home re-prompt
    texts += ["1", "1*9"]  # strands, strands re-prompt
    for strand_index in range(1, 6):
        texts.append(f"1*{strand_index}")  # each sub-strands screen
        texts.append(f"1*{strand_index}*9")  # ...and its re-prompt
        for substrand_index in range(1, 4):
            texts.append(f"1*{strand_index}*{substrand_index}")  # each END screen

    for text in texts:
        body = dial(seeded_client, text, session_id=f"ATUid_{text or 'root'}")
        assert len(body) <= 160, f"screen for text={text!r} is {len(body)} chars"
