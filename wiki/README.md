# ElimuTayari LLM wiki

This directory is the curriculum knowledge base for the ElimuTayari teaching companion.
Pages are written for two readers at once: a teacher who needs a usable teaching pack and
an LLM that needs small, attributable chunks of curriculum knowledge.

## Current scope

The first learning area is **Grade 10 Core Mathematics** in the STEM pathway. It is based
on the Grade 10 Core Mathematics design visible in the supplied Drive document:
`Core Mathematics Grade 10 - HI 2025.pdf`. The HI label is retained as source metadata;
the teaching guidance below is a plain-language draft and is not a replacement for the
official design or a signed-off adaptation for learners with hearing impairment.

## Retrieval contract

1. Start at the learning-area hub: `grade-10/core-mathematics/README.md`.
2. Use the strand page for a teacher-facing lookup; display the official curriculum
   reference and title before the internal `M-*` alias.
3. Use `graph.json` for relationships, stable IDs, and file paths.
4. Retrieve one sub-strand page at a time. Do not merge outcomes from neighbouring
   sub-strands unless the graph marks the relationship.
5. Treat the `Curriculum alignment` section as the curriculum-derived layer. Treat
   `Teacher pack`, examples, misconceptions, and SMS text as ElimuTayari-authored support.
6. Preserve the `M-*` identifier in teacher packs, test-generation requests, SMS commands,
   and analytics events.
7. If a page conflicts with a newer KICD design, prefer the newer official design and
   record the change in the page's `Review notes` section before editing the graph.

## Page contract

Every sub-strand page has:

- YAML metadata with `id`, `curriculum_ref`, `strand_id`, `status`, `source`, and
  `prerequisites`.
- a concise curriculum focus and paraphrased learning outcomes;
- a concept map and links to neighbouring graph nodes;
- a teacher-ready learning sequence, low-resource activity, Kenyan context, and checks;
- common misconceptions and one worked example;
- a three-part SMS teaching pack designed for short messages;
- an explicit review note.

`status: draft-human-review` is intentional. A mathematics teacher must approve the
paraphrases, examples, assessment language, and any future HI-specific adaptation before
the content is treated as published curriculum.

## Adding another learning area

Create a new folder under `grade-10/`, give it its own hub and graph, and use a subject
prefix different from `M` so identifiers remain globally unique. Do not put another
subject's nodes into the Mathematics graph.
