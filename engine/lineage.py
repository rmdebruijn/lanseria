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

# Revenue sub-components (NWL)
_n("rev_sewage", "rev_greenfield_sewage + rev_brownfield_sewage", (
    "rev_greenfield_sewage", "rev_brownfield_sewage",
), label="Sewage Revenue", source="engine/ops_model.py:nwl_ops")

_n("rev_reuse", "rev_greenfield_reuse + rev_construction + rev_agri", (
    "rev_greenfield_reuse", "rev_construction", "rev_agri",
), label="Re-use Revenue", source="engine/ops_model.py:nwl_ops")

_n("rev_operating", "rev_total - rev_bulk_services", (
    "rev_total", "rev_bulk_services",
), sign=(1, -1), label="Operating Revenue", source="engine/loop.py:build_annual")

# Revenue aggregation (entity-specific driver keys feed into rev_total)
_n("rev_total", "sum of revenue streams", (
    "rev_sewage", "rev_reuse", "rev_bulk_services", "rev_ic_nwl",
    "rev_ppa_pv", "rev_ppa_bess", "rev_wheeling",
    "rev_lease", "rev_training", "rev_timber_sales", "rev_coe_sale",
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

_n("cf_net", "cf_ops + cf_capex + cf_grant - cf_ds - cf_swap_ds", (
    "cf_ops", "cf_capex", "cf_grant", "cf_ds", "cf_swap_ds",
), sign=(1, 1, 1, -1, -1), label="Net Cash Flow", source="engine/loop.py:build_annual")

# CF detail (from build_annual in loop.py)
_n("cf_tax", "tax from P&L", ("tax",),
   label="Tax Paid", source="engine/loop.py:build_annual")

_n("cf_ie", "cf_ie_sr + cf_ie_mz", ("cf_ie_sr", "cf_ie_mz"),
   label="Cash Interest Expense", source="engine/loop.py:build_annual")

_n("cf_pr", "cf_pr_sr + cf_pr_mz", ("cf_pr_sr", "cf_pr_mz"),
   label="Principal Repayment", source="engine/loop.py:build_annual")

_n("cf_draw", "cf_draw_sr + cf_draw_mz", ("cf_draw_sr", "cf_draw_mz"),
   label="Loan Drawdowns", source="engine/loop.py:build_annual")

_n("cf_grants", "cf_grant_dtic + cf_grant_iic", ("cf_grant_dtic", "cf_grant_iic"),
   label="Grant Receipts", source="engine/loop.py:build_annual")

_n("cf_after_debt_service", "cf_ops - cf_ds - cf_swap_ds", (
    "cf_ops", "cf_ds", "cf_swap_ds",
), sign=(1, -1, -1), label="Cash After Debt Service",
   source="engine/loop.py:build_annual")

# Swap CF detail
_n("cf_swap_ds", "cf_swap_ds_i + cf_swap_ds_p", ("cf_swap_ds_i", "cf_swap_ds_p"),
   label="Swap Debt Service (EUR equiv.)", source="engine/loop.py:build_annual")

_n("cf_swap_zar_i", "swap_zar_interest_cash in EUR", ("swap_zar_interest_cash",),
   label="Swap ZAR Interest (EUR)", source="engine/loop.py:build_annual")


# ── Facility Schedule Lineage ────────────────────────────────────────
# Column keys from facility.build_schedule() — these are in the schedule dicts
# not the annual dict, but used for the facility table heritage inspection.

_n("sr_closing", "sr_opening + sr_draw_down + sr_interest + sr_principal - sr_accel", (
    "sr_opening", "sr_draw_down", "sr_interest", "sr_principal", "sr_accel",
), sign=(1, 1, 1, 1, -1), label="Senior IC Closing Balance",
   source="engine/facility.py:build_schedule")

_n("mz_closing", "mz_opening + mz_draw_down + mz_interest + mz_principal - mz_accel", (
    "mz_opening", "mz_draw_down", "mz_interest", "mz_principal", "mz_accel",
), sign=(1, 1, 1, 1, -1), label="Mezz IC Closing Balance",
   source="engine/facility.py:build_schedule")

# Facility schedule leaf / computed nodes for heritage tooltip display.
# sr_opening, sr_draw_down, sr_principal, mz_opening, mz_draw_down,
# mz_principal are referenced as inputs above but have no formula
# (config/driver values). We register them here so the heritage tooltip
# shows a meaningful label + source instead of "key not found".

_n("sr_opening", "previous period sr_closing (or 0 at start)", (),
   label="Senior IC Opening Balance", source="engine/facility.py:build_schedule")

_n("sr_draw_down", "pro_rata * total_drawdown_schedule", (),
   label="Senior IC Draw Down", source="engine/facility.py:build_schedule")

_n("sr_principal", "-(balance_at_repay_start / num_repayments)", (),
   label="Senior IC Principal (P_constant)", source="engine/facility.py:build_schedule")

_n("sr_movement", "sr_closing - sr_opening", ("sr_closing", "sr_opening"),
   sign=(1, -1), label="Senior IC Period Movement",
   source="engine/facility.py:build_schedule")

_n("sr_repayment", "sr_principal + ie_sr + sr_accel", ("sr_principal", "ie_sr", "sr_accel"),
   label="Senior IC Total Repayment (P+I+Accel)",
   source="engine/facility.py:build_schedule")

_n("sr_idc", "sr_opening * sr_rate / 2 (capitalised during construction)", ("sr_opening",),
   label="Senior IDC (Interest During Construction)",
   source="engine/facility.py:build_schedule")

_n("mz_opening", "previous period mz_closing (or 0 at start)", (),
   label="Mezz IC Opening Balance", source="engine/facility.py:build_schedule")

_n("mz_draw_down", "pro_rata * total_drawdown_schedule", (),
   label="Mezz IC Draw Down", source="engine/facility.py:build_schedule")

_n("mz_principal", "-(balance_at_repay_start / num_repayments)", (),
   label="Mezz IC Principal (P_constant)", source="engine/facility.py:build_schedule")

_n("mz_movement", "mz_closing - mz_opening", ("mz_closing", "mz_opening"),
   sign=(1, -1), label="Mezz IC Period Movement",
   source="engine/facility.py:build_schedule")

_n("mz_repayment", "mz_principal + ie_mz + mz_accel", ("mz_principal", "ie_mz", "mz_accel"),
   label="Mezz IC Total Repayment (P+I+Accel)",
   source="engine/facility.py:build_schedule")

_n("mz_idc", "mz_opening * mz_rate / 2 (capitalised during construction)", ("mz_opening",),
   label="Mezz IDC (Interest During Construction)",
   source="engine/facility.py:build_schedule")

# ZAR swap leg schedule columns
_n("swap_zar_opening", "previous period swap_zar_closing (or notional at start)", (),
   label="Swap ZAR Opening Balance", source="engine/swap.py", unit="ZAR")

_n("swap_zar_closing", "swap_zar_opening - swap_zar_p - swap_zar_accel", (
    "swap_zar_opening", "swap_zar_p",
), sign=(1, -1), label="Swap ZAR Closing Balance",
   source="engine/swap.py", unit="ZAR")

_n("swap_zar_payment", "swap_zar_p + swap_zar_interest", (
    "swap_zar_p", "swap_zar_interest",
), label="Swap ZAR Total Payment (P+I)",
   source="engine/swap.py", unit="ZAR")

_n("swap_zar_accel", "zar_leg_accel * fx (waterfall surplus allocation)", (),
   label="Swap ZAR Acceleration", source="engine/waterfall.py", unit="ZAR")


# ── Balance Sheet Lineage ────────────────────────────────────────────

_n("bs_fixed_assets", "min(cum_capex + cum_idc, depr_base + cum_idc) - cum_depr", (
    "cf_capex", "depr",
), sign=(1, -1), label="Fixed Assets (Net)",
   source="engine/loop.py:build_annual")

_n("bs_dsra", "cumulative_net_cash_flow (running CF accumulator)", ("cf_net",),
   label="DSRA / Cash Balance", source="engine/loop.py:build_annual")

_n("bs_assets", "bs_fixed_assets + bs_dsra", (
    "bs_fixed_assets", "bs_dsra",
), label="Total Assets", source="engine/loop.py:build_annual")

_n("bs_sr", "sr_closing_balance", ("sr_closing",),
   label="Senior Debt Outstanding", source="engine/facility.py")

_n("bs_mz", "mz_closing_balance", ("mz_closing",),
   label="Mezz Debt Outstanding", source="engine/facility.py")

_n("bs_debt", "bs_sr + bs_mz", ("bs_sr", "bs_mz"),
   label="Total Debt", source="engine/loop.py:build_annual")

_n("bs_swap_eur", "swap EUR leg closing balance", ("swap_eur_bal",),
   label="Swap EUR Asset", source="engine/loop.py:build_annual")

_n("bs_swap_liability", "swap ZAR leg in EUR", ("swap_zar_bal",),
   label="Swap ZAR Liability (EUR)", source="engine/loop.py:build_annual")

_n("bs_swap_net", "bs_swap_eur - bs_swap_liability", ("bs_swap_eur", "bs_swap_liability"),
   sign=(1, -1), label="Swap Net Position", source="engine/loop.py:build_annual")

_n("bs_equity", "bs_assets - bs_debt", ("bs_assets", "bs_debt"),
   sign=(1, -1), label="Equity", source="engine/loop.py:build_annual")

_n("bs_retained", "bs_equity - entity_equity", ("bs_equity", "bs_equity_sh"),
   sign=(1, -1), label="Retained Earnings", source="engine/loop.py:build_annual")

_n("bs_retained_check", "cum_pat + cum_grants - cum_dividends", (
    "pat", "cf_grants", "cum_dividends",
), label="Retained Earnings (cross-check)",
   source="engine/loop.py:build_annual")

_n("bs_gap", "bs_retained - bs_retained_check", ("bs_retained", "bs_retained_check"),
   sign=(1, -1), label="BS Gap (should be 0)",
   source="engine/loop.py:build_annual",
   unit="EUR")

# Reserve balance detail (BS display aliases)
_n("bs_reserves_total", "wf_ops_reserve + wf_opco_dsra + wf_mz_div_fd + wf_entity_fd", (
    "wf_ops_reserve", "wf_opco_dsra", "wf_mz_div_fd", "wf_entity_fd",
), label="Total Reserve Balances", source="engine/loop.py:build_annual")


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


# ── NWL Ops Revenue ─────────────────────────────────────────────────

_n("rev_greenfield_sewage", "sewage_sold * kl_per_mld * sewage_rate / fx_rate", (
    "sewage_sold", "sewage_rate", "fx_rate",
), label="Greenfield Sewage Revenue",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rev_brownfield_sewage", "brownfield_served * kl_per_mld * honeysucker_rate / fx_rate", (
    "brownfield_served", "honeysucker_rate", "fx_rate",
), label="Brownfield Sewage Revenue",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rev_greenfield_reuse", "reuse_sold_topcos * kl_per_mld * water_rate / fx_rate", (
    "reuse_sold_topcos", "water_rate", "fx_rate",
), label="Greenfield Re-use Revenue",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rev_construction", "reuse_sold_construction * kl_per_mld * water_rate / fx_rate", (
    "reuse_sold_construction", "water_rate", "fx_rate",
), label="Construction Water Revenue",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rev_agri", "reuse_overflow_agri * kl_per_mld * agri_rate / fx_rate", (
    "reuse_overflow_agri", "agri_rate", "fx_rate",
), label="Agricultural Re-use Revenue",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rev_bulk_services", "sum(bulk_row.price_zar) / fx_rate at M12", (
    "bulk_cfg", "fx_rate",
), label="Bulk Services Revenue (lump-sum at M12)",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")


