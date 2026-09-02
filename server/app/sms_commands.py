"""Parsing for teacher SMS upload commands.

Grammar (one question per SMS):

    <prefix> <sub-strand code> <question text>

where the prefix is Q (a student-confusion question) or T (a teacher-authored
test item). The prefix and code are case-insensitive and surrounding
whitespace is tolerated, because teachers type these on feature phones. The
code must be code-shaped (letters-letters-digits, e.g. M-ALG-02); whether it
exists is a database question and stays out of this module, which is pure so
it can be tested without the app.

Reply texts live here beside the grammar they explain, so the help message and
the parser can never drift apart. Anything that does not parse maps to None
and the webhook answers with FORMAT_HELP - a teacher never gets silence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Q records what students asked; T records the teacher's own test item.
PREFIX_TO_SOURCE = {"Q": "student", "T": "teacher"}

# Sub-strand codes look like M-ALG-02: letter block, letter block, digit block.
CODE_SHAPE = re.compile(r"^[A-Za-z]{1,3}-[A-Za-z]{2,4}-\d{2,3}$")

FORMAT_HELP = (
    "Sorry, we could not read that. To upload a question send: "
    "Q <code> <question> for a student question, or "
    "T <code> <question> for your own test item. "
    "Example: Q M-ALG-02 Why do we swap the sign?"
)

UNKNOWN_CODE_HELP = (
    "Sub-strand code {code} is not recognised. Codes look like M-ALG-02 "
    "(see your teaching pack SMS). Send Q <code> <question> to try again."
)


@dataclass(frozen=True)
class QuestionUpload:
    """A well-formed upload command: source, normalised code, question text."""

    source: str  # "student" | "teacher"
    substrand_code: str  # upper-cased, e.g. "M-ALG-02"
    text: str


def parse_upload(message: str) -> QuestionUpload | None:
    """Parse one inbound SMS into an upload command, or None if malformed.

    None covers every failure the same way - no Q/T prefix, missing or
    misshapen code, empty question text - because the teacher's remedy is
    identical: resend in the documented format.
    """
    parts = message.strip().split(maxsplit=2)
    if len(parts) < 3:
        return None
    prefix, code, text = parts
    source = PREFIX_TO_SOURCE.get(prefix.upper())
    if source is None:
        return None
    if not CODE_SHAPE.match(code):
        return None
    text = text.strip()
    if not text:
        return None
    return QuestionUpload(source=source, substrand_code=code.upper(), text=text)
