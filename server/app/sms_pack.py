"""Split a teaching-pack body into SMS-sized parts.

One GSM SMS carries 160 characters; longer packs must go out as several
messages that each fit whole, read in order, and end with the sub-strand
code so the teacher can quote it back after class (Q <code> <question>).

Splitting prefers line breaks, then word boundaries - a part never cuts a
word. When more than one part is needed, each is prefixed "i/n " so parts
that arrive out of order still read correctly; the prefix is budgeted for
before splitting so numbering can never push a part over the limit.
"""

from __future__ import annotations

SMS_LIMIT = 160

# Room reserved for an "i/n " prefix; supports up to 99 parts ("99/99 ").
_PREFIX_BUDGET = len("99/99 ")


def split_pack(body: str, code: str, limit: int = SMS_LIMIT) -> list[str]:
    """Split body into messages of at most limit characters.

    The final message always contains code: it is appended when the body's
    own tail lacks it. Multi-part output is numbered "i/n ".
    """
    if code not in body.rsplit("\n", 1)[-1]:
        body = f"{body}\n{code}"

    if len(body) <= limit:
        return [body]

    chunks = _chunk(body, limit - _PREFIX_BUDGET)
    total = len(chunks)
    return [f"{i}/{total} {chunk}" for i, chunk in enumerate(chunks, start=1)]


def _chunk(body: str, size: int) -> list[str]:
    """Greedy fill: whole lines while they fit, words when a line is too long."""
    chunks: list[str] = []
    current = ""
    for line in body.split("\n"):
        for piece in _fit_line(line, size):
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= size:
                current = f"{current}\n{piece}"
            else:
                chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


def _fit_line(line: str, size: int) -> list[str]:
    """A line as-is if it fits, else word-boundary pieces that each fit."""
    if len(line) <= size:
        return [line]
    pieces: list[str] = []
    current = ""
    for word in line.split(" "):
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= size:
            current = f"{current} {word}"
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces
