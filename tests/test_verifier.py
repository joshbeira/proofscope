import unittest
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files

from proofscope import analyze, parse_proof, verify


class RuleTests(unittest.TestCase):
    def assertValid(self, source):
        result = verify(source)
        self.assertTrue(result.valid, result.to_dict())
        parsed = parse_proof(source)
        self.assertTrue(analyze(parsed.premises, parsed.goal)["entailed"], source)
        return result

    def test_all_rules(self):
        examples = [
            "GIVEN A GIVEN B DERIVE A AND B APPLY AND_INTRO A, B CONCLUDE",
            "GIVEN A AND B DERIVE A APPLY AND_ELIM A AND B, A CONCLUDE",
            "GIVEN A AND B DERIVE B APPLY AND_ELIM A AND B, B CONCLUDE",
            "GIVEN A DERIVE A OR B APPLY OR_INTRO A, B CONCLUDE",
            "GIVEN B DERIVE A OR B APPLY OR_INTRO A, B CONCLUDE",
            "GIVEN A OR B GIVEN NOT A DERIVE B APPLY OR_ELIM A OR B, NOT A CONCLUDE",
            "GIVEN A OR B GIVEN NOT B DERIVE A APPLY OR_ELIM NOT B, A OR B CONCLUDE",
            "GIVEN A IMP B GIVEN A DERIVE B APPLY IMP_ELIM A IMP B, A CONCLUDE",
            "GIVEN A IMP B GIVEN A DERIVE B APPLY IMP_ELIM A, A IMP B CONCLUDE",
            "DERIVE A IMP A ASSUME A END APPLY IMP_INTRO A, A CONCLUDE",
            "GIVEN B DERIVE A IMP B APPLY IMP_INTRO A, B CONCLUDE",
            "GIVEN NOT A DERIVE NOT A ASSUME A APPLY NOT_ELIM A, NOT A END "
            "APPLY NOT_INTRO A CONCLUDE",
            "GIVEN A GIVEN NOT A DERIVE FALSE APPLY NOT_ELIM A, NOT A CONCLUDE",
            "GIVEN NOT NOT A DERIVE A APPLY DNE NOT NOT A CONCLUDE",
            "GIVEN FALSE DERIVE A APPLY EXPLOSION FALSE, A CONCLUDE",
            "GIVEN A DERIVE A APPLY REITERATE A CONCLUDE",
            "GIVEN A OR B GIVEN A IMP C GIVEN B IMP C DERIVE C "
            "ASSUME A APPLY IMP_ELIM A IMP C, A END "
            "ASSUME B APPLY IMP_ELIM B IMP C, B END APPLY OR_CASES A OR B, C CONCLUDE",
        ]
        for source in examples:
            with self.subTest(source=source):
                self.assertValid(source)

    def test_nested_formula_rules(self):
        self.assertValid(
            "GIVEN A AND B GIVEN C OR D DERIVE (A AND B) AND (C OR D) "
            "APPLY AND_INTRO A AND B, C OR D CONCLUDE"
        )
        self.assertValid(
            "DERIVE (A AND B) IMP A ASSUME A AND B "
            "APPLY AND_ELIM A AND B, A END APPLY IMP_INTRO A AND B, A CONCLUDE"
        )

    def test_negation_of_compound(self):
        self.assertValid(
            "GIVEN NOT (A AND B) DERIVE NOT (A AND B) ASSUME A AND B "
            "APPLY NOT_ELIM A AND B, NOT (A AND B) END "
            "APPLY NOT_INTRO A AND B CONCLUDE"
        )

    def test_negation_introduction_retains_double_negation(self):
        self.assertValid(
            "GIVEN A DERIVE NOT NOT A ASSUME NOT A "
            "APPLY NOT_ELIM A, NOT A END APPLY NOT_INTRO NOT A CONCLUDE"
        )

    def test_each_rule_rejects_bad_shape_or_missing_evidence(self):
        cases = [
            ("A", "AND_INTRO A, B"),
            ("A", "AND_ELIM A, B"),
            ("A", "AND_ELIM A AND B, C"),
            ("A", "OR_INTRO B, C"),
            ("A", "OR_ELIM A OR B, A"),
            ("A", "IMP_ELIM A IMP B, B"),
            ("A", "NOT_ELIM A, B"),
            ("A", "DNE A"),
            ("A", "EXPLOSION A, B"),
            ("A", "REITERATE B"),
            ("A", "OR_CASES A, B"),
            ("A", "OR_CASES A OR B, C"),
            ("A", "NOT_INTRO A"),
            ("A", "IMP_INTRO A, B"),
        ]
        for premise, application in cases:
            with self.subTest(rule=application):
                result = verify(f"GIVEN {premise} DERIVE A APPLY {application} CONCLUDE")
                self.assertFalse(result.valid)
                self.assertTrue(result.syntax_valid)

    def test_no_implicit_commutativity(self):
        result = verify("GIVEN A AND B DERIVE B AND A CONCLUDE")
        self.assertFalse(result.valid)
        self.assertEqual(result.diagnostics[0].code, "E_GOAL")

    def test_no_implicit_double_negation(self):
        self.assertFalse(verify("GIVEN NOT NOT A DERIVE A CONCLUDE").valid)

    def test_examples(self):
        for path in files("proofscope").joinpath("examples").iterdir():
            if path.name.endswith(".proof"):
                with self.subTest(example=path.name):
                    source = path.read_text("utf-8")
                    if "invalid" in path.name:
                        self.assertFalse(verify(source).valid)
                    else:
                        self.assertValid(source)

    def test_trace_dependencies_refer_to_earlier_events(self):
        source = (
            files("proofscope").joinpath("examples", "02-contraposition.proof").read_text("utf-8")
        )
        result = self.assertValid(source)
        for event in result.trace:
            self.assertTrue(all(0 < dependency < event.id for dependency in event.dependencies))
        self.assertEqual(result.statistics["max_depth"], 2)
        self.assertEqual(result.trace[-1].kind, "CONCLUDE")

    def test_no_state_between_verifications(self):
        self.assertTrue(verify("GIVEN A DERIVE A CONCLUDE").valid)
        self.assertFalse(verify("DERIVE A CONCLUDE").valid)

    def test_concurrent_verifications_are_isolated(self):
        sources = ["GIVEN A DERIVE A CONCLUDE", "DERIVE A CONCLUDE"] * 50
        with ThreadPoolExecutor(max_workers=8) as executor:
            actual = list(executor.map(lambda source: verify(source).valid, sources))
        self.assertEqual(actual, [True, False] * 50)

    def test_syntax_failure_has_no_misleading_trace(self):
        result = verify("GIVEN A DERIVE A CONCLUDE GIVEN B")
        self.assertFalse(result.valid)
        self.assertFalse(result.syntax_valid)
        self.assertEqual(result.trace, ())


