"""Command-line interface and stable machine-readable output."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .diagnostics import ProofError, render_diagnostic
from .parser import parse_proof
from .rules import RULES
from .semantics import analyze
from .verifier import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proofscope", description="Make every inference explicit."
    )
    parser.add_argument("--version", action="version", version=f"ProofScope {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Verify proof files, or '-' for standard input.")
    check.add_argument("files", nargs="+")
    check.add_argument("--json", action="store_true", help="Emit a JSON array of results.")
    check.add_argument("--trace", action="store_true", help="Show each verified inference.")
    check.add_argument("--semantic", action="store_true", help="Also test classical entailment.")
    model = commands.add_parser("entails", help="Check a sequent and find countermodels.")
    model.add_argument("goal")
    model.add_argument("--given", action="append", default=[])
    model.add_argument("--json", action="store_true")
    model.add_argument("--max-atoms", type=int, choices=range(0, 17), default=12)
    commands.add_parser("rules", help="List inference rules and argument counts.")
    serve = commands.add_parser("serve", help="Start the local interactive proof explorer.")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="Open the explorer in your browser.")
    options = parser.parse_args(argv)

    if options.command == "rules":
        for name, (arity, description) in RULES.items():
            print(f"{name:12} {arity}  {description}")
        return 0
    if options.command == "serve":
        from .server import serve

        try:
            serve(options.port, open_browser=options.open)
            return 0
        except (OSError, ValueError) as error:
            print(f"proofscope: {error}", file=sys.stderr)
            return 2
    if options.command == "entails":
        try:
            result = analyze(options.given, options.goal, max_atoms=options.max_atoms)
        except ProofError as error:
            if options.json:
                print(json.dumps({"status": "error", "diagnostic": error.diagnostic.to_dict()}))
            else:
                print(f"{error.diagnostic.code}: {error}", file=sys.stderr)
            return 2
        if options.json:
            print(json.dumps(result, indent=2))
        elif result["status"] == "limit":
            print(f"LIMIT: {result['message']}")
        elif result["entailed"]:
            suffix = " (inconsistent premises; vacuous entailment)" if result["vacuous"] else ""
            print(f"ENTAILED: {result['goal']}{suffix}")
        else:
            print(
                "COUNTERMODEL: "
                + ", ".join(f"{k}={str(v).lower()}" for k, v in result["countermodel"].items())
            )
        return 2 if result["status"] == "limit" else int(not result["entailed"])

    output, exit_code = [], 0
    for filename in options.files:
        try:
            source = sys.stdin.read() if filename == "-" else Path(filename).read_text("utf-8-sig")
        except (OSError, UnicodeError) as error:
            output.append({"file": filename, "valid": False, "error": str(error)})
            if not options.json:
                print(f"{filename}: {error}", file=sys.stderr)
            exit_code = 2
            continue
        result = verify(source)
        item = {"file": filename, **result.to_dict()}
        if options.semantic and result.syntax_valid:
            proof = parse_proof(source)
            item["semantics"] = analyze(proof.premises, proof.goal)
        output.append(item)
        exit_code = max(exit_code, 0 if result.valid else 1)
        if not options.json:
            print(
                f"{'VALID' if result.valid else 'INVALID'} {filename}"
                f" | {result.statistics['inferences']} inferences | goal: {result.goal or '-'}"
            )
            if options.trace:
                for event in result.trace:
                    refs = ",".join(str(i) for i in event.dependencies) or "-"
                    print(
                        f"  {event.id:>3} {'  ' * event.depth}{event.rule or event.kind:12} "
                        f"{event.formula or ''}  [from {refs}]"
                    )
            for diagnostic in result.diagnostics:
                print(render_diagnostic(diagnostic, source, filename))
            if "semantics" in item:
                semantics = item["semantics"]
                print(
                    f"  Semantics: {semantics['status']}"
                    f" ({semantics['assignments_checked']} assignments checked)"
                )
    if options.json:
        print(json.dumps(output, indent=2))
    return exit_code
