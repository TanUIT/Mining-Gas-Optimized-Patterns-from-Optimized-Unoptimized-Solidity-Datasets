"""Section 5: experimental gas measurement with Foundry.

For every pair we generate a ``Compare_<id>.t.sol`` test that imports both the
unoptimized and optimized contract (aliased ``U`` / ``O``) and measures:
  * deploy gas   - ``gasleft()`` delta around ``new`` (reflects bytecode size)
  * runtime gas  - per configured call, on the happy path and revert path

Results are streamed to a JSONL file via the ``vm.writeLine`` cheatcode and then
parsed back into Python.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import solc
from .astutils import find_nodes
from .dataset import Call, Pair


@dataclass
class GasMeasurement:
    pair_id: str
    tag: str  # "deploy" or a call name
    unopt_gas: int
    opt_gas: int

    @property
    def saved(self) -> int:
        return self.unopt_gas - self.opt_gas

    @property
    def saved_pct(self) -> float:
        return (self.saved / self.unopt_gas * 100.0) if self.unopt_gas else 0.0


@dataclass
class GasReport:
    measurements: list[GasMeasurement] = field(default_factory=list)

    def by_pair(self) -> dict[str, list[GasMeasurement]]:
        out: dict[str, list[GasMeasurement]] = {}
        for m in self.measurements:
            out.setdefault(m.pair_id, []).append(m)
        return out


def contract_name(pair: Pair, solc_version: str = solc.DEFAULT_SOLC_VERSION) -> str:
    """Resolve the main contract name (meta override, else first in the AST)."""
    if pair.contract:
        return pair.contract
    ast = solc.compile_ast(pair.unopt_path, solc_version=solc_version)
    defs = find_nodes(ast, "ContractDefinition")
    contracts = [d for d in defs if d.get("contractKind") == "contract"]
    if not contracts:
        raise ValueError(f"no contract found in {pair.unopt_path}")
    return contracts[0]["name"]


def _ensure_harness(harness: Path, solc_version: str, optimizer_runs: int) -> None:
    if not (harness / "lib" / "forge-std").exists():
        harness.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["forge", "init", "--no-commit", "--force", "."],
            cwd=harness,
            capture_output=True,
            text=True,
            check=True,
        )
    # Drop the template sources; keep only forge-std + our generated files.
    for junk in ["src/Counter.sol", "test/Counter.t.sol", "script/Counter.s.sol"]:
        (harness / junk).unlink(missing_ok=True)
    (harness / "foundry.toml").write_text(
        "[profile.default]\n"
        'src = "src"\n'
        'out = "out"\n'
        'libs = ["lib"]\n'
        f'solc = "{solc_version}"\n'
        "optimizer = true\n"
        f"optimizer_runs = {optimizer_runs}\n"
        'fs_permissions = [{ access = "read-write", path = "./" }]\n'
    )


def _ctor(pair: Pair) -> str:
    return ", ".join(pair.constructor_args)


def _setup_stmts(call: Call, var: str) -> str:
    lines = []
    for s in call.setup:
        args = ", ".join(s["args"])
        lines.append(f"        {var}.{s['method']}({args});")
    return "\n".join(lines)


def _call_body(call: Call, var: str) -> str:
    args = ", ".join(call.args)
    if call.expect_revert:
        return f"try {var}.{call.method}({args}) {{}} catch {{}}"
    return f"{var}.{call.method}({args});"


def _gen_test(pair: Pair, name: str, results_path: str, rel_unopt: str, rel_opt: str) -> str:
    """Generate the per-pair comparison test.

    Each side (unopt/opt) is measured in its *own* test function so it runs in
    fresh EVM state. That keeps the EIP-2929 cold/warm baseline symmetric across
    the two sides, so the reported delta reflects only the real optimization.
    """
    ctor = _ctor(pair)
    sid = pair.id.replace("-", "_")

    fns = [
        f"""    function test_deploy__unopt() public {{
        uint256 g = gasleft();
        new U({ctor});
        _rec("deploy", "unopt", g - gasleft());
    }}""",
        f"""    function test_deploy__opt() public {{
        uint256 g = gasleft();
        new O({ctor});
        _rec("deploy", "opt", g - gasleft());
    }}""",
    ]

    for call in pair.calls:
        prelude = f"        {call.prelude}" if call.prelude else ""
        for role, cls, var in (("unopt", "U", "u"), ("opt", "O", "o")):
            setup = _setup_stmts(call, var)
            body = _call_body(call, var)
            fns.append(
                f"""    function test_{call.name}__{role}() public {{
        {cls} {var} = new {cls}({ctor});
{prelude}
{setup}
        uint256 g = gasleft();
        {body}
        _rec("{call.name}", "{role}", g - gasleft());
    }}"""
            )

    functions = "\n\n".join(fns)
    return f"""// SPDX-License-Identifier: MIT
