"""Outbound SMS, behind a seam so tests never touch Africa's Talking.

Every feature that sends SMS (teaching packs, confirmations, tests) goes
through SmsClient. The app wires the real Africa's Talking client at startup;
tests inject RecordingSmsClient via create_app(sms_client=...) and assert on
what was recorded. The africastalking SDK is imported lazily so the app can
run (and the whole suite can pass) without the package configured.
"""

from typing import Protocol


class SmsClient(Protocol):
    def send(self, to: str, message: str) -> None:
        """Send one SMS to one E.164 recipient."""


class AfricasTalkingSmsClient:
    def __init__(self, username: str, api_key: str, sender_id: str = "") -> None:
        self._username = username
        self._api_key = api_key
        self._sender_id = sender_id or None  # AT SDK wants None, not ""
        self._sms = None

    def send(self, to: str, message: str) -> None:
        if self._sms is None:
            import africastalking

            africastalking.initialize(self._username, self._api_key)
            self._sms = africastalking.SMS
        self._sms.send(message, [to], self._sender_id)


class RecordingSmsClient:
    """Test double: records (to, message) pairs instead of sending."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, message: str) -> None:
        self.sent.append((to, message))
