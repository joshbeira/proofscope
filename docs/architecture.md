# Architecture and correctness boundaries

ProofScope separates source recognition, proof checking, and semantic analysis. The CLI and
HTTP server adapt the same public API; neither implements logical rules.

## 1. Source to immutable formulas

The lexer scans left to right, preserving original line and column positions through comments
and line-ending normalization. It recognizes whole identifiers before classifying keywords,
so prefix collisions do not split identifiers.

The formula parser uses precedence climbing. Conjunction/disjunction associate left;
implication associates right. Frozen dataclasses represent atoms, negation, binary connectives,
and falsehood. Equality and hashing are structural. This makes set/dictionary membership
predictable without hiding extra equivalence transformations in the kernel.

A separate statement phase machine enforces premises → goal → proof body → conclusion.
An explicit stack checks nested `ASSUME` / `END` pairs. Parsing must succeed in full before
the verifier processes any steps.

## 2. The verification kernel

Each `verify()` call constructs a fresh kernel. A scope holds:

- A unique identity and a reference to its actual parent.
- Its assumption and the corresponding trace event.
- Locally established formulas mapped to their witness event IDs.
- Closed direct-child subproofs, each with a snapshot of visible facts at closure.

Lookup walks only active ancestors. Closing a subproof copies the evidence visible at that
moment and registers the resulting object only with its immediate parent. Discharge searches
those direct children. Using identities rather than a tuple of assumption formulas avoids
merging distinct sibling scopes that happen to assume the same proposition.

The intended invariant is: **each locally established formula follows from the premises and
the assumptions on its active ancestor path.** Introduction rules remove only the assumption
owned by the discharged direct child. For implication introduction, an already available
consequent is also sufficient: B entails A → B under the same context.

Inference output includes dependency event IDs. All edges point backward. Closed-subproof
rules reference the assumption, conclusion witness, and END event. These traces explain rule
execution; they are not a separate certificate format checked by another trusted kernel.

## 3. Independent semantic analysis

The semantic checker enumerates Boolean assignments and evaluates formulas directly. It does
not use the proof kernel's scope lookup or inference code. It shares the parser and AST, so
it is independent at the rule/semantics layer, not a fully independent implementation of the
whole language.

For each assignment, it tests whether all premises hold and the goal fails. Such an assignment
is a countermodel. If none exists after exhaustive enumeration, the sequent is entailed.
Inconsistent premises are explicitly reported as vacuous entailment. Table display truncation
does not truncate the actual search.

Resource-limit results carry `entailed: null`; they never pretend to establish validity.
Semantic entailment never repairs an invalid proof or changes its verification verdict.

## 4. Interfaces

The CLI supports batch input, stdin, source excerpts, traces, and JSON. The local HTTP adapter
serves only fixed packaged assets and the example/verification endpoints. It binds to
`127.0.0.1`, restricts Host/Origin, caps request size, and never evaluates source as code.
The vanilla JavaScript UI renders user content with text nodes, clears stale results on edit,
and ignores responses for superseded editor revisions.

The server is a local development/workbench service. It has no authentication, multi-tenant
resource scheduler, persistence backend, or public-hosting guarantees.

## Complexity

Let N be source length, S the number of proof statements, F the bounded formula size,
D the scope depth, and A the number of distinct atoms.

- Lexing is O(N). Formula parsing follows the grammar; repeated size checks can make a
  deeply nested expression O(F²), with F capped at 256 occurrences.
- Ordinary evidence lookup visits at most D scopes, with structural hashing cost O(F).
- Discharge searches completed direct children. In the worst case repeated discharges can
  produce O(S²F) total search work.
- Closing scopes snapshots visible facts, trading memory for stable evidence at closure;
  adversarial proofs can require quadratic total snapshot storage in S.
- Semantic analysis is O(2^A × T), where T is the total formula size of the sequent.
  Only the bounded truth-table preview is retained, alongside the first countermodel.

These are transparent bounds for a small local reasoning tool, not claims of large-scale
theorem-prover performance.

## Validation strategy

Tests cover successful and failed rule applications, exact source locations, structural
equality, scope leakage, repeated assumptions, concurrent invocation isolation, finite
semantic cross-checks, CLI exit contracts, and HTTP boundaries. Randomness is not required
to reproduce failures. The generated single-step corpus has 8 × 8 × 9 = 576 instances.

The implementation is not mechanically verified. Tests and an independent bounded semantic
checker provide complementary evidence; neither establishes soundness for all possible inputs.
See the [design decisions](decisions/001-proof-context.md) for the central tradeoffs.
