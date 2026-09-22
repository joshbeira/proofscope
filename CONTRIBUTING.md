# Contributing

Use Python 3.11+, create a virtual environment, and install with
`python -m pip install -e ".[dev]"`.

Before opening a change:

```bash
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
python -m build
```

Keep the runtime dependency-free. Changes to inference behavior need a successful proof,
a rejected misuse, and a semantic cross-check when the formulas fit the bounded checker.
Scope changes need regression tests for nested assumptions and discharge into the wrong parent.

Keep rule arities in `rules.py`, rule behavior in `verifier.py`, and the rule reference in
`docs/language.md` and the explorer consistent. Keep diagnostics structured; interfaces should
format results without adding inference behavior.

For browser changes, check keyboard navigation, a narrow viewport, an invalid proof, a syntax
error, and a countermodel. New assets belong in the package so installed wheels work without
the repository checkout.

Describe the problem, behavior change, and validation in a pull request. Report bugs with the
smallest proof that reproduces the issue and the output of `proofscope --version`.
