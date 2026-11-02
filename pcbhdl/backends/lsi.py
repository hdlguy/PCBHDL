"""Layout Supplementary Information (.lsi): the design's info text for the layout designer.

Lists the hierarchy with the 'info' text of the design, its nets and its
instances, in the PHDL 2.1 format.
"""
from ..netlist import Netlist

NAME = "lsi"
EXTENSION = ".lsi"


def _wrap(text: str, tabs: str) -> str:
    words = text.split(" ")
    while words and words[-1] == "":
        words.pop()
    out, count = [], 0
    for w in words:
        if count >= 60:
            out.append("\n" + tabs)
            count = 0
        out.append(w + " ")
        count += len(w) + 1
    return "".join(out)


def _block(kind: str, name: str, info: str, tabs: str) -> str:
    if not info.strip():
        return ""
    head = f"{tabs}{kind} {name}\n"
    rule = tabs + "-" * len(head) + "\n"
    return head + rule + tabs + _wrap(info, tabs) + "\n" + rule


def _unit(u: dict, depth: int) -> str:
    t = "\t" * depth
    head = f"{t}{'DESIGN' if u['kind'] == 'design' else 'SUBINSTANCE'} {u['name']}\n"
    rule = t + "-" * (len(head) - 1)
    s = head + rule + "\n"
    if u["info"]:
        s += t + _wrap(u["info"], t) + "\n"
    s += "\n"
    for n in u["nets"]:
        s += _block("NET", n["base"], n["info"], "\t" * (depth + 1)) + "\n"
    for i in u["instances"]:
        s += _block("INSTANCE", i["name"], i["info"], "\t" * (depth + 1)) + "\n"
    for c in u["children"]:
        s += _unit(c, depth + 1) + "\n"
    return s + rule


def generate(netlist: Netlist) -> str:
    return ("Layout Supplementary Information\n--------------------------------\n\n"
            + _unit(netlist.hierarchy, 1) + "\n")
