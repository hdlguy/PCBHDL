# Compatibility with PHDL 2.1

PCBHDL accepts PHDL 2.1 source unchanged. It is checked against the
PHDL 2.1 test suite and example boards in
[`regression/phdl21`](../regression/phdl21) (see `tests/`):

* all 61 `.phdl` files parse;
* the 5 `GeneratorTest` designs reproduce all 30 golden files byte for byte;
* the 5 example boards (atlys, fmc_module, ptzlanc, seven_segment,
  voice_modulator) produce the same PADS, EAGLE, XML netlist and refdes map
  as the PHDL 2.1 compiler, so net names, pin order and reference
  designators are unchanged;
* the error test cases are flagged on the same lines as PHDL 2.1.

## Where PCBHDL deliberately differs

These are PHDL 2.1 bugs. Each one changes output only for designs that hit
the bug.

| PHDL 2.1 | PCBHDL |
|---|---|
| `attr X = "..."` inside an `inst` was accepted and then ignored. | The attribute is added to the instance and appears in the BOM. This restores the behaviour of the earlier PHDL build that produced the original example outputs. |
| `info { ... }` inside an `inst` was ignored. | It is written to the `.lsi` file after the device's info. |
| Two top-level nets joined only inside a subdesign (for example by `p = q;` between two ports) stayed two separate nets in the netlist. | They are merged into one net, named after the first-declared top-level net. `Options(merge_through_ports=False)` restores the old behaviour. |
| A path attribute (`a.b.ATTR = "v";`) reaching more than one sub-instance crashed. | It applies to every instance the path selects. |
| A path attribute changed the BOM but not the netlist footprint, library or refdes. | The final attribute values are used everywhere. |
| `net = open;` crashed. | Error E0412. |
| A duplicate REFDES was only logged. | Error E0601. |
| An unassigned pin produced one error per pin. | One error per instance lists the unassigned pins. |
| Errors caused by an earlier error (for example "unassigned" after a rejected assignment) were reported. | They are suppressed. |
| A duplicate physical pin produced two errors. | One error, with a note at the first use. |
| `newattr` (PHDL 2.0) was a syntax error. | Accepted as `attr`, with a deprecation warning. |
| Imports of missing packages were silently accepted. | Warning W0104. |

## Kept for compatibility

These PHDL 2.1 behaviours are reproduced because existing designs and
their outputs depend on them:

* Net naming: of several joined nets, the first declared at the highest
  level names the net.
* Pin order inside nets: statement order at the top level, instance then
  device-pin order inside sub-designs. Neighbouring sub-instance arrays at
  the top level sort by text (`s(10)` before `s(2)`).
* Reference designator numbering, including prefix forms such as `A//R1`
  for a prefixless sub-instance inside a prefixed one, and numbering of
  parts inside sub-designs before top-level parts.
* The `phdl-xml` netlist identifies nets by bare name and keeps only the
  first net of each name, as PHDL 2.1 did. Use the `kicad` or `json`
  back ends for complete netlists.
