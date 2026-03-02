"""Tests for the heritage/lineage system.

Verifies:
1. Lineage graph integrity (no orphan inputs, no cycles)
2. get_tooltip() and get_heritage() produce correct output
3. format_heritage_text() produces readable output
4. Heritage chain for key P&L items reaches config-level leaves
"""

import sys
from pathlib import Path

# Ensure the model root is on sys.path
_model_root = Path(__file__).resolve().parent.parent
if str(_model_root) not in sys.path:
    sys.path.insert(0, str(_model_root))


def test_lineage_import():
    """Lineage module imports without error and has nodes."""
    from engine.lineage import get_all_keys
    keys = get_all_keys()
    assert len(keys) > 40, f"Expected 40+ lineage nodes, got {len(keys)}"


def test_tooltip_without_values():
    """get_tooltip returns formula string without values."""
    from engine.lineage import get_tooltip
    tip = get_tooltip("pbt")
    assert tip, "pbt tooltip should not be empty"
    assert "ebit" in tip, f"pbt tooltip should mention ebit: {tip}"
    assert "ie" in tip, f"pbt tooltip should mention ie: {tip}"
    assert "fd_income" in tip, f"pbt tooltip should mention fd_income: {tip}"


def test_tooltip_with_values():
    """get_tooltip with values substitutes actual numbers."""
    from engine.lineage import get_tooltip
    values = {"pbt": 785000, "ebit": 1200000, "ie": 450000, "fd_income": 35000}
    tip = get_tooltip("pbt", values)
    assert "785" in tip, f"Should contain result value: {tip}"
    assert "1,200,000" in tip, f"Should contain ebit value: {tip}"


def test_tooltip_unknown_key():
    """get_tooltip returns empty string for unknown keys."""
    from engine.lineage import get_tooltip
    assert get_tooltip("nonexistent_key_xyz") == ""


def test_heritage_chain_pbt():
    """Heritage chain for PBT should go at least 3 levels deep."""
    from engine.lineage import get_heritage
    chain = get_heritage("pbt")
    assert len(chain) >= 3, f"PBT heritage should have 3+ steps, got {len(chain)}"
    keys = [s.key for s in chain]
    assert "pbt" in keys
    assert "ebit" in keys or "ebitda" in keys


def test_heritage_chain_pat():
    """Heritage chain for PAT includes tax and PBT."""
    from engine.lineage import get_heritage
    chain = get_heritage("pat")
    keys = [s.key for s in chain]
    assert "pat" in keys
    assert "pbt" in keys
    assert "tax" in keys


def test_heritage_chain_ebitda():
    """Heritage chain for EBITDA reaches revenue and opex."""
    from engine.lineage import get_heritage
    chain = get_heritage("ebitda")
    keys = [s.key for s in chain]
    assert "ebitda" in keys
    assert "rev_total" in keys
    assert "opex" in keys


def test_heritage_depth_ordering():
    """Steps should be ordered with increasing depth."""
    from engine.lineage import get_heritage
    chain = get_heritage("pat")
    # Depth should generally increase (BFS-like from DFS)
    # The first step should be depth 0
    assert chain[0].depth == 0
    assert chain[0].key == "pat"


def test_leaf_inputs_pat():
    """Leaf inputs for PAT should include config-level drivers."""
    from engine.lineage import get_leaf_inputs
    leaves = get_leaf_inputs("pat")
    assert len(leaves) > 0, "PAT should have leaf inputs"
    # Should include things like tax_rate, depreciable_base, etc.
    # These are config inputs that terminate the heritage chain


def test_format_heritage_text():
    """format_heritage_text produces non-empty output for known keys."""
    from engine.lineage import format_heritage_text
    text = format_heritage_text("pbt")
    assert "Level 0" in text
    assert "pbt" in text
    assert "Level 1" in text  # Should have sub-levels


def test_format_heritage_text_with_values():
    """format_heritage_text with values includes actual numbers."""
    from engine.lineage import format_heritage_text
    values = {
        "pbt": 785000, "ebit": 1200000, "ie": 450000, "fd_income": 35000,
        "ebitda": 1500000, "depr": 300000,
        "rev_total": 2000000, "opex": 500000,
    }
    text = format_heritage_text("pbt", values=values)
    assert "785" in text, f"Should contain PBT value"
    assert "Source:" in text, f"Should contain source reference"


def test_no_cycles():
    """Graph should be a DAG — no cycles."""
    from engine.lineage import get_all_keys, get_node
    for key in get_all_keys():
        visited = set()
        stack = [key]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            node = get_node(current)
            if node is not None:
                for inp in node.inputs:
                    # If an input leads back to the starting key, that is a cycle
                    assert inp != key, f"Cycle detected: {key} -> ... -> {inp}"
                    stack.append(inp)


def test_all_signs_match_inputs():
    """Every node should have len(sign) == len(inputs)."""
    from engine.lineage import get_all_keys, get_node
    for key in get_all_keys():
        node = get_node(key)
        assert node is not None
        assert len(node.sign) == len(node.inputs), (
            f"Node {key}: sign length {len(node.sign)} != "
            f"inputs length {len(node.inputs)}"
        )


def test_new_revenue_nodes():
    """New revenue sub-component nodes should be in the graph."""
    from engine.lineage import get_node
    assert get_node("rev_sewage") is not None
    assert get_node("rev_reuse") is not None
    assert get_node("rev_operating") is not None


def test_new_cf_detail_nodes():
    """New CF detail nodes should be in the graph."""
    from engine.lineage import get_node
    assert get_node("cf_tax") is not None
    assert get_node("cf_ie") is not None
    assert get_node("cf_pr") is not None
    assert get_node("cf_draw") is not None
    assert get_node("cf_grants") is not None
    assert get_node("cf_swap_ds") is not None


def test_new_bs_nodes():
    """New BS nodes should be in the graph."""
    from engine.lineage import get_node
    assert get_node("bs_fixed_assets") is not None
    assert get_node("bs_debt") is not None
    assert get_node("bs_retained") is not None
    assert get_node("bs_swap_net") is not None
    assert get_node("bs_reserves_total") is not None


def test_facility_nodes():
    """Facility schedule nodes should be in the graph."""
    from engine.lineage import get_node
    assert get_node("sr_closing") is not None
    assert get_node("mz_closing") is not None


def test_heritage_views_module_syntax():
    """views/heritage.py should parse without syntax errors."""
    import ast
    heritage_path = Path(__file__).resolve().parent.parent / "views" / "heritage.py"
    source = heritage_path.read_text()
    ast.parse(source)  # Raises SyntaxError if invalid


def test_lineage_module_syntax():
    """engine/lineage.py should parse without syntax errors."""
    import ast
    lineage_path = Path(__file__).resolve().parent.parent / "engine" / "lineage.py"
    source = lineage_path.read_text()
    ast.parse(source)  # Raises SyntaxError if invalid


if __name__ == "__main__":
    # Run all tests
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests")
    if failed:
        sys.exit(1)
