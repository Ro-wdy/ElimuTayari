"""Africa's Talking inbound-SMS webhook.

AT posts a form-encoded message with the sender in a field literally named
"from", which is a Python keyword, so every field is aliased to a snake_case
parameter here. AT only needs a 2xx to consider the message delivered.
Stub behaviour: ticket #3 replaces this with Q/T command parsing and question
capture.
"""

from fastapi import APIRouter, Form

router = APIRouter()


@router.post("/sms/inbound")
def inbound_sms(
    sender: str = Form(..., alias="from"),
    text: str = Form(default=""),
    to: str = Form(default=""),
    date: str = Form(default=""),
    message_id: str = Form(default="", alias="id"),
    link_id: str = Form(default="", alias="linkId"),
) -> dict[str, str]:
    return {"status": "accepted"}
