# Decision 001: Explicit scope identity and a small inspectable kernel

**Status:** accepted

## Context

Proof blocks create temporary assumptions. Correct discharge depends on where evidence was
established, not just on whether a similarly named assumption occurred somewhere earlier.
Different subproofs can have identical assumption formulas without sharing local facts.

## Decision

Represent each open subproof as a distinct scope object with a parent pointer. Keep local
evidence separate and snapshot visible evidence when the scope closes. Register completed
subproofs with their immediate parent only. Keep all proof state local to one verification call.

Formula objects are immutable and structurally comparable. Do not normalize commutative
operators or erase double negation: explicit rule applications should explain transformations.

Use a separate bounded truth-table evaluator as an executable check of claimed entailment.
Do not use that evaluator to approve invalid inference steps. Keep the Python runtime free
of third-party dependencies so the kernel and its interfaces are easy to inspect and install.

## Consequences

Scope lookup and discharge are easy to reason about and test. The design rejects subproof
evidence from siblings or unrelated ancestors and prevents state contamination across requests.
Evidence snapshots cost memory; discharge scans can become quadratic. Source and formula
limits bound practical work, and the architecture documentation states these tradeoffs.

The system remains a verifier for explicit proofs, rather than an automatic proof searcher.
The truth-table evaluator is exhaustive only within its atom bound and shares the AST/parser
with the kernel. A separately verified certificate checker would be a distinct future feature.
