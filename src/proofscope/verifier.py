"""Natural-deduction kernel with invocation-local state and explicit scope identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .diagnostics import Diagnostic, ProofError
from .formula import FALSE, Binary, Formula, Not, check_complexity
from .parser import Proof, Statement, parse_proof


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    line: int
    column: int
    kind: str
    rule: str
    formula: str | None
    scope: int
    depth: int
    dependencies: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    syntax_valid: bool
    goal: str | None
    trace: tuple[Event, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def statistics(self) -> dict[str, int]:
        return {
            "steps": len(self.trace),
            "inferences": sum(e.kind == "APPLY" for e in self.trace),
            "premises": sum(e.kind == "GIVEN" for e in self.trace),
            "max_depth": max((e.depth for e in self.trace), default=0),
        }

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "syntax_valid": self.syntax_valid,
            "goal": self.goal,
            "trace": [asdict(event) for event in self.trace],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "statistics": self.statistics,
        }


@dataclass(slots=True)
class ClosedScope:
    assumption: Formula
    assumption_id: int
    end_id: int
    snapshot: dict[Formula, int]


@dataclass(slots=True)
class Scope:
    id: int
    parent: Scope | None
    assumption: Formula | None = None
    assumption_id: int = 0
    facts: dict[Formula, int] = field(default_factory=dict)
    children: list[ClosedScope] = field(default_factory=list)


class Kernel:
    """One kernel per proof. Closed subproofs belong only to their actual parent."""

    def __init__(self):
        self.scope = Scope(0, None)
        self.next_scope = 1
        self.depth = 0
        self.trace: list[Event] = []

    def lookup(self, formula: Formula) -> int | None:
        scope: Scope | None = self.scope
        while scope is not None:
            if formula in scope.facts:
                return scope.facts[formula]
            scope = scope.parent
        return None

    def require(self, formula: Formula, statement: Statement) -> int:
        found = self.lookup(formula)
        if found is None:
            raise ProofError(
                "E_UNAVAILABLE",
                f"{formula} is not available in this scope.",
                statement.span,
                "Derive it here or in an enclosing scope. Closed assumptions are unavailable.",
            )
        return found

    def child(
        self, assumption: Formula, conclusion: Formula, statement: Statement
    ) -> tuple[int, ...]:
        for child in reversed(self.scope.children):
            if child.assumption == assumption and conclusion in child.snapshot:
                return child.assumption_id, child.snapshot[conclusion], child.end_id
        raise ProofError(
            "E_DISCHARGE",
            f"No closed subproof of {conclusion} under {assumption} belongs to this scope.",
            statement.span,
            "Open ASSUME here, derive the required conclusion, close END, then discharge it here.",
        )

    def apply(self, statement: Statement) -> tuple[Formula, tuple[int, ...]]:
        rule, args = statement.rule, statement.args
        a = args[0]
        b = args[1] if len(args) > 1 else None
        require = lambda f: self.require(f, statement)  # noqa: E731

        if rule == "REITERATE":
            return a, (require(a),)
        if rule == "AND_INTRO":
            return Binary("AND", a, b), (require(a), require(b))
        if rule == "AND_ELIM" and isinstance(a, Binary) and a.op == "AND":
            if b in (a.left, a.right):
                return b, (require(a),)
        if rule == "OR_INTRO":
            left, right = self.lookup(a), self.lookup(b)
            if left is not None or right is not None:
                return Binary("OR", a, b), (left if left is not None else right,)
            require(a)
        if rule in {"IMP_ELIM", "OR_ELIM"}:
            for compound, other in ((a, b), (b, a)):
                if not isinstance(compound, Binary):
                    continue
                if rule == "IMP_ELIM" and compound.op == "IMP" and compound.left == other:
                    return compound.right, (require(compound), require(other))
                if rule == "OR_ELIM" and compound.op == "OR":
                    for eliminated, remaining in (
                        (compound.left, compound.right),
                        (compound.right, compound.left),
                    ):
                        if other == Not(eliminated):
                            return remaining, (require(compound), require(other))
        if rule == "IMP_INTRO":
            witness = self.lookup(b)
            dependencies = (witness,) if witness is not None else self.child(a, b, statement)
            return Binary("IMP", a, b), dependencies
        if rule == "NOT_INTRO":
            return Not(a), self.child(a, FALSE, statement)
        if rule == "NOT_ELIM" and (a == Not(b) or b == Not(a)):
            return FALSE, (require(a), require(b))
        if rule == "DNE" and isinstance(a, Not) and isinstance(a.value, Not):
            return a.value.value, (require(a),)
        if rule == "EXPLOSION" and a == FALSE:
            return b, (require(a),)
        if rule == "OR_CASES" and isinstance(a, Binary) and a.op == "OR":
            return b, (
                require(a),
                *self.child(a.left, b, statement),
                *self.child(a.right, b, statement),
            )
        raise ProofError(
            "E_RULE",
            f"Arguments do not match {rule}.",
            statement.span,
            "Check the rule reference for argument order and required formula shape.",
        )

    def record(
        self,
        statement: Statement,
        formula: Formula | None = None,
        dependencies: tuple[int, ...] = (),
    ) -> int:
        event_id = len(self.trace) + 1
        self.trace.append(
            Event(
                event_id,
                statement.span.line,
                statement.span.column,
                statement.kind,
                statement.rule,
                str(formula) if formula is not None else None,
                self.scope.id,
                self.depth,
                tuple(dict.fromkeys(dependencies)),
            )
        )
        return event_id

    def run(self, proof: Proof) -> VerificationResult:
        try:
            for statement in proof.statements:
                kind = statement.kind
                if kind in {"GIVEN", "DERIVE"}:
                    formula = statement.args[0]
                    event_id = self.record(statement, formula)
                    if kind == "GIVEN":
                        self.scope.facts[formula] = event_id
                elif kind == "ASSUME":
                    formula = statement.args[0]
                    self.scope = Scope(self.next_scope, self.scope, formula)
                    self.next_scope += 1
                    self.depth += 1
                    event_id = self.record(statement, formula)
                    self.scope.assumption_id = event_id
                    self.scope.facts[formula] = event_id
                elif kind == "END":
                    snapshot: dict[Formula, int] = {}
                    cursor: Scope | None = self.scope
                    while cursor is not None:
                        for formula, witness in cursor.facts.items():
                            snapshot.setdefault(formula, witness)
                        cursor = cursor.parent
                    end_id = self.record(statement, self.scope.assumption)
                    closed = ClosedScope(
                        self.scope.assumption, self.scope.assumption_id, end_id, snapshot
                    )
                    self.scope = self.scope.parent
                    self.scope.children.append(closed)
                    self.depth -= 1
                elif kind == "APPLY":
                    formula, dependencies = self.apply(statement)
                    check_complexity(formula, statement.span)
                    self.scope.facts[formula] = self.record(statement, formula, dependencies)
                else:
                    witness = self.lookup(proof.goal)
                    if witness is None:
                        raise ProofError(
                            "E_GOAL",
                            f"Goal {proof.goal} has not been derived.",
                            statement.span,
                            "Derive the goal in the outermost scope.",
                        )
                    self.record(statement, proof.goal, (witness,))
        except ProofError as error:
            return VerificationResult(
                False, True, str(proof.goal), tuple(self.trace), (error.diagnostic,)
            )
        return VerificationResult(True, True, str(proof.goal), tuple(self.trace), ())


def verify(source: str) -> VerificationResult:
    """Check source without printing, modifying files, or retaining state between calls."""
    try:
        proof = parse_proof(source)
    except ProofError as error:
        return VerificationResult(False, False, None, (), (error.diagnostic,))
    return Kernel().run(proof)
