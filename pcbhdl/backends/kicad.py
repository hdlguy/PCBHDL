"""KiCad netlist back end (KiCad 6+ s-expression netlist, version "E").

Import the result in the KiCad PCB editor with File > Import > Netlist.

Footprints: KiCad identifies footprints as "Library:Footprint". The
footprint for a part is taken from, in order of preference:
  1. a KICAD_FOOTPRINT attribute, used verbatim;
  2. a FOOTPRINT attribute that already contains ':';
  3. LIBRARY:FOOTPRINT, or just FOOTPRINT if there is no LIBRARY.

Timestamps: every component gets a UUID derived from its hierarchical
instance path. KiCad uses these to match footprints on the board with
components in the netlist, so placement survives recompiles and changes
to reference designators.
"""
from __future__ import annotations

import uuid

from ..netlist import Netlist, Part

NAME = "kicad"
EXTENSION = ".net"

# Fixed namespace so that UUIDs are reproducible across machines.
_NAMESPACE = uuid.UUID("6f0c1e7a-5b1e-4c8e-9d43-6a1f3b2c9e10")

_PIN_TYPES = {
    "pin": "passive",
    "passpin": "passive",
    "inpin": "input",
    "outpin": "output",
    "iopin": "bidirectional",
    "pwrpin": "power_in",
    "suppin": "power_out",
    "ocpin": "open_collector",
    "oepin": "open_emitter",
    "tripin": "tri_state",
    "ncpin": "no_connect",
}

# Attributes that are emitted as dedicated KiCad fields rather than as
# generic properties.
_CONSUMED = {"KICAD_FOOTPRINT", "FOOTPRINT", "LIBRARY", "VALUE", "REFDES", "REFPREFIX"}


def q(s: str) -> str:
    """Quote a string as a KiCad s-expression atom."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def footprint_id(part: Part) -> str:
    attrs = part.attributes
    if "KICAD_FOOTPRINT" in attrs:
        return attrs["KICAD_FOOTPRINT"]
    fp = attrs.get("FOOTPRINT", "")
    if ":" in fp or not fp:
        return fp
    lib = attrs.get("LIBRARY", "")
    return f"{lib}:{fp}" if lib else fp


def part_uuid(part: Part) -> str:
    return str(uuid.uuid5(_NAMESPACE, part.path or part.refdes))


def generate(netlist: Netlist) -> str:
    out: list[str] = []
    w = out.append
    w('(export (version "E")')
    w("  (design")
    w(f"    (source {q(netlist.sources[0] if netlist.sources else netlist.design)})")
    w(f"    (tool {q(netlist.tool or 'pcbhdl')})")
    w("    (sheet (number \"1\") (name \"/\") (tstamps \"/\")")
    w(f"      (title_block (title {q(netlist.design)}))))")

    w("  (components")
    for p in netlist.parts:
        w(f"    (comp (ref {q(p.refdes)})")
        w(f"      (value {q(p.value or p.device)})")
        fp = footprint_id(p)
        if fp:
            w(f"      (footprint {q(fp)})")
        w(f"      (libsource (lib \"pcbhdl\") (part {q(p.device)}) (description \"\"))")
        for k, v in sorted(p.attributes.items()):
            if k not in _CONSUMED:
                w(f"      (property (name {q(k)}) (value {q(v)}))")
        w(f"      (property (name \"PCBHDL_PATH\") (value {q(p.path)}))")
        w("      (sheetpath (names \"/\") (tstamps \"/\"))")
        w(f"      (tstamps {q(part_uuid(p))}))")
    w("  )")

    # One libpart per device, so KiCad knows pin names and types.
    w("  (libparts")
    seen: set[str] = set()
    for p in netlist.parts:
        if p.device in seen:
            continue
        seen.add(p.device)
        w(f"    (libpart (lib \"pcbhdl\") (part {q(p.device)})")
        fp = footprint_id(p)
        if fp:
            w(f"      (footprints (fp {q(fp)}))")
        w("      (pins")
        for pin in p.pins:
            ptype = _PIN_TYPES.get(pin.pin_type, "passive")
            w(f"        (pin (num {q(pin.number)}) (name {q(pin.name)}) (type {q(ptype)}))")
        w("      ))")
    w("  )")

    pin_types = {(p.refdes, pin.number): _PIN_TYPES.get(pin.pin_type, "passive")
                 for p in netlist.parts for pin in p.pins}
    pin_names = {(p.refdes, pin.number): pin.name for p in netlist.parts for pin in p.pins}
    w("  (nets")
    for code, n in enumerate(netlist.nets, start=1):
        w(f"    (net (code {q(str(code))}) (name {q(n.name)})")
        for node in n.nodes:
            key = (node.refdes, node.pin)
            extra = ""
            if key in pin_names:
                extra = f" (pinfunction {q(pin_names[key])}) (pintype {q(pin_types[key])})"
            w(f"      (node (ref {q(node.refdes)}) (pin {q(node.pin)}){extra})")
        out[-1] += ")"
    w("  )")
    w(")")
    return "\n".join(out) + "\n"
