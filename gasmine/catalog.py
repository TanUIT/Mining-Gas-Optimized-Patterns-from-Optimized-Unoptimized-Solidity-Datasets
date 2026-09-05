"""Section 6: aggregate labels + gas into a reusable ``catalog.json``."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Optional

from .dataset import Pair
from .detectors import PATTERN_META
from .gas import GasMeasurement


@dataclass
class PairResult:
    pair: Pair
    labels: list[str]
    measurements: list[GasMeasurement] = field(default_factory=list)

    def deploy(self) -> Optional[GasMeasurement]:
        for m in self.measurements:
            if m.tag == "deploy":
                return m
        return None

    def runtime(self) -> list[GasMeasurement]:
        return [m for m in self.measurements if m.tag != "deploy"]


def _confidence(n: int, deploy_savings: list[int]) -> str:
    positive = bool(deploy_savings) and all(s > 0 for s in deploy_savings)
    if n >= 3 and positive:
        return "high"
    if n >= 2:
        return "medium"
    return "low"


def _mean_int(values: list[float]) -> int:
    return int(round(mean(values))) if values else 0


def _mean_pct(values: list[float]) -> float:
    return round(mean(values), 2) if values else 0.0


def build_catalog(results: list[PairResult]) -> dict:
    """Return ``{"patterns": [...], "uncategorized": [...]}``."""
    labels = sorted({lbl for r in results for lbl in r.labels if lbl != "uncategorized"})

    patterns = []
    for label in labels:
        members = [r for r in results if label in r.labels]
        deploy_ms = [m for r in members if (m := r.deploy())]
        deploy_savings = [m.saved for m in deploy_ms]
        deploy_pcts = [m.saved_pct for m in deploy_ms]
        runtime_ms = [m for r in members for m in r.runtime()]
        runtime_savings = [m.saved for m in runtime_ms]
        runtime_pcts = [m.saved_pct for m in runtime_ms]
        ercs = sorted({str(r.pair.erc) for r in members if r.pair.erc})
        meta = PATTERN_META.get(label, {})

        patterns.append(
            {
                "pattern_id": label,
                "erc": ercs,
                "n_instances_in_dataset": len(members),
                "avg_deploy_gas_saved": _mean_int(deploy_savings),
                "avg_deploy_gas_saved_pct": _mean_pct(deploy_pcts),
                "avg_runtime_gas_saved": _mean_int(runtime_savings),
                "avg_runtime_gas_saved_pct": _mean_pct(runtime_pcts),
                "confidence": _confidence(len(members), deploy_savings),
                "detector_rule": meta.get("detector_rule", ""),
                "recommended_fix": meta.get("recommended_fix", ""),
                "example_pair": members[0].pair.directory.as_posix(),
                "instances": [r.pair.id for r in members],
            }
        )

    patterns.sort(key=lambda p: (-p["n_instances_in_dataset"], p["pattern_id"]))

    uncategorized = [
        {"id": r.pair.id, "pair": r.pair.directory.as_posix()}
        for r in results
        if r.labels == ["uncategorized"]
    ]

    return {"patterns": patterns, "uncategorized": uncategorized}
