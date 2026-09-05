"""Section 4a: rule-based pattern detectors.

Each detector is a small, transparent predicate over a :class:`PairDiff`.
``classify_diff`` runs them all and returns the matched pattern labels (or
``["uncategorized"]``). Pattern metadata (human rule, recommended fix) lives in
:data:`PATTERN_META` and feeds the Section 6 catalog.
"""
from __future__ import annotations

import re
from typing import Callable

from . import astutils
from .diffing import PairDiff

_UINT_RE = re.compile(r"^(u?int)(\d+)$")


# --------------------------------------------------------------------------- #
# AST feature helpers (operate on the raw, non-normalized AST)
# --------------------------------------------------------------------------- #
def _require_reason_calls(ast: dict) -> int:
    """require(cond, "reason") calls (a require carrying a reason string)."""
    count = 0
    for call in astutils.find_nodes(ast, "FunctionCall"):
        expr = call.get("expression", {})
        if expr.get("nodeType") == "Identifier" and expr.get("name") == "require":
            args = call.get("arguments", [])
            if len(args) >= 2:
                count += 1
    return count


def _total_string_literal_len(ast: dict) -> int:
    return sum(astutils.string_literal_lengths(ast))


def _custom_error_defs(ast: dict) -> int:
    return len(astutils.find_nodes(ast, "ErrorDefinition"))


def _revert_statements(ast: dict) -> int:
    return len(astutils.find_nodes(ast, "RevertStatement"))


def _unchecked_blocks(ast: dict) -> int:
    return len(astutils.find_nodes(ast, "UncheckedBlock"))


def _params_with_location(ast: dict, location: str) -> int:
    return sum(
        1
        for vd in astutils.find_nodes(ast, "VariableDeclaration")
        if vd.get("storageLocation") == location
    )


def _state_var_mutability(ast: dict, mutability: str) -> int:
    return sum(
        1
        for vd in astutils.find_nodes(ast, "VariableDeclaration")
        if vd.get("stateVariable") and vd.get("mutability") == mutability
    )


def _fn_visibility(ast: dict, visibility: str) -> int:
    return sum(
        1
        for fn in astutils.find_nodes(ast, "FunctionDefinition")
        if fn.get("visibility") == visibility
    )


def _increment_ops(ast: dict, prefix: bool) -> int:
    return sum(
        1
        for op in astutils.find_nodes(ast, "UnaryOperation")
        if op.get("operator") == "++" and bool(op.get("prefix")) == prefix
    )


def _length_member_accesses(ast: dict) -> int:
    return sum(
        1
        for ma in astutils.find_nodes(ast, "MemberAccess")
        if ma.get("memberName") == "length"
    )


def _small_width_type_decls(ast: dict) -> int:
    """Count elementary uint/int declarations narrower than 256 bits."""
    count = 0
    for tn in astutils.find_nodes(ast, "ElementaryTypeName"):
        m = _UINT_RE.match(tn.get("name", ""))
        if m and int(m.group(2)) < 256:
            count += 1
    return count


# --------------------------------------------------------------------------- #
# Detectors (predicate over a PairDiff)
# --------------------------------------------------------------------------- #
def d_revert_string_shortening(d: PairDiff) -> bool:
    # Same structure, but the optimized version carries shorter string literals.
    if not d.shape_equal():
        return False
    len_u = _total_string_literal_len(d.ast_u_raw)
    len_o = _total_string_literal_len(d.ast_o_raw)
    return len_u > 0 and len_o < len_u


def d_require_to_custom_error(d: PairDiff) -> bool:
    req_u = _require_reason_calls(d.ast_u_raw)
    req_o = _require_reason_calls(d.ast_o_raw)
    err_o = _custom_error_defs(d.ast_o_raw)
    err_u = _custom_error_defs(d.ast_u_raw)
    reverts_o = _revert_statements(d.ast_o_raw)
    return req_u > req_o and err_o > err_u and reverts_o > 0


def d_storage_packing(d: PairDiff) -> bool:
    return _small_width_type_decls(d.ast_o_raw) > _small_width_type_decls(d.ast_u_raw)


def d_unchecked_arithmetic(d: PairDiff) -> bool:
    return _unchecked_blocks(d.ast_o_raw) > _unchecked_blocks(d.ast_u_raw)


def d_loop_length_caching(d: PairDiff) -> bool:
    # Optimized code touches `.length` fewer times (cached in a local).
    has_loop = bool(astutils.find_nodes(d.ast_u_raw, "ForStatement"))
    return has_loop and _length_member_accesses(d.ast_o_raw) < _length_member_accesses(
        d.ast_u_raw
    )


