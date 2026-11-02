# PCBHDL language reference

PCBHDL compiles **PHDL 2.1**, a text language for describing the
connectivity of a printed circuit board: which parts are on the board and
which pins are connected. It replaces schematic capture. Placement and
routing are still done in a layout tool such as KiCad.

This page is a complete, compact reference. The [examples](../examples) and
the [PHDL 2.1 regression designs](../regression/phdl21) show it in use.

## Files, packages and imports

A design is any number of `.phdl` files compiled together. Every file sees
every other file.

```
package parts {            // optional namespace
    device R_0603 { ... }
}

import parts.*;            // file-level: everything in package 'parts'
import parts.R_0603;       // or one element
```

Root-level devices and designs (outside any package) are visible
everywhere. A package element is visible by its simple name inside its own
package or where it has been imported; it is always visible by its
qualified name, e.g. `inst r of parts.R_0603 { ... }`.

Comments are `// ...` and `/* ... */`. Strings use `"..."` or `'...'`
with Java-style escapes.

## Names

* **Device, pin, net and port names** may be identifiers (`vcc`, `D_IN`)
  or pin-number-like tokens: `42`, `1A`, `+3V3`, `GND/2`, `EXP-IO_P`.
  Characters allowed: letters, digits, `_ + - $ / @ !`.
* **Design, package, instance and attribute names** are identifiers:
  a letter or `_`, then letters, digits or `_`.

## Devices

A device declares a part: its attributes and how its logical pins map to
physical pins (pads).

```
device LM358 {
    attr REFPREFIX = "U";                         // required: refdes prefix
    attr LIBRARY   = "Package_SO";                // required
    attr FOOTPRINT = "SOIC-8_3.9x4.9mm_P1.27mm";  // required
    attr VALUE     = "LM358";                     // any other attribute: BOM column
    outpin[1:2] out  = {1, 7};    // vector pin: out[1] is pad 1, out[2] is pad 7
    inpin[1:2]  in_n = {2, 6};
    pwrpin      vcc  = {8};
    pin         gnd  = {4};
    info { "Free text for the layout designer." }
}
```

* Pin types (used by the electrical rule check): `pin` (untyped),
  `inpin`, `outpin`, `iopin`, `pwrpin` (power input), `suppin` (power
  supply output), `ocpin` (open collector), `oepin` (open emitter),
  `tripin` (tri-state), `passpin` (passive), `ncpin` (no connect).
* A vector pin `pin[msb:lsb] x = {p, q, ...}` lists physical pins in the
  order the indices are written: `[3:0]` maps x[3], x[2], x[1], x[0].
* Attribute names are case-insensitive and normalised to uppercase.
* Special attributes: `REFPREFIX`, `REFDES` (a fixed reference
  designator; the device must declare `attr REFDES = "";` before an
  instance can set it), `LIBRARY`, `FOOTPRINT`, `PINCOUNT` (optional;
  checked against the number of declared pins), `KICAD_FOOTPRINT`
  (optional; a full `Library:Footprint` for the KiCad back end).

## Designs and subdesigns

```
design board { ... }        // a top-level design: one board, one netlist
subdesign filter { ... }    // a reusable block, used with 'subinst'
```

Inside, statements are processed in order. **Nets and ports must be
declared before they are used.**

```
net vcc, gnd;                    // scalar nets
net[7:0] data;                   // vector net: data[7] ... data[0]
net clk { attr CLASS = "fast"; info { "50 MHz" } }
port in, out;                    // subdesign interface (subdesigns only)
info { "Text for the layout designer." }
```

## Instances

```
inst u1 of LM358 {
    VALUE = "LM358A";            // override a device attribute
    attr ORDER_CODE = "123-456"; // add an attribute to this instance
    out  = {sig1, sig2};         // pin = net expression
    in_n = n[2:1];
    vcc  = vcc;
    gnd  = gnd;
    in_p = open;                 // explicitly unconnected
}
```

**Every pin of every instance must be assigned exactly once.** Use
`open` for unused pins.

### Instance arrays

```
inst(1:8) r of R_0603 {
    a = vcc;                      // broadcast: every element's 'a' to vcc
    combine(b) = led[1:8];        // spread: r(1).b = led[1], ..., r(8).b = led[8]
    this(1).VALUE = "1k";         // only element 1
    this(2:8).VALUE = "4k7";      // elements 2..8
}
```

Without `combine`, the right-hand side is applied to each element
separately, so its width must equal the pin's width. With `combine`, the
selected pins of all elements are concatenated (element order) and matched
against the right-hand side.