# ── NWL Ops Costs ──────────────────────────────────────────────────

_n("om_cost", "om_flat_fee * (1 + indexation) ^ years_from_start / fx_rate", (
    "om_flat_fee", "om_indexation", "fx_rate",
), label="O&M Cost",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("power_cost", "capacity_mld * 1000 * kwh_per_m3 * rate_indexed * days / fx_rate", (
    "vol_capacity_mld", "power_kwh_per_m3", "power_rate", "fx_rate",
), label="Power Cost (IC from LanRED)",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")

_n("rent_cost", "coe_capex * (wacc + om_pct) / 12 * escalation / fx_rate", (
    "coe_capex", "wacc", "rent_escalation", "fx_rate",
), label="CoE Rent (capital-recovery)",
   source="entities/nwl.py:build_nwl_operating_model", unit="EUR")


# ── NWL Ops Volumes ────────────────────────────────────────────────

_n("vol_capacity_mld", "avg(sewage_capacity[H1], sewage_capacity[H2])", (
    "sewage_capacity",
), label="Sewage Capacity (avg MLD)", unit="MLD",
   source="entities/nwl.py:build_nwl_operating_model")

_n("vol_treated_mld", "avg(sewage_sold[H1], sewage_sold[H2])", (
    "sewage_sold",
), label="Sewage Treated (avg MLD)", unit="MLD",
   source="entities/nwl.py:build_nwl_operating_model")

_n("vol_annual_m3", "vol_treated_mld * 1000 * 365", (
    "vol_treated_mld",
), label="Annual Volume Treated", unit="M3",
   source="entities/nwl.py:build_nwl_operating_model")

_n("vol_reuse_annual_m3", "avg(reuse_topcos + reuse_construction + reuse_agri) * 1000 * 365", (
    "reuse_sold_topcos", "reuse_sold_construction", "reuse_overflow_agri",
), label="Annual Re-use Volume", unit="M3",
   source="entities/nwl.py:build_nwl_operating_model")

_n("vol_brownfield_annual_m3", "avg(brownfield_served) * 1000 * 365", (
    "brownfield_served",
), label="Annual Brownfield Volume", unit="M3",
   source="entities/nwl.py:build_nwl_operating_model")


# ── Waterfall ──────────────────────────────────────────────────────

_n("surplus", "max(cash_available - ds_cash, 0)", ("cash_available", "ds_cash"),
   sign=(1, -1), label="Surplus (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("deficit", "min(normal_pool - remaining_ds, 0)", ("normal_pool", "ds_cash"),
   sign=(1, -1), label="Deficit (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("cash_available", "special_pool + normal_pool", ("special_pool", "normal_pool"),
   label="Cash Available for Debt Service",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("ds_cash", "sr_pi + mz_pi + swap_leg_scheduled", ("sr_pi", "mz_pi", "swap_leg_scheduled"),
   label="Total Debt Service (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("sr_pi", "sr_interest + sr_principal", ("ie_sr", "sr_principal"),
   label="Senior P+I (semi-annual)",
   source="engine/facility.py:compute_period", unit="EUR")

_n("mz_pi", "mz_interest + mz_principal", ("ie_mz", "mz_principal"),
   label="Mezz P+I (semi-annual)",
   source="engine/facility.py:compute_period", unit="EUR")

_n("ops_reserve_fill", "min(remaining, ops_reserve_target - ops_reserve_bal)", (
    "ops_reserve_target", "ops_reserve_bal",
), label="Ops Reserve Fill (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("opco_dsra_fill", "min(remaining, opco_dsra_target - opco_dsra_bal)", (
    "opco_dsra_target", "opco_dsra_bal",
), label="OpCo DSRA Fill (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("opco_dsra_release", "max(opco_dsra_bal - opco_dsra_target, 0)", (
    "opco_dsra_bal", "opco_dsra_target",
), sign=(1, -1), label="OpCo DSRA Release (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_lent", "min(remaining, lanred_deficit)", ("lanred_deficit",),
   label="IC Overdraft Lent (NWL to LanRED, semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_received", "od_received from NWL (LanRED, semi-annual)", ("od_lent",),
   label="IC Overdraft Received (LanRED from NWL)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_repaid", "min(remaining, od_bal)", ("od_bal",),
   label="IC Overdraft Repaid (LanRED, semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_interest", "od_bal * od_rate / 2", ("od_bal", "od_rate"),
   label="IC Overdraft Interest (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_accel", "min(remaining * sweep_pct, od_bal)", ("od_bal", "sweep_pct"),
   label="IC Overdraft Acceleration (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_div_fd_fill", "min(remaining, mz_div_liability - mz_div_fd_bal)", (
    "mz_div_liability_bal", "mz_div_fd_bal",
), sign=(1, -1), label="Mezz Dividend FD Fill (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("dividend_paid", "entity_fd_bal * div_pct", ("entity_fd_bal", "div_pct"),
   label="Dividend Paid (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("free_surplus", "remaining after all reserves, acceleration, and dividends", (
    "surplus",
), label="Free Surplus (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("sr_accel_entity", "special_after_pi accel + sweep accel of sr", (
    "surplus", "sr_ic_bal",
), label="Senior IC Acceleration (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_accel_entity", "min(remaining * sweep_pct, mz_ic_bal)", (
    "surplus", "mz_ic_bal",
), label="Mezz IC Acceleration (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("swap_leg_accel", "min(remaining * sweep_pct, swap_leg_bal)", (
    "surplus", "swap_leg_bal",
), label="ZAR Swap Leg Acceleration (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("swap_leg_scheduled", "min(swap_vectors.scheduled_payment[hi], swap_leg_bal)", (
    "swap_leg_bal",
), label="Swap Leg Scheduled Payment (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("entity_fd_fill", "remaining after all debt = 0", ("entity_fd_bal",),
   label="Entity FD Fill (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("cum_dividends", "running sum of dividend_paid across periods", ("dividend_paid",),
   label="Cumulative Dividends", source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("opco_dsra_interest", "opco_dsra_bal * fd_rate / 2", ("opco_dsra_bal", "fd_rate"),
   label="OpCo DSRA Interest", source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("opco_dsra_target", "min(next_sr_pi, sr_ic_bal)", ("sr_pi", "sr_ic_bal"),
   label="OpCo DSRA Target (1x next Sr P+I)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("ops_reserve_target", "opex * ops_reserve_coverage", ("opex", "ops_reserve_coverage"),
   label="Ops Reserve Target",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_div_accrual", "mz_opening * mz_div_gap_rate / 2", ("mz_ic_bal", "mz_div_gap_rate"),
   label="Mezz Dividend Accrual (semi-annual)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_div_liability_bal", "running sum of mz_div_accrual", ("mz_div_accrual",),
   label="Mezz Dividend Liability Balance",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_div_payout_amount", "mz_div_fd_bal when mz_ic_bal reaches zero", ("mz_div_fd_bal",),
   label="Mezz Dividend Payout Amount",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("ie_half_sr", "sr_interest for semi-annual period", ("ie_sr",),
   label="Senior Interest (semi-annual half)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("ie_half_mz", "mz_interest for semi-annual period", ("ie_mz",),
   label="Mezz Interest (semi-annual half)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("ie_year", "ie_half_sr + ie_half_mz", ("ie_half_sr", "ie_half_mz"),
   label="Total Interest (semi-annual half)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("sr_prin_sched", "sr_principal (scheduled)", ("sr_principal",),
   label="Senior Scheduled Principal",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_prin_sched", "mz_principal (scheduled)", ("mz_principal",),
   label="Mezz Scheduled Principal",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("dtic_grant", "DTIC grant inflow at C3", ("dtic_grant_entity",),
   label="DTIC Grant Inflow (waterfall)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("iic_grant", "IIC TA grant inflow at C3", ("ta_grant_entity",),
   label="IIC TA Grant Inflow (waterfall)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("bulk_in_ebitda", "Bulk services revenue in EBITDA (tagging hint → special pool)", ("rev_bulk_services",),
   label="Bulk Services in EBITDA (tag → special)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("specials", "dtic_grant + bulk_in_ebitda + pre_rev_hedge + (ebitda if C2)", (
    "dtic_grant", "bulk_in_ebitda", "pre_rev_hedge",
), label="Special Cash Pool",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("pre_rev_hedge", "mezz_draw + eur_leg_repayment", ("mezz_draw", "eur_leg_repayment"),
   label="Pre-revenue Hedge Inflow",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mezz_draw", "mezz draw at R1 (FEC mode)", (),
   label="Mezz Draw (FEC mode at R1)", source="config", unit="EUR")

_n("eur_leg_repayment", "EUR leg repayment at R1 (swap mode)", (),
   label="EUR Leg Repayment (swap mode at R1)", source="config", unit="EUR")

_n("sr_ic_bal", "sr IC balance after acceleration", ("sr_closing",),
   label="Senior IC Balance (post-acceleration, waterfall)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_ic_bal", "mz IC balance after acceleration", ("mz_closing",),
   label="Mezz IC Balance (post-acceleration, waterfall)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("swap_leg_bal", "ZAR swap leg balance after scheduled + acceleration", (
    "swap_leg_accel", "swap_leg_scheduled",
), label="Swap Leg Balance (closing)",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("mz_div_opening_basis", "mz_ic_bal at start of period (for dividend accrual)", (
    "mz_ic_bal",
), label="Mezz Dividend Opening Basis",
   source="engine/waterfall.py:waterfall_step", unit="EUR")

_n("od_bal", "od_opening + od_lent + od_interest - od_repaid - od_accel", (
    "od_lent", "od_interest", "od_repaid", "od_accel",
), sign=(1, 1, -1, -1), label="IC Overdraft Balance",
   source="engine/waterfall.py:waterfall_step", unit="EUR")


# ── Swap (build_annual swap detail) ───────────────────────────────

_n("swap_eur_interest", "swap_eur_opening * (1 + eur_rate / 2) ^ 2 - swap_eur_opening", (
    "swap_eur_bal", "swap_eur_rate",
), label="Swap EUR Leg Interest",
   source="engine/loop.py:build_annual", unit="EUR")

_n("swap_zar_interest", "sum(schedule.interest) for year", ("swap_zar_bal",),
   label="Swap ZAR Leg Interest (ZAR)",
   source="engine/loop.py:build_annual", unit="ZAR")

_n("swap_zar_interest_cash", "sum(repayment-phase schedule.interest) for year", (
    "swap_zar_bal",
), label="Swap ZAR Interest Cash (ZAR, repayment phase only)",
   source="engine/loop.py:build_annual", unit="ZAR")

_n("swap_zar_p", "sum(repayment-phase schedule.principal) for year", (
    "swap_zar_bal",
), label="Swap ZAR Principal (ZAR)",
   source="engine/loop.py:build_annual", unit="ZAR")

_n("swap_zar_total", "swap_zar_p + swap_zar_interest_cash", (
    "swap_zar_p", "swap_zar_interest_cash",
), label="Swap ZAR Total Payment (ZAR)",
   source="engine/loop.py:build_annual", unit="ZAR")

_n("cf_swap_ds_i", "ZAR(swap_zar_interest_cash).to_eur(fx_rate)", (
    "swap_zar_interest_cash", "fx_rate",
), label="Swap Debt Service Interest (EUR equiv.)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_swap_ds_p", "ZAR(swap_zar_principal).to_eur(fx_rate)", (
    "swap_zar_p", "fx_rate",
), label="Swap Debt Service Principal (EUR equiv.)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("swap_eur_interest_cash", "EUR leg cash interest (0 during construction)", (
    "swap_eur_bal",
), label="Swap EUR Interest Cash",
   source="engine/loop.py:build_annual", unit="EUR")


# ── DSRA / FD Roll-forward ─────────────────────────────────────────

_n("dsra_opening", "previous period dsra_bal (running CF accumulator)", (
    "dsra_bal",
), label="DSRA Opening Balance (cash accumulator)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("dsra_interest", "ii_dsra (reserve FD income)", (
    "ii_dsra",
), label="DSRA Interest (= reserve FD income)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("dsra_deposit", "cf_net - ii_dsra", ("cf_net", "ii_dsra"),
   sign=(1, -1), label="DSRA Net Deposit (CF net less interest)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("dsra_bal", "dsra_opening + cf_net", ("dsra_opening", "cf_net"),
   label="DSRA Closing Balance (running CF accumulator)",
   source="engine/loop.py:build_annual", unit="EUR")


# ── CF Detail (build_annual) ──────────────────────────────────────

_n("cf_draw_sr", "sr.Draw_Down", ("sr_drawdowns",),
   label="Senior IC Drawdown", source="engine/loop.py:build_annual", unit="EUR")

_n("cf_draw_mz", "mz.Draw_Down", ("mz_drawdowns",),
   label="Mezz IC Drawdown", source="engine/loop.py:build_annual", unit="EUR")

_n("cf_ie_sr", "sum(sr.Interest) where Month >= repayment_start", ("ie_sr",),
   label="Senior Cash Interest (post-construction)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_ie_mz", "sum(mz.Interest) where Month >= repayment_start", ("ie_mz",),
   label="Mezz Cash Interest (post-construction)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_pr_sr", "abs(sr.Principle)", ("sr_principal",),
   label="Senior Principal Repayment",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_pr_mz", "abs(mz.Principle)", ("mz_principal",),
   label="Mezz Principal Repayment",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_operating_pre_debt", "ebitda", ("ebitda",),
   label="Operating CF Pre Debt Service",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_equity", "entity_equity if year 1 else 0", ("bs_equity_sh",),
   label="Equity Injection (year 1 only)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_dtic", "dtic_grant_entity at year 2", ("dtic_grant_entity",),
   label="DTIC Grant Receipt (year 2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_iic", "ta_grant_entity at year 2", ("ta_grant_entity",),
   label="IIC TA Grant Receipt (year 2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_accel_sr", "acceleration from grant-funded prepayment (facility schedule)", (
    "sr_grant_accel",
), label="Grant-funded Sr Acceleration",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_accel", "cf_grant_accel_sr", ("cf_grant_accel_sr",),
   label="Total Grant Acceleration", source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_accel_dtic", "cf_grant_accel * dtic_share", (
    "cf_grant_accel", "dtic_grant_entity", "gepf_grant_entity",
), label="Grant Acceleration (DTIC portion)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_grant_accel_gepf", "cf_grant_accel * (1 - dtic_share)", (
    "cf_grant_accel", "dtic_grant_entity", "gepf_grant_entity",
), label="Grant Acceleration (GEPF portion)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_accel_sr", "wf.sr_accel_entity (waterfall cash sweep)", ("sr_accel_entity",),
   label="Waterfall Sr IC Acceleration",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_accel_mz", "wf.mz_accel_entity (waterfall cash sweep)", ("mz_accel_entity",),
   label="Waterfall Mezz IC Acceleration",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_swap_accel", "wf.swap_leg_accel", ("swap_leg_accel",),
   label="Swap Leg Acceleration (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_od_lent", "wf.od_lent (NWL IC overdraft to LanRED)", ("od_lent",),
   label="IC Overdraft Lent (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_od_received", "wf.od_received (LanRED from NWL)", ("od_received",),
   label="IC Overdraft Received (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_od_repaid", "wf.od_repaid", ("od_repaid",),
   label="IC Overdraft Repaid (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_od_interest", "wf.od_interest", ("od_interest",),
   label="IC Overdraft Interest (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_ops_reserve_fill", "wf.ops_reserve_fill", ("ops_reserve_fill",),
   label="Ops Reserve Fill (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_opco_dsra_fill", "wf.opco_dsra_fill", ("opco_dsra_fill",),
   label="OpCo DSRA Fill (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_opco_dsra_release", "wf.opco_dsra_release", ("opco_dsra_release",),
   label="OpCo DSRA Release (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_mz_div_fd_fill", "wf.mz_div_fd_fill", ("mz_div_fd_fill",),
   label="Mezz Div FD Fill (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_entity_fd_fill", "wf.entity_fd_fill", ("entity_fd_fill",),
   label="Entity FD Fill (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_free_surplus", "wf.free_surplus", ("free_surplus",),
   label="Free Surplus (CF)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_dividend", "wf.dividend_paid", ("dividend_paid",),
   label="Dividend Paid (CF)",
   source="engine/loop.py:build_annual", unit="EUR")