def d_calldata_vs_memory(d: PairDiff) -> bool:
    cd_u = _params_with_location(d.ast_u_raw, "calldata")
    cd_o = _params_with_location(d.ast_o_raw, "calldata")
    mem_u = _params_with_location(d.ast_u_raw, "memory")
    mem_o = _params_with_location(d.ast_o_raw, "memory")
    return cd_o > cd_u and mem_o < mem_u


def d_preincrement(d: PairDiff) -> bool:
    return _increment_ops(d.ast_o_raw, prefix=True) > _increment_ops(
        d.ast_u_raw, prefix=True
    ) and _increment_ops(d.ast_u_raw, prefix=False) > _increment_ops(
        d.ast_o_raw, prefix=False
    )


def d_immutable_constant(d: PairDiff) -> bool:
    imm = _state_var_mutability(d.ast_o_raw, "immutable") > _state_var_mutability(
        d.ast_u_raw, "immutable"
    )
    const = _state_var_mutability(d.ast_o_raw, "constant") > _state_var_mutability(
        d.ast_u_raw, "constant"
    )
    return imm or const


def d_external_visibility(d: PairDiff) -> bool:
    return _fn_visibility(d.ast_o_raw, "external") > _fn_visibility(
        d.ast_u_raw, "external"
    ) and _fn_visibility(d.ast_u_raw, "public") > _fn_visibility(d.ast_o_raw, "public")


def d_storage_read_caching(d: PairDiff) -> bool:
    # Opcode-level signal: fewer SLOADs in the optimized build.
    return d.opcodes_o.get("SLOAD", 0) < d.opcodes_u.get("SLOAD", 0)


Detector = Callable[[PairDiff], bool]

# Ordered so that more specific patterns are listed first.
DETECTORS: list[tuple[str, Detector]] = [
    ("revert-string-shortening", d_revert_string_shortening),
    ("require-to-custom-error", d_require_to_custom_error),
    ("storage-packing", d_storage_packing),
    ("unchecked-arithmetic", d_unchecked_arithmetic),
    ("loop-length-caching", d_loop_length_caching),
    ("calldata-vs-memory", d_calldata_vs_memory),
    ("preincrement", d_preincrement),
    ("immutable-constant", d_immutable_constant),
    ("external-visibility", d_external_visibility),
    ("storage-read-caching", d_storage_read_caching),
]


PATTERN_META: dict[str, dict[str, str]] = {
    "revert-string-shortening": {
        "detector_rule": "shape_equal + total string-literal length decreased",
        "recommended_fix": "Shorten revert messages to <32 bytes or replace with a custom error.",
    },
    "require-to-custom-error": {
        "detector_rule": "require(reason) count down + ErrorDefinition/revert added",
        "recommended_fix": "Replace require(cond, \"msg\") with `if (!cond) revert CustomError();`.",
    },
    "storage-packing": {
        "detector_rule": "more sub-256-bit elementary type declarations in optimized",
        "recommended_fix": "Pack struct/state fields into fewer 32-byte storage slots.",
    },
    "unchecked-arithmetic": {
        "detector_rule": "UncheckedBlock count increased in optimized",
        "recommended_fix": "Wrap provably-safe arithmetic (e.g. loop counters) in `unchecked {}`.",
    },
    "loop-length-caching": {
        "detector_rule": "for-loop present + fewer `.length` member accesses in optimized",
        "recommended_fix": "Cache array length in a local variable before the loop.",
    },
    "calldata-vs-memory": {
        "detector_rule": "more `calldata` params + fewer `memory` params in optimized",
        "recommended_fix": "Use `calldata` for read-only reference-type function arguments.",
    },
    "preincrement": {
        "detector_rule": "more prefix `++` and fewer postfix `++` in optimized",
        "recommended_fix": "Use `++i` instead of `i++` where the return value is unused.",
    },
    "immutable-constant": {
        "detector_rule": "more immutable/constant state variables in optimized",
        "recommended_fix": "Mark write-once state as `immutable` and compile-time values as `constant`.",
    },
    "external-visibility": {
        "detector_rule": "more `external` and fewer `public` functions in optimized",
        "recommended_fix": "Declare functions never called internally as `external`.",
    },
    "storage-read-caching": {
        "detector_rule": "fewer SLOAD opcodes in the optimized build",
        "recommended_fix": "Cache repeated storage reads in memory/stack locals.",
    },
    "uncategorized": {
        "detector_rule": "no rule matched",
        "recommended_fix": "Manual review (candidate for clustering / new pattern).",
    },
}


def classify_diff(d: PairDiff) -> list[str]:
    labels = [label for label, detector in DETECTORS if detector(d)]
    return labels or ["uncategorized"]
