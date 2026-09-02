"""Confusion-hotspot analytics: the weekly digest for the maintainer.

Ranks sub-strands by student questions per teaching session (not raw counts,
so a sub-strand taught every day does not look confusing just because it is
popular), then clusters each hotspot's question texts into named confusion
themes through the LlmClient seam. The digest is a Markdown report the
maintainer reads to decide which wiki pages to revise.

Zero-session handling: a sub-strand with student questions but no recorded
teaching session has an undefined ratio. It is neither ranked (no denominator)
nor dropped (the questions are real signal); it goes in a separate "unrated"
list that the digest surfaces with raw counts.

Run it manually with `python -m app.analytics` (see main() for flags), or on a
schedule from cron; the report is rewritten in place, so re-running is safe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm_client import LlmClient
from app.models import Question, Substrand, TeachingSession

CLUSTER_SYSTEM_PROMPT = (
    "You analyse questions that Kenyan Grade 10 students asked after class, "
    "to find what confuses them about a topic. Group the questions into a "
    "small number of named confusion themes. Reply with ONLY a JSON array, "
    "no prose and no code fences, where each element is an object "
    '{"theme": "<short theme name>", "question_indexes": [<1-based indexes '
    "of the questions in that theme>]}."
)


@dataclass(frozen=True)
class HotspotStats:
    """Per-sub-strand confusion stats for one digest run."""

    substrand_code: str
    title: str
    student_questions: int
    teaching_sessions: int

    @property
    def questions_per_session(self) -> float | None:
        if self.teaching_sessions == 0:
            return None
        return self.student_questions / self.teaching_sessions


@dataclass(frozen=True)
class HotspotRanking:
    """rated: sessions recorded, sorted hottest first. unrated: questions but
    no sessions, so the ratio is undefined. Zero-question sub-strands appear in
    neither: with nothing to cluster they are not hotspots."""

    rated: list[HotspotStats]
    unrated: list[HotspotStats]


def compute_hotspots(session: Session) -> HotspotRanking:
    question_counts = dict(
        session.execute(
            select(Question.substrand_code, func.count())
            .where(Question.source == "student")
            .group_by(Question.substrand_code)
        ).all()
    )
    session_counts = dict(
        session.execute(
            select(TeachingSession.substrand_code, func.count()).group_by(
                TeachingSession.substrand_code
            )
        ).all()
    )
    titles = dict(session.execute(select(Substrand.code, Substrand.title)).all())

    stats = [
        HotspotStats(
            substrand_code=code,
            title=titles[code],
            student_questions=count,
            teaching_sessions=session_counts.get(code, 0),
        )
        for code, count in question_counts.items()
    ]
    rated = sorted(
        (s for s in stats if s.teaching_sessions > 0),
        key=lambda s: (
            -s.questions_per_session,
            -s.student_questions,
            s.substrand_code,
        ),
    )
    unrated = sorted(
        (s for s in stats if s.teaching_sessions == 0),
        key=lambda s: (-s.student_questions, s.substrand_code),
    )
    return HotspotRanking(rated=rated, unrated=unrated)


@dataclass(frozen=True)
class ConfusionTheme:
    theme: str
    questions: list[str]


@dataclass(frozen=True)
class ClusterResult:
    """themes when Claude's reply parsed; otherwise raw_reply carries the
    verbatim text so the digest still shows something instead of crashing."""

    themes: list[ConfusionTheme]
    raw_reply: str | None = None


def _strip_code_fence(reply: str) -> str:
    text = reply.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1 and text.endswith("```"):
            text = text[first_newline + 1 : -3]
    return text.strip()


def _parse_clusters(reply: str, questions: list[str]) -> list[ConfusionTheme] | None:
    """The strict shape asked of Claude, or None if the reply strays from it."""
    try:
        parsed = json.loads(_strip_code_fence(reply))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    themes: list[ConfusionTheme] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            return None
        theme = entry.get("theme")
        indexes = entry.get("question_indexes")
        if not isinstance(theme, str) or not isinstance(indexes, list):
            return None
        if not all(isinstance(i, int) and not isinstance(i, bool) for i in indexes):
            return None
        matched = [questions[i - 1] for i in indexes if 1 <= i <= len(questions)]
        themes.append(ConfusionTheme(theme=theme, questions=matched))
    return themes


def cluster_questions(
    llm: LlmClient, substrand_title: str, questions: list[str]
) -> ClusterResult:
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(questions, start=1))
    prompt = (
        f'Sub-strand: "{substrand_title}"\n'
        f"Student questions:\n{numbered}"
    )
    reply = llm.complete(CLUSTER_SYSTEM_PROMPT, prompt)
    themes = _parse_clusters(reply, questions)
    if themes is None:
        return ClusterResult(themes=[], raw_reply=reply)
    return ClusterResult(themes=themes)