# ── CF Aliases (backward-compat) ──────────────────────────────────

_n("cf_prepay_sr", "cf_grant_accel_sr", ("cf_grant_accel_sr",),
   label="Prepayment Sr (alias for cf_grant_accel_sr)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_prepay", "cf_grant_accel", ("cf_grant_accel",),
   label="Prepayment (alias for cf_grant_accel)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_prepay_dtic", "cf_grant_accel_dtic", ("cf_grant_accel_dtic",),
   label="Prepayment DTIC (alias for cf_grant_accel_dtic)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_prepay_gepf", "cf_grant_accel_gepf", ("cf_grant_accel_gepf",),
   label="Prepayment GEPF (alias for cf_grant_accel_gepf)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_sr_accel", "cf_accel_sr", ("cf_accel_sr",),
   label="Sr IC Acceleration (alias for cf_accel_sr)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_mz_accel", "cf_accel_mz", ("cf_accel_mz",),
   label="Mezz IC Acceleration (alias for cf_accel_mz)",
   source="engine/loop.py:build_annual", unit="EUR")


# ── Waterfall Reserve Balances (annual display aliases) ───────────

_n("wf_ops_reserve", "ops_reserve_bal", ("ops_reserve_bal",),
   label="Ops Reserve Balance (annual, from waterfall H2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("wf_opco_dsra", "opco_dsra_bal", ("opco_dsra_bal",),
   label="OpCo DSRA Balance (annual, from waterfall H2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("wf_mz_div_fd", "mz_div_fd_bal", ("mz_div_fd_bal",),
   label="Mezz Div FD Balance (annual, from waterfall H2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("wf_entity_fd", "entity_fd_bal", ("entity_fd_bal",),
   label="Entity FD Balance (annual, from waterfall H2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("wf_od_bal", "od_bal", ("od_bal",),
   label="IC Overdraft Balance (annual, from waterfall H2)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("bs_ops_reserve", "wf_ops_reserve", ("wf_ops_reserve",),
   label="Ops Reserve (BS alias for wf_ops_reserve)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("bs_opco_dsra", "wf_opco_dsra", ("wf_opco_dsra",),
   label="OpCo DSRA (BS alias for wf_opco_dsra)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("bs_mz_div_fd", "wf_mz_div_fd", ("wf_mz_div_fd",),
   label="Mezz Div FD (BS alias for wf_mz_div_fd)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("bs_entity_fd", "wf_entity_fd", ("wf_entity_fd",),
   label="Entity FD (BS alias for wf_entity_fd)",
   source="engine/loop.py:build_annual", unit="EUR")


