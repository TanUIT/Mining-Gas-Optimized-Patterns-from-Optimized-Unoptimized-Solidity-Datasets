"""Thin wrappers around the ``solc`` / ``solc-select`` command line.

Only the subset needed by the pipeline is exposed:
  * :func:`compile_ast`      - ``solc --ast-compact-json``  (Section 3, AST tier)
  * :func:`compile_opcodes`  - ``solc --opcodes``           (Section 3, opcode tier)
"""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

DEFAULT_SOLC_VERSION = "0.8.30"

# Opcodes whose counts are strong gas signals.
GAS_RELEVANT_OPCODES = (
    "SLOAD",
    "SSTORE",
    "MLOAD",
    "MSTORE",
    "MSTORE8",
    "CALLDATALOAD",
    "CALLDATACOPY",
    "KECCAK256",
    "LOG1",
    "LOG2",
    "REVERT",
)


class SolcError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _select_version(version: str) -> None:
    """Ensure the requested solc version is installed and selected."""
    subprocess.run(
        ["solc-select", "install", version],
        capture_output=True,
        text=True,
        check=False,
    )
    res = subprocess.run(
        ["solc-select", "use", version],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise SolcError(f"solc-select use {version} failed: {res.stderr.strip()}")


def _run_solc(args: list[str], cwd: Optional[Path] = None) -> str:
    res = subprocess.run(
        ["solc", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if res.returncode != 0:
        raise SolcError(f"solc {' '.join(args)} failed:\n{res.stderr.strip()}")
    return res.stdout


def _extract_json_block(stdout: str) -> str:
    """``solc --ast-compact-json`` prints a preamble, a ``======= file =======``
    header, then the JSON. Return the JSON that follows the first header."""
    lines = stdout.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("=======")), None
    )
    if header_idx is None:
        raise SolcError("no '=======' header in solc AST output")

    body: list[str] = []
    for line in lines[header_idx + 1 :]:
        if line.startswith("======="):
            break  # stop at the next source (single file only)
        body.append(line)

    text = "\n".join(body).strip()
    brace = text.find("{")
    if brace == -1:
        raise SolcError("no JSON found in solc AST output")
    return text[brace:]


def compile_ast(path: str | Path, solc_version: str = DEFAULT_SOLC_VERSION) -> dict:
    """Return the compact-JSON AST of a single ``.sol`` file."""
    _select_version(solc_version)
    path = Path(path)
    stdout = _run_solc(
        ["--ast-compact-json", "--allow-paths", str(path.parent), path.name],
        cwd=path.parent,
    )
    return json.loads(_extract_json_block(stdout))


def compile_opcodes(
    path: str | Path,
    solc_version: str = DEFAULT_SOLC_VERSION,
    optimize: bool = False,
    optimizer_runs: int = 200,
) -> dict[str, str]:
    """Return ``{contract_name: opcode_string}`` for every contract in the file."""
    _select_version(solc_version)
    path = Path(path)
    args = ["--opcodes"]
    if optimize:
        args += ["--optimize", "--optimize-runs", str(optimizer_runs)]
    args += ["--allow-paths", str(path.parent), path.name]
    stdout = _run_solc(args, cwd=path.parent)

    result: dict[str, str] = {}
    current: Optional[str] = None
    for line in stdout.splitlines():
        if line.startswith("======="):
            # e.g. "======= file.sol:ContractName ======="
            label = line.strip("= ").strip()
            current = label.split(":", 1)[-1] if ":" in label else label
        elif line.strip() == "Opcodes:":
            continue
        elif current is not None and line.strip():
            result[current] = result.get(current, "") + " " + line.strip()
    return {k: v.strip() for k, v in result.items()}


def count_opcodes(opcode_string: str) -> dict[str, int]:
    """Count occurrences of every opcode mnemonic in a solc opcode dump."""
    counts: dict[str, int] = {}
    for token in opcode_string.split():
        # Skip PUSH immediates like "0x80".
        if token.startswith("0x"):
            continue
        counts[token] = counts.get(token, 0) + 1
    return counts


def gas_relevant_counts(opcode_string: str) -> dict[str, int]:
    counts = count_opcodes(opcode_string)
    return {op: counts.get(op, 0) for op in GAS_RELEVANT_OPCODES}
