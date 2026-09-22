import unittest

from proofscope import analyze, parse_formula
from proofscope.formula import evaluate


class SemanticsTests(unittest.TestCase):
    def test_tautology(self):
        result = analyze([], "A OR NOT A")
        self.assertTrue(result["entailed"])
        self.assertEqual(result["assignments_checked"], 2)
        self.assertFalse(result["vacuous"])

    def test_countermodel(self):
        result = analyze(["A IMP B", "B"], "A")
        self.assertFalse(result["entailed"])
        self.assertEqual(result["countermodel"], {"A": False, "B": True})

    def test_constant_countermodel(self):
        result = analyze([], "FALSE")
        self.assertEqual(result["countermodel"], {})
        self.assertEqual(result["assignments_checked"], 1)
        self.assertFalse(result["entailed"])

    def test_inconsistent_premises_are_explicit(self):
        result = analyze(["A", "NOT A"], "B")
        self.assertTrue(result["entailed"])
        self.assertTrue(result["vacuous"])
        self.assertEqual(result["premise_models"], 0)

    def test_limit_is_not_a_verdict(self):
        result = analyze([], "A AND B", max_atoms=1)
        self.assertEqual(result["status"], "limit")
        self.assertIsNone(result["entailed"])
        self.assertEqual(result["assignments_checked"], 0)

    def test_table_limit_does_not_limit_search(self):
        result = analyze(["A"], "A", table_limit=1)
        self.assertTrue(result["entailed"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["assignments_checked"], 2)
        self.assertTrue(result["table_truncated"])

    def test_limit_arguments(self):
        for kwargs in ({"max_atoms": 17}, {"max_atoms": -1}, {"table_limit": 257}):
            with self.assertRaises(ValueError):
                analyze([], "A", **kwargs)

    def test_truth_functions(self):
        expected = {
            "A AND B": [False, False, False, True],
            "A OR B": [False, True, True, True],
            "A IMP B": [True, True, False, True],
            "NOT A": [True, True, False, False],
        }
        values = [(False, False), (False, True), (True, False), (True, True)]
        for formula, outputs in expected.items():
            with self.subTest(formula=formula):
                actual = [evaluate(parse_formula(formula), {"A": a, "B": b}) for a, b in values]
                self.assertEqual(actual, outputs)

    def test_formula_objects_and_generators(self):
        self.assertTrue(analyze((parse_formula(f) for f in ["A"]), parse_formula("A"))["entailed"])


if __name__ == "__main__":
    unittest.main()
