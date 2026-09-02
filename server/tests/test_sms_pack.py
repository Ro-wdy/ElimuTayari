"""Pack splitting, tested at the split_pack seam.

A teaching pack body must arrive as SMS parts that each fit one message, in
readable order, with the sub-strand code in the final part so the teacher can
quote it back (Q <code> <question>) after class.
"""

from app.sms_pack import SMS_LIMIT, split_pack

CODE = "M-ALG-02"

LONG_BODY = (
    f"[PLACEHOLDER] {CODE} Formulae and Variations\n"
    "1. Outcome: learners can work with formulae and variations.\n"
    "2. Activity: worked example on the board, then pairs.\n"
    "3. Materials: exercise books, chalkboard.\n"
    "Reply Q <code> <question> after class."
)


def test_short_body_is_a_single_message_carrying_the_code():
    parts = split_pack("Teach fractions today.", CODE)

    assert len(parts) == 1
    assert CODE in parts[0]


def test_long_body_splits_into_parts_that_each_fit_one_sms():
    parts = split_pack(LONG_BODY, CODE)

    assert len(parts) >= 2
    assert all(len(part) <= SMS_LIMIT for part in parts)


def test_parts_are_numbered_and_content_is_preserved_in_order():
    parts = split_pack(LONG_BODY, CODE)

    total = len(parts)
    for i, part in enumerate(parts, start=1):
        assert part.startswith(f"{i}/{total} ")
    reassembled = " ".join(p.split(" ", 1)[1] for p in parts)
    body_words = LONG_BODY.split()
    # The splitter may append the code as a trailer; the body itself must
    # survive verbatim and in order.
    assert reassembled.split()[: len(body_words)] == body_words


def test_final_part_carries_the_substrand_code():
    parts = split_pack(LONG_BODY, CODE)

    assert CODE in parts[-1]


def test_final_part_gains_the_code_when_the_body_tail_lacks_it():
    body = "First line about teaching.\n" + ("word " * 60).strip()
    parts = split_pack(body, CODE)

    assert CODE in parts[-1]
    assert all(len(part) <= SMS_LIMIT for part in parts)


def test_a_line_longer_than_one_sms_is_split_on_word_boundaries():
    body = ("equations " * 40).strip()
    parts = split_pack(body, CODE)

    assert all(len(part) <= SMS_LIMIT for part in parts)
    words = " ".join(p.split(" ", 1)[1] for p in parts).split()
    assert set(words) <= {"equations", CODE}
