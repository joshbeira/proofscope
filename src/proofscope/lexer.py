"""A location-preserving lexer with word, ASCII, and Unicode operators."""

import re
from dataclasses import dataclass

from .diagnostics import ProofError, Span

MAX_SOURCE_CHARS = 65_536
MAX_TOKENS = 16_384
KEYWORDS = {
    "GIVEN",
    "DERIVE",
    "ASSUME",
    "END",
    "APPLY",
    "CONCLUDE",
    "AND",
    "OR",
    "IMP",
    "NOT",
    "FALSE",
}
ALIASES = {
    "&&": "AND",
    "∧": "AND",
    "||": "OR",
    "∨": "OR",
    "->": "IMP",
    "→": "IMP",
    "!": "NOT",
    "¬": "NOT",
    "⊥": "FALSE",
}
PATTERN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|&&|\|\||->|[∧∨→!¬⊥(),]")


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    text: str
    span: Span


def lex(source: str) -> list[Token]:
    if len(source) > MAX_SOURCE_CHARS:
        raise ProofError("E_LIMIT", "Source exceeds 65,536 characters.", Span())
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    tokens: list[Token] = []
    pos, line, column = 0, 1, 1

    def advance(text: str) -> None:
        nonlocal pos, line, column
        pos += len(text)
        if "\n" in text:
            line += text.count("\n")
            column = len(text.rsplit("\n", 1)[-1]) + 1
        else:
            column += len(text)

    while pos < len(source):
        span = Span(line, column)
        if source.startswith("###", pos):
            end = source.find("###", pos + 3)
            if end == -1:
                raise ProofError("E_LEX", "Unclosed block comment.", span, "Close it with ###.")
            advance(source[pos : end + 3])
        elif source[pos] == "#":
            end = source.find("\n", pos)
            advance(source[pos : end if end != -1 else len(source)])
        elif source[pos].isspace():
            advance(source[pos])
        else:
            match = PATTERN.match(source, pos)
            if match is None:
                raise ProofError("E_LEX", f"Unexpected character {source[pos]!r}.", span)
            text = match.group()
            kind = ALIASES.get(text, text if text in KEYWORDS or text in "()," else "ID")
            tokens.append(Token(kind, text, span))
            advance(text)
            if len(tokens) > MAX_TOKENS:
                raise ProofError("E_LIMIT", "Source has too many tokens.", span)
    tokens.append(Token("EOF", "end of input", Span(line, column)))
    return tokens
