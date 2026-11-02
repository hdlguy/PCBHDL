"""Command-line interface:  pcbhdl [options] FILE...

Examples:
  pcbhdl board.phdl devices.phdl                 # check only
  pcbhdl -f kicad -o out/ *.phdl                 # write out/<top>.net for KiCad
  pcbhdl -f json -f bom --top main *.phdl        # neutral netlist + BOM
  pcbhdl --diagnostics json *.phdl               # machine-readable errors
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .backends import BACKENDS
from .compiler import compile_files
from .diagnostics import Reporter


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pcbhdl", description="Compile PHDL designs to PCB netlists.")
    ap.add_argument("files", nargs="+", type=Path, help="PHDL source files (.phdl); directories are searched recursively")
    ap.add_argument("-t", "--top", help="name of the top-level design (default: the only 'design' found)")
    ap.add_argument("-f", "--format", action="append", default=[], choices=sorted(BACKENDS),
                    help="output format; may be repeated (default: none, check only)")
    ap.add_argument("-o", "--output-dir", type=Path, default=Path("."), help="directory for output files")
    ap.add_argument("--diagnostics", choices=["text", "json"], default="text",
                    help="format for errors and warnings (json is intended for tools and AI agents)")
    ap.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("-W", "--no-warnings", action="store_true", help="suppress warnings")
    ap.add_argument("--version", action="version", version=f"pcbhdl {__version__}")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for f in args.files:
        files.extend(sorted(f.rglob("*.phdl")) if f.is_dir() else [f])

    reporter = Reporter()
    netlists = compile_files(files, reporter, top=args.top)

    if args.no_warnings:
        reporter.diagnostics = [d for d in reporter.diagnostics if d.severity.value == "error"]
    if args.diagnostics == "json":
        print(reporter.render_json())
    elif reporter.diagnostics:
        color = args.color == "always" or (args.color == "auto" and sys.stderr.isatty())
        print(reporter.render_text(color=color), file=sys.stderr)

    if netlists is None:
        if args.diagnostics == "text":
            print(f"pcbhdl: compilation failed with {reporter.error_count} error(s)", file=sys.stderr)
        return 1

    if args.format:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for netlist in netlists:
        for fmt in args.format:
            backend = BACKENDS[fmt]
            path = args.output_dir / (netlist.output_name + backend.EXTENSION)
            path.write_text(backend.generate(netlist), encoding="utf-8", newline="\n")
            if args.diagnostics == "text":
                print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
