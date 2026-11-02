"""Flatten an elaborated hierarchy into nets, assign reference designators,
run the electrical rule check, and produce the neutral :class:`Netlist`.

Net formation, net naming, pin order and reference designator numbering
all follow PHDL 2.1 exactly, so that existing designs keep the same net
names and refdes when compiled with PCBHDL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import __version__
from .diagnostics import Reporter
from .elaborate import Conn, InstElem, Unit
from .netlist import Net, Netlist, Node, Part, PartPin


@dataclass(eq=False)
class FlatNet:
    rep: Conn
    members: list[Conn] = field(default_factory=list)
    pins: list[tuple[InstElem, object]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.rep.hier_name


# ---------------------------------------------------------------------------
# Nets
# ---------------------------------------------------------------------------

def _sort_key(c: Conn) -> str:
    """Neighbour order: hierarchical name in plain string order.

    PHDL 2.1: elements of a sub-design instance array that is not instanced
    directly by the top design are ordered by creation, not by index text.
    """
    parts = []
    u = c.unit
    while u.parent is not None:
        if u.nested_array:
            parts.append(f"{u.name}(#{u.seq:06d})")
        else:
            parts.append(u.name_index)
        u = u.parent
    parts.reverse()
    parts.append(c.name)
    return "/".join(parts)


def form_nets(top: Unit) -> list[FlatNet]:
    visited: set[int] = set()
    nets: list[FlatNet] = []
    for u in top.walk():
        for c in u.conns:
            c.edges.sort(key=_sort_key)

    def visit(c: Conn, net: FlatNet) -> None:
        # Iterative pre-order depth-first search.
        stack = [iter(c.edges)]
        while stack:
            for n in stack[-1]:
                if id(n) not in visited:
                    visited.add(id(n))
                    net.members.append(n)
                    net.pins.extend(n.pins)
                    stack.append(iter(n.edges))
                    break
            else:
                stack.pop()

    def start(c: Conn) -> None:
        if id(c) in visited:
            return
        visited.add(id(c))
        net = FlatNet(c, [c], list(c.pins))
        visit(c, net)
        nets.append(net)

    for c in top.conns:
        start(c)
    for sub in top.subs:
        for u in sub.walk():
            for c in u.conns:
                start(c)
    return nets


# ---------------------------------------------------------------------------
# Reference designators
# ---------------------------------------------------------------------------

def assign_refdes(top: Unit, reporter: Reporter) -> dict[str, InstElem]:
    """Assign refdes to every instance element; returns refdes -> element."""
    taken: dict[str, InstElem] = {}

    # Pass 1, pre-order: sub-instance prefixes, then fixed REFDES values.
    def pass1(u: Unit) -> None:
        if not u.is_top:
            p = u.own_prefix
            if not u.parent.is_top:
                p = u.parent.final_prefix + p
            if u.index is not None and p.strip():
                p = p + str(u.index)
            if p.strip():
                u.final_prefix = p + "/"
            else:
                u.final_prefix = ""
        for e in u.insts:
            fixed = e.attrs.get("REFDES", "")
            if fixed:
                e.refdes = (u.final_prefix if not u.is_top else "") + fixed
                if e.refdes in taken:
                    other = taken[e.refdes]
                    reporter.error("E0601", f"reference designator '{e.refdes}' is used by both "
                                            f"'{other.path}' and '{e.path}'", e.loc,
                                   notes=[("other instance", other.loc)])
                else:
                    taken[e.refdes] = e
        for s in u.subs:
            pass1(s)

    # Pass 2, post-order: generate the rest, smallest free number first.
    def pass2(u: Unit) -> None:
        for s in u.subs:
            pass2(s)
        for e in u.insts:
            if e.refdes:
                continue
            prefix = (u.final_prefix if not u.is_top else "") + e.attrs.get("REFPREFIX", "")
            k = 1
            while f"{prefix}{k}" in taken:
                k += 1
            e.refdes = f"{prefix}{k}"
            taken[e.refdes] = e

    pass1(top)
    pass2(top)
    return taken


# ---------------------------------------------------------------------------
# Electrical rule check
# ---------------------------------------------------------------------------

_ERC_TYPES = ["inpin", "outpin", "iopin", "tripin", "passpin", "pin", "pwrpin", "suppin", "ocpin", "oepin", "ncpin"]
_ERC_MATRIX = """
. . . . . W . . . . E
. E . W . W . E E E E
. . . . . W . W . W E
. W . . . W W E W W E
. . . . . W . . . . E
W W W W W . W W W W E
. . . W . W . . . . E
. E W E . W . E E E E
. E . W . W . E . . E
. E W W . W . E . . E
E E E E E E E E E E E
"""
_ERC = {}
for _i, _row in enumerate(_ERC_MATRIX.strip().splitlines()):
    for _j, _v in enumerate(_row.split()):
        _ERC[(_ERC_TYPES[_i], _ERC_TYPES[_j])] = _v


def erc(nets: list[FlatNet], reporter: Reporter) -> None:
    for n in nets:
        loc = n.rep.loc
        if len(n.pins) == 0:
            reporter.warning("W0701", f"net '{n.name}' is not connected to any pin", loc)
            continue
        if len(n.pins) == 1:
            e, b = n.pins[0]
            reporter.warning("W0701", f"net '{n.name}' connects to only one pin ({e.refdes}.{b.number})", loc)
        worst = None
        count = 0
        for i in range(len(n.pins)):
            ei, bi = n.pins[i]
            for j in range(i + 1, len(n.pins)):
                ej, bj = n.pins[j]
                v = _ERC.get((bi.pin_type, bj.pin_type), ".")
                if v == ".":
                    continue
                count += 1
                if worst is None or (v == "E" and worst[0] == "W"):
                    worst = (v, ei, bi, ej, bj)
        if worst:
            v, ei, bi, ej, bj = worst
            more = f" ({count} conflicting pin pairs)" if count > 1 else ""
            reporter.warning("W0702" if v == "W" else "W0703",
                             f"net '{n.name}' connects {bi.pin_type} {ei.refdes}.{bi.number} ({bi.name}) "
                             f"to {bj.pin_type} {ej.refdes}.{bj.number} ({bj.name}){more}", loc)


# ---------------------------------------------------------------------------
# Neutral netlist
# ---------------------------------------------------------------------------

def _hierarchy(u: Unit) -> dict:
    return {
        "kind": "design" if u.is_top else "subinstance",
        "name": u.name,
        "index": u.index,
        "design": u.design.name,
        "info": u.info,
        "nets": [{"name": c.name, "base": c.base, "info": c.info} for c in u.conns if c.kind == "net"],
        "instances": [{"name": e.name, "index": e.index, "refdes": e.refdes, "info": e.info} for e in u.insts],
        "children": [_hierarchy(s) for s in u.subs],
    }


def to_netlist(top: Unit, nets: list[FlatNet], sources: list[str]) -> Netlist:
    parts = []
    for u in top.walk():
        for e in u.insts:
            parts.append(Part(e.refdes, e.device.name, e.path, dict(e.attrs),
                              [PartPin(b.number, b.name, b.pin_type) for b in e.device.pins], e.info))
    out_nets = []
    for n in nets:
        attrs: dict[str, str] = {}
        for m in n.members:
            for k, v in m.attrs.items():
                attrs.setdefault(k, v)
        out_nets.append(Net(n.name, [Node(e.refdes, b.number) for e, b in n.pins], attrs,
                            [m.hier_name for m in n.members[1:]], n.rep.base))
    return Netlist(design=top.design.name, package=top.design.package, parts=parts, nets=out_nets,
                   sources=sources, tool=f"pcbhdl {__version__}", info=top.info, hierarchy=_hierarchy(top))
