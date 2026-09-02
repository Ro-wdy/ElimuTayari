"""Answer a student question for the teacher, grounded in the wiki.

When a teacher uploads a student question (Q <code> <question>), saving it for
analytics is half the job - the teacher also has to face that student again
tomorrow. This module composes a short, teacher-facing explanation through the
LlmClient seam, grounded in the sub-strand's guidance content so the answer
speaks the wiki's language.

Constraints: the answer travels by SMS, so the prompt demands plain text (no
markdown) tight enough to fit ANSWER_CHAR_BUDGET; the reply is clipped to that
budget as a hard stop. A malformed or failed LLM call yields None and the
webhook falls back to the plain confirmation - an answer is a bonus, never a
gate on saving the question.
"""

import logging

from app.llm_client import LlmClient
from app.models import Substrand

logger = logging.getLogger(__name__)

# ~3 SMS incl. the confirmation line and split_pack's part numbering.
ANSWER_CHAR_BUDGET = 380

ANSWER_SYSTEM_PROMPT = (
    "You help Kenyan Grade 10 teachers (CBC curriculum) explain concepts their "
    "students found confusing. Reply with a clear explanation the teacher can "
    "use in class: the key idea, then one short concrete example. Plain text "
    "only - no markdown, no headings, no lists. At most {budget} characters."
)


def compose_answer(
    llm: LlmClient, substrand: Substrand, guidance: str | None, question: str
) -> str | None:
    """A teacher-facing answer to one student question, or None on failure."""
    grounding = (
        f"Wiki guidance for this sub-strand:\n{guidance}\n\n"
        if guidance
        else "No wiki guidance is available; answer from the sub-strand topic.\n\n"
    )
    prompt = (
        f'Sub-strand: {substrand.code} "{substrand.title}"\n\n'
        f"{grounding}"
        f"A student asked: {question}\n\n"
        "How should the teacher explain this?"
    )
    try:
        answer = llm.complete(
            ANSWER_SYSTEM_PROMPT.format(budget=ANSWER_CHAR_BUDGET), prompt
        ).strip()
    except Exception:
        # Fall back to the plain confirmation, but never silently.
        logger.exception("answer generation failed for %s", substrand.code)
        return None
    if not answer:
        return None
    return answer[:ANSWER_CHAR_BUDGET]
