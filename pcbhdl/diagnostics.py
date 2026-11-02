"""Compiler diagnostics: errors, warnings and notes with source locations.

Diagnostics are collected rather than raised so that one run of the compiler
reports as many problems as possible. They can be rendered for humans
(gcc/rustc style, with the offending source line and a caret) or as JSON for
tools and AI agents.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True)
class Loc:
    """A source location. Lines and columns are 1-based."""
    file: str
    line: int
    col: int
    length: int = 1

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.col}"


@dataclass
class Diagnostic:
    severity: Severity
    code: str
    message: str
    loc: Loc | None = None
    notes: list[tuple[str, Loc | None]] = field(default_factory=list)
    hint: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"severity": self.severity.value, "code": self.code, "message": self.message}
        if self.loc:
            d["file"], d["line"], d["column"] = self.loc.file, self.loc.line, self.loc.col
        if self.hint:
            d["hint"] = self.hint
        if self.notes:
            d["notes"] = [{"message": m, **({"file": l.file, "line": l.line, "column": l.col} if l else {})}
                          for m, l in self.notes]
        return d


class CompileError(Exception):
    """Raised to abort compilation after errors have been reported."""


class Reporter:
    """Collects diagnostics and renders them."""

    def __init__(self, sources: dict[str, str] | None = None):
        self.diagnostics: list[Diagnostic] = []
        self._seen: set[tuple] = set()
        self.sources: dict[str, list[str]] = {}
        for name, text in (sources or {}).items():
            self.add_source(name, text)

    def add_source(self, name: str, text: str) -> None:
        self.sources[name] = text.splitlines()

    def report(self, severity: Severity, code: str, message: str, loc: Loc | None = None,
               hint: str | None = None, notes: Iterable[tuple[str, Loc | None]] = ()) -> Diagnostic:
        d = Diagnostic(severity, code, message, loc, list(notes), hint)
        # A sub-design is elaborated once per instance; report each problem once.
        key = (severity, code, message, loc)
        if key not in self._seen:
            self._seen.add(key)
            self.diagnostics.append(d)
        return d

    def error(self, code: str, message: str, loc: Loc | None = None, **kw) -> Diagnostic:
        return self.report(Severity.ERROR, code, message, loc, **kw)

    def warning(self, code: str, message: str, loc: Loc | None = None, **kw) -> Diagnostic:
        return self.report(Severity.WARNING, code, message, loc, **kw)

    @property
    def error_count(self) -> int:
        return sum(d.severity is Severity.ERROR for d in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(d.severity is Severity.WARNING for d in self.diagnostics)

    def check(self) -> None:
        """Abort if any errors have been reported."""
        if self.error_count:
            raise CompileError(f"{self.error_count} error(s)")

    def sorted(self) -> list[Diagnostic]:
        def key(d: Diagnostic):
            l = d.loc
            return (l.file, l.line, l.col) if l else ("", 0, 0)
        return sorted(self.diagnostics, key=key)

    # -- rendering -----------------------------------------------------------

    def render_text(self, color: bool = False) -> str:
        out = []
        for d in self.sorted():
            out.append(self._render_one(d, color))
        return "\n".join(out)

    def render_json(self) -> str:
        return json.dumps({"errors": self.error_count, "warnings": self.warning_count,
                           "diagnostics": [d.to_dict() for d in self.sorted()]}, indent=2)

    def _render_one(self, d: Diagnostic, color: bool) -> str:
        def c(code: str, s: str) -> str:
            return f"\x1b[{code}m{s}\x1b[0m" if color else s
        sev_color = {"error": "1;31", "warning": "1;33", "note": "1;36"}[d.severity.value]
        head = f"{d.loc}: " if d.loc else ""
        lines = [f"{c('1', head)}{c(sev_color, f'{d.severity.value}[{d.code}]')}: {c('1', d.message)}"]
        lines += self._snippet(d.loc, color)
        for msg, loc in d.notes:
            lines.append(f"{loc}: {c('1;36', 'note')}: {msg}" if loc else f"  {c('1;36', 'note')}: {msg}")
            lines += self._snippet(loc, color)
        if d.hint:
            lines.append(f"  {c('1;32', 'hint')}: {d.hint}")
        return "\n".join(lines)

    def _snippet(self, loc: Loc | None, color: bool) -> list[str]:
        if not loc or loc.file not in self.sources:
            return []
        src = self.sources[loc.file]
        if not 1 <= loc.line <= len(src):
            return []
        text = src[loc.line - 1].expandtabs(4)
        # Recompute the column after tab expansion.
        raw = src[loc.line - 1]
        col = len(raw[: loc.col - 1].expandtabs(4)) + 1
        gutter = f"{loc.line:>5} | "
        caret = " " * (col - 1) + "^" * max(1, loc.length)
        if color:
            caret = f"\x1b[1;32m{caret}\x1b[0m"
        return [gutter + text, " " * (len(gutter) - 2) + "| " + caret]
