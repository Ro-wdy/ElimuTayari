---
id: M-ALG-02
curriculum_ref: 1.2
type: sub-strand
title: Indices and Logarithms
strand_id: M-ALG
status: draft-human-review
source: drive-1SoNJpdbn-9Pzs4T-u8UqttUZx2cPAD_c
prerequisites:
  - M-ALG-01
---

# M-ALG-02: Indices and Logarithms

**Inquiry question:** Why do we use indices and logarithms?

## Curriculum alignment

The design expects learners to express numbers in index form, derive and apply the laws of
indices, connect index notation with base-10 logarithm notation, find common logarithms from
tables and calculators, use common logarithms for multiplication, division, powers, and roots,
and value their use in computation.

**Concepts:** base, index/exponent, zero and negative indices, fractional indices, common
logarithm, characteristic and mantissa (when using tables), inverse operations.

**CBC emphasis:** learning to learn and digital literacy; responsibility and respect when
using tables, calculators, and group reasoning; self-awareness through explaining a method.

## Knowledge graph

- **Prerequisite:** [Real Numbers](./M-ALG-01-real-numbers.md), especially multiplication,
  division, and reciprocals.
- **Leads to:** [Quadratic Expressions and Equations](./M-ALG-03-quadratic-expressions-and-equations.md).
- **Supports:** scientific notation, growth/decay reasoning, and later STEM computation.

## Teacher pack

### Learning sequence

1. Rewrite repeated multiplication as powers, identify base and exponent, and compare
   equivalent forms such as `2 x 2 x 2 = 2^3`.
2. Derive `a^m x a^n = a^(m+n)`, `a^m / a^n = a^(m-n)`, and `(a^m)^n = a^(mn)` by counting
   factors before presenting the rules. Add `a^0 = 1`, `a^(-n) = 1/a^n`, and fractional
   indices as roots with domain care.
3. Introduce `log10(N) = p` as the statement `10^p = N`. Move between index and logarithm
   notation, then use tables/calculators to approximate values.
4. Apply `log(AB) = log A + log B`, `log(A/B) = log A - log B`, and `log(A^n) = n log A`
   to products, quotients, powers, and roots. Check positive-number conditions.

### Low-resource activity

Give groups cards showing repeated products, index form, and logarithm form. Learners match
triples, then justify one match by expanding the power. A second round mixes one incorrect
rule so the group must diagnose it.

### Kenyan context

Use powers of ten for Kenyan population estimates, mobile-data sizes, and distances in
scientific notation. A calculator exercise can compare a rounded logarithm with the exact
power of ten used to model the quantity.

### Check for understanding

- Simplify `3^4 x 3^(-2)` and explain why the answer is not `3^2` by guesswork alone.
- Convert `10^2.5 = N` to logarithm notation and estimate `log(1000)`.
- Evaluate a product with common logs, then verify on a calculator.
- Ask which log expressions are undefined over the real numbers and why.

### Common misconceptions

- Adding exponents when bases differ; the index laws require compatible bases.
- Reading `a^(m+n)` as `a^m + a^n`.
- Treating `log(a+b)` as `log a + log b`; the product law does not apply to sums.
- Forgetting that common logarithms here have base 10 and require positive arguments.

## Worked example

Simplify `8^(2/3)`.

Use the fractional-index meaning: `8^(2/3) = (cube root of 8)^2 = 2^2 = 4`. Check with a
calculator. The exponent is not a percentage; the denominator indicates a root.

## SMS teaching pack

**SMS 1/3:** `M-ALG-02` Index laws: a^m*a^n=a^(m+n); a^m/a^n=a^(m-n); (a^m)^n=a^(mn). Bases must match.

**SMS 2/3:** Common log means base 10: log(N)=p iff 10^p=N. Product becomes a sum of logs; quotient becomes a difference.

**SMS 3/3:** Try: simplify 2^3*2^-1; write 10^3=1000 as a log statement; explain why log(-2) is not real.

## Review notes

This page paraphrases the supplied 2025 Core Mathematics design family. Verify table-reading
conventions and the HI variant's presentation requirements against the source PDF before
publication.
