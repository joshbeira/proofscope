"""Immutable syntax trees; equality means structure, never logical equivalence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .diagnostics import ProofError, Span

MAX_FORMULA_NODES = 256
MAX_FORMULA_DEPTH = 64


@dataclass(frozen=True, slots=True)
class Atom:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Bottom:
    def __str__(self) -> str:
        return "FALSE"


@dataclass(frozen=True, slots=True)
class Not:
    value: Formula

    def __str__(self) -> str:
        return f"NOT {self.value}"


@dataclass(frozen=True, slots=True)
class Binary:
    op: str
    left: Formula
    right: Formula

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


Formula: TypeAlias = Atom | Bottom | Not | Binary
FALSE = Bottom()


def check_complexity(formula: Formula, span: Span) -> Formula:
    """Count occurrences, including shared subtrees, before hashing or rendering."""
    pending = [(formula, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_FORMULA_NODES or depth > MAX_FORMULA_DEPTH:
            raise ProofError(
                "E_LIMIT",
                "Formula exceeds the size or nesting limit.",
                span,
                f"Use at most {MAX_FORMULA_NODES} nodes and depth {MAX_FORMULA_DEPTH}.",
            )
        if isinstance(node, Not):
            pending.append((node.value, depth + 1))
        elif isinstance(node, Binary):
            pending.extend([(node.left, depth + 1), (node.right, depth + 1)])
    return formula


def atoms(formula: Formula) -> set[str]:
    if isinstance(formula, Atom):
        return {formula.name}
    if isinstance(formula, Not):
        return atoms(formula.value)
    if isinstance(formula, Binary):
        return atoms(formula.left) | atoms(formula.right)
    return set()


def evaluate(formula: Formula, assignment: dict[str, bool]) -> bool:
    if isinstance(formula, Atom):
        return assignment[formula.name]
    if isinstance(formula, Bottom):
        return False
    if isinstance(formula, Not):
        return not evaluate(formula.value, assignment)
    left = evaluate(formula.left, assignment)
    right = evaluate(formula.right, assignment)
    if formula.op == "AND":
        return left and right
    if formula.op == "OR":
        return left or right
    return not left or right
