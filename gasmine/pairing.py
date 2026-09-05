"""Section 2 (optional): pair unoptimized <-> optimized files by AST similarity.

Used only when the dataset is delivered as two flat directories that are *not*
matched by filename. Similarity uses Zhang-Shasha tree edit distance (``zss``)
over role-normalized ASTs, and one-to-one assignment uses maximum-weight
matching (``scipy.optimize.linear_sum_assignment``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
from zss import Node, simple_distance

from . import astutils, solc


@dataclass
class PairCandidate:
    unopt_path: Path
    opt_path: Path
    similarity: float


def _role_normalized_tree(ast: dict) -> Node:
    """Build a zss tree labelled only by nodeType (identifiers stripped)."""

    def build(node: Any) -> Node | None:
        if isinstance(node, dict):
            label = node.get("nodeType", "?")
            z = Node(label)
            for v in node.values():
                if isinstance(v, dict):
                    child = build(v)
                    if child is not None:
                        z.addkid(child)
                elif isinstance(v, list):
                    for item in v:
                        child = build(item)
                        if child is not None:
                            z.addkid(child)
            return z
        return None

    root = build(ast)
    return root if root is not None else Node("root")


def _tree_size(node: Node) -> int:
    return 1 + sum(_tree_size(c) for c in Node.get_children(node))


def similarity(ast_a: dict, ast_b: dict) -> float:
    """1 - normalized tree edit distance in [0, 1]."""
    ta = _role_normalized_tree(ast_a)
    tb = _role_normalized_tree(ast_b)
    dist = simple_distance(ta, tb)
    denom = max(_tree_size(ta), _tree_size(tb)) or 1
    return 1.0 - min(dist / denom, 1.0)


def pair_files(
    unopt_files: list[Path],
    opt_files: list[Path],
    solc_version: str = solc.DEFAULT_SOLC_VERSION,
) -> list[PairCandidate]:
    """Return the best one-to-one matching as PairCandidates (desc similarity)."""
    unopt_asts = [
        astutils.normalize_ast(solc.compile_ast(p, solc_version)) for p in unopt_files
    ]
    opt_asts = [
        astutils.normalize_ast(solc.compile_ast(p, solc_version)) for p in opt_files
    ]

    n, m = len(unopt_files), len(opt_files)
    sim = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            sim[i, j] = similarity(unopt_asts[i], opt_asts[j])

    # linear_sum_assignment minimizes cost -> use (1 - similarity).
    rows, cols = linear_sum_assignment(1.0 - sim)
    candidates = [
        PairCandidate(unopt_files[i], opt_files[j], float(sim[i, j]))
        for i, j in zip(rows, cols)
    ]
    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates
