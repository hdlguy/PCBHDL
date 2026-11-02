# PHDL 2.1 regression corpus

This directory contains PHDL 2.1 designs and test cases from the original
PHDL project at Brigham Young University. PCBHDL uses them as a regression
suite to make sure it stays source-compatible with PHDL 2.1.

**License:** everything in this directory is distributed under the
GNU General Public License, version 3 (see [`COPYING`](COPYING)), as it was
in the original project. The rest of the PCBHDL repository is MIT-licensed;
the compiler only reads these files as input data and does not incorporate
them.

The files are unmodified copies, apart from this README.

## Provenance

| Directory | Source (SVN, revision 507, 2014-05-10) |
|---|---|
| `tests/`    | `https://svn.code.sf.net/p/phdl/svn/trunk/phdl-2.1/tests/resources` |
| `examples/` | `https://svn.code.sf.net/p/phdl/svn/trunk/misc/projects/Working-2.1-Examples` |
| `COPYING`   | `https://svn.code.sf.net/p/phdl/svn/trunk/COPYING` |

Project home: <https://sourceforge.net/p/phdl/>

PHDL was created at the BYU Department of Electrical and Computer
Engineering. Contributors include Brent Nelson, Brad Riching,
Richard Black, Wesley Landaker, Pete Dudley and others.

## Contents

- `tests/*Test/` — feature tests from the PHDL 2.1 test suite. Several
  contain deliberately invalid code that the compiler must reject.
- `tests/GeneratorTest/*/` — small designs with `golden.*` output files
  produced by the PHDL 2.1 compiler (`.net` XML netlist, PADS `.asc`,
  EAGLE `.scr`, `.bom`, `.rdm`, `.lsi`).
- `tests/ExamplesTest/` and `examples/` — complete board designs
  (ptzlanc, fmc_module, atlys, seven segment, voice modulator, RC circuit).
  Some include the original compiler outputs. The `.php` files are
  HTML-formatted listings of the sources from the old project website.
