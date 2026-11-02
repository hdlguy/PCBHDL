"""PHDL 2.1 compatibility regression, using the corpus in regression/phdl21.

Golden files were mangled when they were stored in the original project
(CRLF line endings, missing final newline), so comparisons normalise both.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcbhdl.backends import BACKENDS
from pcbhdl.compiler import compile_files
from pcbhdl.diagnostics import Reporter
from pcbhdl.elaborate import Options
from pcbhdl.frontend import parse_file

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "regression" / "phdl21"
LEGACY = {"net": "phdl-xml", "asc": "pads", "scr": "eagle", "bom": "bom", "rdm": "rdm", "lsi": "lsi"}

# Outputs that differ from PHDL 2.1 on purpose, because PCBHDL fixes a PHDL
# 2.1 bug. Each entry: (board, extension) -> reason.
INTENTIONAL = {
    ("atlys", "bom"): "instance-level 'attr' is honoured (PHDL 2.1 dropped it)",
    ("atlys", "lsi"): "instance-level 'info' is written (PHDL 2.1 dropped it)",
    ("ptzlanc", "bom"): "instance-level 'attr' is honoured (PHDL 2.1 dropped it)",
    ("voice_modulator", "bom"): "instance-level 'attr' is honoured (PHDL 2.1 dropped it)",
    ("voice_modulator", "lsi"): "instance-level 'info' is written (PHDL 2.1 dropped it)",
    ("voicemod", "lsi"): "instance-level 'info' is written (PHDL 2.1 dropped it)",
}


def norm(text: str) -> str:
    return text.replace("\r", "").rstrip("\n") + "\n"


def compile_ok(files) -> list:
    r = Reporter()
    netlists = compile_files(files, r, options=Options(refdes_style="phdl"))
    assert netlists is not None, r.render_text()
    return netlists


def test_whole_corpus_parses():
    files = sorted(CORPUS.rglob("*.phdl"))
    assert len(files) == 61
    r = Reporter()
    for f in files:
        assert parse_file(f, r) is not None, r.render_text()


GENERATOR_TESTS = sorted(p.name for p in (CORPUS / "tests" / "GeneratorTest").iterdir())


@pytest.mark.parametrize("ext", sorted(LEGACY))
@pytest.mark.parametrize("case", GENERATOR_TESTS)
def test_generator_goldens(case, ext):
    d = CORPUS / "tests" / "GeneratorTest" / case
    (netlist,) = compile_ok([d / "test.phdl"])
    golden = (d / f"golden.{ext}").read_text()
    assert norm(BACKENDS[LEGACY[ext]].generate(netlist)) == norm(golden)


BOARDS = ["atlys", "fmc_module", "ptzlanc", "seven_segment", "voice_modulator"]


@pytest.mark.parametrize("ext", sorted(LEGACY))
@pytest.mark.parametrize("board", BOARDS)
def test_boards_match_phdl21_compiler(board, ext):
    """Outputs of the PHDL 2.1 compiler on the ExamplesTest boards."""
    (netlist,) = compile_ok(sorted((CORPUS / "tests" / "ExamplesTest" / board).glob("*.phdl")))
    ref = CORPUS / "reference" / board / f"{netlist.output_name}.{ext}"
    if (board, ext) in INTENTIONAL:
        pytest.xfail(INTENTIONAL[(board, ext)])
    assert norm(BACKENDS[LEGACY[ext]].generate(netlist)) == norm(ref.read_text())


EXAMPLE_GOLDENS = [
    ("sevenseg", ["ss_Control.phdl", "ss_Devices.phdl"], "ss_Control"),
    ("voicemod", ["vm_amp.phdl", "vm_design.phdl", "vm_devices.phdl", "vm_modulator.phdl"], "vm_design"),
    ("ptzlanc", None, "ptzlanc"),
    ("rc_circuit", ["rc_complete.phdl"], "top"),
]


@pytest.mark.parametrize("ext", ["net", "bom", "lsi"])
@pytest.mark.parametrize("example,files,stem", EXAMPLE_GOLDENS)
def test_example_goldens(example, files, stem, ext):
    """Goldens from the PHDL project's own examples (only formats that were stable across PHDL builds)."""
    d = CORPUS / "examples" / example
    golden = d / f"{stem}.{ext}"
    if not golden.exists():
        pytest.skip("no golden")
    paths = [d / f for f in files] if files else sorted(d.glob("*.phdl"))
    (netlist,) = compile_ok(paths)
    if (example, ext) in INTENTIONAL:
        pytest.xfail(INTENTIONAL[(example, ext)])
    assert norm(BACKENDS[LEGACY[ext]].generate(netlist)) == norm(golden.read_text())


EXPECTED_LINES = json.loads((ROOT / "tests" / "data" / "phdl21_diagnostic_lines.json").read_text())

# PHDL 2.1 reports an error on both copies of a duplicate physical pin;
# PCBHDL reports one error with a note pointing at the first copy.
NOTE_INSTEAD_OF_ERROR = {"tests/DeviceTest/testPhysicalPins.phdl": {5}}


@pytest.mark.parametrize("path", sorted(EXPECTED_LINES))
def test_diagnostics_on_same_lines_as_phdl21(path):
    r = Reporter()
    compile_files([CORPUS / path], r, run_erc=False)
    errors = {d.loc.line for d in r.diagnostics if d.severity.value == "error" and d.loc}
    warnings = {d.loc.line for d in r.diagnostics if d.severity.value == "warning" and d.loc}
    notes = {l.line for d in r.diagnostics for _, l in d.notes if l}
    expected = set(EXPECTED_LINES[path]["error_lines"])
    note_lines = NOTE_INSTEAD_OF_ERROR.get(path, set())
    assert errors == expected - note_lines
    assert note_lines <= notes
    assert warnings == set(EXPECTED_LINES[path]["warning_lines"])
