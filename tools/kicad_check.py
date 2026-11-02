#!/usr/bin/env python3
"""Check a compiled netlist against the installed KiCad footprint libraries.

Uses KiCad's own Python API (pcbnew) to load every footprint named in a
pcbhdl JSON netlist and to verify that every pin in the netlist exists as a
pad. Optionally writes a starter .kicad_pcb with the footprints placed in a
grid and their pads assigned to nets, so the ratsnest shows the connections.

    python3 tools/kicad_check.py out/preamp/preamp.netlist.json [-o board.kicad_pcb]

Run it with the system Python that KiCad's pcbnew module is installed for
(not a virtualenv). Footprint libraries are looked up in KICAD_FOOTPRINT_DIR,
default /usr/share/kicad/footprints.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def footprint_id(part: dict) -> tuple[str, str]:
    a = part["attributes"]
    fp = a.get("KICAD_FOOTPRINT") or a.get("FOOTPRINT", "")
    if ":" in fp:
        lib, name = fp.split(":", 1)
    else:
        lib, name = a.get("LIBRARY", ""), fp
    return lib, name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("netlist", type=Path, help="pcbhdl JSON netlist (pcbhdl -f json)")
    ap.add_argument("-o", "--board", type=Path, help="write a starter .kicad_pcb here")
    args = ap.parse_args()

    import pcbnew  # noqa: E402  (only available with KiCad's Python)

    fp_dir = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
    nl = json.loads(args.netlist.read_text())
    board = pcbnew.BOARD() if args.board else None
    nets: dict[str, object] = {}
    pin_net = {(x["refdes"], x["pin"]): n["name"] for n in nl["nets"] for x in n["nodes"]}
    problems = 0

    for k, part in enumerate(nl["parts"]):
        lib, name = footprint_id(part)
        path = fp_dir / f"{lib}.pretty"
        fp = pcbnew.FootprintLoad(str(path), name) if path.is_dir() else None
        if fp is None:
            print(f"error: {part['refdes']}: footprint '{lib}:{name}' not found in {fp_dir}")
            problems += 1
            continue
        pads = {p.GetNumber() for p in fp.Pads()}
        for pin in part["pins"]:
            if pin["number"] not in pads:
                print(f"error: {part['refdes']}: pin {pin['number']} ({pin['name']}) has no pad "
                      f"in '{lib}:{name}' (pads: {', '.join(sorted(pads))})")
                problems += 1
        if board is None:
            continue
        fp.SetReference(part["refdes"])
        fp.SetValue(part["attributes"].get("VALUE") or part["device"])
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(10 + 12 * (k % 8)), pcbnew.FromMM(10 + 12 * (k // 8))))
        board.Add(fp)
        for pad in fp.Pads():
            net_name = pin_net.get((part["refdes"], pad.GetNumber()))
            if net_name is None:
                continue
            if net_name not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net_name)
                board.Add(ni)
                nets[net_name] = ni
            pad.SetNet(nets[net_name])

    print(f"{len(nl['parts'])} parts, {len(nl['nets'])} nets checked: "
          + ("OK" if not problems else f"{problems} problem(s)"))
    if board is not None:
        board.Save(str(args.board))
        print(f"wrote {args.board}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
