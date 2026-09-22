"""Stable diagnostic codes and source locations shared by every interface."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Span:
    line: int = 1
    column: int = 1


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    line: int
    column: int
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ProofError(ValueError):
    def __init__(self, code: str, message: str, span: Span, hint: str = ""):
        self.diagnostic = Diagnostic(code, message, span.line, span.column, hint)
        super().__init__(message)


def render_diagnostic(diagnostic: Diagnostic, source: str, filename: str = "<input>") -> str:
    lines = source.splitlines()
    excerpt = lines[diagnostic.line - 1] if diagnostic.line <= len(lines) else ""
    location = f"{filename}:{diagnostic.line}:{diagnostic.column}"
    result = f"{location}: {diagnostic.code}: {diagnostic.message}"
    if excerpt:
        result += f"\n  {excerpt}\n  {' ' * (diagnostic.column - 1)}^"
    if diagnostic.hint:
        result += f"\n  Hint: {diagnostic.hint}"
    return result
