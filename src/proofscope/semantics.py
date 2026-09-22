"""Bounded exhaustive model checking, independent of inference-rule execution."""

from collections.abc import Iterable
from itertools import product

from .diagnostics import Span
from .formula import Formula, atoms, check_complexity, evaluate
from .parser import parse_formula


def analyze(
    premises: Iterable[str | Formula],
    goal: str | Formula,
    *,
    max_atoms: int = 12,
    table_limit: int = 64,
) -> dict:
    """Decide classical entailment, or explicitly return 'limit' without a verdict.

    At most 16 atoms may be requested. Truth-table output is capped independently
    of the search, so a shortened table never implies a shortened entailment check.
    """
    if not 0 <= max_atoms <= 16 or not 0 <= table_limit <= 256:
        raise ValueError("max_atoms must be 0..16 and table_limit must be 0..256")
    formulas = tuple(
        parse_formula(f) if isinstance(f, str) else check_complexity(f, Span()) for f in premises
    )
    target = parse_formula(goal) if isinstance(goal, str) else check_complexity(goal, Span())
    names = sorted(set().union(atoms(target), *(atoms(f) for f in formulas)))
    base = {"atoms": names, "premises": [str(f) for f in formulas], "goal": str(target)}
    if len(names) > max_atoms:
        return {
            **base,
            "status": "limit",
            "entailed": None,
            "countermodel": None,
            "message": f"{len(names)} atoms exceeds the configured limit of {max_atoms}.",
            "assignments_checked": 0,
            "premise_models": None,
            "rows": [],
            "table_truncated": False,
            "vacuous": None,
        }
    countermodel = None
    rows = []
    premise_models = 0
    for values in product((False, True), repeat=len(names)):
        assignment = dict(zip(names, values, strict=True))
        given = all(evaluate(f, assignment) for f in formulas)
        conclusion = evaluate(target, assignment)
        premise_models += given
        if given and not conclusion and countermodel is None:
            countermodel = assignment
        if len(rows) < table_limit:
            rows.append(
                {
                    "assignment": assignment,
                    "premises_hold": given,
                    "goal_holds": conclusion,
                    "counterexample": given and not conclusion,
                }
            )
    total = 2 ** len(names)
    return {
        **base,
        "status": "entailed" if countermodel is None else "counterexample",
        "entailed": countermodel is None,
        "countermodel": countermodel,
        "assignments_checked": total,
        "premise_models": premise_models,
        "vacuous": premise_models == 0,
        "rows": rows,
        "table_truncated": total > len(rows),
    }
