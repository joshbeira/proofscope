# Proof language reference

A proof begins with zero or more `GIVEN` statements, exactly one `DERIVE`, a sequence of
inferences/subproofs, and a final `CONCLUDE`. Statements are separated by whitespace;
line breaks and indentation improve readability but do not define scope.

```ebnf
proof       = { "GIVEN" formula }, "DERIVE" formula, block, "CONCLUDE" ;
block       = { application | "ASSUME" formula, block, "END" } ;
application = "APPLY", rule, formula, [ ",", formula ] ;
formula     = implication ;
implication = disjunction, [ "IMP", implication ] ;
disjunction = conjunction, { "OR", conjunction } ;
conjunction = unary, { "AND", unary } ;
unary       = "NOT", unary | "(", formula, ")" | identifier | "FALSE" ;
identifier  = (letter | "_"), { letter | digit | "_" } ;
```

Rule arity determines whether a second argument is required. Keywords and rule names are
case-sensitive. Identifiers use ASCII letters, digits, and underscores; reserved statement and
operator words cannot be identifiers. Identifiers may contain keyword prefixes (`ANDROID` is
one identifier).

`#` starts a line comment. `### ... ###` delimits a block comment. Comments preserve diagnostic
line positions; an unclosed block comment is an error.

## Operators

| Meaning | Word | ASCII | Unicode | Binding |
| --- | --- | --- | --- | --- |
| Negation | `NOT` | `!` | `¬` | Tightest |
| Conjunction | `AND` | `&&` | `∧` | Left associative |
| Disjunction | `OR` | `\|\|` | `∨` | Left associative |
| Implication | `IMP` | `->` | `→` | Loosest; right associative |
| Contradiction | `FALSE` | | `⊥` | Constant falsehood |

`A OR B AND C -> D` means `(A OR (B AND C)) -> D`.
`A -> B -> C` means `A -> (B -> C)`. Parentheses override precedence.
Negation is explicit: `NOT NOT A` is a different syntax tree from `A`.

## Inference rules

In this table, A, B, and C stand for any formulas, including compounds. “Available” means
established in the current scope or one of its active ancestors. Rules inspect structure, not
semantic equivalence.

| Application | Result | Required evidence |
| --- | --- | --- |
| `AND_INTRO A, B` | `A AND B` | A and B available |
| `AND_ELIM A AND B, A` | A | The conjunction available; second argument selects the result |
| `AND_ELIM A AND B, B` | B | As above |
| `OR_INTRO A, B` | `A OR B` | At least one of A, B available |
| `OR_ELIM A OR B, NOT A` | B | Both inputs available; also works with `NOT B` to produce A |
| `OR_CASES A OR B, C` | C | Disjunction available; closed direct-child subproofs A ⊢ C and B ⊢ C |
| `IMP_INTRO A, B` | `A IMP B` | A closed direct-child subproof A ⊢ B, or B already available here |
| `IMP_ELIM A IMP B, A` | B | Both inputs available |
| `NOT_INTRO A` | `NOT A` | A closed direct-child subproof A ⊢ FALSE |
| `NOT_ELIM A, NOT A` | FALSE | Both inputs available |
| `DNE NOT NOT A` | A | The double negation available |
| `EXPLOSION FALSE, A` | A | FALSE available |
| `REITERATE A` | A | A available |

`IMP_ELIM`, `OR_ELIM`, and `NOT_ELIM` accept either argument order. `AND_ELIM` always takes
the conjunction first and the desired result second. `OR_ELIM` names disjunctive syllogism;
use `OR_CASES` for a proof by cases. `NOT_INTRO` takes one argument.

## Scope and discharge

Every `ASSUME` opens a fresh scope, even if an identical formula was assumed earlier.
`END` closes only the most recent scope. Formulas in closed scopes cannot be used directly.
A completed subproof may be discharged only by its actual parent scope; a grandchild's
evidence cannot skip a level. Completed subproofs can be cited again in the same parent.

```text
DERIVE A -> A
ASSUME A
END
APPLY IMP_INTRO A, A
CONCLUDE
```

An assumption itself is valid evidence inside its scope, so this identity proof needs no
additional inference. In contrast, the following is rejected:

```text
DERIVE A -> B
ASSUME A
    ASSUME B
    END
END
APPLY IMP_INTRO A, B
CONCLUDE
```

B was available only under the additional assumption B; it was never established under A alone.

All scopes must close before `CONCLUDE`. The goal must be available in global scope; it may
already be a premise. No statements are allowed after `CONCLUDE`.

## Diagnostics and limits

| Code | Meaning |
| --- | --- |
| `E_LEX` | Invalid character or unclosed comment |
| `E_SYNTAX` | Malformed formula, statement, or proof structure |
| `E_SCOPE` | Unmatched END or an assumption still open at CONCLUDE |
| `E_RULE` | Unknown inference or mismatched argument structure |
| `E_UNAVAILABLE` | Required formula is not available in the active context |
| `E_DISCHARGE` | No suitable closed subproof belongs to the current scope |
| `E_GOAL` | Goal has not been established globally |
| `E_LIMIT` | Source, token, formula, or scope resource limit exceeded |

Limits: 65,536 source characters, 16,384 tokens, 256 formula-node occurrences, formula-tree
depth 64, formula-parser recursion depth 64 (including parentheses), and 64 nested assumptions.
Generated formulas are checked before hashing or rendering to bound expansion from repeated
conjunctions. HTTP requests are separately limited to 300,000 bytes.
