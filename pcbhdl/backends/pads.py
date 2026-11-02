"""Mentor PADS ASCII netlist (.asc), as written by PHDL 2.1."""
from ..netlist import Netlist

NAME = "pads"
EXTENSION = ".asc"


def generate(netlist: Netlist) -> str:
    o = ["!PADS-POWERPCB-V9.0-MILS! NETLIST FILE FROM PADS LOGIC V9.3", "", "*PART*"]
    for p in sorted(netlist.parts, key=lambda p: p.refdes):
        o.append(f"{p.refdes} {p.library}@{p.footprint}")
    o += ["", "*CONNECTION*"]
    for n in netlist.nets:
        o.append(f"*SIGNAL* {n.name}")
        # Pins are written as a chain of consecutive pairs.
        for a, b in zip(n.nodes, n.nodes[1:]):
            o.append(f" {a.refdes}.{a.pin} {b.refdes}.{b.pin}")
    o += ["", "*END*"]
    return "\n".join(o) + "\n"
