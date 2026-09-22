"""Precedence-based formula parsing and a deterministic statement/scope stack."""

from dataclasses import dataclass

from .diagnostics import ProofError, Span
from .formula import FALSE, Atom, Binary, Formula, Not, check_complexity
from .lexer import Token, lex
from .rules import RULES

MAX_SCOPE_DEPTH = 64
PRECEDENCE = {"IMP": 1, "OR": 2, "AND": 3}


@dataclass(frozen=True, slots=True)
class Statement:
    kind: str
    span: Span
    args: tuple[Formula, ...] = ()
    rule: str = ""


@dataclass(frozen=True, slots=True)
class Proof:
    statements: tuple[Statement, ...]

    @property
    def premises(self) -> tuple[Formula, ...]:
        return tuple(s.args[0] for s in self.statements if s.kind == "GIVEN")

    @property
    def goal(self) -> Formula:
        return next(s.args[0] for s in self.statements if s.kind == "DERIVE")


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def take(self, kind: str | None = None) -> Token:
        token = self.current
        if kind is not None and token.kind != kind:
            raise ProofError("E_SYNTAX", f"Expected {kind}; found {token.text!r}.", token.span)
        if token.kind != "EOF":
            self.index += 1
        return token

    def formula(self, minimum: int = 0, depth: int = 0) -> Formula:
        token = self.current
        if depth >= 64:
            raise ProofError("E_LIMIT", "Formula parsing depth exceeds 64.", token.span)
        if token.kind == "NOT":
            self.take()
            left = Not(self.formula(4, depth + 1))
        elif token.kind == "(":
            self.take()
            left = self.formula(0, depth + 1)
            self.take(")")
        elif token.kind == "ID":
            left = Atom(self.take().text)
        elif token.kind == "FALSE":
            self.take()
            left = FALSE
        else:
            raise ProofError("E_SYNTAX", f"Expected a formula; found {token.text!r}.", token.span)
        while self.current.kind in PRECEDENCE:
            op = self.current.kind
            power = PRECEDENCE[op]
            if power < minimum:
                break
            self.take()
            right = self.formula(power if op == "IMP" else power + 1, depth + 1)
            left = Binary(op, left, right)
        return check_complexity(left, token.span)


def parse_formula(source: str) -> Formula:
    parser = Parser(source)
    formula = parser.formula()
    parser.take("EOF")
    return formula


def parse_proof(source: str) -> Proof:
    parser = Parser(source)
    statements: list[Statement] = []
    phase = "premises"
    scopes: list[Span] = []
    while parser.current.kind != "EOF":
        token = parser.take()
        kind = token.kind
        if phase == "done":
            raise ProofError("E_SYNTAX", "No statements are allowed after CONCLUDE.", token.span)
        if phase == "premises":
            if kind not in {"GIVEN", "DERIVE"}:
                raise ProofError("E_SYNTAX", "Expected GIVEN or DERIVE.", token.span)
            statements.append(Statement(kind, token.span, (parser.formula(),)))
            if kind == "DERIVE":
                phase = "body"
        elif kind == "APPLY":
            rule = parser.take("ID")
            if rule.text not in RULES:
                raise ProofError(
                    "E_RULE",
                    f"Unknown inference rule {rule.text!r}.",
                    rule.span,
                    "Run 'proofscope rules' to list supported rules.",
                )
            args = [parser.formula()]
            for _ in range(RULES[rule.text][0] - 1):
                parser.take(",")
                args.append(parser.formula())
            statements.append(Statement(kind, token.span, tuple(args), rule.text))
        elif kind == "ASSUME":
            scopes.append(token.span)
            if len(scopes) > MAX_SCOPE_DEPTH:
                raise ProofError("E_LIMIT", "More than 64 nested assumptions.", token.span)
            statements.append(Statement(kind, token.span, (parser.formula(),)))
        elif kind == "END":
            if not scopes:
                raise ProofError("E_SCOPE", "END has no matching ASSUME.", token.span)
            scopes.pop()
            statements.append(Statement(kind, token.span))
        elif kind == "CONCLUDE":
            if scopes:
                raise ProofError(
                    "E_SCOPE",
                    "Close every assumption before CONCLUDE.",
                    token.span,
                    f"ASSUME on line {scopes[-1].line} still needs END.",
                )
            statements.append(Statement(kind, token.span))
            phase = "done"
        else:
            raise ProofError(
                "E_SYNTAX",
                f"Unexpected statement {token.text!r}.",
                token.span,
                "Use APPLY, ASSUME, END, or CONCLUDE after DERIVE.",
            )
    if phase != "done":
        raise ProofError(
            "E_SYNTAX", "Proof requires DERIVE and a final CONCLUDE.", parser.current.span
        )
    return Proof(tuple(statements))
