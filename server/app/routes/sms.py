"""Africa's Talking inbound-SMS webhook: teacher question uploads.

AT posts a form-encoded message with the sender in a field literally named
"from", which is a Python keyword, so every field is aliased to a snake_case
parameter here. AT only needs a 2xx to consider the message delivered, so the
webhook returns 200 whatever the parse outcome - a teacher's typo must never
look like a delivery failure and trigger AT retries.

Q/T commands (see app.sms_commands for the grammar) store a questions row and
confirm by SMS. A student question (Q) additionally gets a short teacher-facing
answer composed through the LlmClient seam, grounded in the sub-strand's
guidance - and falls back to the plain confirmation when the LLM fails, so
saving never depends on answering. Everything else - malformed commands,
unknown sub-strand codes, plain conversational texts - gets a help SMS instead
of silence. The teachers row is created on first contact, keyed by the sending
phone number.
"""

from fastapi import APIRouter, Depends, Form
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_llm_client, get_session, get_sms_client
from app.llm_client import LlmClient
from app.models import ContentUnit, Question, Substrand, Teacher
from app.question_answer import compose_answer
from app.sms_client import SmsClient
from app.sms_commands import FORMAT_HELP, UNKNOWN_CODE_HELP, parse_upload
from app.sms_pack import split_pack

router = APIRouter()

CONFIRMATION = "Saved: {what} for {code} {title}. Send more anytime."

ANSWERED_CONFIRMATION = "Saved your {code} question. How to explain it:\n{answer}"

SOURCE_LABELS = {"student": "student question", "teacher": "test item"}


@router.post("/sms/inbound")
def inbound_sms(
    sender: str = Form(..., alias="from"),
    text: str = Form(default=""),
    to: str = Form(default=""),
    date: str = Form(default=""),
    message_id: str = Form(default="", alias="id"),
    link_id: str = Form(default="", alias="linkId"),
    session: Session = Depends(get_session),
    sms_client: SmsClient = Depends(get_sms_client),
    llm_client: LlmClient = Depends(get_llm_client),
) -> dict[str, str]:
    upload = parse_upload(text)
    if upload is None:
        sms_client.send(sender, FORMAT_HELP)
        return {"status": "accepted"}

    substrand = session.get(Substrand, upload.substrand_code)
    if substrand is None:
        sms_client.send(sender, UNKNOWN_CODE_HELP.format(code=upload.substrand_code))
        return {"status": "accepted"}

    teacher = session.get(Teacher, sender)
    if teacher is None:
        teacher = Teacher(phone=sender)
        session.add(teacher)

    session.add(
        Question(
            teacher=teacher,
            substrand_code=substrand.code,
            text=upload.text,
            source=upload.source,
        )
    )

    answer = None
    if upload.source == "student":
        answer = compose_answer(
            llm_client, substrand, _latest_guidance(session, substrand.code), upload.text
        )
    if answer is None:
        sms_client.send(
            sender,
            CONFIRMATION.format(
                what=SOURCE_LABELS[upload.source],
                code=substrand.code,
                title=substrand.title,
            ),
        )
    else:
        body = ANSWERED_CONFIRMATION.format(code=substrand.code, answer=answer)
        for part in split_pack(body, substrand.code):
            sms_client.send(sender, part)
    return {"status": "accepted"}


def _latest_guidance(session: Session, code: str) -> str | None:
    unit = session.scalars(
        select(ContentUnit)
        .where(ContentUnit.substrand_code == code, ContentUnit.kind == "guidance")
        .order_by(ContentUnit.version.desc())
        .limit(1)
    ).one_or_none()
    return None if unit is None else unit.body
