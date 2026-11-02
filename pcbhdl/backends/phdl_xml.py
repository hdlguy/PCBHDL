"""PHDL 2.1 XML netlist (.net).

Reproduces the PHDL 2.1 format exactly, including its limitation that nets
are identified by bare name (no hierarchy path, no bit index): only the
first net with a given bare name is written. Use the KiCad or JSON back end
for a complete netlist.
"""
from ..netlist import Netlist

NAME = "phdl-xml"
EXTENSION = ".net"


def _x(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def generate(netlist: Netlist) -> str:
    o = ["<netlist>", f"  <name>{_x(netlist.design)}</name>"]
    parts = sorted(netlist.parts, key=lambda p: p.refdes)
    if parts:
        o.append("  <parts>")
        for p in parts:
            o += ["    <part>", f"      <name>{_x(p.refdes)}</name>",
                  f"      <footprint>{_x(p.footprint)}</footprint>",
                  f"      <library>{_x(p.library)}</library>", "    </part>"]
        o.append("  </parts>")
    else:
        o.append("  <parts/>")
    nets = {}
    for n in netlist.nets:
        nets.setdefault(n.base or n.name, n)
    if nets:
        o.append("  <nets>")
        for name in sorted(nets):
            o += ["    <net>", f"      <name>{_x(name)}</name>"]
            if nets[name].nodes:
                o.append("      <pins>")
                for x in nets[name].nodes:
                    o += ["        <pin>", f"          <partName>{_x(x.refdes)}</partName>",
                          f"          <pinName>{_x(x.pin)}</pinName>", "        </pin>"]
                o.append("      </pins>")
            else:
                o.append("      <pins/>")
            o.append("    </net>")
        o.append("  </nets>")
    else:
        o.append("  <nets/>")
    o.append("</netlist>")
    return "\n".join(o) + "\n"
