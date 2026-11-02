"""Abstract syntax tree for PHDL 2.1.

These classes mirror the language closely; they carry no semantic
information beyond what is written in the source. Every node has a `loc`
pointing at the token that best identifies it in error messages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from .diagnostics import Loc


# ---------------------------------------------------------------------------
# Ranges and selections
# ---------------------------------------------------------------------------

@dataclass
class Range:
    """A declared [msb:lsb] vector or (msb:lsb) instance array."""
    msb: int
    lsb: int
    loc: Loc

    @property
    def width(self) -> int:
        return abs(self.msb - self.lsb) + 1

    def indices(self) -> list[int]:
        """Indices in declaration order, msb first."""
        step = -1 if self.msb >= self.lsb else 1
        return list(range(self.msb, self.lsb + step, step))


@dataclass
class Selection:
    """A [msb:lsb] / [i,j,k] slice, or a (msb:lsb) / (i,j,k) index selection."""
    items: list[int]          # selected indices in written order
    is_range: bool
    loc: Loc


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

@dataclass
class Import:
    name: list[str]
    wildcard: bool
    loc: Loc

    def __str__(self) -> str:
        return ".".join(self.name) + (".*" if self.wildcard else "")


@dataclass
class Attr:
    name: str
    value: str
    loc: Loc
    deprecated_newattr: bool = False


@dataclass
class Info:
    text: str
    loc: Loc


@dataclass
class PinDecl:
    pin_type: str              # 'pin', 'inpin', 'pwrpin', ...
    vector: Range | None
    name: str
    numbers: list[str]         # physical pin names in written order
    loc: Loc
    numbers_loc: Loc | None = None


@dataclass
class Device:
    name: str
    attrs: list[Attr]
    pins: list[PinDecl]
    infos: list[Info]
    loc: Loc
    package: str | None = None
    file: str = ""


@dataclass
class ConnectionDecl:
    """'net' or 'port' declaration of one or more names."""
    kind: str                  # 'net' | 'port'
    vector: Range | None
    names: list[tuple[str, Loc]]
    attrs: list[Attr]
    infos: list[Info]
    loc: Loc


@dataclass
class ConnectionRef:
    name: str
    slices: Selection | None
    loc: Loc


@dataclass
class Concatenation:
    kind: str                  # 'list' | 'amp' | 'replicate' | 'star' | 'open'
    refs: list[ConnectionRef]
    loc: Loc

    @property
    def replicated(self) -> bool:
        return self.kind in ("replicate", "star")


@dataclass
class Qualifier:
    """this(indices). prefix selecting elements of an instance array."""
    indices: Selection
    loc: Loc


@dataclass
class Assign:
    """Pin assignment (inst), port assignment (subinst) or net assignment (design)."""
    target: str
    slices: Selection | None
    concat: Concatenation
    loc: Loc
    qualifier: Qualifier | None = None
    combine: bool = False


@dataclass
class RefAttr:
    """Attribute override on a device instance:  [this(i).]NAME = "value";"""
    name: str
    value: str
    loc: Loc
    qualifier: Qualifier | None = None


@dataclass
class PathStep:
    name: str
    indices: Selection | None
    loc: Loc


@dataclass
class SubAttr:
    """Attribute override inside a sub-design:  [this(i).]a(1).b.ATTR = "value";"""
    path: list[PathStep]       # instance path; the last step names the attribute
    value: str
    loc: Loc
    qualifier: Qualifier | None = None


InstanceElement = Union[Attr, RefAttr, Assign, Info]
SubInstanceElement = Union[Attr, SubAttr, Assign, Info]


@dataclass
class DeviceInstance:
    name: str
    array: Range | None
    ref: list[str]
    attrs: list[Attr] = field(default_factory=list)
    ref_attrs: list[RefAttr] = field(default_factory=list)
    assigns: list[Assign] = field(default_factory=list)
    infos: list[Info] = field(default_factory=list)
    loc: Loc | None = None
    ref_loc: Loc | None = None


@dataclass
class SubDesignInstance:
    name: str
    array: Range | None
    ref: list[str]
    prefix: str | None
    attrs: list[Attr] = field(default_factory=list)
    sub_attrs: list[SubAttr] = field(default_factory=list)
    assigns: list[Assign] = field(default_factory=list)
    infos: list[Info] = field(default_factory=list)
    loc: Loc | None = None
    ref_loc: Loc | None = None


@dataclass
class Design:
    name: str
    is_subdesign: bool
    connections: list[ConnectionDecl] = field(default_factory=list)
    instances: list[Union[DeviceInstance, SubDesignInstance]] = field(default_factory=list)
    assigns: list[Assign] = field(default_factory=list)
    infos: list[Info] = field(default_factory=list)
    loc: Loc | None = None
    package: str | None = None
    file: str = ""
    # All of the above in source order; declaration order matters.
    elements: list = field(default_factory=list)


@dataclass
class Package:
    name: str
    imports: list[Import]
    devices: list[Device]
    designs: list[Design]
    loc: Loc


@dataclass
class SourceFile:
    path: str
    imports: list[Import]
    packages: list[Package]
    devices: list[Device]
    designs: list[Design]
