"""Neutral JSON netlist (see pcbhdl.netlist). Useful for other tools and scripts."""
from ..netlist import Netlist

NAME = "json"
EXTENSION = ".netlist.json"


def generate(netlist: Netlist) -> str:
    return netlist.to_json()
