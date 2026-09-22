"""The public rule catalogue; arities are checked before verification."""

RULES = {
    "AND_INTRO": (2, "Combine two available formulas into a conjunction."),
    "AND_ELIM": (2, "Select either conjunct: conjunction, desired conjunct."),
    "OR_INTRO": (2, "Introduce a disjunction when at least one disjunct is available."),
    "OR_ELIM": (2, "Disjunctive syllogism: disjunction and a negated disjunct."),
    "OR_CASES": (2, "Derive a common conclusion from two closed case subproofs."),
    "IMP_INTRO": (2, "Discharge a closed subproof: assumption, conclusion."),
    "IMP_ELIM": (2, "Modus ponens: implication and its antecedent."),
    "NOT_INTRO": (1, "Negate an assumption whose closed subproof derives FALSE."),
    "NOT_ELIM": (2, "Derive FALSE from a formula and its negation."),
    "DNE": (1, "Eliminate exactly two negations (classical logic)."),
    "EXPLOSION": (2, "Derive any formula from FALSE: FALSE, target."),
    "REITERATE": (1, "Record a formula already available in the current scope."),
}
