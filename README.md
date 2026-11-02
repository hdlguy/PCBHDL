# PCBHDL

A hardware description language compiler for printed circuit boards.
Describe which parts are on a board and how their pins connect in plain
text, the way you would instance blocks in an FPGA design, and compile it
to a netlist for KiCad or other layout tools. No schematic drawing.

PCBHDL is a new implementation of **PHDL 2.1**, the PCB HDL developed at
Brigham Young University. It reads PHDL 2.1 source unchanged and is checked
against PHDL's own test suite and example boards.

* [Install](#install)
* [Quick start](#quick-start)
* [Writing a design](#writing-a-design)
* [Compiling](#compiling)
* [Errors and warnings](#errors-and-warnings)
* [Taking the netlist into KiCad](#taking-the-netlist-into-kicad)
* [Compiling existing PHDL boards](#compiling-existing-phdl-boards)
* [Project layout and development](#project-layout-and-development)

Further documentation:

* [Language reference](docs/language.md): complete syntax, semantics and every diagnostic code
* [Compatibility with PHDL 2.1](docs/compatibility.md): what is reproduced exactly and which PHDL 2.1 bugs are fixed

## Install

Requires Python 3.10 or newer.

```
git clone <this repository> PCBHDL
cd PCBHDL
python3 -m venv .venv
.venv/bin/pip install -e .
```

This installs the `pcbhdl` command into `.venv/bin`. Either run it as
`.venv/bin/pcbhdl`, or activate the environment once per shell:

```
source .venv/bin/activate
pcbhdl --version
```

Java is **not** needed. (It is only used to regenerate the parser after
changing the grammar; see [development](#project-layout-and-development).)

## Quick start

Compile the example board and write a KiCad netlist and a BOM:

```
pcbhdl -f kicad -f bom -o out examples/preamp
```

```
wrote out/preamp.net
wrote out/preamp.bom
```

Then in the KiCad PCB editor, open or create a board and use
**File > Import > Netlist**, select `out/preamp.net`, and click
**Load and Test Netlist**, then **Update PCB**. The footprints appear
with their ratsnest, ready to place and route.

The example is two files:

* [`examples/preamp/parts.phdl`](examples/preamp/parts.phdl): the device
  definitions (an LM358, 0603 resistors and capacitors, a 3-pin header),
  using footprints from the standard KiCad libraries;
* [`examples/preamp/preamp.phdl`](examples/preamp/preamp.phdl): the board,
  a two-channel inverting preamp built from a reusable `gain_stage`
  subdesign.

## Writing a design

A board is described in one or more `.phdl` files. They contain three kinds
of things: **devices** (the parts you can use), **subdesigns** (reusable
blocks, like modules) and one **design** (the board).

### 1. Describe each part as a device

A device gives the part's attributes and maps its logical pins to the
physical pins (pads) of its footprint:

```
device LM358 {
    attr REFPREFIX = "U";                          // reference designator prefix
    attr LIBRARY   = "Package_SO";                 // footprint library
    attr FOOTPRINT = "SOIC-8_3.9x4.9mm_P1.27mm";   // footprint name
    attr VALUE     = "LM358";                      // any other attr becomes a BOM column
    outpin[1:2] out  = {1, 7};      // out[1] is pad 1, out[2] is pad 7
    inpin[1:2]  in_n = {2, 6};
    inpin[1:2]  in_p = {3, 5};
    pwrpin      vcc  = {8};
    pwrpin      gnd  = {4};
}
```

`REFPREFIX`, `LIBRARY` and `FOOTPRINT` are required. For KiCad, `LIBRARY`
and `FOOTPRINT` are the KiCad footprint library and footprint name. The
pin type (`inpin`, `outpin`, `pwrpin`, `passpin`, ... or plain `pin`) is
used by the electrical rule check.

Devices are usually kept in a separate file inside a `package`, and
imported where they are used:

```
package parts {
    device LM358 { ... }
    device R_0603 { ... }
}
```

```
import parts.*;
```

### 2. Describe the board as a design

```
import parts.*;

design preamp {
    net vcc, gnd, vref;          // declare nets before using them
    net[1:2] in, out, in_n;      // vector nets: in[1], in[2]

    inst u1 of LM358 {
        out  = out;              // pin = net
        in_n = in_n;
        in_p = <vref>;           // <x> repeats one net to every bit
        vcc  = vcc;
        gnd  = gnd;
    }

    inst cdec of C_0603 { VALUE = "100n"; a = vcc; b = gnd; }
    inst j_pwr of HDR_1x03 { p = {vcc, gnd, vref}; }   // {...} concatenates
    ...
}
```

The rules that catch most mistakes:

* **Every pin of every instance must be assigned exactly once.** Write
  `pin = open;` for a pin that is intentionally unconnected.
* **Widths must match.** A 3-bit pin needs 3 bits on the right-hand side.
* **Nets are declared before the statements that use them.**

### 3. Use arrays and subdesigns to avoid repetition

An instance array creates several identical parts:

```
inst(1:8) r of R_0603 {
    VALUE = "330";
    a = vcc;                  // without combine: every r(i).a goes to vcc
    combine(b) = led[1:8];    // with combine: r(1).b = led[1], ..., r(8).b = led[8]
    this(8).VALUE = "1k";     // change just one element
}
```

A subdesign is a reusable block with ports, instanced with `subinst`:

```
subdesign gain_stage {
    port in, in_n, out;
    inst rin of R_0603 { VALUE = "10k";  a = in;   b = in_n; }
    inst rf  of R_0603 { VALUE = "100k"; a = in_n; b = out;  }
}

design preamp {
    ...
    subinst(1:2) ch of gain_stage {
        combine(in) = in;            // ports are assigned like pins
        combine(in_n) = in_n;
        combine(out) = out;
        this(2).rf.VALUE = "47k";    // reach inside to change a part's attribute
    }
}
```

### 4. Leave notes for the layout designer

`info { "..." }` blocks are kept (unlike `// comments`) and collected into
the `.lsi` file for whoever lays out the board:

```
inst(1:14) cap_vcco of C_0603 {
    ...
    info { "Place these caps next to the VCCO_0 pins of the FPGA." }
}
```

`info` can be written on a design, a net, a device or an instance.

See the [language reference](docs/language.md) for the complete language.

## Compiling

```
pcbhdl [options] FILE_OR_DIRECTORY...
```

Give it all the `.phdl` files of the board, or a directory (searched
recursively). Every `design` found is compiled, and each produces its own
set of output files, named after the design.

| Option | Meaning |
|---|---|
| *(no `-f`)* | check the design only; nothing is written |
| `-f FORMAT` | write an output; repeat for several formats |
| `-o DIR` | output directory (default: current directory) |
| `-t NAME`, `--top NAME` | compile only the design with this name |
| `--refdes flat` | reference designators R1, R2, ... across the whole board (default) |
| `--refdes phdl` | PHDL 2.1 hierarchical designators such as `CH1/R2` |
| `--diagnostics json` | print errors and warnings as JSON |
| `-W` | hide warnings |

Output formats:

| `-f` | File | Use |
|---|---|---|
| `kicad` | `<design>.net` | KiCad PCB editor: File > Import > Netlist |
| `bom` | `<design>.bom` | bill of materials (comma separated) |
| `json` | `<design>.netlist.json` | complete neutral netlist, for scripts and other tools |
| `lsi` | `<design>.lsi` | layout notes collected from `info` blocks |
| `rdm` | `<design>.rdm` | map from reference designator to hierarchical instance |
| `pads` | `<design>.asc` | Mentor PADS netlist |
| `eagle` | `<design>.scr` | EAGLE script |
| `phdl-xml` | `<design>.net` | PHDL 2.1 XML netlist (legacy) |

`kicad` and `phdl-xml` both use the `.net` extension; write them to
different directories if you need both.

Reference designators: parts with a fixed `REFDES` attribute keep it, and
the rest are numbered in design order: top-level parts first, then each
subdesign instance in turn, so a channel's parts get consecutive numbers.

## Errors and warnings

The compiler reports every problem it finds, with the source line, a
stable error code and often a hint:

```
preamp.phdl:20:10: error[E0409]: pin 'u1.gnd' is not assigned
   20 |     inst u1 of LM358 {
      |          ^^
  hint: every pin must be connected; assign unused pins to 'open'
preamp.phdl:31:30: error[E0404]: width mismatch: pin 'p' is 3 bits wide but the right-hand side is 2
   31 |     inst j_in  of HDR_1x03 { p = {in[1], in[2]}; }
      |                              ^
pcbhdl: compilation failed with 2 error(s)
```

If there are errors, no output files are written and the exit status is 1.

Warnings do not stop compilation. The most common ones come from the
**electrical rule check**, which runs on the finished netlist:

* `W0701`: a net connects to fewer than two pins (often a typo in a net name);
* `W0702` / `W0703`: a pin-type conflict, such as two outputs driving the
  same net or a `ncpin` that is connected.

With `--diagnostics json` the same information is printed as JSON
(file, line, column, code, message, hint), which is convenient for editor
integration, scripts and AI assistants. Every code is listed in the
[language reference](docs/language.md#diagnostics).

## Taking the netlist into KiCad

1. `pcbhdl -f kicad -o out board/`
2. In the KiCad PCB editor: **File > Import > Netlist**, choose
   `out/<design>.net`, **Load and Test Netlist**, **Update PCB**.
3. After changing the design, compile again and repeat step 2. Each part
   has a stable identity derived from its place in the design hierarchy,
   so parts you have already placed stay where they are, even if their
   reference designators change.

**Footprints.** The KiCad footprint is `LIBRARY:FOOTPRINT` from the
device's attributes. If you want to keep `LIBRARY`/`FOOTPRINT` for
another tool, add `attr KICAD_FOOTPRINT = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm";`,
which takes precedence. The library must be in your KiCad footprint library
table.

**Checking footprints before import.** `tools/kicad_check.py` uses KiCad's
own Python API to confirm that every footprint exists and has a pad for
every pin. It can also write a starter board with the footprints placed in
a grid:

```
pcbhdl -f json -o out examples/preamp
/usr/bin/python3 tools/kicad_check.py out/preamp.netlist.json -o out/preamp.kicad_pcb
```

```
12 parts, 9 nets checked: OK
wrote out/preamp.kicad_pcb
```

Run it with the system Python that KiCad is installed for, not the
`.venv`. It looks for footprints in `/usr/share/kicad/footprints`; set
`KICAD_FOOTPRINT_DIR` to use another location. (On a machine with a
custom wxWidgets build in `/usr/local/lib`, prefix the command with
`LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu` so KiCad's Python module
loads.)

## Compiling existing PHDL boards

PHDL 2.1 files compile unchanged. To keep the reference designators the
old compiler assigned, use `--refdes phdl`:

```
pcbhdl --refdes phdl -f kicad -f bom -o out old_board/
```

The output also includes two things PHDL 2.1 silently dropped: `attr`
written on an instance now appears in the BOM, and `info` written on an
instance now appears in the `.lsi` file. See
[compatibility](docs/compatibility.md) for the details.

## Project layout and development

```
.phdl files ─▶ ANTLR 4 parser ─▶ AST ─▶ elaborator ─▶ hierarchy ─▶ flatten ─▶ neutral netlist ─▶ back ends
                                         (checks)                  (nets,      (pcbhdl/netlist.py)   kicad, bom,
                                                                    refdes, ERC)                     pads, ...
```

| Path | Contents |
|---|---|
| `pcbhdl/grammar/Phdl.g4` | ANTLR 4 grammar |
| `pcbhdl/_generated/` | parser generated from the grammar (committed) |
| `pcbhdl/frontend.py`, `pcbhdl/ast.py` | parsing, AST |
| `pcbhdl/elaborate.py` | name resolution, hierarchy, semantic checks |
| `pcbhdl/flatten.py` | net formation, reference designators, ERC |
| `pcbhdl/netlist.py` | the neutral netlist: the only thing back ends see |
| `pcbhdl/backends/` | one module per output format |
| `examples/` | example designs |
| `regression/phdl21/` | PHDL 2.1 test suite and example boards (GPLv3, see below) |
| `tests/` | pytest suite |

Run the tests:

```
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

After changing the grammar, regenerate the parser (needs Java; the ANTLR
jar is downloaded into `tools/` on first use):

```
.venv/bin/python tools/gen_parser.py
```

To support another layout tool, add a module to `pcbhdl/backends/` with
`NAME`, `EXTENSION` and `generate(netlist) -> str`, and register it in
`pcbhdl/backends/__init__.py`. Back ends receive only the neutral
`Netlist`, never the source language.

## License

PCBHDL is MIT licensed (see [`LICENSE`](LICENSE)).

The PHDL 2.1 regression corpus in [`regression/phdl21`](regression/phdl21)
is copied unmodified from the original PHDL project and remains under the
GNU GPL v3; see its [README](regression/phdl21/README.md) for provenance.
PCBHDL only reads those files as test input.
