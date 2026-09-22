"""Public, side-effect-free API for ProofScope."""

from .parser import parse_formula, parse_proof
from .semantics import analyze
from .verifier import VerificationResult, verify

__all__ = ["VerificationResult", "analyze", "parse_formula", "parse_proof", "verify"]
__version__ = "1.0.0"
