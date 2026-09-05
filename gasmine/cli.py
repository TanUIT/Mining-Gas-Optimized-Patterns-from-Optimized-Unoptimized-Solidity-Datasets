"""Command-line orchestrator: ``python -m gasmine ...``.

Subcommands:
  run     - full pipeline: diff -> classify -> gas -> catalog
  pair    - Section 2: match an unpaired dataset by AST similarity
  cluster - Section 4b: cluster diffs to surface unknown patterns
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import clustering, dataset, detectors, diffing, gas, pairing, solc
from .catalog import PairResult, build_catalog


def _pair_report(result: PairResult) -> dict:
    deploy = result.deploy()
    runtime = {
        m.tag: {
            "unopt": m.unopt_gas,
            "opt": m.opt_gas,
            "saved": m.saved,
            "saved_pct": round(m.saved_pct, 2),
        }
        for m in result.runtime()
    }
    return {
        "id": result.pair.id,
        "name": result.pair.name,
        "erc": result.pair.erc,
        "labels": result.labels,
        "deploy": (
            {
                "unopt": deploy.unopt_gas,
                "opt": deploy.opt_gas,
                "saved": deploy.saved,
                "saved_pct": round(deploy.saved_pct, 2),
            }
            if deploy
            else None
        ),
        "runtime": runtime,
    }


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.dataset)
    if not dataset.is_paired_layout(root):
        print(
            f"ERROR: {root} is not a paired dataset. Run `gasmine pair` first.",
            file=sys.stderr,
        )
        return 2

    pairs = dataset.load_paired_dataset(root)
    if not pairs:
        print(f"ERROR: no pairs found under {root}", file=sys.stderr)
        return 2
    print(f"Loaded {len(pairs)} pair(s) from {root}")

    diffs = []
    labels_by_pair: dict[str, list[str]] = {}
    for pair in pairs:
        d = diffing.diff_pair(pair, solc_version=args.solc_version)
        labels = detectors.classify_diff(d)
        diffs.append(d)
        labels_by_pair[pair.id] = labels
        print(f"  [{pair.id}] {pair.name}: {', '.join(labels)}")

    report = gas.GasReport()
    if not args.no_gas:
        print("Measuring gas with Foundry ...")
        report = gas.measure(
            pairs,
            harness_dir=args.harness,
            solc_version=args.solc_version,
            optimizer_runs=args.optimizer_runs,
        )
    gas_by_pair = report.by_pair()

    results = [
        PairResult(
            pair=pair,
            labels=labels_by_pair[pair.id],
            measurements=gas_by_pair.get(pair.id, []),
        )
        for pair in pairs
    ]

    catalog = build_catalog(results)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2))
    (out / "pairs.json").write_text(
        json.dumps([_pair_report(r) for r in results], indent=2)
    )

    if args.cluster:
        cres = clustering.cluster_diffs(diffs, min_cluster_size=args.min_cluster_size)
        (out / "clusters.json").write_text(json.dumps(cres.clusters, indent=2))
        print(f"Clusters: {cres.clusters}")

    print(f"\nCatalog: {len(catalog['patterns'])} pattern(s) -> {out / 'catalog.json'}")
    for p in catalog["patterns"]:
        print(
            f"  {p['pattern_id']:<26} n={p['n_instances_in_dataset']} "
            f"deploy_saved={p['avg_deploy_gas_saved']} "
            f"runtime_saved={p['avg_runtime_gas_saved']} "
            f"conf={p['confidence']}"
        )
    if catalog["uncategorized"]:
        print(f"  uncategorized: {[u['id'] for u in catalog['uncategorized']]}")
    return 0


def cmd_pair(args: argparse.Namespace) -> int:
    unopt, opt = dataset.load_unpaired_dataset(args.dataset)
    print(f"Pairing {len(unopt)} unoptimized x {len(opt)} optimized files ...")
    candidates = pairing.pair_files(unopt, opt, solc_version=args.solc_version)

    out = Path(args.out)
    with out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["unopt_path", "opt_path", "similarity_score", "review"])
        for c in candidates:
            review = "REVIEW" if c.similarity < args.threshold else ""
            writer.writerow(
                [str(c.unopt_path), str(c.opt_path), f"{c.similarity:.4f}", review]
            )
            print(f"  {c.similarity:.3f}  {c.unopt_path.name} <-> {c.opt_path.name}")
    print(f"Wrote {out}")
    return 0


def cmd_cluster(args: argparse.Namespace) -> int:
    pairs = dataset.load_paired_dataset(args.dataset)
    diffs = [diffing.diff_pair(p, solc_version=args.solc_version) for p in pairs]
    cres = clustering.cluster_diffs(diffs, min_cluster_size=args.min_cluster_size)
    Path(args.out).write_text(json.dumps(cres.clusters, indent=2))
    print(f"Clusters: {cres.clusters}")
    print(f"Wrote {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gasmine", description=__doc__)
    parser.add_argument(
        "--solc-version", default=solc.DEFAULT_SOLC_VERSION, help="solc version to use"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="full pipeline")
    run.add_argument("--dataset", default="dataset")
    run.add_argument("--out", default="out")
    run.add_argument("--harness", default=".gasmine_foundry")
    run.add_argument("--optimizer-runs", type=int, default=200)
    run.add_argument("--no-gas", action="store_true", help="skip Foundry gas step")
    run.add_argument("--cluster", action="store_true", help="also run clustering")
    run.add_argument("--min-cluster-size", type=int, default=2)
    run.set_defaults(func=cmd_run)

    pair = sub.add_parser("pair", help="pair an unpaired dataset by AST similarity")
    pair.add_argument("--dataset", default="dataset")
    pair.add_argument("--out", default="pairs.csv")
    pair.add_argument("--threshold", type=float, default=0.5)
    pair.set_defaults(func=cmd_pair)

    cluster = sub.add_parser("cluster", help="cluster diffs (Section 4b)")
    cluster.add_argument("--dataset", default="dataset")
    cluster.add_argument("--out", default="clusters.json")
    cluster.add_argument("--min-cluster-size", type=int, default=2)
    cluster.set_defaults(func=cmd_cluster)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
