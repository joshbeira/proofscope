# Python and HTTP APIs

## Python

```python
from proofscope import analyze, parse_formula, parse_proof, verify

result = verify("GIVEN A DERIVE A CONCLUDE")
assert result.valid
assert result.syntax_valid
assert result.goal == "A"
print(result.statistics)
print(result.to_dict())
```

`verify(source: str) -> VerificationResult` returns an immutable result with a verdict,
syntax verdict, formatted goal, trace events, and diagnostics. Expected input failures are
returned as diagnostics, not printed or raised. A syntax failure has an empty trace;
a failed inference retains only the preceding verified events. `statistics` reports recorded
steps, successful inferences, premises, and maximum observed scope depth.

Every trace event contains `id`, `line`, `column`, `kind`, `rule`, `formula`, `scope`, `depth`,
and `dependencies`. IDs are one-based event IDs, not source line numbers. Diagnostics contain
`code`, `message`, `line`, `column`, and `hint`.

`parse_formula(source)` returns a frozen formula tree. `parse_proof(source)` returns a parsed
proof with `.premises` and `.goal`. Both raise `proofscope.diagnostics.ProofError` for bad input;
the exception carries a `.diagnostic`.

```python
model = analyze(["A -> B", "B"], "A", max_atoms=12, table_limit=64)
assert model["status"] == "counterexample"
assert model["countermodel"] == {"A": False, "B": True}
```

`analyze(premises, goal, *, max_atoms=12, table_limit=64)` accepts formula strings or parsed
formula objects. It returns `status` (`entailed`, `counterexample`, or `limit`), `entailed`,
`countermodel`, `atoms`, `premises`, `goal`, `assignments_checked`, `premise_models`, `vacuous`,
`rows`, and `table_truncated`. On `limit`, no verdict is available and `entailed` is `None`.
On successful analysis, `vacuous` is true exactly when no assignment satisfies the premises.

`max_atoms` must be 0..16 and `table_limit` 0..256; invalid settings raise `ValueError`.
Malformed formulas raise `ProofError`. Limit the preview independently of the exhaustive search.

## Local HTTP

Start with `proofscope serve`. The server is available only on loopback.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/` | Explorer HTML |
| GET | `/api/examples` | Array of `{name, source}` objects |
| POST | `/api/verify` | Verification result plus `semantics` when syntax is valid |

POST a JSON object with `Content-Type: application/json`:

```json
{"source": "GIVEN A DERIVE A CONCLUDE"}
```

A rejected proof is a normal HTTP 200 verification result with `valid: false`. Malformed
requests receive 400, wrong origins/hosts 403, unknown routes 404, size violations 413, and
wrong content types 415. The endpoint accepts proof source only; it cannot read a file path
or execute a command.

## CLI JSON contract

`proofscope check ... --json` always emits an array, including for one input. Each entry adds
`file` to the verification result. File-read failures contain `file`, `valid: false`, and `error`.
`--semantic` adds semantic analysis only if parsing succeeded.

`proofscope entails ... --json` emits one semantic-analysis object. Formula errors instead
emit `{ "status": "error", "diagnostic": ... }` and exit 2.
