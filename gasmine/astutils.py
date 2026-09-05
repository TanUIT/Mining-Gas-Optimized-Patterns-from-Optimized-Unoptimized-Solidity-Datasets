"""Section 3 foundation: AST normalization + shape comparison.

``normalize_ast`` strips volatile identity (ids, source ranges) and collapses
string-literal *contents* into a ``<STR len=N>`` marker so that two contracts
that differ only in a literal's length still normalize to the same *shape*.

``ast_shape`` reduces a node tree to nodeType structure only (ignoring every
scalar value, including identifiers and literals), which is what Section 4a's
``shape_equal`` compares.
"""
from __future__ import annotations

from typing import Any


def normalize_ast(node: Any) -> Any:
    """Remove volatile fields and collapse string-literal contents.

    Mirrors the reference implementation in the design doc.
    """
    if isinstance(node, dict):
        out: dict[str, Any] = dict(node)
        out.pop("id", None)
        out.pop("src", None)
        out.pop("nameLocation", None)
        if out.get("nodeType") == "Literal" and out.get("kind") == "string":
            value = out.get("value") or out.get("hexValue") or ""
            out["value"] = f"<STR len={len(str(value))}>"
            out.pop("hexValue", None)
        for k, v in list(out.items()):
            out[k] = normalize_ast(v)
        return out
    if isinstance(node, list):
        return [normalize_ast(x) for x in node]
    return node


def ast_shape(node: Any) -> Any:
    """Structure-only fingerprint: nodeType tree, scalar values ignored."""
    if isinstance(node, dict):
        children = tuple(
            (k, ast_shape(v))
            for k, v in sorted(node.items())
            if isinstance(v, (dict, list))
        )
        return ("D", node.get("nodeType"), children)
    if isinstance(node, list):
        return ("L", tuple(ast_shape(x) for x in node))
    return ("S",)


def shape_equal(a: Any, b: Any) -> bool:
    """True when two ASTs share identical structure (ignoring values)."""
    return ast_shape(a) == ast_shape(b)


def iter_nodes(node: Any):
    """Yield every dict node in the AST (preorder)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from iter_nodes(v)
    elif isinstance(node, list):
        for x in node:
            yield from iter_nodes(x)


def node_type_sequence(node: Any) -> list[str]:
    """Preorder list of ``nodeType`` values (feature for clustering)."""
    return [n["nodeType"] for n in iter_nodes(node) if "nodeType" in n]


def find_nodes(node: Any, node_type: str) -> list[dict]:
    return [n for n in iter_nodes(node) if n.get("nodeType") == node_type]


def string_literal_lengths(node: Any) -> list[int]:
    """Lengths of all string literals (reads the ``<STR len=N>`` marker if
    normalized, else the raw value length)."""
    lengths: list[int] = []
    for n in iter_nodes(node):
        if n.get("nodeType") == "Literal" and n.get("kind") == "string":
            value = str(n.get("value", ""))
            if value.startswith("<STR len=") and value.endswith(">"):
                try:
                    lengths.append(int(value[len("<STR len="):-1]))
                    continue
                except ValueError:
                    pass
            lengths.append(len(value))
    return lengths
