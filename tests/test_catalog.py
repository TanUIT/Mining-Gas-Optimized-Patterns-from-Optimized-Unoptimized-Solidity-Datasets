from pathlib import Path

from gasmine.catalog import PairResult, build_catalog
from gasmine.dataset import Pair
from gasmine.gas import GasMeasurement


def _pair(pid: str, erc=None) -> Pair:
    d = Path(f"dataset/{pid}")
    return Pair(
        id=pid,
        name=pid,
        directory=d,
        unopt_path=d / "unoptimized.sol",
        opt_path=d / "optimized.sol",
        meta={"erc": erc} if erc else {},
    )


def test_gas_measurement_math():
    m = GasMeasurement(pair_id="x", tag="deploy", unopt_gas=1000, opt_gas=750)
    assert m.saved == 250
    assert round(m.saved_pct, 1) == 25.0


def test_build_catalog_aggregates_and_scores_confidence():
    results = [
        PairResult(
            pair=_pair("001", "20"),
            labels=["storage-read-caching"],
            measurements=[
                GasMeasurement("001", "deploy", 1000, 900),
                GasMeasurement("001", "call", 500, 400),
            ],
        ),
        PairResult(
            pair=_pair("002", "721"),
            labels=["storage-read-caching"],
            measurements=[GasMeasurement("002", "deploy", 2000, 1800)],
        ),
        PairResult(
            pair=_pair("003"),
            labels=["storage-read-caching"],
            measurements=[GasMeasurement("003", "deploy", 3000, 2700)],
        ),
        PairResult(pair=_pair("009"), labels=["uncategorized"], measurements=[]),
    ]

    catalog = build_catalog(results)
    assert [u["id"] for u in catalog["uncategorized"]] == ["009"]

    entry = next(p for p in catalog["patterns"] if p["pattern_id"] == "storage-read-caching")
    assert entry["n_instances_in_dataset"] == 3
    # deploy savings: (100, 200, 300) -> mean 200
    assert entry["avg_deploy_gas_saved"] == 200
    # runtime savings: only pair 001 has a call -> 100
    assert entry["avg_runtime_gas_saved"] == 100
    # 3 instances, all-positive deploy savings -> high confidence
    assert entry["confidence"] == "high"
    assert sorted(entry["erc"]) == ["20", "721"]
    assert entry["detector_rule"]  # metadata populated
    assert entry["recommended_fix"]


def test_confidence_low_for_single_instance():
    results = [
        PairResult(
            pair=_pair("001"),
            labels=["preincrement"],
            measurements=[GasMeasurement("001", "deploy", 100, 90)],
        )
    ]
    entry = build_catalog(results)["patterns"][0]
    assert entry["confidence"] == "low"
