"""Bill of materials (.bom), in the PHDL 2.1 comma-separated format.

One row per distinct part: parts with the same device, LIBRARY, FOOTPRINT
and other attribute values are merged and counted. Every attribute other
than REFPREFIX, REFDES, LIBRARY and FOOTPRINT becomes a column.
"""
from ..netlist import Netlist

NAME = "bom"
EXTENSION = ".bom"

_FIXED = ("REFPREFIX", "REFDES", "FOOTPRINT", "LIBRARY")


def generate(netlist: Netlist) -> str:
    columns: list[str] = []
    for p in netlist.parts:
        for k in sorted(p.attributes):
            if k not in _FIXED and k not in columns:
                columns.append(k)
    rows: list[list] = []   # [qty, key, refdes list, values]
    index: dict[tuple, list] = {}
    for p in netlist.parts:
        values = tuple(p.attributes.get(c, "") for c in columns)
        key = (p.device, p.library, p.footprint, values)
        if key in index:
            index[key][0] += 1
            index[key][2].append(p.refdes)
        else:
            row = [1, key, [p.refdes], values]
            index[key] = row
            rows.append(row)
    out = [", ".join(["QUANTITY", "NAME", "REFDES", "LIBRARY", "FOOTPRINT", *columns])]
    for qty, (device, lib, fp, _), refs, values in rows:
        out.append(", ".join([str(qty), device, "; ".join(refs), lib, fp, *values]))
    return "\n".join(out) + "\n"
