"""EAGLE PCB script (.scr), as written by PHDL 2.1. Run it in an empty EAGLE board."""
from ..netlist import Netlist

NAME = "eagle"
EXTENSION = ".scr"


def generate(netlist: Netlist) -> str:
    o = ["# Auto-generated EAGLE PCB script from: ", "SET UNDO_LOG OFF;", "GRID INCH;",
         "CHANGE DISPLAY OFF;", "CHANGE SIZE 0.25;", "", "# PARTS #"]
    # Parts are dropped on a 0.25 x 0.5 inch grid, 120 per row.
    x, y = 0.0, 0.0
    for p in sorted(netlist.parts, key=lambda p: p.refdes):
        x += 0.25
        if x > 30:
            x, y = 0.0, y + 0.5
        o.append(f"ADD {p.footprint}@{p.library} '{p.refdes}' ({x!r} {y!r});")
    o += ["", "# SIGNALS #"]
    for n in netlist.nets:
        o.append(f"SIGNAL '{n.name}'" + "".join(f" {x.refdes} {x.pin}" for x in n.nodes) + ";")
    return "\n".join(o) + "\n"
