"""Output back ends. Each module exposes NAME, EXTENSION and generate(netlist) -> str.

Back ends only see the neutral :class:`pcbhdl.netlist.Netlist`, never the
source language, so adding support for another layout tool means adding
one module here.
"""
from . import bom, eagle, json_netlist, kicad, lsi, pads, phdl_xml, rdm

BACKENDS = {m.NAME: m for m in (json_netlist, kicad, pads, eagle, bom, rdm, lsi, phdl_xml)}
