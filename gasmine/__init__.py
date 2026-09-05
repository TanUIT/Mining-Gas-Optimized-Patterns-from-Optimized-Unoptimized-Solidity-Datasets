"""gasmine: mine gas-optimization patterns from optimized/unoptimized Solidity pairs.

Pipeline stages (see README):
  1. dataset  - discover/normalize the optimized/unoptimized dataset
  2. pairing  - (optional) match unpaired files via AST similarity
  3. diffing  - source / AST / opcode-level diff of each pair
  4. detectors- rule-based labelling of each diff
     clustering - (optional) data-driven discovery of unknown patterns
  5. gas      - Foundry-based deploy + runtime gas measurement
  6. catalog  - aggregate labels + gas into a reusable catalog.json
"""

__all__ = [
    "dataset",
    "solc",
    "astutils",
    "diffing",
    "detectors",
    "pairing",
    "clustering",
    "gas",
    "catalog",
]

__version__ = "0.1.0"
