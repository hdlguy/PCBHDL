"""PHDL reference designator map (.rdm): one 'REFDES,hierarchical/path' line per part."""
from ..netlist import Netlist

NAME = "rdm"
EXTENSION = ".rdm"


def generate(netlist: Netlist) -> str:
    return "".join(f"{p.refdes},{p.path}\n" for p in sorted(netlist.parts, key=lambda p: p.refdes))
