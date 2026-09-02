"""Africa's Talking USSD callback.

AT posts a form-encoded session payload and expects a plain-text body whose
first token is CON (keep the session open) or END (close it). Its field names
are camelCase on the wire and aliased to snake_case here. The menu itself
lives in app.ussd_menu (a pure function of the accumulated text and the
database); this route owns the side effects of a selection: recording the
teaching session, updating the teacher, and sending the pack by SMS - and,
for a Get a test selection, generating the test through the LlmClient seam,
sending it by SMS, and storing the tests row.
"""

from fastapi import APIRouter, Depends, Form
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_llm_client, get_session, get_sms_client
from app.llm_client import LlmClient
from app.models import (
    ContentUnit,
    GeneratedTest,
    Question,
    Substrand,
    Teacher,
    TeachingSession,
    utcnow,
)
from app.sms_client import SmsClient
from app.sms_pack import split_pack
from app.test_generation import generate_test
from app.ussd_menu import Selection, TestSelection, navigate

router = APIRouter()


@router.post("/ussd", response_class=PlainTextResponse)
def ussd_callback(
    session_id: str = Form(..., alias="sessionId"),
    phone_number: str = Form(..., alias="phoneNumber"),
    text: str = Form(default=""),
    service_code: str = Form(default="", alias="serviceCode"),
    network_code: str = Form(default="", alias="networkCode"),
    db: Session = Depends(get_session),
    sms_client: SmsClient = Depends(get_sms_client),
    llm_client: LlmClient = Depends(get_llm_client),
) -> str:
    outcome = navigate(db, text, phone_number)
    if isinstance(outcome, Selection):
        return _complete_selection(db, sms_client, phone_number, outcome.substrand)
    if isinstance(outcome, TestSelection):
        return _complete_test_selection(
            db, sms_client, llm_client, phone_number, outcome.substrand
        )
    return outcome.render()


def _complete_selection(
    db: Session, sms_client: SmsClient, phone: str, substrand: Substrand
) -> str:
    """Record the teaching session, remember the teacher's pick, send the
    pack, reply END."""
    teacher = db.get(Teacher, phone)
    if teacher is None:
        teacher = Teacher(phone=phone)
        db.add(teacher)
    teacher.last_substrand = substrand.code
    db.add(TeachingSession(teacher_phone=phone, substrand_code=substrand.code))
    _send_pack(db, sms_client, phone, substrand.code)
    return (
        f"END {substrand.code} {substrand.title}: "
        "your teaching pack is on its way by SMS."
    )


def _complete_test_selection(
    db: Session,
    sms_client: SmsClient,
    llm_client: LlmClient,
    phone: str,
    substrand: Substrand,
) -> str:
    """Generate a test from the sub-strand's guidance and question bank, send
    it by SMS, store the tests row, reply END.

    With neither guidance nor questions there is nothing to generate from, so
    the session ends with an explanation instead of an LLM call. A Claude
    error or an unparseable reply degrades to an apologetic SMS - the session
    still ends normally and nothing malformed is sent or stored.
    """
    code = substrand.code
    guidance = _latest_guidance(db, code)
    questions = list(
        db.scalars(
            select(Question)
            .where(Question.substrand_code == code)
            .order_by(Question.id)
        )
    )
    if guidance is None and not questions:
        return (
            f"END {code} {substrand.title}: no content or questions to make a "
            f"test from yet. SMS Q {code} <question> after class."
        )
    if db.get(Teacher, phone) is None:
        db.add(Teacher(phone=phone))
    items = generate_test(llm_client, substrand, guidance, questions)
    if items is None:
        sms_client.send(
            phone,
            f"Sorry, we could not prepare your {code} test right now. "
            "Please try Get a test again later.",
        )
        return f"END {code} {substrand.title}: your test is on its way by SMS."
    body = f"Test {code} {substrand.title}\n" + "\n".join(
        f"{i}. {item}" for i, item in enumerate(items, start=1)
    )
    for part in split_pack(body, code):
        sms_client.send(phone, part)
    db.add(
        GeneratedTest(
            teacher_phone=phone,
            substrand_codes=[code],
            items_json={"questions": items},
            sent_at=utcnow(),
        )
    )
    return f"END {code} {substrand.title}: your test is on its way by SMS."


def _latest_guidance(db: Session, code: str) -> str | None:
    """The latest guidance content unit body for the sub-strand, if any."""
    unit = db.scalars(
        select(ContentUnit)
        .where(ContentUnit.substrand_code == code, ContentUnit.kind == "guidance")
        .order_by(ContentUnit.version.desc())
        .limit(1)
    ).one_or_none()
    return None if unit is None else unit.body


def _send_pack(db: Session, sms_client: SmsClient, phone: str, code: str) -> None:
    """Send the latest seeded sms_pack for the sub-strand, split to SMS size."""
    pack = db.scalars(
        select(ContentUnit)
        .where(ContentUnit.substrand_code == code, ContentUnit.kind == "sms_pack")
        .order_by(ContentUnit.version.desc())
        .limit(1)
    ).one_or_none()
    if pack is None:
        return
    for part in split_pack(pack.body, code):
        sms_client.send(phone, part)
