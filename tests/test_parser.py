import unittest

from proofscope import parse_formula, parse_proof
from proofscope.diagnostics import ProofError
from proofscope.formula import FALSE, Atom, Binary, Not
from proofscope.lexer import lex


class FormulaTests(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(
            parse_formula("A OR B AND NOT C -> D"),
            Binary(
                "IMP", Binary("OR", Atom("A"), Binary("AND", Atom("B"), Not(Atom("C")))), Atom("D")
            ),
        )

    def test_right_associative_implication(self):
        self.assertEqual(parse_formula("A -> B -> C"), parse_formula("A -> (B -> C)"))
        self.assertNotEqual(parse_formula("A -> B -> C"), parse_formula("(A -> B) -> C"))

    def test_left_associative_conjunction(self):
        self.assertEqual(parse_formula("A AND B AND C"), parse_formula("(A AND B) AND C"))

    def test_aliases_without_spaces(self):
        for spelling in ("!(A&&B)||C->D", "¬(A∧B)∨C→D", "NOT (A AND B) OR C IMP D"):
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    parse_formula(spelling), parse_formula("(NOT (A AND B) OR C) IMP D")
                )
        self.assertEqual(parse_formula("⊥"), FALSE)

    def test_double_negation_is_not_simplified(self):
        self.assertEqual(parse_formula("NOT NOT A"), Not(Not(Atom("A"))))
        self.assertNotEqual(parse_formula("A"), parse_formula("NOT NOT A"))

    def test_structural_equality(self):
        self.assertNotEqual(parse_formula("A AND B"), parse_formula("B AND A"))
        self.assertEqual(len({parse_formula("A && B"), parse_formula("A AND B")}), 1)

    def test_keyword_prefixes_are_identifiers(self):
        self.assertEqual(parse_formula("ANDROID"), Atom("ANDROID"))
        self.assertEqual(parse_formula("GIVEN_name"), Atom("GIVEN_name"))

    def test_comments_preserve_locations(self):
        tokens = lex("# header\r\n### two\r\nlines ###\r\n  GIVEN A")
        self.assertEqual((tokens[0].span.line, tokens[0].span.column), (4, 3))

    def test_malformed_formulas(self):
        for source in ("", "A B", "(A", "A)", "A AND", "NOT", "A & B", "A @ B", "1A"):
            with self.subTest(source=source), self.assertRaises(ProofError):
                parse_formula(source)

    def test_unclosed_block_comment(self):
        with self.assertRaises(ProofError) as context:
            lex("\n### unclosed")
        self.assertEqual(context.exception.diagnostic.line, 2)

    def test_resource_limits(self):
        for source in (
            "NOT " * 100 + "A",
            "(" * 100 + "A" + ")" * 100,
            " AND ".join(["A"] * 300),
            "A" * 65537,
        ):
            with self.subTest(size=len(source)), self.assertRaises(ProofError) as context:
                parse_formula(source)
            self.assertEqual(context.exception.diagnostic.code, "E_LIMIT")

    def test_roundtrip_generated_trees(self):
        trees = [Atom("A"), Atom("B"), FALSE]
        for _ in range(3):
            previous = trees[-12:]
            trees.extend(Not(f) for f in previous)
            trees.extend(
                Binary(op, a, b)
                for op in ("AND", "OR", "IMP")
                for a in previous[:4]
                for b in previous[:4]
            )
        for tree in trees:
            with self.subTest(formula=str(tree)):
                self.assertEqual(parse_formula(str(tree)), tree)


class ProofParserTests(unittest.TestCase):
    def test_compact_proof(self):
        proof = parse_proof("GIVEN A DERIVE A CONCLUDE")
        self.assertEqual(proof.premises, (Atom("A"),))
        self.assertEqual(proof.goal, Atom("A"))

    def test_structure_rejections(self):
        for source in (
            "",
            "CONCLUDE",
            "GIVEN A CONCLUDE",
            "DERIVE A",
            "DERIVE A END CONCLUDE",
            "DERIVE A ASSUME A CONCLUDE",
            "DERIVE A CONCLUDE GIVEN B",
            "DERIVE A DERIVE B CONCLUDE",
            "DERIVE A GIVEN A CONCLUDE",
            "DERIVE A APPLY AND_INTRO A CONCLUDE",
            "DERIVE A APPLY REITERATE A, A CONCLUDE",
        ):
            with self.subTest(source=source), self.assertRaises(ProofError):
                parse_proof(source)

    def test_unknown_rule(self):
        with self.assertRaises(ProofError) as context:
            parse_proof("DERIVE A APPLY MAGIC A CONCLUDE")
        self.assertEqual(context.exception.diagnostic.code, "E_RULE")

    def test_scope_depth_limit(self):
        source = "DERIVE A\n" + "ASSUME A\n" * 65 + "END\n" * 65 + "CONCLUDE"
        with self.assertRaises(ProofError) as context:
            parse_proof(source)
        self.assertEqual(context.exception.diagnostic.code, "E_LIMIT")

    def test_token_limit(self):
        with self.assertRaises(ProofError) as context:
            lex("A " * 16385)
        self.assertEqual(context.exception.diagnostic.code, "E_LIMIT")


if __name__ == "__main__":
    unittest.main()