# ── BS Detail (build_annual) ──────────────────────────────────────

_n("bs_equity_sh", "entity_equity", ("entity_equity",),
   label="Shareholder Equity (config input)",
   source="config", unit="EUR")

_n("bs_dtl", "0.0 (no DTL — same depr for accounting and tax)", (),
   label="Deferred Tax Liability (N/A)",
   source="engine/loop.py:build_annual", unit="EUR")


# ── Interest Breakdown (build_annual informational) ───────────────

_n("ie_sr_all", "sr.Interest (all, including IDC)", ("sr_closing",),
   label="Senior Interest (all, incl. IDC)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("ie_mz_all", "mz.Interest (all, including IDC)", ("mz_closing",),
   label="Mezz Interest (all, incl. IDC)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("idc_sr", "idc * sr_share_of_total_interest", ("ie_sr_all", "ie_mz_all"),
   label="IDC (Senior portion)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("idc_mz", "idc - idc_sr", ("idc_sr",),
   label="IDC (Mezz portion)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_idc_sr", "sr.IDC", ("sr_closing",),
   label="IDC Sr (capitalised, IAS 23)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_idc_mz", "mz.IDC", ("mz_closing",),
   label="IDC Mz (capitalised, IAS 23)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("cf_idc", "cf_idc_sr + cf_idc_mz", ("cf_idc_sr", "cf_idc_mz"),
   label="Total IDC (capitalised, IAS 23)",
   source="engine/loop.py:build_annual", unit="EUR")

