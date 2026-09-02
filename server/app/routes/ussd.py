"""Africa's Talking USSD callback.

AT posts a form-encoded session payload and expects a plain-text body whose
first token is CON (keep the session open) or END (close it). Its field names
are camelCase on the wire and aliased to snake_case here. Stub behaviour:
the ticket #2 work replaces the menu body with real strand navigation.
"""

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.post("/ussd", response_class=PlainTextResponse)
def ussd_callback(
    session_id: str = Form(..., alias="sessionId"),
    phone_number: str = Form(..., alias="phoneNumber"),
    text: str = Form(default=""),
    service_code: str = Form(default="", alias="serviceCode"),
    network_code: str = Form(default="", alias="networkCode"),
) -> str:
    return "CON Welcome to ElimuTayari\n1. Mathematics"
