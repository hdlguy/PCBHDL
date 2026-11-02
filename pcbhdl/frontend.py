"""Parse PHDL source text into the AST in :mod:`pcbhdl.ast`."""
from __future__ import annotations

import re
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream, Token
from antlr4.error.ErrorListener import ErrorListener

from . import ast
from ._generated.PhdlLexer import PhdlLexer
from ._generated.PhdlParser import PhdlParser
from ._generated.PhdlVisitor import PhdlVisitor
from .diagnostics import Loc, Reporter


# ---------------------------------------------------------------------------
# Syntax errors
# ---------------------------------------------------------------------------

def _describe_token(tok: Token) -> str:
    if tok.type == Token.EOF:
        return "end of file"
    return repr(tok.text)


class _SyntaxErrorListener(ErrorListener):
    """Turns ANTLR's error callbacks into PHDL diagnostics."""

    def __init__(self, path: str, reporter: Reporter):
        self.path = path
        self.reporter = reporter

    def syntaxError(self, recognizer, offending, line, column, msg, e):
        length = 1
        if isinstance(offending, Token) and offending.type != Token.EOF and offending.text:
            length = len(offending.text)
        loc = Loc(self.path, line, column + 1, length)
        if isinstance(offending, Token) and offending.type == PhdlLexer.ERROR_CHAR:
            self.reporter.error("E0001", f"invalid character {offending.text!r}", loc)
            return
        message, hint = self._rewrite(msg, offending)
        if msg.startswith("missing ';'") and isinstance(offending, Token):
            prev = self._previous_visible(recognizer, offending)
            if prev is not None:
                # Point just past the token the ';' should follow.
                end_col = prev.column + len(prev.text) + 1
                loc = Loc(self.path, prev.line, end_col, 1)
                message = f"expected ';' after {prev.text!r}"
        self.reporter.error("E0001", message, loc, hint=hint)

    @staticmethod
    def _previous_visible(recognizer, tok: Token) -> Token | None:
        stream = recognizer.getTokenStream()
        i = tok.tokenIndex - 1
        while i >= 0:
            t = stream.get(i)
            if t.channel == Token.DEFAULT_CHANNEL:
                return t
            i -= 1
        return None

    @staticmethod
    def _rewrite(msg: str, offending) -> tuple[str, str | None]:
        """Make ANTLR's messages read like a compiler's."""
        def expected(s: str) -> str:
            items = [t.strip() for t in s.strip("{}").split(",")]
            items = [t.replace("<EOF>", "end of file") for t in items]
            return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]

        if m := re.match(r"token recognition error at: '(.*)'", msg, re.S):
            return f"invalid character {m.group(1)!r}", None
        if m := re.match(r"missing (.+) at (.+)", msg):
            what = m.group(1)
            hint = "the previous statement may be missing its terminating ';'" if what == "';'" else None
            return f"expected {what} before {m.group(2)}", hint
        if m := re.match(r"mismatched input (.+) expecting (.+)", msg, re.S):
            exp = m.group(2)
            hint = "the previous statement may be missing its terminating ';'" if "';'" in exp else None
            return f"unexpected {m.group(1)}; expected {expected(exp)}", hint
        if m := re.match(r"extraneous input (.+) expecting (.+)", msg, re.S):
            return f"unexpected {m.group(1)}; expected {expected(m.group(2))}", None
        if m := re.match(r"no viable alternative at input (.+)", msg, re.S):
            tok = _describe_token(offending) if isinstance(offending, Token) else m.group(1)
            return f"syntax error at {tok}", None
        return msg, None


# ---------------------------------------------------------------------------
# Parse tree -> AST
# ---------------------------------------------------------------------------

_ESCAPES = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "'": "'", "\\": "\\"}


