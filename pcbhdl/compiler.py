"""Compiler driver: source files in, one neutral netlist per top-level design out."""
from __future__ import annotations

from pathlib import Path

from .diagnostics import Reporter
from .elaborate import Elaborator, Options, Scope
from .flatten import assign_refdes, erc, form_nets, to_netlist
from .frontend import parse_file
from .netlist import Netlist


def compile_files(files: list[str | Path], reporter: Reporter, top: str | None = None,
                  options: Options | None = None, run_erc: bool = True) -> list[Netlist] | None:
    """Compile PHDL files. Returns None if there were errors.

    Every 'design' (as opposed to 'subdesign') is a top-level design and
    produces one netlist; `top` restricts that to designs with this name.
    """
    paths = sorted({str(f) for f in files})
    sources = [s for s in (parse_file(p, reporter) for p in paths) if s is not None]
    if reporter.error_count:
        return None

    scope = Scope(sources, reporter)
    # Check every device, including ones no design uses.
    for f in sources:
        for d in [*f.devices, *(d for p in f.packages for d in p.devices)]:
            scope.device_def(d)

    tops = [d for d in scope.designs if not d.is_subdesign and (top is None or d.name == top)]
    if top is not None and not tops:
        reporter.error("E0120", f"no top-level design named '{top}'")
        return None
    if not tops:
        reporter.warning("W0121", "no top-level design found; nothing to generate",
                         hint="a board is described by a 'design'; 'subdesign's are only used through 'subinst'")

    # Sub-designs never instanced from a top design are still checked.
    elab = Elaborator(scope, reporter, options)
    used: set[int] = set()
    units = []
    for d in tops:
        unit = elab.elaborate_top(d)
        units.append(unit)
        used.update(id(u.design) for u in unit.walk())
    for d in scope.designs:
        if d.is_subdesign and id(d) not in used:
            elab.elaborate_top(d)
    if reporter.error_count:
        return None

    options = options or Options()
    netlists = []
    for unit in units:
        nets = form_nets(unit)
        assign_refdes(unit, reporter, options.refdes_style)
        if run_erc:
            erc(nets, reporter)
        netlists.append(to_netlist(unit, nets, paths))
    if reporter.error_count:
        return None
    return netlists
