from pathlib import Path

from gasmine import dataset

ROOT = Path(__file__).resolve().parent.parent / "dataset"


def test_paired_layout_detected():
    assert dataset.is_paired_layout(ROOT)


def test_load_paired_dataset():
    pairs = dataset.load_paired_dataset(ROOT)
    ids = {p.id for p in pairs}
    assert {"001", "002", "003", "004", "005", "006", "007", "008", "009"} <= ids
    for p in pairs:
        assert p.unopt_path.exists()
        assert p.opt_path.exists()


def test_meta_and_calls_parsed():
    pairs = {p.id: p for p in dataset.load_paired_dataset(ROOT)}
    vault = pairs["001"]
    assert vault.contract == "Vault"
    assert vault.erc == "20"
    assert vault.calls[0].expect_revert is True

    averager = pairs["005"]
    assert averager.calls[0].setup[0]["method"] == "seed"

    cfg = pairs["008"]
    assert cfg.constructor_args == ["100"]