def _unquote(text: str) -> str:
    body = text[1:-1]
    if "\\" not in body:
        return body
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", body[i + 2:i + 6]):
                out.append(chr(int(body[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


class _AstBuilder(PhdlVisitor):
    def __init__(self, path: str):
        self.path = path

    # -- helpers -------------------------------------------------------------

    def tloc(self, tok: Token) -> Loc:
        return Loc(self.path, tok.line, tok.column + 1, max(1, len(tok.text or "")))

    def cloc(self, ctx) -> Loc:
        start, stop = ctx.start, ctx.stop
        length = 1
        if stop is not None and stop.line == start.line:
            length = max(1, stop.stop - start.start + 1)
        return Loc(self.path, start.line, start.column + 1, length)

    def range_(self, ctx) -> ast.Range | None:
        if ctx is None:
            return None
        return ast.Range(int(ctx.msb.text), int(ctx.lsb.text), self.cloc(ctx))

    def selection(self, ctx) -> ast.Selection | None:
        if ctx is None:
            return None
        if isinstance(ctx, (PhdlParser.SliceRangeContext, PhdlParser.IndexRangeContext)):
            r = ast.Range(int(ctx.msb.text), int(ctx.lsb.text), self.cloc(ctx))
            return ast.Selection(r.indices(), True, self.cloc(ctx))
        return ast.Selection([int(t.getText()) for t in ctx.INT()], False, self.cloc(ctx))

    def qualifier(self, ctx) -> ast.Qualifier | None:
        if ctx is None:
            return None
        return ast.Qualifier(self.selection(ctx.indices()), self.cloc(ctx))

    def qname(self, ctx) -> list[str]:
        return [p.getText() for p in ctx.phdlId()]

    def attr(self, ctx, deprecated=False) -> ast.Attr:
        return ast.Attr(ctx.name.text, _unquote(ctx.value.text), self.tloc(ctx.name), deprecated)

    def info(self, ctx) -> ast.Info:
        return ast.Info(_unquote(ctx.value.text), self.cloc(ctx))

    # -- top level -----------------------------------------------------------

    def build(self, ctx: PhdlParser.ModelContext) -> ast.SourceFile:
        imports = [self.import_(c) for c in ctx.importDecl()]
        packages = [self.package(c) for c in ctx.packageDecl()]
        devices = [self.device(c, None) for c in ctx.device()]
        designs = [self.design(c, None) for c in ctx.design()]
        return ast.SourceFile(self.path, imports, packages, devices, designs)

    def import_(self, ctx) -> ast.Import:
        return ast.Import(self.qname(ctx.qualifiedName()), ctx.wildcard is not None, self.cloc(ctx))

    def package(self, ctx) -> ast.Package:
        name = ctx.name.text
        return ast.Package(name, [self.import_(c) for c in ctx.importDecl()],
                           [self.device(c, name) for c in ctx.device()],
                           [self.design(c, name) for c in ctx.design()], self.tloc(ctx.name))

    # -- devices -------------------------------------------------------------

    def device(self, ctx, package: str | None) -> ast.Device:
        attrs, pins, infos = [], [], []
        for el in ctx.deviceElement():
            if el.attr():
                attrs.append(self.attr(el.attr()))
            elif el.pinDecl():
                p = el.pinDecl()
                ids = p.phdlId()  # first is the pin name, the rest are physical pins
                numbers = [i.getText() for i in ids[1:]]
                nloc = self.cloc(ids[1]) if len(ids) > 1 else None
                pins.append(ast.PinDecl(p.pinType().getText(), self.range_(p.vector()),
                                        p.name.getText(), numbers, self.cloc(p.name), nloc))
            else:
                infos.append(self.info(el.info()))
        return ast.Device(ctx.name.getText(), attrs, pins, infos, self.cloc(ctx.name), package, self.path)

    # -- designs -------------------------------------------------------------

    def design(self, ctx, package: str | None) -> ast.Design:
        d = ast.Design(ctx.name.text, ctx.kind.text == "subdesign", loc=self.tloc(ctx.name),
                       package=package, file=self.path)
        for el in ctx.designElement():
            if c := el.connectionDecl():
                node = self.connection_decl(c)
                d.connections.append(node)
            elif c := el.instance():
                node = self.instance(c)
                d.instances.append(node)
            elif c := el.connectionAssign():
                node = ast.Assign(c.phdlId().getText(), self.selection(c.slices()),
                                  self.concat(c.concatenation()), self.cloc(c.phdlId()))
                d.assigns.append(node)
            else:
                node = self.info(el.info())
                d.infos.append(node)
            d.elements.append(node)
        return d

    def connection_decl(self, ctx) -> ast.ConnectionDecl:
        names = [(i.getText(), self.cloc(i)) for i in ctx.phdlId()]
        return ast.ConnectionDecl(ctx.kind.text, self.range_(ctx.vector()), names,
                                  [self.attr(a) for a in ctx.attr()],
                                  [self.info(i) for i in ctx.info()], self.tloc(ctx.kind))

    def instance(self, ctx):
        common = dict(name=ctx.name.text, array=self.range_(ctx.array()),
                      ref=self.qname(ctx.ref), loc=self.tloc(ctx.name), ref_loc=self.cloc(ctx.ref))
        if isinstance(ctx, PhdlParser.DeviceInstanceContext):
            inst = ast.DeviceInstance(**common)
            for el in ctx.instanceElement():
                if el.attr():
                    inst.attrs.append(self.attr(el.attr()))
                elif el.newAttr():
                    inst.attrs.append(self.attr(el.newAttr(), deprecated=True))
                elif c := el.refAttr():
                    inst.ref_attrs.append(ast.RefAttr(c.name.text, _unquote(c.value.text),
                                                      self.tloc(c.name), self.qualifier(c.qualifier())))
                elif el.pinAssign():
                    inst.assigns.append(self.assign(el.pinAssign()))
                else:
                    inst.infos.append(self.info(el.info()))
            return inst
        prefix = _unquote(ctx.prefix.text) if ctx.prefix else None
        inst = ast.SubDesignInstance(prefix=prefix, **common)
        for el in ctx.subInstanceElement():
            if el.attr():
                inst.attrs.append(self.attr(el.attr()))
            elif c := el.subAttr():
                inst.sub_attrs.append(self.sub_attr(c))
            elif el.portAssign():
                inst.assigns.append(self.assign(el.portAssign()))
            else:
                inst.infos.append(self.info(el.info()))
        return inst

    def sub_attr(self, ctx) -> ast.SubAttr:
        path = [ast.PathStep(ctx.name.text, self.selection(ctx.indices()), self.tloc(ctx.name))]
        tail = ctx.refTail()
        while tail is not None:
            path.append(ast.PathStep(tail.name.text, self.selection(tail.indices()), self.tloc(tail.name)))
            tail = tail.refTail()
        return ast.SubAttr(path, _unquote(ctx.value.text), self.tloc(ctx.name),
                           self.qualifier(ctx.qualifier()))

    def assign(self, ctx) -> ast.Assign:
        target = ctx.phdlId()
        return ast.Assign(target.getText(), self.selection(ctx.slices()),
                          self.concat(ctx.concatenation()), self.cloc(target),
                          self.qualifier(ctx.qualifier()), ctx.combine is not None)

    def concat(self, ctx) -> ast.Concatenation:
        loc = self.cloc(ctx)
        if isinstance(ctx, PhdlParser.OpenConcatContext):
            return ast.Concatenation("open", [], loc)
        if isinstance(ctx, PhdlParser.ListConcatContext):
            kind, refs = "list", ctx.connectionRef()
        elif isinstance(ctx, PhdlParser.AmpConcatContext):
            kind, refs = "amp", ctx.connectionRef()
        elif isinstance(ctx, PhdlParser.ReplicateConcatContext):
            kind, refs = "replicate", [ctx.connectionRef()]
        else:
            kind, refs = "star", [ctx.connectionRef()]
        return ast.Concatenation(kind, [ast.ConnectionRef(r.phdlId().getText(), self.selection(r.slices()),
                                                          self.cloc(r)) for r in refs], loc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_text(text: str, path: str, reporter: Reporter) -> ast.SourceFile | None:
    """Parse one source text. Returns None if it had syntax errors."""
    reporter.add_source(path, text)
    before = reporter.error_count
    listener = _SyntaxErrorListener(path, reporter)
    lexer = PhdlLexer(InputStream(text))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)
    parser = PhdlParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(listener)
    tree = parser.model()
    if reporter.error_count > before:
        return None
    return _AstBuilder(path).build(tree)


def parse_file(path: str | Path, reporter: Reporter) -> ast.SourceFile | None:
    p = Path(path)
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return parse_text(text, str(path), reporter)
