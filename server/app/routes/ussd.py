"""Africa's Talking USSD callback.

AT posts a form-encoded session payload and expects a plain-text body whose
first token is CON (keep the session open) or END (close it). Its field names
are camelCase on the wire and aliased to snake_case here. The menu itself
lives in app.ussd_menu (a pure function of the accumulated text and the
database); this route owns the side effects of a selection: recording the
teaching session, updating the teacher, and sending the pack by SMS.
"""

from fastapi import APIRouter, Depends, Form
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_session, get_sms_client
from app.models import ContentUnit, Substrand, Teacher, TeachingSession
from app.sms_client import SmsClient
from app.sms_pack import split_pack
from app.ussd_menu import Selection, navigate

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
) -> str:
    outcome = navigate(db, text)
    if isinstance(outcome, Selection):
        return _complete_selection(db, sms_client, phone_number, outcome.substrand)
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
