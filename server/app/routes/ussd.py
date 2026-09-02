"""Africa's Talking USSD callback.

AT posts a form-encoded session payload and expects a plain-text body whose
first token is CON (keep the session open) or END (close it). Stub behaviour:
the ticket #2 work replaces the menu body with real strand navigation.
"""

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.post("/ussd", response_class=PlainTextResponse)
def ussd_callback(
    sessionId: str = Form(...),
    phoneNumber: str = Form(...),
    text: str = Form(default=""),
    serviceCode: str = Form(default=""),
    networkCode: str = Form(default=""),
) -> str:
    return "CON Welcome to ElimuTayari\n1. Mathematics"
