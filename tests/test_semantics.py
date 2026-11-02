"""Behaviour tests on small inline designs, including the PHDL 2.1 bugs PCBHDL fixes."""
from __future__ import annotations

import json

from pcbhdl.backends import BACKENDS
from pcbhdl.compiler import compile_files
from pcbhdl.diagnostics import Reporter
from pcbhdl.elaborate import Options
from pcbhdl.netlist import Netlist

DEVICES = """
device R {
    attr REFPREFIX = "R"; attr LIBRARY = "Resistor_SMD"; attr FOOTPRINT = "R_0603_1608Metric";
    attr VALUE = "10k";
    pin a = {1}; pin b = {2};
}
device U {
    attr REFPREFIX = "U"; attr LIBRARY = "lib"; attr FOOTPRINT = "SOIC8";
    inpin[3:0] d = {1,2,3,4}; pwrpin vcc = {8}; pwrpin gnd = {5}; outpin y = {6}; ncpin nc = {7};
}
"""


def compile_src(tmp_path, src: str, **kw):
    f = tmp_path / "t.phdl"
    f.write_text(DEVICES + src)
    r = Reporter()
    return compile_files([f], r, **kw), r


def nets_by_name(netlist: Netlist) -> dict[str, list[str]]:
    return {n.name: [f"{x.refdes}.{x.pin}" for x in n.nodes] for n in netlist.nets}


def codes(r: Reporter) -> list[str]:
    return [d.code for d in r.diagnostics]


def test_vector_bits_and_concatenation(tmp_path):
    out, r = compile_src(tmp_path, """
design top {
    net vcc, gnd; net[1:0] bus; net y;
    inst u of U { d = {bus, vcc, gnd}; vcc = vcc; gnd = gnd; y = y; nc = open; }
    inst(1:2) r of R { a = y; combine(b) = bus; }
}""")
    assert out, r.render_text()
    nets = nets_by_name(out[0])
    # d[3:0] = {bus[1], bus[0], vcc, gnd}  ->  pins 1..4
    assert nets["bus[1]"] == ["U1.1", "R1.2"]
    assert nets["bus[0]"] == ["U1.2", "R2.2"]
    assert nets["vcc"] == ["U1.3", "U1.8"]
    assert nets["y"] == ["U1.6", "R1.1", "R2.1"]


def test_unassigned_and_width_errors(tmp_path):
    out, r = compile_src(tmp_path, """
design top {
    net[2:0] n;
    inst r of R { a = n; }
}""")
    assert out is None
    assert set(codes(r)) == {"E0404", "E0409"}  # width mismatch; pin b unassigned


def test_net_used_before_declaration(tmp_path):
    out, r = compile_src(tmp_path, """
design top {
    net a;
    inst r of R { a = a; b = late; }
    net late;
}""")
    assert out is None
    assert codes(r) == ["E0305"]


def test_shorts_through_subdesign_are_merged(tmp_path):
    src = """
subdesign link { port p, q; p = q; }
design top {
    net n1, n2;
    inst r1 of R { a = n1; b = open; }
    inst r2 of R { a = n2; b = open; }
    subinst s of link { p = n1; q = n2; }
}"""
    out, r = compile_src(tmp_path, src)
    assert out, r.render_text()
    nets = nets_by_name(out[0])
    assert nets["n1"] == ["R1.1", "R2.1"]
    assert "n2" not in nets
    assert out[0].nets[0].aliases == ["s/p", "s/q", "n2"]
    # PHDL 2.1 kept them as two nets (shorted on the board, but not in the netlist).
    out, r = compile_src(tmp_path, src, options=Options(merge_through_ports=False))
    nets = nets_by_name(out[0])
    assert nets["n1"] == ["R1.1"] and nets["n2"] == ["R2.1"]


def test_net_assigned_open_is_an_error(tmp_path):
    out, r = compile_src(tmp_path, "design top { net n; n = open; }")
    assert out is None and codes(r) == ["E0412"]


def test_instance_attributes_and_pushdown_fan_out(tmp_path):
    out, r = compile_src(tmp_path, """
subdesign leaf { port p; inst r of R { a = p; b = p; } }
subdesign mid { port p; subinst(1:2) l of leaf "L" { p = p; } }
design top {
    net n;
    subinst(1:2) m of mid "M" { p = n; l.r.VALUE = "4k7"; }
    inst x of R { attr TOLERANCE = "1%"; VALUE = "1k"; a = n; b = n; }
}""")
    assert out, r.render_text()
    parts = {p.refdes: p for p in out[0].parts}
    # Pushdown reaches every element of both arrays (PHDL 2.1 crashed here).
    assert sorted(p.attributes["VALUE"] for p in parts.values()) == ["1k", "4k7", "4k7", "4k7", "4k7"]
    assert parts["R1"].attributes["TOLERANCE"] == "1%"
    assert "M1/L1/R1" in parts and "M2/L2/R1" in parts
    bom = BACKENDS["bom"].generate(out[0])
    assert bom.splitlines()[0] == "QUANTITY, NAME, REFDES, LIBRARY, FOOTPRINT, TOLERANCE, VALUE"


def test_duplicate_refdes_is_an_error(tmp_path):
    out, r = compile_src(tmp_path, """
device C { attr REFPREFIX = "C"; attr LIBRARY = "l"; attr FOOTPRINT = "f"; attr REFDES = ""; pin a = {1}; }
design top {
    net n;
    inst a of C { REFDES = "C1"; a = n; }
    inst b of C { REFDES = "C1"; a = n; }
}""")
    assert out is None and codes(r) == ["E0601"]


def test_refdes_override_needs_declared_attribute(tmp_path):
    out, r = compile_src(tmp_path, """
design top { net n; inst a of R { REFDES = "R7"; a = n; b = n; } }""")
    assert out is None and codes(r) == ["E0501"]


def test_erc_warns_but_does_not_fail(tmp_path):
    out, r = compile_src(tmp_path, """
design top {
    net vcc, gnd; net[3:0] d; net y;
    inst u1 of U { d = d; vcc = vcc; gnd = gnd; y = y; nc = y; }
    inst u2 of U { d = d; vcc = vcc; gnd = gnd; y = y; nc = open; }
}""")
    assert out is not None
    assert "W0703" in codes(r)        # outputs driving each other / NC pin connected


def test_json_round_trip_and_kicad(tmp_path):
    out, r = compile_src(tmp_path, """
design top { net a, b; inst r of R { a = a; b = b; } }""")
    nl = out[0]
    again = Netlist.from_dict(json.loads(nl.to_json()))
    assert again.to_json() == nl.to_json()
    kicad = BACKENDS["kicad"].generate(nl)
    assert kicad.count("(") == kicad.count(")")
    assert '(footprint "Resistor_SMD:R_0603_1608Metric")' in kicad
    assert '(node (ref "R1") (pin "1") (pinfunction "a") (pintype "passive"))' in kicad
    # Timestamps are stable across compiles.
    assert BACKENDS["kicad"].generate(compile_src(tmp_path, """
design top { net a, b; inst r of R { a = a; b = b; } }""")[0][0]) == kicad


def test_syntax_error_is_reported_with_location(tmp_path):
    out, r = compile_src(tmp_path, "design top { net a }")
    assert out is None
    d = r.diagnostics[0]
    assert d.code == "E0001" and d.loc.line == DEVICES.count("\n") + 1
