"""Section 1: input data structure.

Canonical layout (already paired)::

    dataset/
      001_long_reason_string/
        unoptimized.sol
        optimized.sol
        meta.json        # optional

Unpaired layout (needs Section 2 pairing first)::

    dataset/
      unoptimized/*.sol
      optimized/*.sol
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

UNOPT_NAME = "unoptimized.sol"
OPT_NAME = "optimized.sol"
META_NAME = "meta.json"


@dataclass
class Call:
    """A runtime call to measure gas for (Section 5).

    ``setup`` lists unmeasured calls run on both contracts before the measured
    call (e.g. seed storage with ``setData(50)`` before measuring ``sum()``).
    """

    name: str
    method: str
    args: list[str] = field(default_factory=list)
    expect_revert: bool = False
    setup: list[dict[str, Any]] = field(default_factory=list)
    prelude: str = ""  # raw Solidity statements run before setup (builds locals)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Call":
        return cls(
            name=d["name"],
            method=d["method"],
            args=[str(a) for a in d.get("args", [])],
            expect_revert=bool(d.get("expect_revert", False)),
            setup=[
                {"method": s["method"], "args": [str(a) for a in s.get("args", [])]}
                for s in d.get("setup", [])
            ],
            prelude=str(d.get("prelude", "")),
        )


@dataclass
class Pair:
    """A single optimized/unoptimized example."""

    id: str
    name: str
    directory: Path
    unopt_path: Path
    opt_path: Path
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def contract(self) -> str:
        """Main contract name (used for Foundry import aliasing)."""
        return self.meta.get("contract", "")

    @property
    def erc(self) -> Optional[str]:
        return self.meta.get("erc")

    @property
    def tag_hint(self) -> Optional[str]:
        return self.meta.get("tag_hint")

    @property
    def constructor_args(self) -> list[str]:
        return [str(a) for a in self.meta.get("constructor_args", [])]

    @property
    def calls(self) -> list[Call]:
        return [Call.from_dict(c) for c in self.meta.get("calls", [])]

    def unopt_source(self) -> str:
        return self.unopt_path.read_text()

    def opt_source(self) -> str:
        return self.opt_path.read_text()


def _read_meta(directory: Path, default_id: str) -> dict[str, Any]:
    meta_path = directory / META_NAME
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        meta = {}
    meta.setdefault("id", default_id)
    return meta


def is_paired_layout(root: Path) -> bool:
    """True when `root` contains per-example subdirectories with both files."""
    for child in root.iterdir():
        if child.is_dir() and (child / UNOPT_NAME).exists() and (child / OPT_NAME).exists():
            return True
    return False


def load_paired_dataset(root: str | Path) -> list[Pair]:
    """Load a pre-paired dataset (Section 1)."""
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"dataset root not found: {root}")

    pairs: list[Pair] = []
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        unopt = child / UNOPT_NAME
        opt = child / OPT_NAME
        if not (unopt.exists() and opt.exists()):
            continue
        # Directory names look like "001_long_reason_string".
        did = child.name.split("_", 1)[0]
        meta = _read_meta(child, default_id=did)
        pairs.append(
            Pair(
                id=str(meta.get("id", did)),
                name=child.name,
                directory=child,
                unopt_path=unopt,
                opt_path=opt,
                meta=meta,
            )
        )
    return pairs


def load_unpaired_dataset(root: str | Path) -> tuple[list[Path], list[Path]]:
    """Load an unpaired dataset: (unoptimized_files, optimized_files).

    Feed the result to :func:`gasmine.pairing.pair_files`.
    """
    root = Path(root)
    unopt_dir = root / "unoptimized"
    opt_dir = root / "optimized"
    if not unopt_dir.exists() or not opt_dir.exists():
        raise FileNotFoundError(
            f"expected {unopt_dir} and {opt_dir} for an unpaired dataset"
        )
    unopt = sorted(unopt_dir.glob("*.sol"))
    opt = sorted(opt_dir.glob("*.sol"))
    return unopt, opt