_n("idc_memo", "cf_idc (memo line for P&L display)", ("cf_idc",),
   label="IDC Memo (capitalised this year)",
   source="engine/loop.py:build_annual", unit="EUR")


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
# LanRED + TimberWorx Entity Lineage  (Agent 2 — merge-safe block)
# ══════════════════════════════════════════════════════════════════════


# ── LanRED Greenfield Capacity ────────────────────────────────────────

_n("installed_mwp", "pv_budget / cost_per_kwp / 1000",
   ("pv_budget", "cost_per_kwp"),
   unit="MWp", label="Installed PV Capacity",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("bess_capacity_kwh", "bess_budget / cost_per_kwh_bess",
   ("bess_budget", "cost_per_kwh_bess"),
   unit="KWh", label="BESS Nameplate Capacity",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("bess_effective_kwh",
   "bess_capacity_kwh * usable_pct * (1 - bess_degradation_pa) ^ years_since_cod",
   ("bess_capacity_kwh", "usable_pct", "bess_degradation_pa"),
   unit="KWh", label="BESS Effective Usable Capacity",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("generation_kwh",
   "installed_mwp * 1000 * capacity_factor_adj * hours_operating",
   ("installed_mwp", "capacity_factor_adj", "hours_operating"),
   unit="KWh", label="Annual Solar Generation",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("capacity_factor_pct",
   "capacity_factor_base * (1 - solar_degradation_pa) ^ years_since_cod * 100",
   ("capacity_factor_base", "solar_degradation_pa"),
   unit="%", label="Degraded Capacity Factor",
   source="entities/lanred.py:_build_lanred_greenfield_model")


# ── LanRED Greenfield Revenue ─────────────────────────────────────────

_n("rev_ic_nwl",
   "generation_kwh * ic_share * ic_rate_indexed / fx_rate",
   ("generation_kwh", "ic_share_pct", "ic_rate_indexed", "fx_rate"),
   label="IC Power Sales to NWL",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("rev_smart_city",
   "generation_kwh * sc_share * sc_rate_indexed / fx_rate",
   ("generation_kwh", "sc_share_pct", "sc_rate_indexed", "fx_rate"),
   label="Smart City Off-take Revenue",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("rev_open_market",
   "generation_kwh * mkt_share * mkt_rate_indexed / fx_rate",
   ("generation_kwh", "mkt_share_pct", "mkt_rate_indexed", "fx_rate"),
   label="Open Market Power Sales",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("rev_bess_arbitrage",
   "bess_eff_kwh * (hd_spread * hd_days + hd_solar_spread * hd_days + ld_solar_spread * ld_days) / fx_rate",
   ("bess_effective_kwh", "hd_peak_rate", "hd_offpeak_rate",
    "ld_peak_rate", "arb_solar_cost", "fx_rate"),
   label="BESS TOU Arbitrage Revenue",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("rev_power_sales",
   "rev_ic_nwl + rev_smart_city + rev_open_market + rev_bess_arbitrage",
   ("rev_ic_nwl", "rev_smart_city", "rev_open_market", "rev_bess_arbitrage"),
   label="Total Power Sales Revenue (Greenfield)",
   source="entities/lanred.py:_build_lanred_greenfield_model")


# ── LanRED Greenfield Allocation Shares ───────────────────────────────

_n("ic_share_pct",
   "min(nwl_annual_kwh / generation_kwh, 1.0) * 100",
   ("nwl_annual_kwh", "generation_kwh"),
   unit="%", label="IC NWL Demand Share",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("sc_share_pct", "share_of_generation_pct_by_year[yi]",
   ("sc_share_by_year",),
   unit="%", label="Smart City Allocation Share",
   source="entities/lanred.py:_build_lanred_greenfield_model")

_n("mkt_share_pct", "max(1 - ic_share - sc_share, 0) * 100",
   ("ic_share_pct", "sc_share_pct"),
   sign=(1, 1), unit="%", label="Open Market Residual Share",
   source="entities/lanred.py:_build_lanred_greenfield_model")


# ── LanRED Greenfield Costs ───────────────────────────────────────────

_n("grid_cost",
   "grid_monthly_zar * (1 + grid_escalation) ^ years * months / fx_rate",
   ("grid_monthly_zar", "grid_escalation", "fx_rate"),
   label="Grid Connection Cost",
   source="entities/lanred.py:_build_lanred_greenfield_model")


# ── LanRED Brownfield Revenue ─────────────────────────────────────────

_n("rev_northlands_gross_zar",
   "sum(site.monthly_income_zar) * 12 * (1 + rev_escalation) ^ year_index",
   ("monthly_income_zar", "rev_escalation"),
   unit="ZAR", label="Northlands Gross Revenue (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")

_n("northlands_cogs_zar",
   "sum(site.monthly_cogs_zar) * 12 * (1 + cost_escalation) ^ year_index",
   ("monthly_cogs_zar", "cost_escalation"),
   unit="ZAR", label="Northlands COGS (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")

_n("northlands_gross_profit_zar",
   "rev_northlands_gross_zar - northlands_cogs_zar",
   ("rev_northlands_gross_zar", "northlands_cogs_zar"),
   sign=(1, -1), unit="ZAR", label="Northlands Gross Profit (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")

_n("northlands_ins_zar",
   "sum(site.monthly_insurance_zar) * 12 * (1 + cost_escalation) ^ year_index",
   ("monthly_insurance_zar", "cost_escalation"),
   unit="ZAR", label="Northlands Insurance (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")

_n("northlands_om_zar",
   "sum(site.monthly_om_zar) * 12 * (1 + cost_escalation) ^ year_index",
   ("monthly_om_zar", "cost_escalation"),
   unit="ZAR", label="Northlands O&M (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")

_n("northlands_net_zar",
   "northlands_gross_profit_zar - northlands_ins_zar - northlands_om_zar",
   ("northlands_gross_profit_zar", "northlands_ins_zar", "northlands_om_zar"),
   sign=(1, -1, -1), unit="ZAR", label="Northlands Net Profit (ZAR)",
   source="entities/lanred.py:_build_lanred_brownfield_model")


# ── TimberWorx Revenue ────────────────────────────────────────────────

_n("rev_lease",
   "monthly_rental_zar * (1 + lease_escalation) ^ years * months * occupancy / fx_rate",
   ("monthly_rental_zar", "lease_escalation", "occupancy_pct", "fx_rate"),
   label="CoE Lease Revenue",
   source="entities/timberworx.py:build_twx_operating_model")

_n("rev_training",
   "students * (fee_indexed + subsidy_indexed) / fx_rate",
   ("students", "training_fee_zar", "seta_subsidy_zar", "fx_rate"),
   label="Training Programs Revenue",
   source="entities/timberworx.py:build_twx_operating_model")

_n("rev_timber_gross",
   "timber_units * price_per_unit_indexed / fx_rate",
   ("timber_units", "price_per_unit_zar", "sales_escalation", "fx_rate"),
   label="Gross Timber Sales Revenue",
   source="entities/timberworx.py:build_twx_operating_model")

_n("rev_timber_sales",
   "rev_timber_gross - labor_cost",
   ("rev_timber_gross", "labor_cost"),
   sign=(1, -1), label="Net Timber Sales Revenue",
   source="entities/timberworx.py:build_twx_operating_model")

_n("rev_coe_sale",
   "coe_capex * (1 + premium_pct) [one-time in sale year]",
   ("coe_capex", "coe_sale_premium_pct"),
   label="CoE Sale to LLC (One-time)",
   source="entities/timberworx.py:build_twx_operating_model")


# ── TimberWorx Costs ──────────────────────────────────────────────────

_n("labor_cost",
   "timber_units * labor_per_house_zar * (1 + labor_escalation) ^ years / fx_rate",
   ("timber_units", "labor_per_house_zar", "labor_escalation", "fx_rate"),
   label="Timber Labor Cost",
   source="entities/timberworx.py:build_twx_operating_model")


# ── TimberWorx Operational Metrics ────────────────────────────────────

_n("occupancy_pct", "occupancy_ramp[year_index] * 100",
   ("occupancy_ramp",),
   unit="%", label="CoE Occupancy Rate",
   source="entities/timberworx.py:build_twx_operating_model")

_n("students", "throughput_students_per_year[year_index] (pro-rated if partial)",
   ("training_throughput",),
   unit="Units", label="Training Students Enrolled",
   source="entities/timberworx.py:build_twx_operating_model")

_n("timber_units", "units_per_year[year_index] (pro-rated if partial)",
   ("units_per_year",),
   unit="Units", label="Timber Houses Produced",
   source="entities/timberworx.py:build_twx_operating_model")

_n("coe_sold", "coe_sale_enabled AND year >= coe_sale_year",
   ("coe_sale_enabled", "coe_sale_year"),
   unit="Units", label="CoE Sold Flag",
   source="entities/timberworx.py:build_twx_operating_model")


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


def format_heritage_text(
    key: str,
    values: dict[str, float] | None = None,
    max_depth: int = 8,
) -> str:
    """Format the full heritage chain as indented monospace text.

    Produces a human-readable "notepad" view of the calculation chain,
    suitable for display in an expander or modal.

    Example output:
        Level 0: Profit Before Tax (pbt) = EUR 785,000
          = ebit - ie + fd_income
          = EUR 1,200,000 - EUR 450,000 + EUR 35,000
          Source: engine/pnl.py:L101

          Level 1: EBIT (ebit) = EUR 750,000
            = ebitda - depr
            = EUR 950,000 - EUR 200,000
            Source: engine/pnl.py:L98
            ...
    """
    steps = get_heritage(key, max_depth=max_depth, values=values)
    if not steps:
        node = _GRAPH.get(key)
        if node is None:
            return f"{key}: leaf value (config input / driver)"
        return get_tooltip(key, values)

    lines: list[str] = []
    for step in steps:
        indent = "  " * step.depth
        child_indent = "  " * (step.depth + 1)

        # Header: Level N: Label (key) = value
        result_str = ""
        if step.result_value is not None:
            result_str = f" = {_fmt_val(step.result_value, step.unit)}"
        lines.append(f"{indent}Level {step.depth}: {step.label} ({step.key}){result_str}")

        # Formula line
        lines.append(f"{child_indent}= {step.formula}")

        # Values substitution line
        if step.input_values:
            val_parts: list[str] = []
            for inp, s in zip(step.inputs, step.sign):
                v = step.input_values.get(inp)
                if v is not None:
                    prefix = "- " if s < 0 and val_parts else ("+ " if s > 0 and val_parts else "")
                    if s < 0 and not val_parts:
                        prefix = "-"
                    val_parts.append(f"{prefix}{_fmt_val(abs(v), step.unit)}")
                else:
                    prefix = "- " if s < 0 and val_parts else ("+ " if s > 0 and val_parts else "")
                    val_parts.append(f"{prefix}{inp}")
            if val_parts:
                lines.append(f"{child_indent}= {' '.join(val_parts)}")

        # Source
        if step.source:
            lines.append(f"{child_indent}Source: {step.source}")

        lines.append("")  # blank line between steps

    return "\n".join(lines)


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
