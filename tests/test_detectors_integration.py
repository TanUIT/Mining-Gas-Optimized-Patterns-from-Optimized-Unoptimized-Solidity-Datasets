"""Integration tests: run solc + detectors over the sample dataset.

Skipped automatically when the solc toolchain is unavailable.
"""
import shutil
from pathlib import Path

import pytest

from gasmine import dataset, detectors, diffing

ROOT = Path(__file__).resolve().parent.parent / "dataset"

pytestmark = pytest.mark.skipif(
    shutil.which("solc") is None
    or shutil.which("solc-select") is None
    or not ROOT.exists(),
    reason="solc toolchain and/or sample dataset/ not available",
)

EXPECTED = {
    "001": "revert-string-shortening",
    "002": "require-to-custom-error",
    "003": "storage-packing",
    "004": "unchecked-arithmetic",
    "005": "loop-length-caching",
    "006": "calldata-vs-memory",
    "007": "external-visibility",
    "008": "immutable-constant",
}


@pytest.fixture(scope="module")
def labels_by_id():
    out = {}
    for pair in dataset.load_paired_dataset(ROOT):
        d = diffing.diff_pair(pair)
        out[pair.id] = detectors.classify_diff(d)
    return out


@pytest.mark.parametrize("pid,expected", EXPECTED.items())
def test_expected_label_detected(labels_by_id, pid, expected):
    assert expected in labels_by_id[pid], (pid, labels_by_id[pid])


def test_rename_only_is_uncategorized(labels_by_id):
    assert labels_by_id["009"] == ["uncategorized"]


def test_preincrement_also_detected(labels_by_id):
    assert "preincrement" in labels_by_id["004"]
