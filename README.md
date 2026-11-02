# PCBHDL

A hardware description language compiler for printed circuit boards.
Describe which parts are on a board and how their pins connect in plain
text, the way you would instance blocks in an FPGA design, and compile it
to a netlist for KiCad or other layout tools. No schematic drawing.

PCBHDL is a new implementation of **PHDL 2.1**, the PCB HDL developed at
Brigham Young University. It is source-compatible with PHDL 2.1 and is
checked against PHDL's own test suite and example boards.

```
design preamp {
    net vcc, gnd, vref;
    net[1:2] in, out, in_n;

    inst u1 of LM358 { out = out; in_n = in_n; in_p = <vref>; vcc = vcc; gnd = gnd; }
    inst(1:2) rdiv of R_0603 { VALUE = "10k"; combine(a) = {vcc, gnd}; b = <vref>; }

    subinst(1:2) ch of gain_stage "CH" {
        combine(in) = in; combine(in_n) = in_n; combine(out) = out;
        this(2).rf.VALUE = "47k";
    }
    ...
}
```

The complete example is in [`examples/preamp`](examples/preamp).

## Install

```
python3 -m venv .venv
.venv/bin/pip install -e .
```

Requires Python 3.10+. Java is needed only to regenerate the parser from
the grammar (`python tools/gen_parser.py`); the generated parser is
committed.

## Use

```
pcbhdl examples/preamp                              # check only
pcbhdl -f kicad -f bom -o out examples/preamp       # out/preamp.net, out/preamp.bom
pcbhdl --diagnostics json board/*.phdl              # machine-readable errors
```

In the KiCad PCB editor, load the result with **File > Import > Netlist**.
Footprints are named `LIBRARY:FOOTPRINT` from the device attributes (or
`KICAD_FOOTPRINT`, if set). Each part gets a stable UUID derived from its
hierarchical instance path, so re-importing after a change keeps your
placement.

`tools/kicad_check.py` uses KiCad's own Python API to check that every
footprint exists and has a pad for every pin, and can write a starter
`.kicad_pcb`.

Other formats: `json` (neutral netlist), `pads`, `eagle`, `bom`, `rdm`,
`lsi`, and `phdl-xml` (legacy PHDL netlist). See
[`docs/language.md`](docs/language.md).

## How it works

```
.phdl files ──ANTLR 4 parser──▶ AST ──elaborator──▶ hierarchy ──flatten──▶ neutral netlist ──▶ back ends
                                       (checks)                 (nets, refdes,   (pcbhdl/netlist.py)   kicad, pads,
                                                                 ERC)                                  eagle, bom, ...
```

| Path | Contents |
|---|---|
| `pcbhdl/grammar/Phdl.g4` | ANTLR 4 grammar |
| `pcbhdl/frontend.py`, `pcbhdl/ast.py` | parsing, AST |
| `pcbhdl/elaborate.py` | name resolution, hierarchy, semantic checks |
| `pcbhdl/flatten.py` | net formation, reference designators, ERC |
| `pcbhdl/netlist.py` | the neutral netlist: the only thing back ends see |
| `pcbhdl/backends/` | one module per output format |
| `regression/phdl21/` | PHDL 2.1 test suite and boards (GPLv3, see below) |
| `tests/` | pytest suite |

Adding a layout tool means adding one module to `pcbhdl/backends/` that
turns a `Netlist` into text.

## Documentation

* [Language reference](docs/language.md): syntax, semantics and every diagnostic code
* [Compatibility with PHDL 2.1](docs/compatibility.md): what is reproduced exactly and which PHDL 2.1 bugs are fixed

## License

PCBHDL is MIT licensed (see [`LICENSE`](LICENSE)).

The PHDL 2.1 regression corpus in [`regression/phdl21`](regression/phdl21)
is copied unmodified from the original PHDL project and remains under the
GNU GPL v3; see its [README](regression/phdl21/README.md) for provenance.
PCBHDL only reads those files as test input.
