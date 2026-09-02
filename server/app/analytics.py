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

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Question, Substrand, TeachingSession


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
