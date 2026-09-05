# Mining Gas-Optimized Patterns from Optimized/Unoptimized Solidity Datasets

A pipeline that turns a dataset of `unoptimized.sol` / `optimized.sol` pairs into
a **reusable catalog of gas-optimization patterns**, each with a detector rule
and experimentally measured gas savings.

The pipeline is intentionally staged so each part is usable on its own:

| Stage | Module | Purpose |
|------|--------|---------|
| §1 Dataset | `gasmine/dataset.py` | Discover/normalize the dataset layout + `meta.json`. |
| §2 Pairing *(optional)* | `gasmine/pairing.py` | Match unpaired files by AST similarity (tree edit distance + optimal assignment). |
| §3 Diffing | `gasmine/diffing.py`, `gasmine/astutils.py`, `gasmine/solc.py` | Source / AST / opcode diff of each pair. |
| §4a Detectors | `gasmine/detectors.py` | Rule-based labelling of each diff. |
| §4b Clustering *(optional)* | `gasmine/clustering.py` | TF-IDF + HDBSCAN discovery of unknown patterns. |
| §5 Gas | `gasmine/gas.py` | Foundry-based deploy + runtime gas measurement. |
| §6 Catalog | `gasmine/catalog.py` | Aggregate labels + gas into `catalog.json`. |
| CLI | `gasmine/cli.py` | Orchestrate the stages. |

## Requirements

- Python 3.12 with the packages in [`requirements.txt`](requirements.txt).
- [`solc`](https://github.com/ethereum/solidity) managed by
  [`solc-select`](https://github.com/crytic/solc-select) (default `0.8.30`).
- [Foundry](https://book.getfoundry.sh/) (`forge`) for gas measurement.

The Cloud Agent environment installs all of the above automatically. Locally:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pipx install solc-select && solc-select install 0.8.30 && solc-select use 0.8.30
curl -L https://foundry.paradigm.xyz | bash && foundryup
```

## Dataset layout

Pre-paired (preferred):

```
dataset/
  001_revert_string/
    unoptimized.sol
    optimized.sol
    meta.json        # optional
```

Unpaired (needs §2 first): two flat directories `dataset/unoptimized/*.sol` and
`dataset/optimized/*.sol`.

`meta.json` drives contract selection and gas measurement:

```json
{
  "id": "003",
  "erc": "20",
  "tag_hint": "struct-packing",
  "source": "manual",
  "contract": "Packer",
  "constructor_args": ["100"],
  "calls": [
    {
      "name": "stats",
      "method": "stats",
      "args": [],
      "setup": [{ "method": "seed", "args": ["30"] }],
      "prelude": "uint256[] memory xs = new uint256[](8);",
      "expect_revert": false
    }
  ]
}
```

- `contract` — main contract name (both files must define it; imported aliased
  as `U`/`O`). Falls back to the first contract in the AST.
- `calls` — runtime calls to benchmark. `setup` runs unmeasured beforehand;
  `prelude` injects raw Solidity to build local args; `expect_revert` wraps the
  call in `try/catch` to measure the revert path.

## Usage

```bash
# Full pipeline: diff -> classify -> gas -> catalog (writes out/)
python -m gasmine run --dataset dataset --out out

# Skip the Foundry step (labels only)
python -m gasmine run --no-gas

# Also run unsupervised clustering (§4b)
python -m gasmine run --cluster

# Pair an unpaired dataset (§2) -> pairs.csv
python -m gasmine pair --dataset dataset --out pairs.csv

# Cluster diffs on their own (§4b)
python -m gasmine cluster --dataset dataset --out clusters.json
```

Outputs:

- `out/catalog.json` — aggregated pattern catalog (see below).
- `out/pairs.json` — per-pair labels + deploy/runtime gas.
- `out/clusters.json` — cluster membership (with `--cluster`).

## Catalog schema (`out/catalog.json`)

```json
{
  "patterns": [
    {
      "pattern_id": "storage-packing",
      "erc": ["20"],
      "n_instances_in_dataset": 1,
      "avg_deploy_gas_saved": -42364,
      "avg_deploy_gas_saved_pct": -30.66,
      "avg_runtime_gas_saved": 43897,
      "avg_runtime_gas_saved_pct": 49.6,
      "confidence": "low",
      "detector_rule": "more sub-256-bit elementary type declarations in optimized",
      "recommended_fix": "Pack struct/state fields into fewer 32-byte storage slots.",
      "example_pair": "dataset/003_storage_packing",
      "instances": ["003"]
    }
  ],
  "uncategorized": [{ "id": "009", "pair": "dataset/009_rename_only" }]
}
```

Deploy gas and runtime gas are reported separately (they trade off — e.g.
storage packing costs deploy gas but saves runtime gas). `confidence` is
`high`/`medium`/`low` from instance count and sign consistency.

## Built-in detectors (§4a)

`revert-string-shortening`, `require-to-custom-error`, `storage-packing`,
`unchecked-arithmetic`, `loop-length-caching`, `calldata-vs-memory`,
`preincrement`, `immutable-constant`, `external-visibility`,
`storage-read-caching`. Each is a small predicate in `gasmine/detectors.py`
with an entry in `PATTERN_META` (rule + recommended fix).

## Design decisions / trade-offs

- **Isolated gas measurement.** Each side of a pair is measured in its own
  Foundry test so both share a symmetric EIP-2929 cold/warm baseline. Measuring
  both in one test made the second (warm) call look ~2500 gas cheaper.
- **Clustering uses TF-IDF, not CodeBERT.** §4b vectorizes AST-node-type
  sequences with TF-IDF + scikit-learn HDBSCAN to keep the environment light and
  reproducible (no torch/transformers). Swap in an embedding backend if the
  dataset grows large enough to warrant it.
- **Opcode tier via `solc --opcodes`.** SLOAD/SSTORE/etc. counts come from
  parsing solc's opcode dump rather than adding a `pyevmasm` dependency.
- **Optimizer sensitivity.** Some patterns (`preincrement`, `unchecked` loop
  counters, `public`→`external`) show ~0 runtime delta at `optimizer_runs=200`
  because the optimizer already normalizes them; deploy gas still differs. Vary
  `--optimizer-runs` to study this.

## Downstream uses of the catalog (§6)

1. **Slither/linter detector** — flag un-optimized patterns in new contracts.
2. **Auto-rewriter** — AST transforms that apply a learned pattern.
3. **Benchmark suite** — the generated `Compare_*.t.sol` tests as a public gas
   benchmark.

## Tests

```bash
python -m pytest -q
```

Unit tests cover AST normalization, dataset loading, and catalog aggregation.
Integration tests (auto-skipped without the toolchain) run solc + detectors over
the sample dataset and a Foundry gas measurement.

## Note on the sample dataset

`dataset/` ships **9 small example pairs** (one per detector, plus one
`uncategorized` rename) so the pipeline runs end-to-end out of the box. Replace
it with your real corpus and re-run `python -m gasmine run`.
