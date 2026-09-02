"""Compose a short test from a sub-strand's guidance and question bank.

The first live-LLM feature: one Claude call per "Get a test" selection,
through the LlmClient seam - this module never imports anthropic and never
names a model. The prompt hands over the sub-strand's guidance content
(learning outcomes) and its uploaded question bank (student questions and
teacher-authored items, labelled), and demands a strict, parseable reply:
a JSON array of exactly QUESTION_COUNT question strings and nothing else.

Parsing is defensive: chatter around the array is tolerated, but a reply
whose array is missing, malformed, or not a non-empty list of non-empty
strings yields None - as does an LLM error - so the route can degrade to an
apologetic SMS instead of dropping the session or sending garbage.
"""

from __future__ import annotations

import json

from app.llm_client import LlmClient
from app.models import Question, Substrand

QUESTION_COUNT = 5

SYSTEM = (
    "You write short tests for Grade 10 teachers in Kenya following the CBC "
    "curriculum. Questions must be answerable with pen and paper, phrased in "
    "plain text with no markup (they are delivered by SMS), and grounded in "
    "the sub-strand's learning outcomes."
)


def build_prompt(
    substrand: Substrand, guidance: str | None, questions: list[Question]
) -> str:
    lines = [
        f"Compose a test of exactly {QUESTION_COUNT} questions for this "
        "Grade 10 sub-strand:",
        f"{substrand.code} {substrand.title}"
        f" ({substrand.learning_area} / {substrand.strand})",
        "",
    ]
    if guidance is not None:
        lines += ["Learning outcomes and guidance:", guidance, ""]
    if questions:
        lines.append("Question bank uploaded after class, labelled by source")
        lines.append("(draw on these; fill any gaps from the outcomes):")
        lines += [f"- [{q.source}] {q.text}" for q in questions]
        lines.append("")
    else:
        lines.append(
            "The question bank for this sub-strand is empty: compose every "
            "question from the learning outcomes alone."
        )
        lines.append("")
    lines.append(
        f"Reply with ONLY a JSON array of exactly {QUESTION_COUNT} strings, "
        "one question per string. No numbering, no markdown, no text outside "
        "the array."
    )
    return "\n".join(lines)


def parse_reply(reply: str) -> list[str] | None:
    """The question list in a reply, or None when it cannot be trusted."""
    start, end = reply.find("["), reply.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        items = json.loads(reply[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or not items:
        return None
    if not all(isinstance(item, str) and item.strip() for item in items):
        return None
    return [item.strip() for item in items[:QUESTION_COUNT]]


def generate_test(
    llm_client: LlmClient,
    substrand: Substrand,
    guidance: str | None,
    questions: list[Question],
) -> list[str] | None:
    """One Claude call; the parsed questions, or None on error or garbage."""
    try:
        reply = llm_client.complete(SYSTEM, build_prompt(substrand, guidance, questions))
    except Exception:
        return None
    return parse_reply(reply)
