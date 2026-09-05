"""End-to-end gas measurement test (requires solc + Foundry + network for the
one-time forge-std install). Skipped automatically when tools are missing."""
import shutil
from pathlib import Path

import pytest

from gasmine import dataset, gas

ROOT = Path(__file__).resolve().parent.parent / "dataset"

pytestmark = pytest.mark.skipif(
    shutil.which("forge") is None or shutil.which("solc") is None,
    reason="Foundry / solc toolchain not installed",
)


def test_measure_known_savings(tmp_path):
    pairs = {p.id: p for p in dataset.load_paired_dataset(ROOT)}
    subset = [pairs["002"], pairs["003"]]
    report = gas.measure(subset, harness_dir=tmp_path / "harness")

    by_pair = report.by_pair()
    assert "002" in by_pair and "003" in by_pair

    # 002 (require -> custom error): smaller bytecode => positive deploy saving.
    deploy_002 = next(m for m in by_pair["002"] if m.tag == "deploy")
    assert deploy_002.saved > 0

    # 003 (storage packing): fewer cold SSTOREs => large positive runtime saving.
    set_cold = next(m for m in by_pair["003"] if m.tag == "set_cold")
    assert set_cold.saved > 10_000
