# ElimuTayari — 3-minute lightning script

**AI Mashinani** · Nirel, Alphonce, David, Millicent, Rhodah

180 seconds, 7 slides. The demo is the pitch; the slides set it up and land it.
Times are cumulative — if you are past the marker, cut to the next slide.

Before you start: the server is running, the phone is in your hand, and the SMS
you will send after class is already typed but unsent.

---

## 1 — Title · 0:00–0:12 (12s)

> ElimuTayari is a CBC teaching companion for Grade 10 teachers in Kenya.
> It runs on the phone a teacher already owns — no smartphone, no data bundle,
> nothing to install.

Say the last line slowly. It is the whole differentiator.

## 2 — The problem · 0:12–0:37 (25s)

> Senior School CBC started, and teachers were handed a curriculum most had never
> taught. English alone is 45 sub-strands across 9 themes — 180 lessons, each with
> its own outcomes and assessment.
>
> Every tool built to help assumes a smartphone and a data bundle. That is not
> what a teacher in Turkana is holding. The phone was never the constraint — the
> delivery was.

## 3 — How it works · 0:37–1:02 (25s)

> Four steps. The teacher dials a USSD code and browses to a sub-strand. The
> teaching pack arrives by SMS in whole 160-character parts. After class they
> reply with what confused their students — Q, the sub-strand code, the question.
> Those questions generate tests and show which topics are hardest.
>
> That last step compounds: every question sent back improves the next pack.

## 4 — Live demo · 1:02–1:52 (50s)

Narrate while you dial. Do not read the slide.

> I am dialling now, on a normal phone, with data switched off.

1. Home screen → "Core Mathematics".
2. Strand → "Algebra". Sub-strand → "Indices and Logarithms".
3. Session ends. **Read the SMS aloud** as it arrives — that is the payoff.
4. Send `Q M-ALG-02 Why do we swap the sign?`
5. Show the question stored against that sub-strand.

> Every screen fits inside 160 characters, and M-ALG-02 is the same identifier in
> the wiki, the database, the USSD menu and that SMS.

**If the demo fails:** say "the screens are on the slide", talk through steps 3–5
from it, and move on. Do not retry the dial. Budget 10 seconds.

## 5 — The architecture decision · 1:52–2:17 (25s)

The engineering heart of the pitch. Do not rush this one.

> We had a choice: put a chatbot in front of teachers, or pre-generate a wiki.
> We chose the wiki, for three reasons.
>
> Curriculum is static — a sub-strand does not change per teacher or per question.
> So a teaching pack is a database read, not an inference: **zero token cost per
> lesson**, and the next teacher costs one SMS. This scales to every teacher in
> Kenya without the model bill scaling with it.
>
> It is deterministic, which is what makes review possible — you cannot sign off
> on an answer that comes out different every time it is asked. And it means a
> hallucination can never reach a classroom. The live model only writes tests and
> clusters questions; it is never the source of what a teacher is told to teach.

## 6 — Online and offline · 2:17–2:39 (22s)

> The system is deliberately split in two.
>
> Updating the wiki is an online job, and it belongs to the education board — they
> review the official KICD design, the wiki is versioned and signed off, and it is
> seeded into the database on deploy. Institutional work, done once.
>
> Teaching is the offline half. Past that line, nothing needs the internet: the
> teacher dials USSD, gets an SMS, replies with questions. Daily work, done
> anywhere — including where there is no coverage.

## 7 — Where this goes · 2:39–3:00 (21s)

> Core Mathematics is done — 14 sub-strands against the KICD design. English is
> extracted, all 45 sub-strands, pending teacher review. The pipeline is the
> asset: point it at a design, get a learning area.
>
> Every Kenyan teacher already owns the hardware. We are asking for the pilot that
> proves the loop.

Stop there. Do not add a summary.

---

## Likely judge questions

**"Why not just call an LLM per question?"** Cost and reviewability. Per-request
inference means the bill grows with every teacher and every lesson, and no two
answers are the same — so nobody can sign off on the content. Pre-generating makes
the marginal cost of a teaching pack an SMS, and makes teacher review possible at
all. We spend model tokens where they actually add value: tests and clustering.

**"How is this not just SMS blasting?"** The loop back is the product. A teacher
replies with real student confusion against a stable sub-strand code, which makes
the next pack and the generated tests specific rather than generic.

**"Who keeps the content current?"** The education board, online — that is the
whole point of the split. A new KICD design means re-running the extraction and a
review pass, not rewriting the system.

**"What if the LLM gets the curriculum wrong?"** It cannot reach that layer.
Content is generated ahead of time from the official design and carries
`status: draft-human-review` until a subject teacher approves it.

**"What does it cost per teacher?"** USSD and SMS are billed per session and per
message through Africa's Talking. No per-teacher software cost, no token cost per
lesson, and no data cost to the teacher. Have the current rates to hand.

**"Why not WhatsApp?"** WhatsApp needs a smartphone and data. The teachers
furthest from support have neither.

**"How do you know teachers will reply?"** We do not yet — that is the pilot, and
the metric is packs delivered versus questions returned.
