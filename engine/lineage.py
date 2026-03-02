"""Calculation lineage — zero-overhead formula provenance for every displayed value.

Hover a number → first-order formula (tooltip).
Click a number → full calculation chain (heritage) to base assumptions.

Architecture
────────────
The lineage system is a STATIC GRAPH. No runtime computation. The graph is
defined once at import time from the formula definitions that already exist
in the engine. When the UI renders a cell, it looks up the column key in the
lineage graph and gets:

    Level 0 (hover):  "pbt = ebit - ie + fd_income"
    Level 1 (click):  ebit  = ebitda - depr
                      ebitda = rev_total - opex
                      rev_total = rev_water + rev_sewage + ...
                      ie = ie_sr + ie_mz
                      fd_income = ops_reserve_interest + entity_fd_interest + ...

The graph is a DAG (directed acyclic graph) where each node is a column key
and edges point from output to inputs. Walking edges = walking the heritage.

Zero overhead:
- Graph is built once at module import (frozenset, tuple — no allocation)
- Lookup is O(1) dict access
- Heritage walk is O(depth) — max depth ~8 for any value in the model
- No FormulaRef objects created at compute time
- No registry, no IDs, no timestamps, no mutation

Integration:
- Views call `get_tooltip(key)` for hover text
- Views call `get_heritage(key)` for full chain
- Both return plain strings/lists — no Streamlit dependency in this module

Usage:
    from engine.lineage import get_tooltip, get_heritage, LineageNode

    tooltip = get_tooltip("pbt")
    # → "pbt = ebit - ie + fd_income"

    chain = get_heritage("pbt")
    # → [("pbt", "ebit - ie + fd_income", ["ebit", "ie", "fd_income"]),
    #    ("ebit", "ebitda - depr", ["ebitda", "depr"]),
    #    ("ebitda", "rev_total - opex", ["rev_total", "opex"]),
    #    ...]

    # With actual values (from annual dict):
    tooltip_v = get_tooltip("pbt", values=annual_row)
    # → "pbt = ebit - ie + fd_income = €1,200,000 - €450,000 + €35,000 = €785,000"
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Node definition ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LineageNode:
    """One node in the lineage DAG.

    key:     Column key (e.g. "pbt")
    formula: Human-readable formula string (e.g. "ebit - ie + fd_income")
    inputs:  Tuple of input column keys (e.g. ("ebit", "ie", "fd_income"))
    sign:    Tuple of signs per input (+1 or -1) for formatting with values
    unit:    Display unit (e.g. "EUR", "ZAR", "ratio", "%")
    label:   Human-readable label (e.g. "Profit Before Tax")
    source:  Where this formula lives in the engine (e.g. "engine/pnl.py:L101")
    """
    key: str
    formula: str
    inputs: tuple[str, ...]
    sign: tuple[int, ...] = ()
    unit: str = "EUR"
    label: str = ""
    source: str = ""


# ── Static lineage graph ─────────────────────────────────────────────
# Every computed column in the model, with its first-order formula and inputs.
# Grouped by accounting statement for readability.
# Driver columns (config inputs, not computed) are NOT in this graph —
# they are leaf nodes that terminate the heritage walk.

_GRAPH: dict[str, LineageNode] = {}


def _n(key: str, formula: str, inputs: tuple[str, ...], *,
       sign: tuple[int, ...] = (), unit: str = "EUR",
       label: str = "", source: str = "") -> None:
    """Register a node in the lineage graph."""
    if not sign:
        sign = tuple(1 for _ in inputs)
    _GRAPH[key] = LineageNode(
        key=key, formula=formula, inputs=inputs,
        sign=sign, unit=unit, label=label, source=source,
    )


# ── P&L Lineage ──────────────────────────────────────────────────────

# Revenue aggregation (entity-specific driver keys feed into rev_total)
_n("rev_total", "sum of revenue streams", (
    "rev_water", "rev_sewage", "rev_reuse", "rev_ic_nwl",
    "rev_ppa_pv", "rev_ppa_bess", "rev_wheeling",
    "rev_lease", "rev_training",
), label="Total Revenue", source="engine/loop.py:build_annual")

# OpEx aggregation
_n("opex", "om_cost + power_cost + rent_cost", (
    "om_cost", "power_cost", "rent_cost",
), label="Total Operating Expenditure", source="engine/loop.py:build_annual")

# P&L cascade
_n("ebitda", "rev_total - opex", ("rev_total", "opex"),
   sign=(1, -1), label="EBITDA", source="engine/pnl.py:L95")

_n("depr", "depreciable_base * s12c_rate", ("depreciable_base",),
   label="Depreciation (S12C)", source="engine/depreciation.py")

_n("ebit", "ebitda - depr", ("ebitda", "depr"),
   sign=(1, -1), label="EBIT", source="engine/pnl.py:L98")

# Interest expense
_n("ie_sr", "sr_opening * sr_rate / 2", ("sr_opening", "sr_rate"),
   label="Senior Interest Expense", source="engine/facility.py:step")

_n("ie_mz", "mz_opening * mz_rate / 2", ("mz_opening", "mz_rate"),
   label="Mezz Interest Expense", source="engine/facility.py:step")

_n("ie_swap", "swap_zar_leg * swap_rate / 2", ("swap_zar_leg", "swap_rate"),
   label="Swap Interest Expense", source="engine/swap.py")

_n("ie", "ie_sr + ie_mz + ie_swap", ("ie_sr", "ie_mz", "ie_swap"),
   label="Total Interest Expense", source="engine/pnl.py:L100")

# FD income (from reserve assets)
_n("fd_income", "ops_reserve_interest + entity_fd_interest + mz_div_fd_interest", (
    "ops_reserve_interest", "entity_fd_interest", "mz_div_fd_interest",
), label="FD Income (Reserve Interest)", source="engine/reserves.py:accrue")

_n("ii_dsra", "ops_reserve_interest + entity_fd_interest + mz_div_fd_interest", (
    "ops_reserve_interest", "entity_fd_interest", "mz_div_fd_interest",
), label="DSRA Interest Income", source="engine/loop.py:build_annual")

# Reserve interest detail
_n("ops_reserve_interest", "ops_reserve_bal * fd_rate / 2", (
    "ops_reserve_bal", "fd_rate",
), label="Ops Reserve Interest", source="engine/reserves.py:OpsReserve.accrue")

_n("entity_fd_interest", "entity_fd_bal * fd_rate / 2", (
    "entity_fd_bal", "fd_rate",
), label="Entity FD Interest", source="engine/reserves.py:EntityFD.accrue")

_n("mz_div_fd_interest", "mz_div_fd_bal * fd_rate / 2", (
    "mz_div_fd_bal", "fd_rate",
), label="Mezz Div FD Interest", source="engine/reserves.py:MezzDivFD.accrue")

# PBT → PAT
_n("pbt", "ebit - ie + fd_income", ("ebit", "ie", "fd_income"),
   sign=(1, -1, 1), label="Profit Before Tax", source="engine/pnl.py:L101")

_n("tax", "max(taxable_income * tax_rate, 0)", ("pbt", "tax_rate", "tax_loss_pool"),
   label="Corporate Tax (27%)", source="engine/formulas.py:calc_tax")

_n("pat", "pbt - tax", ("pbt", "tax"),
   sign=(1, -1), label="Profit After Tax", source="engine/pnl.py:L105")


# ── Cash Flow Lineage ────────────────────────────────────────────────

_n("cf_ops", "ebitda + ii_dsra - cf_tax", ("ebitda", "ii_dsra", "cf_tax"),
   sign=(1, 1, -1), label="Operating Cash Flow", source="engine/loop.py:build_annual")

_n("cf_capex", "-(capex_gross)", ("capex_gross",),
   sign=(-1,), label="Capital Expenditure", source="engine/loop.py:build_annual")

_n("cf_grant", "grant_received", ("grant_received",),
   label="Grant Receipts", source="engine/loop.py:build_annual")

_n("cf_ds", "cf_ds_sr + cf_ds_mz", ("cf_ds_sr", "cf_ds_mz"),
   label="Debt Service", source="engine/loop.py:build_annual")

_n("cf_ds_sr", "sr_interest + sr_principal", ("ie_sr", "sr_principal"),
   label="Senior Debt Service", source="engine/facility.py")

_n("cf_ds_mz", "mz_interest + mz_principal", ("ie_mz", "mz_principal"),
   label="Mezz Debt Service", source="engine/facility.py")

_n("cf_swap_ds", "swap_net_settlement", ("swap_eur_leg", "swap_zar_leg"),
   label="Swap Debt Service", source="engine/swap.py")

_n("cf_net", "cf_ops + cf_capex + cf_grant - cf_ds - cf_swap_ds", (
    "cf_ops", "cf_capex", "cf_grant", "cf_ds", "cf_swap_ds",
), sign=(1, 1, 1, -1, -1), label="Net Cash Flow", source="engine/loop.py:build_annual")


# ── Balance Sheet Lineage ────────────────────────────────────────────

_n("bs_fa", "capex_cumulative - depr_cumulative", ("capex_cumulative", "depr_cumulative"),
   sign=(1, -1), label="Fixed Assets (Net)", source="engine/loop.py:build_annual")

_n("bs_dsra", "dsra_closing_balance", ("dsra_closing",),
   label="DSRA Balance", source="engine/loop.py:build_annual")

_n("bs_cash", "cumulative_net_cash_flow", ("cf_net_cumulative",),
   label="Cash & Equivalents", source="engine/loop.py:build_annual")

_n("bs_assets", "bs_fa + bs_dsra + bs_cash + bs_od_asset", (
    "bs_fa", "bs_dsra", "bs_cash", "bs_od_asset",
), label="Total Assets", source="engine/loop.py:build_annual")

_n("bs_sr", "sr_closing_balance", ("sr_closing",),
   label="Senior Debt Outstanding", source="engine/facility.py")

_n("bs_mz", "mz_closing_balance", ("mz_closing",),
   label="Mezz Debt Outstanding", source="engine/facility.py")

_n("bs_swap", "swap_zar_outstanding", ("swap_zar_closing",),
   label="Swap ZAR Leg Outstanding", source="engine/swap.py")

_n("bs_liabilities", "bs_sr + bs_mz + bs_swap + bs_od_liability", (
    "bs_sr", "bs_mz", "bs_swap", "bs_od_liability",
), label="Total Liabilities", source="engine/loop.py:build_annual")

_n("bs_equity", "bs_assets - bs_liabilities", ("bs_assets", "bs_liabilities"),
   sign=(1, -1), label="Equity", source="engine/loop.py:build_annual")

_n("bs_re", "cumulative_pat", ("pat_cumulative",),
   label="Retained Earnings", source="engine/loop.py:build_annual")

_n("bs_gap", "bs_equity - bs_re", ("bs_equity", "bs_re"),
   sign=(1, -1), label="BS Gap (should be 0)",
   source="engine/loop.py:build_annual",
   unit="EUR")


# ── Waterfall / Reserve Lineage ──────────────────────────────────────

_n("ops_reserve_bal", "ops_reserve_opening + ops_reserve_fill - ops_reserve_release", (
    "ops_reserve_opening", "ops_reserve_fill", "ops_reserve_release",
), sign=(1, 1, -1), label="Ops Reserve Balance", source="engine/waterfall.py")

_n("opco_dsra_bal", "dsra_opening + dsra_fill - dsra_release", (
    "dsra_opening", "dsra_fill", "dsra_release",
), sign=(1, 1, -1), label="DSRA Balance", source="engine/waterfall.py")

_n("entity_fd_bal", "entity_fd_opening + entity_fd_fill - entity_fd_release", (
    "entity_fd_opening", "entity_fd_fill", "entity_fd_release",
), sign=(1, 1, -1), label="Entity FD Balance", source="engine/waterfall.py")

_n("mz_div_fd_bal", "mz_div_fd_opening + mz_div_fill - mz_div_payout", (
    "mz_div_fd_opening", "mz_div_fill", "mz_div_payout",
), sign=(1, 1, -1), label="Mezz Div FD Balance", source="engine/waterfall.py")

_n("sr_accel", "surplus allocated to sr prepayment", ("surplus_after_reserves",),
   label="Senior Acceleration", source="engine/waterfall.py")

_n("mz_accel", "surplus allocated to mz prepayment", ("surplus_after_sr_accel",),
   label="Mezz Acceleration", source="engine/waterfall.py")

_n("dividend", "surplus after all reserves and acceleration", ("free_surplus",),
   label="Dividend", source="engine/waterfall.py")


# ── Ratio Lineage ────────────────────────────────────────────────────

_n("dscr", "cf_ops / (cf_ds + cf_swap_ds)", ("cf_ops", "cf_ds", "cf_swap_ds"),
   unit="ratio", label="Debt Service Coverage Ratio",
   source="engine/loop.py:build_annual")

_n("llcr", "npv_cfads / outstanding_debt", ("npv_cfads", "outstanding_debt"),
   unit="ratio", label="Loan Life Coverage Ratio",
   source="models/financial_ratios.py")

_n("plcr", "npv_cfads_project / outstanding_debt", ("npv_cfads_project", "outstanding_debt"),
   unit="ratio", label="Project Life Coverage Ratio",
   source="models/financial_ratios.py")


# ── SCLCA Holding Lineage ────────────────────────────────────────────

_n("ii_total", "ii_sr + ii_mz", ("ii_sr", "ii_mz"),
   label="IC Interest Income (Total)", source="entities/sclca.py")

_n("ic_margin_income", "ii_total - ie", ("ii_total", "ie"),
   sign=(1, -1), label="IC Margin Income", source="entities/sclca.py")

_n("cons_rev", "rev_total - ic_revenue_elim", ("rev_total", "ic_revenue_elim"),
   sign=(1, -1), label="Consolidated Revenue", source="entities/sclca.py")

_n("cons_ebitda", "ebitda - ic_revenue_elim", ("ebitda", "ic_revenue_elim"),
   sign=(1, -1), label="Consolidated EBITDA", source="entities/sclca.py")

_n("cons_equity", "cons_assets_net - cons_debt", ("cons_assets_net", "cons_debt"),
   sign=(1, -1), label="Consolidated Equity", source="entities/sclca.py")


# ══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════


def get_node(key: str) -> LineageNode | None:
    """Look up a lineage node by column key. Returns None if not mapped."""
    return _GRAPH.get(key)


def get_tooltip(key: str, values: dict[str, float] | None = None) -> str:
    """First-order formula for hover display.

    Without values:  "pbt = ebit - ie + fd_income"
    With values:     "pbt = ebit - ie + fd_income = €1,200,000 - €450,000 + €35,000 = €785,000"

    Args:
        key: Column key (e.g. "pbt")
        values: Optional dict of actual values (e.g. from annual row) for
                inline resolution display.

    Returns:
        Tooltip string. Empty string if key not in lineage graph.
    """
    node = _GRAPH.get(key)
    if node is None:
        return ""

    base = f"{key} = {node.formula}"

    if values is None:
        return base

    # Resolve with actual values
    parts: list[str] = []
    for inp, s in zip(node.inputs, node.sign):
        v = values.get(inp)
        if v is not None:
            prefix = "- " if s < 0 and parts else ("+ " if s > 0 and parts else "")
            if s < 0 and not parts:
                prefix = "-"
            parts.append(f"{prefix}{_fmt_val(abs(v), node.unit)}")
        else:
            prefix = "- " if s < 0 and parts else ("+ " if s > 0 and parts else "")
            parts.append(f"{prefix}{inp}")

    result = values.get(key)
    result_str = f" = {_fmt_val(result, node.unit)}" if result is not None else ""

    return f"{base} = {' '.join(parts)}{result_str}"


def get_heritage(
    key: str,
    max_depth: int = 8,
    values: dict[str, float] | None = None,
) -> list[HeritageStep]:
    """Full calculation chain — walk the DAG from output to leaf inputs.

    Returns a list of HeritageStep, each representing one formula resolution
    in the chain, ordered from the requested key down to base inputs.

    Args:
        key: Starting column key (e.g. "pbt")
        max_depth: Maximum recursion depth (prevents infinite loops)
        values: Optional actual values for inline display

    Returns:
        List of HeritageStep (may be empty if key not in graph)
    """
    result: list[HeritageStep] = []
    visited: set[str] = set()

    def _walk(k: str, depth: int) -> None:
        if depth > max_depth or k in visited:
            return
        node = _GRAPH.get(k)
        if node is None:
            return  # Leaf node (driver/config input) — stop

        visited.add(k)

        # Get actual values for this node's inputs
        input_values: dict[str, float | None] = {}
        if values is not None:
            for inp in node.inputs:
                input_values[inp] = values.get(inp)

        result.append(HeritageStep(
            key=k,
            label=node.label or k,
            formula=node.formula,
            inputs=node.inputs,
            sign=node.sign,
            unit=node.unit,
            source=node.source,
            depth=depth,
            input_values=input_values if values else {},
            result_value=values.get(k) if values else None,
        ))

        # Recurse into inputs
        for inp in node.inputs:
            _walk(inp, depth + 1)

    _walk(key, 0)
    return result


def get_all_keys() -> frozenset[str]:
    """All column keys that have lineage definitions."""
    return frozenset(_GRAPH.keys())


def get_leaf_inputs(key: str, max_depth: int = 10) -> frozenset[str]:
    """Get all leaf inputs (base assumptions) for a given key.

    Leaf inputs are keys that appear as inputs but have no lineage node
    of their own — they are the terminal driver values.
    """
    leaves: set[str] = set()
    visited: set[str] = set()

    def _walk(k: str, depth: int) -> None:
        if depth > max_depth or k in visited:
            return
        visited.add(k)
        node = _GRAPH.get(k)
        if node is None:
            leaves.add(k)
            return
        for inp in node.inputs:
            _walk(inp, depth + 1)

    _walk(key, 0)
    return frozenset(leaves)


# ── Heritage step data ───────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class HeritageStep:
    """One step in a heritage (provenance) chain."""
    key: str
    label: str
    formula: str
    inputs: tuple[str, ...]
    sign: tuple[int, ...]
    unit: str
    source: str
    depth: int
    input_values: dict[str, float | None]
    result_value: float | None


# ── Value formatting ─────────────────────────────────────────────────

def _fmt_val(value: float | None, unit: str = "EUR") -> str:
    """Format a value for tooltip display."""
    if value is None:
        return "?"
    if unit == "EUR":
        return f"\u20ac{value:,.0f}"
    elif unit == "ZAR":
        return f"R{value:,.0f}"
    elif unit == "ratio":
        return f"{value:.2f}x"
    elif unit == "%":
        return f"{value:.1f}%"
    else:
        return f"{value:,.0f}"
