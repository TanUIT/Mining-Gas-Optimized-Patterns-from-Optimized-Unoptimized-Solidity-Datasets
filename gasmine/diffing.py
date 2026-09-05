"""Section 3: extract diffs at multiple representation tiers.

Produces a :class:`PairDiff` bundling everything the Section 4a detectors and
the Section 4b clustering need: raw + normalized ASTs, structural shapes, the
source text unified diff, and gas-relevant opcode counts (optimized build).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import unified_diff
from typing import Any

from . import astutils, solc
from .dataset import Pair


@dataclass
class PairDiff:
    pair: Pair
    unopt_source: str
    opt_source: str
    ast_u_raw: dict
    ast_o_raw: dict
    ast_u: dict  # normalized
    ast_o: dict  # normalized
    text_diff: list[str] = field(default_factory=list)
    opcodes_u: dict[str, int] = field(default_factory=dict)
    opcodes_o: dict[str, int] = field(default_factory=dict)

    def shape_equal(self) -> bool:
        return astutils.shape_equal(self.ast_u, self.ast_o)

    def node_types_u(self) -> list[str]:
        return astutils.node_type_sequence(self.ast_u)

    def node_types_o(self) -> list[str]:
        return astutils.node_type_sequence(self.ast_o)


def _aggregate_opcode_counts(
    path, solc_version: str, optimize: bool = True
) -> dict[str, int]:
    """Sum gas-relevant opcode counts across every contract in a file."""
    per_contract = solc.compile_opcodes(
        path, solc_version=solc_version, optimize=optimize
    )
    total: dict[str, int] = {op: 0 for op in solc.GAS_RELEVANT_OPCODES}
    for opcode_string in per_contract.values():
        for op, n in solc.gas_relevant_counts(opcode_string).items():
            total[op] += n
    return total


def diff_pair(pair: Pair, solc_version: str = solc.DEFAULT_SOLC_VERSION) -> PairDiff:
    unopt_src = pair.unopt_source()
    opt_src = pair.opt_source()

    ast_u_raw = solc.compile_ast(pair.unopt_path, solc_version=solc_version)
    ast_o_raw = solc.compile_ast(pair.opt_path, solc_version=solc_version)

    text_diff = list(
        unified_diff(
            unopt_src.splitlines(),
            opt_src.splitlines(),
            fromfile="unoptimized.sol",
            tofile="optimized.sol",
            lineterm="",
        )
    )

    return PairDiff(
        pair=pair,
        unopt_source=unopt_src,
        opt_source=opt_src,
        ast_u_raw=ast_u_raw,
        ast_o_raw=ast_o_raw,
        ast_u=astutils.normalize_ast(ast_u_raw),
        ast_o=astutils.normalize_ast(ast_o_raw),
        text_diff=text_diff,
        opcodes_u=_aggregate_opcode_counts(pair.unopt_path, solc_version),
        opcodes_o=_aggregate_opcode_counts(pair.opt_path, solc_version),
    )