class ScopeRegressionTests(unittest.TestCase):
    def assertRejected(self, source, code):
        result = verify(source)
        self.assertFalse(result.valid)
        self.assertEqual(result.diagnostics[0].code, code, result.to_dict())

    def test_nested_assumption_cannot_escape_through_implication(self):
        self.assertRejected(
            "DERIVE A IMP B ASSUME A ASSUME B END END APPLY IMP_INTRO A, B CONCLUDE", "E_DISCHARGE"
        )

    def test_closed_assumption_is_not_available(self):
        self.assertRejected("DERIVE A ASSUME A END APPLY REITERATE A CONCLUDE", "E_UNAVAILABLE")

    def test_goal_must_be_global(self):
        self.assertRejected("DERIVE A ASSUME A END CONCLUDE", "E_GOAL")

    def test_repeated_assumption_does_not_inherit_sibling_facts(self):
        self.assertRejected(
            "DERIVE A IMP (A OR B) "
            "ASSUME A APPLY OR_INTRO A, B END "
            "ASSUME A APPLY REITERATE A OR B END "
            "APPLY IMP_INTRO A, A OR B CONCLUDE",
            "E_UNAVAILABLE",
        )

    def test_negation_cannot_discharge_a_descendant(self):
        self.assertRejected(
            "GIVEN NOT B DERIVE NOT A "
            "ASSUME A ASSUME B APPLY NOT_ELIM B, NOT B END END "
            "APPLY NOT_INTRO A CONCLUDE",
            "E_DISCHARGE",
        )

    def test_subproof_cannot_be_reused_from_an_unrelated_parent(self):
        self.assertRejected(
            "DERIVE A IMP B ASSUME C ASSUME A ASSUME B END END END APPLY IMP_INTRO A, B CONCLUDE",
            "E_DISCHARGE",
        )

    def test_cases_require_both_branches(self):
        self.assertRejected(
            "GIVEN A OR B GIVEN A IMP C DERIVE C "
            "ASSUME A APPLY IMP_ELIM A IMP C, A END "
            "APPLY OR_CASES A OR B, C CONCLUDE",
            "E_DISCHARGE",
        )

    def test_closed_subproof_records_facts_at_close_time(self):
        source = "GIVEN A DERIVE A IMP (A OR B) ASSUME A END "
        result = verify(source + "APPLY IMP_INTRO A, A OR B CONCLUDE")
        self.assertFalse(result.valid)

    def test_parent_evidence_can_be_used_in_nested_scope(self):
        source = "GIVEN B DERIVE A IMP (C IMP B) ASSUME A ASSUME C "
        source += "APPLY REITERATE B END APPLY IMP_INTRO C, B END "
        source += "APPLY IMP_INTRO A, C IMP B CONCLUDE"
        self.assertTrue(verify(source).valid)


class FiniteSoundnessTests(unittest.TestCase):
    """Finite semantic cross-checks are regression evidence, not a soundness proof."""

    def test_rule_instances_against_truth_assignments(self):
        formulas = ["A", "B", "NOT A", "NOT B", "A AND B", "A OR B", "A IMP B", "FALSE"]
        for a in formulas:
            for b in formulas:
                cases = [
                    ([a, b], f"({a}) AND ({b})", f"AND_INTRO {a}, {b}"),
                    ([a], f"({a}) OR ({b})", f"OR_INTRO {a}, {b}"),
                    ([f"({a}) AND ({b})"], a, f"AND_ELIM ({a}) AND ({b}), {a}"),
                    ([a, f"({a}) IMP ({b})"], b, f"IMP_ELIM ({a}) IMP ({b}), {a}"),
                    ([f"({a}) OR ({b})", f"NOT ({a})"], b, f"OR_ELIM ({a}) OR ({b}), NOT ({a})"),
                    ([a, f"NOT ({a})"], "FALSE", f"NOT_ELIM {a}, NOT ({a})"),
                    ([b], f"({a}) IMP ({b})", f"IMP_INTRO {a}, {b}"),
                    ([f"NOT NOT ({a})"], a, f"DNE NOT NOT ({a})"),
                    (["FALSE"], b, f"EXPLOSION FALSE, {b}"),
                ]
                for premises, goal, step in cases:
                    source = "\n".join(
                        [
                            *(f"GIVEN {f}" for f in premises),
                            f"DERIVE {goal}",
                            f"APPLY {step}",
                            "CONCLUDE",
                        ]
                    )
                    with self.subTest(a=a, b=b, step=step):
                        self.assertTrue(verify(source).valid, source)
                        self.assertTrue(analyze(premises, goal)["entailed"], source)


if __name__ == "__main__":
    unittest.main()
