"""scripts/topology_rules.py: check's exit codes and a draw smoke test (graph-layout task 7)."""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("topology_rules", ROOT / "scripts" / "topology_rules.py")
topology_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(topology_rules)


def test_check_passes_on_shipped_files(capsys):
    assert topology_rules.main(["check"]) == 0
    assert "all checks passed" in capsys.readouterr().out


def test_check_fails_with_full_report_on_broken_copy(tmp_path, capsys):
    text = (ROOT / "rules" / "topology" / "classic_eq.toml").read_text(encoding="utf-8")
    text = text.replace('kind = "deep",     size = "huge"', 'kind = "deep",     size = "big"')
    text = text.replace("apply = { loop = 3, ring = 1 }", "apply = { loop = 3, rng = 1 }")
    bad = tmp_path / "classic_eq.toml"
    bad.write_text(text, encoding="utf-8")
    assert topology_rules.main(["check", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "start_nodes[2].size" in out and "apply.rng" in out


def test_draw_writes_parseable_page(tmp_path):
    assert topology_rules.main(["draw", "classic_eq", "--out", str(tmp_path),
                                "--example-rooms", "8"]) == 0
    page = (tmp_path / "classic_eq.html").read_text(encoding="utf-8")
    svgs = re.findall(r"<svg.*?</svg>", page, re.S)
    for s in svgs:
        ET.fromstring(s)
    # legend, start graph, one per rule (base + fitting layers), example graph
    base = topology_rules.load_rule_set(ROOT / "rules" / "topology" / "classic_eq.toml")
    n_rules = len(base.rules) + sum(len(l.rules) for l in topology_rules.fitting_layers(base))
    assert len(svgs) == 2 + n_rules + 1
    assert 'id="rule-shortcut"' in page and 'id="rule-nave"' in page