## Net expressions (right-hand sides)

| Form | Meaning |
|---|---|
| `n` | all bits of n, in declaration order |
| `n[3:1]`, `n[0,2,5]` | selected bits, in the order written |
| `{a, b[1:0], c}` or `a & b[1:0] & c` | concatenation, left to right |
| `<n>` or `n*` | one bit, repeated to the width of the left-hand side |
| `open` | not connected (pins and ports only) |

Bit k of the left-hand side connects to bit k of the right-hand side,
counting from the first-written index.

## Connecting nets

```
gnd_a = gnd;            // join two nets (they become one electrical net)
bus[1:0] = {x, y};
```

When nets are joined, the one declared first gives the net its name.

## Sub-design instances

```
subinst(1:2) ch of gain_stage "CH" {   // "CH" prefixes refdes: CH1/R1, CH2/R1, ...
    combine(in) = in;                  // ports are assigned like pins
    out = <vout>;
    this(2).rf.VALUE = "47k";          // set an attribute deep inside (path to an inst)
}
```

* The optional string is the reference designator prefix for parts inside;
  `attr REFPREFIX = "CH";` in the body does the same.
* Every port must be assigned (`open` is allowed).
* A path like `amp(1).stage.rf.VALUE = "1k";` sets an attribute on the
  instance it names, through any number of levels; without indices it
  applies to every element of an array.

## Reference designators

Parts with a fixed `REFDES` are reserved first. The rest are numbered
`REFPREFIX` + the smallest free number. Parts inside sub-designs with a
prefix are named `PREFIX[index]/REFPREFIXn`, e.g. `CH1/R2`. Numbering
follows PHDL 2.1, so existing PHDL designs keep their reference designators.

## Outputs

| Format (`-f`) | File | Use |
|---|---|---|
| `kicad` | `.net` | KiCad PCB editor: File > Import > Netlist |
| `json` | `.netlist.json` | neutral netlist for scripts and other tools |
| `bom` | `.bom` | bill of materials |
| `pads` | `.asc` | Mentor PADS |
| `eagle` | `.scr` | EAGLE script |
| `rdm` | `.rdm` | refdes → hierarchical instance path |
| `lsi` | `.lsi` | layout notes collected from `info` blocks |
| `phdl-xml` | `.net` | PHDL 2.1 XML netlist (legacy; nets by bare name only) |

## Diagnostics

Each diagnostic has a stable code. `--diagnostics json` prints them as
JSON (file, line, column, code, message, hint) for tools and AI agents.

| Code | Meaning |
|---|---|
| E0001 | syntax error |
| E0101 | duplicate device or design |
| E0102 | unknown device or subdesign |
| E0103 | invalid import |
| E0110 / E0111 | hierarchy cycle / a `design` used as a subdesign |
| E0120 | no top-level design with the name given to `--top` |
| E0201 | device lacks REFPREFIX, LIBRARY or FOOTPRINT |
| E0204 / E0205 | PINCOUNT not an integer / does not match the pins |
| E0206 | pin width differs from its number of physical pins |
| E0207 / E0208 | physical pin used twice / duplicate name in a device |
| E0301 | `port` in a top-level design |
| E0302 / E0303 | duplicate net or port / duplicate instance name |
| E0306 | attributes on a port |
| E0304 / E0305 | unknown net / net used before its declaration |
| E0401 | `this(...)` on something that is not an array |
| E0402 | index out of range |
| E0403 | slice of a scalar |
| E0404 | width mismatch |
| E0405 | replicating more than one bit |
| E0406 / E0407 | unknown pin / unknown port |
| E0408 / E0410 | pin / port assigned twice |
| E0409 / E0411 | pin / port not assigned |
| E0412 | net assigned `open` |
| E0413 | indices on something that is not an array |
| E0501 | unknown attribute |
| E0502 | `attr` re-declares a device attribute |
| E0506 | invalid attribute path |
| E0601 | duplicate reference designator |
| W0104 | imported package or element not found |
| W0121 | no top-level design found |
| W0202 / W0203 | lowercase REFPREFIX value / attribute name |
| W0209 | attribute differs from another only in case (ignored) |
| W0503 | attribute set more than once |
| W0504 | `newattr` (PHDL 2.0 syntax) |
| W0505 | attribute on a subinst has no effect |
| W0701 | net with fewer than two pins |
| W0702 / W0703 | pin type conflict (warning / error level), e.g. two outputs |
