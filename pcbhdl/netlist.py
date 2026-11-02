"""The neutral netlist: the contract between the compiler and its back ends.

The elaborator produces a :class:`Netlist`; every output format (KiCad,
PADS, EAGLE, BOM, ...) is generated from it and from nothing else. A
netlist can be written to and read from JSON, so third-party tools can
consume compiled designs without importing the compiler.

All collections are kept in a deterministic order so that output files
diff cleanly between compiles.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

FORMAT = "pcbhdl-netlist"
FORMAT_VERSION = 1


@dataclass
class PartPin:
    number: str                # physical pin / pad name, e.g. "1", "A3"
    name: str                  # logical pin name, e.g. "VCC", "D[3]"
    pin_type: str = "pin"      # PHDL pin type: pin, inpin, outpin, pwrpin, ...


@dataclass
class Part:
    refdes: str                # e.g. "R12"
    device: str                # PHDL device name
    path: str                  # hierarchical instance path, e.g. "top/psu/R2"
    attributes: dict[str, str] = field(default_factory=dict)
    pins: list[PartPin] = field(default_factory=list)
    info: str = ""

    @property
    def footprint(self) -> str:
        return self.attributes.get("FOOTPRINT", "")

    @property
    def library(self) -> str:
        return self.attributes.get("LIBRARY", "")

    @property
    def value(self) -> str:
        return self.attributes.get("VALUE", "")


@dataclass
class Node:
    refdes: str
    pin: str                   # physical pin number


@dataclass
class Net:
    name: str                  # hierarchical name, e.g. "vcc", "bus[3]", "psu/v_sense"
    nodes: list[Node] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)   # other names joined into this net
    base: str = ""             # local name without path or bit index, e.g. "bus"


@dataclass
class Netlist:
    design: str
    package: str | None = None
    parts: list[Part] = field(default_factory=list)   # in hierarchy order
    nets: list[Net] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    tool: str = ""
    info: str = ""
    # Design hierarchy, for documentation outputs. Each node is
    #   {"kind": "design"|"subinstance", "name", "index", "info",
    #    "nets": [{"name", "base", "info"}], "instances": [{"name", "index", "refdes", "info"}],
    #    "children": [...]}
    hierarchy: dict = field(default_factory=dict)

    @property
    def output_name(self) -> str:
        """Base name for output files: the design name, prefixed by its package if any."""
        return f"{self.package}_{self.design}" if self.package else self.design

    def part(self, refdes: str) -> Part | None:
        for p in self.parts:
            if p.refdes == refdes:
                return p
        return None

    # -- JSON ----------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "design": self.design,
            "package": self.package,
            "tool": self.tool,
            "sources": self.sources,
            "info": self.info,
            "parts": [
                {"refdes": p.refdes, "device": p.device, "path": p.path,
                 "attributes": p.attributes, "info": p.info,
                 "pins": [{"number": q.number, "name": q.name, "type": q.pin_type} for q in p.pins]}
                for p in self.parts
            ],
            "nets": [
                {"name": n.name, "base": n.base, "attributes": n.attributes, "aliases": n.aliases,
                 "nodes": [{"refdes": x.refdes, "pin": x.pin} for x in n.nodes]}
                for n in self.nets
            ],
            "hierarchy": self.hierarchy,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2) + "\n"

    @classmethod
    def from_dict(cls, d: dict) -> "Netlist":
        if d.get("format") != FORMAT:
            raise ValueError(f"not a {FORMAT} file")
        if d.get("version", 0) > FORMAT_VERSION:
            raise ValueError(f"{FORMAT} version {d['version']} is newer than this tool supports")
        return cls(
            design=d["design"],
            package=d.get("package"),
            tool=d.get("tool", ""),
            sources=list(d.get("sources", [])),
            info=d.get("info", ""),
            parts=[Part(p["refdes"], p["device"], p.get("path", ""), dict(p.get("attributes", {})),
                        [PartPin(q["number"], q["name"], q.get("type", "pin")) for q in p.get("pins", [])],
                        p.get("info", ""))
                   for p in d["parts"]],
            nets=[Net(n["name"], [Node(x["refdes"], x["pin"]) for x in n["nodes"]],
                      dict(n.get("attributes", {})), list(n.get("aliases", [])), n.get("base", ""))
                  for n in d["nets"]],
            hierarchy=d.get("hierarchy", {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Netlist":
        return cls.from_dict(json.loads(Path(path).read_text()))