pragma solidity >=0.8.0;

import "forge-std/Test.sol";
import {{{name} as U}} from "{rel_unopt}";
import {{{name} as O}} from "{rel_opt}";

contract Compare_{sid} is Test {{
    string constant RESULTS = "{results_path}";

    function _rec(string memory tag, string memory role, uint256 gas) internal {{
        vm.writeLine(
            RESULTS,
            string.concat(
                '{{"id":"{pair.id}","tag":"', tag,
                '","role":"', role,
                '","gas":', vm.toString(gas), '}}'
            )
        );
    }}

{functions}
}}
"""


def measure(
    pairs: list[Pair],
    harness_dir: str | Path,
    solc_version: str = solc.DEFAULT_SOLC_VERSION,
    optimizer_runs: int = 200,
) -> GasReport:
    """Generate tests for every pair, run Foundry, and parse gas results."""
    harness = Path(harness_dir).resolve()
    _ensure_harness(harness, solc_version, optimizer_runs)

    srcs = harness / "dataset_srcs"
    tests = harness / "test"
    if srcs.exists():
        shutil.rmtree(srcs)
    for old in tests.glob("Compare_*.t.sol"):
        old.unlink()

    results_file = harness / "gasmine_gas.jsonl"
    results_file.unlink(missing_ok=True)

    for pair in pairs:
        pdir = srcs / pair.id
        pdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(pair.unopt_path, pdir / "unoptimized.sol")
        shutil.copy(pair.opt_path, pdir / "optimized.sol")
        name = contract_name(pair, solc_version=solc_version)
        rel_unopt = f"../dataset_srcs/{pair.id}/unoptimized.sol"
        rel_opt = f"../dataset_srcs/{pair.id}/optimized.sol"
        test_src = _gen_test(pair, name, "gasmine_gas.jsonl", rel_unopt, rel_opt)
        (tests / f"Compare_{pair.id.replace('-', '_')}.t.sol").write_text(test_src)

    proc = subprocess.run(
        ["forge", "test", "--match-contract", "Compare_", "-vv"],
        cwd=harness,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Surface forge output but still parse whatever was measured.
        print("WARNING: `forge test` returned non-zero:\n" + proc.stdout[-2000:] + proc.stderr[-1000:])

    return _parse_results(results_file)


def _parse_results(results_file: Path) -> GasReport:
    report = GasReport()
    if not results_file.exists():
        return report

    # Merge per-role lines ({id, tag, role, gas}) into unopt/opt measurements.
    merged: dict[tuple[str, str], dict[str, int]] = {}
    order: list[tuple[str, str]] = []
    for line in results_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        key = (obj["id"], obj["tag"])
        if key not in merged:
            merged[key] = {}
            order.append(key)
        merged[key][obj["role"]] = int(obj["gas"])  # last write wins if re-run

    for key in order:
        pair_id, tag = key
        roles = merged[key]
        if "unopt" in roles and "opt" in roles:
            report.measurements.append(
                GasMeasurement(
                    pair_id=pair_id,
                    tag=tag,
                    unopt_gas=roles["unopt"],
                    opt_gas=roles["opt"],
                )
            )
    return report
