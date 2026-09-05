"""Section 4b (optional): data-driven discovery of unknown patterns.

Each diff is represented as a TF-IDF vector over the concatenated AST-node-type
sequences of both sides (a light, dependency-free stand-in for a code-embedding
model such as CodeBERT). Clusters are found with HDBSCAN, which does not need a
predefined cluster count and marks outliers as ``-1``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from .diffing import PairDiff


@dataclass
class ClusterResult:
    labels: list[int]
    pair_ids: list[str]
    clusters: dict[int, list[str]] = field(default_factory=dict)


def _diff_document(d: PairDiff) -> str:
    return " ".join(d.node_types_u() + d.node_types_o())


def cluster_diffs(diffs: list[PairDiff], min_cluster_size: int = 2) -> ClusterResult:
    docs = [_diff_document(d) for d in diffs]
    pair_ids = [d.pair.id for d in diffs]

    vectorizer = TfidfVectorizer(token_pattern=r"[A-Za-z_]+")
    x = vectorizer.fit_transform(docs).toarray()

    hdb = HDBSCAN(min_cluster_size=min_cluster_size, copy=True)
    labels = hdb.fit_predict(x).tolist()

    clusters: dict[int, list[str]] = {}
    for pid, lbl in zip(pair_ids, labels):
        clusters.setdefault(int(lbl), []).append(pid)

    return ClusterResult(labels=labels, pair_ids=pair_ids, clusters=clusters)
