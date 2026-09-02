"""Test generation via Claude (issue #8), tested at the /ussd HTTP seam.

A teacher picks "Get a test" from the home screen, navigates the same
area/strand/sub-strand menu, and the route asks Claude (through the LlmClient
seam) for ~5 questions composed from the sub-strand's guidance content and
its question bank, delivers them by SMS, and stores a tests row. Sessions are
simulated as in test_ussd_browse: successive posts of the accumulated text,
asserting on the CON/END body, the database rows, the recorded SMS outbox and
the recorded Claude prompts - never a live API.
"""

import json
from typing import Iterator

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import create_db_engine, create_session_factory
from app.llm_client import StubLlmClient
from app.main import create_app
from app.models import ContentUnit, GeneratedTest, Question, Teacher
from app.seed import seed_placeholder_content

PHONE = "+254711223344"

CODE = "M-ALG-02"
GUIDANCE = "Learners can rearrange formulae and apply direct and inverse variation."
FIVE_QUESTIONS = [
    "Make r the subject of V = pi r^2 h.",
    "If y varies directly as x and y=6 when x=2, find y when x=5.",
    "State the difference between direct and inverse variation.",
    "Given P varies inversely as Q, and P=4 when Q=3, find P when Q=6.",
    "Rearrange s = ut + (1/2)at^2 to make a the subject.",
]


def seed_rows(url: str, *rows) -> None:
    """Seed the placeholder content plus any extra rows into the database."""
    engine = create_db_engine(url)
    session = create_session_factory(engine)()
    try:
        seed_placeholder_content(session)
        session.add_all(rows)
        session.commit()
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_client(client, migrated_database_url) -> Iterator:
    """The conftest client, with the placeholder Mathematics content seeded."""
    seed_rows(migrated_database_url)
    yield client


@pytest.fixture
def make_client(migrated_database_url, sms_outbox) -> Iterator:
    """Build a TestClient over the shared throwaway database with a caller-
    chosen LlmClient, following how conftest wires the stock stub."""
    stack = []

    def _make(llm_client) -> TestClient:
        app = create_app(
            database_url=migrated_database_url,
            sms_client=sms_outbox,
            llm_client=llm_client,
        )
        test_client = TestClient(app)
        stack.append(test_client)
        return test_client.__enter__()

    yield _make
    for test_client in stack:
        test_client.__exit__(None, None, None)


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


def test_first_time_home_offers_get_a_test_after_the_learning_areas(seeded_client):
    body = dial(seeded_client, "")

    assert body.startswith("CON ")
    assert "1. Mathematics" in body
    assert "2. Get a test" in body


def test_returning_home_offers_get_a_test_after_the_teacher_options(seeded_client):
    teach(seeded_client)

    body = dial(seeded_client, "", session_id="ATUid_2")

    assert body.startswith("CON ")
    assert "1. Continue: Formulae and Variations" in body
    assert "3. My coverage" in body
    assert "4. Upload questions" in body
    assert "5. Get a test" in body


def test_get_a_test_reuses_the_area_strand_substrand_navigation(seeded_client):
    body = dial(seeded_client, "2")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "Get a test" in body
    assert "1. Mathematics" in body

    body = dial(seeded_client, "2*1")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "1. Algebra" in body

    body = dial(seeded_client, "2*1*1")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "2. Formulae and Variations" in body


def test_get_a_test_navigation_works_from_the_returning_home(seeded_client):
    teach(seeded_client)

    body = dial(seeded_client, "5", session_id="ATUid_2")
    assert body.startswith("CON ")
    assert "Get a test" in body
    assert "1. Mathematics" in body


def test_invalid_choice_on_the_test_area_screen_re_prompts(seeded_client):
    body = dial(seeded_client, "2*9")

    assert body.startswith("CON ")
    assert "Invalid" in body
    assert "1. Mathematics" in body


def bank_rows() -> tuple:
    """A guidance unit and a mixed question bank for M-ALG-02."""
    return (
        Teacher(phone=PHONE),
        ContentUnit(substrand_code=CODE, kind="guidance", body=GUIDANCE, version=1),
        Question(
            teacher_phone=PHONE,
            substrand_code=CODE,
            text="Why do we flip the inequality sign?",
            source="student",
        ),
        Question(
            teacher_phone=PHONE,
            substrand_code=CODE,
            text="Make x the subject of y = 3x + 2.",
            source="teacher",
        ),
    )


def test_selecting_a_substrand_sends_the_generated_test_and_stores_it(
    make_client, migrated_database_url, sms_outbox, session
):
    seed_rows(migrated_database_url, *bank_rows())
    stub = StubLlmClient(replies=[json.dumps(FIVE_QUESTIONS)])
    client = make_client(stub)

    # Get a test -> Mathematics -> Algebra -> Formulae and Variations
    body = dial(client, "2*1*1*2")

    assert body.startswith("END ")
    assert CODE in body
    assert "your test is on its way by SMS" in body

    assert len(stub.calls) == 1
    messages = [message for _, message in sms_outbox.sent]
    assert messages, "the test should be delivered by SMS"
    assert all(len(message) <= 160 for message in messages)
    joined = "\n".join(messages)
    for question in FIVE_QUESTIONS:
        assert question in joined
    assert CODE in messages[-1]

    stored = session.scalars(select(GeneratedTest)).all()
    assert len(stored) == 1
    assert stored[0].teacher_phone == PHONE
    assert stored[0].substrand_codes == [CODE]
    assert stored[0].items_json == {"questions": FIVE_QUESTIONS}
    assert stored[0].sent_at is not None
