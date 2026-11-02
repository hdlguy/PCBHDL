"""Elaboration: resolve names, build and check the instance hierarchy.

The elaborator turns the AST of one top-level design into a tree of
:class:`Unit` objects (the design and one unit per sub-design instance),
each holding its connections (net and port bits) and device instance
elements with their pin assignments. :mod:`pcbhdl.flatten` then turns that
tree into electrical nets and reference designators.

The rules implemented here follow PHDL 2.1. Where PHDL 2.1 was ambiguous
or buggy, the behaviour chosen is noted in a comment marked "PHDL 2.1:".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import ast
from .diagnostics import Loc, Reporter

REQUIRED_DEVICE_ATTRS = ("REFPREFIX", "LIBRARY", "FOOTPRINT")


def bit_name(base: str, index: int | None) -> str:
    return base if index is None else f"{base}[{index}]"


def index_name(name: str, index: int | None) -> str:
    return name if index is None else f"{name}({index})"


def _not_assigned(what: str, keys: list[str]) -> str:
    if len(keys) == 1:
        return f"{what} '{keys[0]}' is not assigned"
    shown = ", ".join(f"'{k}'" for k in keys[:8])
    more = f" and {len(keys) - 8} more" if len(keys) > 8 else ""
    return f"{len(keys)} {what}s are not assigned: {shown}{more}"


def _range_text(r: ast.Range) -> str:
    return f"{r.msb}:{r.lsb}"


# ---------------------------------------------------------------------------
# Elaborated model
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class DevicePin:
    base: str
    index: int | None
    number: str              # physical pin name
    pin_type: str
    seq: int                 # position in the device's pin order

    @property
    def name(self) -> str:
        return bit_name(self.base, self.index)


@dataclass(eq=False)
class PinGroup:
    name: str
    vector: ast.Range | None
    bits: list[DevicePin]


@dataclass(eq=False)
class DeviceDef:
    node: ast.Device
    name: str
    qualified: str
    attrs: dict[str, str]                # UPPERCASE name -> value, sorted by name
    attr_locs: dict[str, Loc]
    pins: list[DevicePin]
    groups: dict[str, PinGroup]
    info: str


@dataclass(eq=False)
class Conn:
    """One bit of a net or port in one unit."""
    unit: "Unit"
    base: str
    index: int | None
    kind: str                            # 'net' | 'port'
    loc: Loc
    attrs: dict[str, str] = field(default_factory=dict)
    info: str = ""
    pins: list[tuple["InstElem", DevicePin]] = field(default_factory=list)
    edges: list["Conn"] = field(default_factory=list)

    @property
    def name(self) -> str:
        return bit_name(self.base, self.index)

    @property
    def hier_name(self) -> str:
        prefix = self.unit.hier_path
        return f"{prefix}/{self.name}" if prefix else self.name


@dataclass(eq=False)
class ConnGroup:
    name: str
    kind: str
    vector: ast.Range | None
    bits: list[Conn]
    loc: Loc


@dataclass(eq=False)
class InstElem:
    """One element of a device instance (one physical part)."""
    unit: "Unit"
    name: str
    index: int | None
    device: DeviceDef
    attrs: dict[str, str]
    info: str
    seq: int
    loc: Loc
    assigned: dict[str, Loc] = field(default_factory=dict)
    refdes: str = ""

    @property
    def name_index(self) -> str:
        return index_name(self.name, self.index)

    @property
    def path(self) -> str:
        return f"{self.unit.path}/{self.name_index}"


@dataclass(eq=False)
class InstGroup:
    kind: str                            # 'inst' | 'subinst'
    array: ast.Range | None
    members: dict                        # index (or None) -> InstElem | Unit
    loc: Loc


@dataclass(eq=False)
class Unit:
    """The top design, or one element of a sub-design instance."""
    design: ast.Design
    name: str
    index: int | None
    parent: "Unit | None"
    loc: Loc | None = None
    own_prefix: str = ""
    final_prefix: str = ""
    info: str = ""
    groups: dict[str, ConnGroup] = field(default_factory=dict)
    conns: list[Conn] = field(default_factory=list)
    insts: list[InstElem] = field(default_factory=list)
    subs: list["Unit"] = field(default_factory=list)
    inst_groups: dict[str, InstGroup] = field(default_factory=dict)
    seq: int = 0                         # creation order among its siblings
    nested_array: bool = False           # element of an array not instanced by the top

    @property
    def is_top(self) -> bool:
        return self.parent is None

    @property
    def name_index(self) -> str:
        return index_name(self.name, self.index)

    @property
    def hier_path(self) -> str:
        """Path from (not including) the top design, e.g. 's(1)/l'."""
        if self.parent is None:
            return ""
        p = self.parent.hier_path
        return f"{p}/{self.name_index}" if p else self.name_index

    @property
    def path(self) -> str:
        """Path including the top design name, e.g. 'top/s(1)/l'."""
        if self.parent is None:
            return self.name
        return f"{self.parent.path}/{self.name_index}"

    def walk(self):
        yield self
        for s in self.subs:
            yield from s.walk()


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------

class Scope:
    """Project-wide symbol tables and the PHDL 2.1 visibility rules."""

    def __init__(self, files: list[ast.SourceFile], reporter: Reporter):
        self.r = reporter
        self.root_devices: dict[str, ast.Device] = {}
        self.root_designs: dict[str, ast.Design] = {}
        self.packages: dict[str, dict[str, dict]] = {}   # pkg -> {'device': {}, 'design': {}}
        self.file_imports: dict[str, list[ast.Import]] = {}
        self.package_imports: dict[str, list[ast.Import]] = {}
        self.device_defs: dict[int, DeviceDef] = {}
        self.designs: list[ast.Design] = []

        for f in files:
            self.file_imports[f.path] = f.imports
            for d in f.devices:
                self._add(self.root_devices, d, "device")
            for d in f.designs:
                self._add(self.root_designs, d, "design")
                self.designs.append(d)
            for p in f.packages:
                tables = self.packages.setdefault(p.name, {"device": {}, "design": {}})
                self.package_imports.setdefault(p.name, []).extend(p.imports)
                for d in p.devices:
                    self._add(tables["device"], d, "device", p.name)
                for d in p.designs:
                    self._add(tables["design"], d, "design", p.name)
                    self.designs.append(d)
        for imports in [*self.file_imports.values(), *self.package_imports.values()]:
            for imp in imports:
                self._check_import(imp)

    def _add(self, table: dict, node, kind: str, package: str | None = None) -> None:
        if node.name in table:
            first = table[node.name]
            where = f" in package '{package}'" if package else ""
            self.r.error("E0101", f"duplicate {kind} '{node.name}'{where}", node.loc,
                         notes=[("first defined here", first.loc)])
            return
        table[node.name] = node

    def _check_import(self, imp: ast.Import) -> None:
        if len(imp.name) < 2 and not imp.wildcard:
            self.r.error("E0103", f"invalid import '{imp}'", imp.loc,
                         hint="import a package with 'import pkg.*;' or one element with 'import pkg.Name;'")
            return
        pkg = imp.name[0]
        if pkg not in self.packages:
            self.r.warning("W0104", f"package '{pkg}' not found", imp.loc)
        elif not imp.wildcard and len(imp.name) == 2:
            t = self.packages[pkg]
            if imp.name[1] not in t["device"] and imp.name[1] not in t["design"]:
                self.r.warning("W0104", f"package '{pkg}' has no device or design '{imp.name[1]}'", imp.loc)

    def lookup(self, kind: str, name: list[str], file: str, package: str | None):
        """Find a device or design by (possibly qualified) name; None if not visible."""
        if len(name) == 2:
            t = self.packages.get(name[0])
            return t[kind].get(name[1]) if t else None
        n = name[0]
        if package is not None:
            hit = self.packages[package][kind].get(n)
            if hit is not None:
                return hit
        imports = (self.package_imports.get(package, []) if package else []) + self.file_imports.get(file, [])
        for imp in imports:
            t = self.packages.get(imp.name[0])
            if t is None:
                continue
            if imp.wildcard or (len(imp.name) == 2 and imp.name[1] == n):
                hit = t[kind].get(n)
                if hit is not None:
                    return hit
        table = self.root_devices if kind == "device" else self.root_designs
        return table.get(n)

    def device_def(self, node: ast.Device) -> DeviceDef:
        dd = self.device_defs.get(id(node))
        if dd is None:
            dd = self.device_defs[id(node)] = build_device(node, self.r)
        return dd


def build_device(dev: ast.Device, r: Reporter) -> DeviceDef:
    """Check a device declaration and build its definition."""
    attrs: dict[str, str] = {}
    locs: dict[str, Loc] = {}
    element_names: dict[str, Loc] = {}

    for a in dev.attrs:
        if a.name in element_names:
            r.error("E0208", f"duplicate name '{a.name}' in device '{dev.name}'", a.loc,
                    notes=[("first declared here", element_names[a.name])])
            continue
        element_names[a.name] = a.loc
        up = a.name.upper()
        if a.name != up:
            r.warning("W0203", f"attribute name '{a.name}' should be uppercase; it is treated as '{up}'", a.loc)
        if up in attrs:
            # PHDL 2.1: attribute names are case-insensitive; the first one wins.
            r.warning("W0209", f"attribute '{a.name}' duplicates '{up}' (attribute names are case-insensitive); ignored",
                      a.loc, notes=[("first declared here", locs[up])])
            continue
        attrs[up] = a.value
        locs[up] = a.loc

    for req in REQUIRED_DEVICE_ATTRS:
        if req not in attrs:
            r.error("E0201", f"device '{dev.name}' is missing required attribute '{req}'", dev.loc,
                    hint=f"add  attr {req} = \"...\";")
    if "REFPREFIX" in attrs and attrs["REFPREFIX"] != attrs["REFPREFIX"].upper():
        r.warning("W0202", f"REFPREFIX value '{attrs['REFPREFIX']}' should be uppercase", locs["REFPREFIX"])

    pins: list[DevicePin] = []
    groups: dict[str, PinGroup] = {}
    numbers: dict[str, Loc] = {}
    for p in dev.pins:
        if p.name in element_names:
            r.error("E0208", f"duplicate name '{p.name}' in device '{dev.name}'", p.loc,
                    notes=[("first declared here", element_names[p.name])])
            continue
        element_names[p.name] = p.loc
        width = p.vector.width if p.vector else 1
        if width != len(p.numbers):
            r.error("E0206", f"pin '{p.name}' is {width} bit{'s' if width != 1 else ''} wide "
                             f"but has {len(p.numbers)} physical pin{'s' if len(p.numbers) != 1 else ''}",
                    p.numbers_loc or p.loc)
        indices = p.vector.indices() if p.vector else [None]
        bits = []
        for idx, num in zip(indices, p.numbers):
            if num in numbers:
                r.error("E0207", f"physical pin '{num}' is used more than once in device '{dev.name}'",
                        p.numbers_loc or p.loc, notes=[("first used here", numbers[num])])
            else:
                numbers[num] = p.numbers_loc or p.loc
            bit = DevicePin(p.name, idx, num, p.pin_type, len(pins))
            pins.append(bit)
            bits.append(bit)
        groups[p.name] = PinGroup(p.name, p.vector, bits)

    if "PINCOUNT" in attrs:
        try:
            count = int(attrs["PINCOUNT"].strip())
        except ValueError:
            r.error("E0204", "PINCOUNT attribute must be an integer", locs["PINCOUNT"])
        else:
            declared = sum((p.vector.width if p.vector else 1) for p in dev.pins)
            if count != declared:
                r.error("E0205", f"PINCOUNT is {count} but {declared} pins are declared", locs["PINCOUNT"])

    qualified = f"{dev.package}.{dev.name}" if dev.package else dev.name
    return DeviceDef(dev, dev.name, qualified, dict(sorted(attrs.items())), locs, pins, groups,
                     "".join(i.text for i in dev.infos))


# ---------------------------------------------------------------------------
# Elaborator
# ---------------------------------------------------------------------------

@dataclass
class Options:
    # PHDL 2.1 did not merge two top-level nets that were joined only through
    # a sub-design (for example by 'p = q;' between two ports). True fixes
    # that; False reproduces PHDL 2.1 exactly.
    merge_through_ports: bool = True
    # Reference designator style: "flat" (R1, R2, ... across the whole board)
    # or "phdl" (PHDL 2.1 hierarchical designators such as "CH1/R2").
    refdes_style: str = "flat"


class Elaborator:
    def __init__(self, scope: Scope, reporter: Reporter, options: Options | None = None):
        self.scope = scope
        self.r = reporter
        self.opt = options or Options()
        self._stack: list[ast.Design] = []

    # -- entry point ---------------------------------------------------------

    def elaborate_top(self, design: ast.Design) -> Unit:
        top = Unit(design, design.name, None, None, design.loc)
        self._stack = [design]
        self._unit(design, top)
        return top

    # -- units ---------------------------------------------------------------

    def _unit(self, design: ast.Design, unit: Unit) -> None:
        declared_later = {n for c in design.connections for n, _ in c.names}
        for el in design.elements:
            if isinstance(el, ast.ConnectionDecl):
                self._declare(el, unit)
            elif isinstance(el, ast.DeviceInstance):
                self._device_instance(el, unit, declared_later)
            elif isinstance(el, ast.SubDesignInstance):
                self._sub_instance(el, unit, declared_later)
            elif isinstance(el, ast.Assign):
                self._connection_assign(el, unit, declared_later)
            elif isinstance(el, ast.Info):
                unit.info += el.text
        if not unit.is_top:
            # PHDL 2.1: inside sub-designs, a net's pins are listed by instance
            # and then by device pin order, regardless of statement order.
            order = {id(e): e.seq for e in unit.insts}
            for c in unit.conns:
                c.pins.sort(key=lambda p: (order[id(p[0])], p[1].seq))

    def _declare(self, d: ast.ConnectionDecl, unit: Unit) -> None:
        if d.kind == "port" and not unit.design.is_subdesign:
            self.r.error("E0301", "ports are not allowed in a top-level design", d.loc,
                         hint="use 'net' here, or make this a 'subdesign'")
        if d.kind == "port" and d.attrs:
            self.r.error("E0306", "attributes are not allowed on ports", d.attrs[0].loc)
        attrs: dict[str, str] = {}
        for a in d.attrs:
            if a.name.upper() in attrs:
                self.r.error("E0208", f"duplicate attribute '{a.name}'", a.loc)
            attrs[a.name.upper()] = a.value
        info = "".join(i.text for i in d.infos)
        for name, loc in d.names:
            if name in unit.groups:
                self.r.error("E0302", f"'{name}' is already declared in {unit.design.name}", loc,
                             notes=[("previous declaration", unit.groups[name].loc)])
                continue
            indices = d.vector.indices() if d.vector else [None]
            bits = [Conn(unit, name, i, d.kind, loc, dict(attrs), info) for i in indices]
            unit.groups[name] = ConnGroup(name, d.kind, d.vector, bits, loc)
            unit.conns.extend(bits)

    def _claim_instance_name(self, name: str, loc: Loc, unit: Unit) -> bool:
        if name in unit.inst_groups:
            self.r.error("E0303", f"instance name '{name}' is already used in {unit.design.name}", loc,
                         notes=[("previous instance", unit.inst_groups[name].loc)])
            return False
        return True

    # -- connection references ---------------------------------------------

    def _group(self, name: str, loc: Loc, unit: Unit, later: set[str]) -> ConnGroup | None:
        g = unit.groups.get(name)
        if g is not None:
            return g
        if name in later:
            self.r.error("E0305", f"net '{name}' is used before it is declared", loc,
                         hint="PHDL requires nets and ports to be declared before the statements that use them")
        else:
            self.r.error("E0304", f"no net or port named '{name}' in {unit.design.name}", loc)
        return None

    def _select(self, items: list, vector: ast.Range | None, sel: ast.Selection | None,
                what: str, loc: Loc) -> list | None:
        """Apply a [slice] to the bits of a vector (items are in declaration order)."""
        if sel is None:
            return items
        if vector is None:
            self.r.error("E0403", f"{what} is not a vector and cannot be sliced", sel.loc)
            return None
        by_index = dict(zip(vector.indices(), items))
        out = []
        for i in sel.items:
            if i not in by_index:
                self.r.error("E0402", f"index {i} is out of range for {what} [{_range_text(vector)}]", sel.loc)
                return None
            out.append(by_index[i])
        return out

    def _ref_bits(self, ref: ast.ConnectionRef, unit: Unit, later: set[str]) -> list[Conn] | None:
        g = self._group(ref.name, ref.loc, unit, later)
        if g is None:
            return None
        return self._select(g.bits, g.vector, ref.slices, f"'{ref.name}'", ref.loc)

    def _rhs(self, c: ast.Concatenation, unit: Unit, later: set[str]):
        """Returns ('open', None), ('replicate', Conn) or ('list', [Conn]); None on error."""
        if c.kind == "open":
            return ("open", None)
        if c.replicated:
            ref = c.refs[0]
            g = self._group(ref.name, ref.loc, unit, later)
            if g is None:
                return None
            if g.vector is not None and ref.slices is None:
                self.r.error("E0405", f"cannot replicate vector '{ref.name}'", ref.loc,
                             hint="replicate a single bit, e.g. <" + ref.name + f"[{g.vector.lsb}]>")
                return None
            bits = self._select(g.bits, g.vector, ref.slices, f"'{ref.name}'", ref.loc)
            if bits is None:
                return None
            if len(bits) != 1:
                self.r.error("E0405", f"cannot replicate more than one bit of '{ref.name}'", ref.loc)
                return None
            return ("replicate", bits[0])
        out: list[Conn] = []
        ok = True
        for ref in c.refs:
            bits = self._ref_bits(ref, unit, later)
            if bits is None:
                ok = False
            else:
                out.extend(bits)
        return ("list", out) if ok else None

    # -- shared pin/port assignment logic -----------------------------------

    def _targets(self, q: ast.Qualifier | None, group: InstGroup, what: str) -> list | None:
        members = list(group.members.values())
        if q is None:
            return members
        if group.array is None:
            self.r.error("E0401", f"'this(...)' is only allowed on instance arrays; '{what}' is not an array", q.loc)
            return None
        out = []
        for i in q.indices.items:
            if i not in group.members:
                self.r.error("E0402", f"index {i} is out of range for '{what}' ({_range_text(group.array)})", q.loc)
                return None
            out.append(group.members[i])
        return out

    def _assign(self, a: ast.Assign, group: InstGroup, inst_name: str, unit: Unit, later: set[str],
                lhs_bits, connect, what: str) -> bool:
        """Common pin/port assignment: broadcast or combine the RHS over the targets.

        Returns False if the statement was rejected.
        """
        targets = self._targets(a.qualifier, group, inst_name)
        if targets is None:
            return False
        per_target = [lhs_bits(t) for t in targets]
        if any(b is None for b in per_target):
            return False
        rhs = self._rhs(a.concat, unit, later)

        def give_up() -> None:
            # Treat the targets as handled so that the error is not followed
            # by a cascade of "not assigned" errors for the same pins.
            for t, bits in zip(targets, per_target):
                for b in bits:
                    connect(t, b, None, a.loc)

        if rhs is None:
            give_up()
            return False
        kind, value = rhs
        if kind == "list":
            lw = len(per_target[0]) * (len(targets) if a.combine else 1)
            if lw != len(value):
                target = f"{what} '{a.target}'" + (" (combined)" if a.combine else "")
                self.r.error("E0404", f"width mismatch: {target} is {lw} bit{'s' if lw != 1 else ''} wide "
                                      f"but the right-hand side is {len(value)}", a.loc,
                             hint=None if a.combine or len(targets) == 1 else
                             "on an instance array the right-hand side is applied to every element; "
                             "use combine(...) to spread it across the elements")
                give_up()
                return False
        pairs = []
        if a.combine:
            flat = [(t, b) for t, bits in zip(targets, per_target) for b in bits]
            pairs = [(t, b, value[k] if kind == "list" else value) for k, (t, b) in enumerate(flat)]
        else:
            for t, bits in zip(targets, per_target):
                pairs += [(t, b, value[k] if kind == "list" else value) for k, b in enumerate(bits)]
        for t, b, conn in pairs:
            connect(t, b, conn, a.loc)
        return True

    # -- device instances ----------------------------------------------------

    def _device_instance(self, inst: ast.DeviceInstance, unit: Unit, later: set[str]) -> None:
        node = self.scope.lookup("device", inst.ref, unit.design.file, unit.design.package)
        if node is None:
            self.r.error("E0102", f"unknown device '{'.'.join(inst.ref)}'", inst.ref_loc)
            return
        dev = self.scope.device_def(node)
        if not self._claim_instance_name(inst.name, inst.loc, unit):
            return
        indices = inst.array.indices() if inst.array else [None]
        info = dev.info + "".join(i.text for i in inst.infos)
        members = {}
        for i in indices:
            e = InstElem(unit, inst.name, i, dev, dict(dev.attrs), info, len(unit.insts), inst.loc)
            unit.insts.append(e)
            members[i] = e
        group = InstGroup("inst", inst.array, members, inst.loc)
        unit.inst_groups[inst.name] = group
        elems = list(members.values())

        # New instance-level attributes.
        # PHDL 2.1 accepted these but then ignored them; here they take effect.
        for a in inst.attrs:
            up = a.name.upper()
            if a.deprecated_newattr:
                self.r.warning("W0504", "'newattr' is PHDL 2.0 syntax; use 'attr'", a.loc)
            if up in dev.attrs:
                self.r.error("E0502", f"attribute '{a.name}' is already declared by device '{dev.name}'", a.loc,
                             hint=f"to change its value write  {a.name} = \"{a.value}\";")
                continue
            if a.name != up:
                self.r.warning("W0203", f"attribute name '{a.name}' should be uppercase; it is treated as '{up}'", a.loc)
            for e in elems:
                e.attrs[up] = a.value

        # Attribute overrides.
        first_write: dict[tuple[int, str], Loc] = {}
        for ra in inst.ref_attrs:
            up = ra.name.upper()
            targets = self._targets(ra.qualifier, group, inst.name)
            if targets is None:
                continue
            if up not in targets[0].attrs:
                self.r.error("E0501", f"device '{dev.name}' has no attribute '{ra.name}'", ra.loc,
                             hint=f"to add a new attribute write  attr {up} = \"{ra.value}\";")
                continue
            for e in targets:
                key = (id(e), up)
                if key in first_write:
                    self.r.warning("W0503", f"attribute '{e.name_index}.{ra.name}' is set more than once; "
                                            "the last value is used", ra.loc,
                                   notes=[("first set here", first_write[key])])
                else:
                    first_write[key] = ra.loc
                e.attrs[up] = ra.value

        # Pin assignments.
        def lhs_bits(e: InstElem, a: ast.Assign):
            pg = dev.groups.get(a.target)
            if pg is None:
                self.r.error("E0406", f"device '{dev.name}' has no pin '{a.target}'", a.loc)
                return None
            return self._select(pg.bits, pg.vector, a.slices, f"pin '{a.target}'", a.loc)

        def connect(e: InstElem, b: DevicePin, conn: Conn | None, loc: Loc) -> None:
            key = f"{e.name_index}.{b.name}"
            if key in e.assigned:
                self.r.error("E0408", f"pin '{key}' is assigned more than once", loc,
                             notes=[("first assigned here", e.assigned[key])])
                return
            e.assigned[key] = loc
            if conn is not None:
                conn.pins.append((e, b))

        # Pins named in a rejected assignment are not reported again as unassigned.
        rejected: set[str] = set()
        for a in inst.assigns:
            if not self._assign(a, group, inst.name, unit, later, lambda e, a=a: lhs_bits(e, a), connect, "pin"):
                rejected.add(a.target)

        for e in elems:
            missing = sorted(f"{e.name_index}.{b.name}" for b in dev.pins
                             if f"{e.name_index}.{b.name}" not in e.assigned and b.base not in rejected)
            if missing:
                self.r.error("E0409", _not_assigned("pin", missing), inst.loc,
                             hint="every pin must be connected; assign unused pins to 'open'")

    # -- sub-design instances -------------------------------------------------

    def _sub_instance(self, si: ast.SubDesignInstance, unit: Unit, later: set[str]) -> None:
        node = self.scope.lookup("design", si.ref, unit.design.file, unit.design.package)
        if node is None:
            self.r.error("E0102", f"unknown subdesign '{'.'.join(si.ref)}'", si.ref_loc)
            return
        if not node.is_subdesign:
            self.r.error("E0111", f"'{node.name}' is a top-level design and cannot be instanced", si.ref_loc,
                         hint=f"declare it as 'subdesign {node.name}'")
            return
        if any(d is node for d in self._stack):
            self.r.error("E0110", f"hierarchy cycle: '{node.name}' instances itself", si.ref_loc,
                         notes=[(" -> ".join(d.name for d in self._stack + [node]), None)])
            return
        if not self._claim_instance_name(si.name, si.loc, unit):
            return

        indices = si.array.indices() if si.array else [None]
        members = {}
        self._stack.append(node)
        for k, i in enumerate(indices):
            child = Unit(node, si.name, i, unit, si.loc, seq=len(unit.subs),
                         nested_array=si.array is not None and not unit.is_top)
            self._unit(node, child)
            unit.subs.append(child)
            members[i] = child
        self._stack.pop()
        group = InstGroup("subinst", si.array, members, si.loc)
        unit.inst_groups[si.name] = group
        children = list(members.values())

        # Prefix: the quoted string, else attr REFPREFIX.
        prefix = ""
        for a in si.attrs:
            if a.name.upper() == "REFPREFIX":
                prefix = a.value
            else:
                self.r.warning("W0505", f"attribute '{a.name}' on a subdesign instance has no effect", a.loc,
                               hint="set attributes of parts inside it with  inst.ATTR = \"value\";")
        if si.prefix:
            prefix = si.prefix
        for c in children:
            c.own_prefix = prefix

        # Port assignments.
        def lhs_bits(child: Unit, a: ast.Assign):
            g = child.groups.get(a.target)
            if g is None or g.kind != "port":
                extra = " (it is a net, not a port)" if g is not None else ""
                self.r.error("E0407", f"subdesign '{node.name}' has no port '{a.target}'{extra}", a.loc)
                return None
            return self._select(g.bits, g.vector, a.slices, f"port '{a.target}'", a.loc)

        assigned: dict[tuple[int, str], Loc] = {}
        bidirectional = self.opt.merge_through_ports or not unit.is_top

        def connect(child: Unit, port: Conn, conn: Conn | None, loc: Loc) -> None:
            key = (id(child), port.name)
            if key in assigned:
                self.r.error("E0410", f"port '{child.name_index}.{port.name}' is assigned more than once", loc,
                             notes=[("first assigned here", assigned[key])])
                return
            assigned[key] = loc
            if conn is not None:
                conn.edges.append(port)
                if bidirectional:
                    port.edges.append(conn)

        rejected: set[str] = set()
        for a in si.assigns:
            if not self._assign(a, group, si.name, unit, later, lambda c, a=a: lhs_bits(c, a), connect, "port"):
                rejected.add(a.target)

        for child in children:
            missing = sorted(f"{child.name_index}.{p.name}" for p in child.conns
                             if p.kind == "port" and (id(child), p.name) not in assigned
                             and p.base not in rejected)
            if missing:
                self.r.error("E0411", _not_assigned("port", missing), si.loc,
                             hint="every port must be connected; assign unused ports to 'open'")

        # Attribute pushdown into the hierarchy.
        for sa in si.sub_attrs:
            targets = self._targets(sa.qualifier, group, si.name)
            if targets is not None:
                self._push_attr(sa, targets)

    def _push_attr(self, sa: ast.SubAttr, units: list[Unit]) -> None:
        """Apply  a(1).b.ATTR = "v";  to every instance the path selects."""
        *steps, attr_step = sa.path
        if attr_step.indices is not None:
            self.r.error("E0413", "an attribute name cannot have indices", attr_step.indices.loc)
            return
        current: list[Unit] = units
        elems: list[InstElem] | None = None
        for k, step in enumerate(steps):
            if elems is not None:
                self.r.error("E0506", f"'{steps[k - 1].name}' is a device instance; "
                                      f"'{step.name}' must be its last path segment", step.loc)
                return
            nxt: list = []
            for u in current:
                g = u.inst_groups.get(step.name)
                if g is None:
                    self.r.error("E0506", f"no instance named '{step.name}' in subdesign '{u.design.name}'", step.loc)
                    return
                members = list(g.members.values())
                if step.indices is not None:
                    if g.array is None:
                        self.r.error("E0413", f"'{step.name}' is not an array; indices are not allowed",
                                     step.indices.loc)
                        return
                    members = []
                    for i in step.indices.items:
                        if i not in g.members:
                            self.r.error("E0402", f"index {i} is out of range for '{step.name}' "
                                                  f"({_range_text(g.array)})", step.indices.loc)
                            return
                        members.append(g.members[i])
                nxt.extend(members)
                kind = g.kind
            if kind == "inst":
                elems = nxt
            else:
                current = nxt
        if elems is None:
            self.r.error("E0506", f"'{attr_step.name}' must follow a device instance in the path", attr_step.loc)
            return
        up = attr_step.name.upper()
        for e in elems:
            if up not in e.attrs:
                self.r.error("E0501", f"device '{e.device.name}' has no attribute '{attr_step.name}'", attr_step.loc)
                return
            e.attrs[up] = sa.value

    # -- design-level net assignment -----------------------------------------

    def _connection_assign(self, a: ast.Assign, unit: Unit, later: set[str]) -> None:
        g = self._group(a.target, a.loc, unit, later)
        rhs = self._rhs(a.concat, unit, later)
        if g is None or rhs is None:
            return
        lhs = self._select(g.bits, g.vector, a.slices, f"'{a.target}'", a.loc)
        if lhs is None:
            return
        kind, value = rhs
        if kind == "open":
            # PHDL 2.1 crashed on this.
            self.r.error("E0412", "a net cannot be assigned 'open'", a.concat.loc,
                         hint="'open' is only meaningful for pins and ports")
            return
        if kind == "list" and len(lhs) != len(value):
            self.r.error("E0404", f"width mismatch: '{a.target}' is {len(lhs)} bit{'s' if len(lhs) != 1 else ''} "
                                  f"wide but the right-hand side is {len(value)}", a.loc)
            return
        for k, c in enumerate(lhs):
            other = value[k] if kind == "list" else value
            if other is not c:
                c.edges.append(other)
                other.edges.append(c)
