from gasmine import astutils


def test_normalize_collapses_string_literal_value():
    node = {
        "nodeType": "Literal",
        "kind": "string",
        "id": 7,
        "src": "1:2:0",
        "value": "a very long revert reason string",
    }
    out = astutils.normalize_ast(node)
    assert out["value"] == "<STR len=32>"
    assert "id" not in out and "src" not in out


def test_shape_equal_ignores_identifiers_and_literal_values():
    a = {
        "nodeType": "Return",
        "expression": {"nodeType": "Identifier", "name": "gamma"},
    }
    b = {
        "nodeType": "Return",
        "expression": {"nodeType": "Identifier", "name": "c"},
    }
    assert astutils.shape_equal(a, b)


def test_shape_differs_on_structure():
    a = {"nodeType": "Block", "statements": [{"nodeType": "Return"}]}
    b = {"nodeType": "Block", "statements": []}
    assert not astutils.shape_equal(a, b)


def test_string_literal_lengths_reads_marker():
    normalized = {"nodeType": "Literal", "kind": "string", "value": "<STR len=180>"}
    assert astutils.string_literal_lengths(normalized) == [180]
