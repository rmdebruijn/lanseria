#!/usr/bin/env python3
"""
Guarantor Financial Analysis Engine.

Analyses structured management account JSONs (from re_extract_mgmt_accounts.py)
and AFS JSONs to produce:
  1. Lifecycle stage classification (8 stages)
  2. Monthly trend signals (revenue, cash, debt, DSCR, D/E)
  3. Event detection (restructuring, property sales, capital injections)
  4. Narrative story generation for ECA assessment

Input: structured JSON files with statement_of_comprehensive_income + statement_of_financial_position
Output: analysis dict per entity, suitable for UI rendering or reporting

Can be used standalone (CLI) or imported into app.py.
"""

import json
import math
from pathlib import Path
from typing import Optional


# ============================================================================
# Constants
# ============================================================================

LIFECYCLE_STAGES = {
    "cash_generating": {"label": "Cash Generating", "color": "green", "severity": 0},
    "growth":          {"label": "Growth", "color": "purple", "severity": 1},
    "stabilising":     {"label": "Stabilising", "color": "amber", "severity": 2},
    "early_stage":     {"label": "Early-stage", "color": "sky", "severity": 3},
    "revenue_only":    {"label": "Revenue Only", "color": "teal", "severity": 4},
    "stalled":         {"label": "Stalled", "color": "orange", "severity": 5},
    "distressed":      {"label": "Distressed", "color": "red", "severity": 6},
    "holding":         {"label": "Holding / Pass-through", "color": "grey", "severity": 7},
    "dormant":         {"label": "Dormant", "color": "grey", "severity": 8},
    "unknown":         {"label": "Unknown", "color": "grey", "severity": 9},
}

MONTH_LABELS = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb"]


# ============================================================================
# Helpers
# ============================================================================

def _sf(v):
    """Safe float."""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _gval(d, *keys, idx=0):
    """Navigate nested dict by keys, extract values[idx] from leaf."""
    node = d
    for k in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
        if node is None:
            return None
    if isinstance(node, dict) and "values" in node:
        vals = node["values"]
        if isinstance(vals, list) and len(vals) > idx:
            v = vals[idx]
            return float(v) if v is not None else None
    return None


def _slope(series):
    """Simple linear regression slope for a series of floats. Returns slope per period."""
    pts = [(i, v) for i, v in enumerate(series) if v is not None and v != 0]
    if len(pts) < 3:
        return None
    n = len(pts)
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-10:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _pct_change(old, new):
    """Percentage change from old to new."""
    if old is None or new is None or abs(old) < 1e-2:
        return None
    return (new - old) / abs(old) * 100


def _last_nonzero(series):
    """Return last non-zero value in a series."""
    for v in reversed(series):
        if v is not None and v != 0:
            return v
    return None


def _count_active_months(monthly_cy):
    """Count how many months have non-zero IS data."""
    if not monthly_cy:
        return 0
    return sum(1 for v in monthly_cy if v != 0)


# ============================================================================
# Core Analysis Functions
# ============================================================================

def analyse_is_monthly(mgmt_data: dict) -> dict:
    """Analyse monthly IS trends from management account GL detail.

    Returns dict with:
      - monthly_revenue: list of monthly revenue values (absolute income basis)
      - monthly_opex: list of monthly opex values
      - monthly_ebitda: list of monthly operating result proxy (rev + other income - COS - opex)
      - revenue_slope: trend slope per month
      - opex_slope: trend slope per month
      - active_months: count of months with data
      - revenue_volatility: coefficient of variation
      - event_months: list of (month_idx, event_type, magnitude) for anomalies
    """
    gl = mgmt_data.get("general_ledger_detail", {}).get("accounts", {})
    mip = mgmt_data.get("metadata", {}).get("months_in_period", {})
    n_months = mip.get("current_year", 10)

    # Aggregate monthly revenue and opex from GL accounts
    monthly_rev = [0.0] * 13
    monthly_opex = [0.0] * 13
    monthly_cos = [0.0] * 13
    monthly_oi = [0.0] * 13
    monthly_fc = [0.0] * 13  # finance charges are in Expenses category

    for acct_id, acct in gl.items():
        cat = acct.get("category", "")
        cy = acct.get("monthly_cy", [])
        desc = acct.get("description", "").lower()

        for p in range(min(len(cy), 13)):
            if cat == "revenue":
                monthly_rev[p] += abs(cy[p])  # revenue is negative in GL
            elif cat == "cost_of_sales":
                monthly_cos[p] += abs(cy[p])
            elif cat == "operating_expenses":
                # Separate finance charges from opex
                if "finance" in desc or "interest" in desc:
                    monthly_fc[p] += abs(cy[p])
                else:
                    monthly_opex[p] += abs(cy[p])
            elif cat == "other_income":
                monthly_oi[p] += abs(cy[p])

    # Trim to active months
    monthly_rev = monthly_rev[:n_months]
    monthly_opex = monthly_opex[:n_months]
    monthly_cos = monthly_cos[:n_months]
    monthly_oi = monthly_oi[:n_months]
    monthly_fc = monthly_fc[:n_months]

    # Operating result proxy = Revenue + Other Income - COS - OpEx (before finance charges)
    monthly_ebitda = [
        monthly_rev[i] + monthly_oi[i] - monthly_cos[i] - monthly_opex[i]
        for i in range(len(monthly_rev))
    ]

    # Monthly DSCR = EBITDA / Finance Charges
    monthly_dscr = []
    for i in range(len(monthly_ebitda)):
        if monthly_fc[i] > 0:
            monthly_dscr.append(round(monthly_ebitda[i] / monthly_fc[i], 2))
        else:
            monthly_dscr.append(None)  # no finance charges
    dscr_vals = [d for d in monthly_dscr if d is not None]
    dscr_median = None
    dscr_min = None
    dscr_cover_ratio = None
    if dscr_vals:
        dscr_sorted = sorted(dscr_vals)
        mid = len(dscr_sorted) // 2
        if len(dscr_sorted) % 2:
            dscr_median = dscr_sorted[mid]
        else:
            dscr_median = round((dscr_sorted[mid - 1] + dscr_sorted[mid]) / 2, 2)
        dscr_min = min(dscr_sorted)
        dscr_cover_ratio = sum(1 for d in dscr_sorted if d >= 1.0) / len(dscr_sorted)

    # Active months (non-zero operating income base)
    monthly_operating_income = [monthly_rev[i] + monthly_oi[i] for i in range(len(monthly_rev))]
    active_months = sum(1 for v in monthly_operating_income if v > 0)

    # Revenue stats
    active_rev = [v for v in monthly_operating_income if v > 0]
    rev_mean = sum(active_rev) / len(active_rev) if active_rev else 0
    rev_std = (sum((v - rev_mean) ** 2 for v in active_rev) / len(active_rev)) ** 0.5 if len(active_rev) > 1 else 0
    rev_cv = rev_std / rev_mean if rev_mean > 0 else 0

    # Slopes
    rev_slope = _slope(monthly_rev)
    opex_slope = _slope(monthly_opex)
    ebitda_slope = _slope(monthly_ebitda)

    # Event detection: months where value > 2x average
    events = []
    for i, v in enumerate(monthly_oi):
        if v > 0 and rev_mean > 0 and v > rev_mean * 2:
            events.append((i, "large_other_income", v))
    for i, v in enumerate(monthly_rev):
        if v > 0 and rev_mean > 0 and v > rev_mean * 3:
            events.append((i, "revenue_spike", v))
    for i, v in enumerate(monthly_opex):
        if v > 0 and len(active_rev) > 0:
            opex_mean = sum(monthly_opex) / len(monthly_opex) if monthly_opex else 0
            if opex_mean > 0 and v > opex_mean * 3:
                events.append((i, "expense_spike", v))

    # If disposal-like income event exists, evaluate DSCR after that event.
    sale_like_months = [i for i, etype, _ in events if etype == "large_other_income"]
    post_sale_dscr = []
    post_sale_dscr_median = None
    post_sale_dscr_cover_ratio = None
    post_sale_dscr_count = 0
    post_sale_start_month = None
    if sale_like_months:
        post_sale_start_month = min(sale_like_months) + 1  # month after one-off event
        if post_sale_start_month < len(monthly_dscr):
            post_sale_dscr = [d for d in monthly_dscr[post_sale_start_month:] if d is not None]
            if post_sale_dscr:
                post_sale_dscr_count = len(post_sale_dscr)
                ps = sorted(post_sale_dscr)
                mid = len(ps) // 2
                if len(ps) % 2:
                    post_sale_dscr_median = ps[mid]
                else:
                    post_sale_dscr_median = round((ps[mid - 1] + ps[mid]) / 2, 2)
                post_sale_dscr_cover_ratio = sum(1 for d in ps if d >= 1.0) / len(ps)

    return {
        "monthly_revenue": [round(v, 2) for v in monthly_rev],
        "monthly_opex": [round(v, 2) for v in monthly_opex],
        "monthly_cos": [round(v, 2) for v in monthly_cos],
        "monthly_ebitda": [round(v, 2) for v in monthly_ebitda],
        "monthly_finance_charges": [round(v, 2) for v in monthly_fc],
        "monthly_other_income": [round(v, 2) for v in monthly_oi],
        "monthly_dscr": monthly_dscr,
        "dscr_median": round(dscr_median, 2) if dscr_median is not None else None,
        "dscr_min": round(dscr_min, 2) if dscr_min is not None else None,
        "dscr_cover_ratio": round(dscr_cover_ratio, 2) if dscr_cover_ratio is not None else None,
        "post_sale_start_month": post_sale_start_month,
        "post_sale_dscr_median": round(post_sale_dscr_median, 2) if post_sale_dscr_median is not None else None,
        "post_sale_dscr_cover_ratio": round(post_sale_dscr_cover_ratio, 2) if post_sale_dscr_cover_ratio is not None else None,
        "post_sale_dscr_count": post_sale_dscr_count,
        "active_months": active_months,
        "revenue_mean": round(rev_mean, 2),
        "revenue_cv": round(rev_cv, 3),
        "revenue_slope": round(rev_slope, 2) if rev_slope is not None else None,
        "opex_slope": round(opex_slope, 2) if opex_slope is not None else None,
        "ebitda_slope": round(ebitda_slope, 2) if ebitda_slope is not None else None,
        "event_months": events,
    }


def analyse_bs_trajectory(mgmt_data: dict) -> dict:
    """Analyse BS trajectory from management account monthly cumulative positions.

    Returns dict with:
      - monthly_equity, monthly_assets, monthly_debt, monthly_cash, monthly_ar, monthly_ap
      - de_trajectory: monthly D/E ratios
      - ltv_trajectory: monthly LTV (debt / fixed assets)
      - deleveraging_rate: monthly change in total debt
      - cash_burn_rate: average monthly cash change
      - equity_cure: True if equity went from negative to positive
    """
    bs = mgmt_data.get("statement_of_financial_position", {})
    if not bs:
        return {}

    def _get_monthly(path_keys):
        node = bs
        for k in path_keys:
            if not isinstance(node, dict):
                return []
            node = node.get(k, {})
        if isinstance(node, dict):
            return node.get("monthly_cumulative", [])
        return []

    def _get_vals(path_keys):
        node = bs
        for k in path_keys:
            if not isinstance(node, dict):
                return [0, 0]
            node = node.get(k, {})
        if isinstance(node, dict):
            return node.get("values", [0, 0])
        return [0, 0]

    m_equity = _get_monthly(["equity_and_liabilities", "equity", "total_equity"])
    m_assets = _get_monthly(["assets", "total_assets"])
    m_ncl = _get_monthly(["equity_and_liabilities", "non_current_liabilities", "total_non_current_liabilities"])
    m_cl = _get_monthly(["equity_and_liabilities", "current_liabilities", "total_current_liabilities"])
    m_cash = _get_monthly(["assets", "current_assets", "cash_and_bank"])
    m_ar = _get_monthly(["assets", "current_assets", "trade_receivables"])
    m_ap = _get_monthly(["equity_and_liabilities", "current_liabilities", "trade_payables"])
    m_nca = _get_monthly(["assets", "non_current_assets", "total_non_current_assets"])
    m_lt_debt = _get_monthly(["equity_and_liabilities", "non_current_liabilities", "long_term_borrowings"])

    # Total debt = NCL + CL
    m_debt = []
    for i in range(max(len(m_ncl), len(m_cl))):
        ncl = m_ncl[i] if i < len(m_ncl) else 0
        cl = m_cl[i] if i < len(m_cl) else 0
        m_debt.append(round(ncl + cl, 2))

    # D/E ratio trajectory
    de_traj = []
    for i in range(len(m_equity)):
        eq = m_equity[i] if i < len(m_equity) else 0
        debt = m_debt[i] if i < len(m_debt) else 0
        if eq and abs(eq) > 100:
            de_traj.append(round(abs(debt / eq), 2))
        else:
            de_traj.append(None)

    # LTV trajectory (debt / NCA)
    ltv_traj = []
    for i in range(max(len(m_lt_debt), len(m_nca))):
        debt = m_lt_debt[i] if i < len(m_lt_debt) else 0
        nca = m_nca[i] if i < len(m_nca) else 0
        if nca and abs(nca) > 100:
            ltv_traj.append(round(abs(debt / nca) * 100, 1))
        else:
            ltv_traj.append(None)

    # Deleveraging: slope of total debt
    debt_slope = _slope(m_debt) if len(m_debt) >= 3 else None

    # Cash/working-capital trajectories
    cash_slope = _slope(m_cash) if len(m_cash) >= 3 else None
    ar_slope = _slope(m_ar) if len(m_ar) >= 3 else None
    ap_slope = _slope(m_ap) if len(m_ap) >= 3 else None

    # Equity cure: did equity go from negative to positive?
    equity_cure = False
    if len(m_equity) >= 2:
        first_eq = m_equity[0] if m_equity[0] != 0 else None
        last_eq = _last_nonzero(m_equity)
        if first_eq is not None and last_eq is not None:
            equity_cure = first_eq < 0 and last_eq > 0

    # Opening vs latest for key metrics
    v_equity = _get_vals(["equity_and_liabilities", "equity", "total_equity"])
    v_assets = _get_vals(["assets", "total_assets"])
    v_debt = _get_vals(["equity_and_liabilities", "total_liabilities"])

    return {
        "monthly_equity": m_equity,
        "monthly_assets": m_assets,
        "monthly_debt": m_debt,
        "monthly_cash": m_cash,
        "monthly_ar": m_ar,
        "monthly_ap": m_ap,
        "monthly_lt_debt": m_lt_debt,
        "de_trajectory": de_traj,
        "ltv_trajectory": ltv_traj,
        "debt_slope": round(debt_slope, 0) if debt_slope is not None else None,
        "cash_slope": round(cash_slope, 0) if cash_slope is not None else None,
        "ar_slope": round(ar_slope, 0) if ar_slope is not None else None,
        "ap_slope": round(ap_slope, 0) if ap_slope is not None else None,
        "equity_cure": equity_cure,
        "equity_cy": v_equity[0],
        "equity_py": v_equity[1],
        "assets_cy": v_assets[0],
        "assets_py": v_assets[1],
        "liabilities_cy": v_debt[0],
        "liabilities_py": v_debt[1],
    }


def classify_lifecycle(
    afs_data: Optional[dict] = None,
    mgmt_data: Optional[dict] = None,
    is_analysis: Optional[dict] = None,
    bs_analysis: Optional[dict] = None,
) -> dict:
    """Classify entity lifecycle stage from AFS + management account analysis.

    Returns dict:
      - stage: stage key
      - label, color, detail: display values
      - signals: dict of boolean/numeric signals used
      - confidence: float 0-1 (how much data supports the classification)
    """
    signals = {}

    # ---------- Input availability (4-input architecture; currently 2 live inputs) ----------
    has_afs = bool(afs_data)
    has_mgmt_accounts = bool(mgmt_data)
    # Not yet ingested in structured form in this pipeline.
    has_mgmt_report = False
    has_valuation = False

    signals["has_afs"] = has_afs
    signals["has_mgmt_accounts"] = has_mgmt_accounts
    signals["has_mgmt_report"] = has_mgmt_report
    signals["has_valuation"] = has_valuation
    signals["inputs_available"] = int(has_afs) + int(has_mgmt_accounts) + int(has_mgmt_report) + int(has_valuation)
    signals["inputs_expected"] = 4
    signals["uses_occupancy_proxy"] = (not has_mgmt_report) and has_mgmt_accounts
    signals["uses_asset_value_proxy"] = (not has_valuation) and has_afs

    # ---------- Extract AFS data ----------
    if afs_data:
        meta = afs_data.get("metadata", {})
        bs = afs_data.get("statement_of_financial_position", {})
        pl = afs_data.get("statement_of_comprehensive_income", {})
        cf = afs_data.get("statement_of_cash_flows", {})
        notes = meta.get("notes", {})

        signals["is_gc"] = meta.get("going_concern") is False
        signals["is_neg_eq"] = notes.get("negative_equity") or (_gval(bs, "equity_and_liabilities", "equity", "total_equity") or 0) < 0
        signals["is_dormant"] = bool(notes.get("dormant_entity"))
        signals["is_holdco"] = bool(notes.get("holding_company") or notes.get("pass_through_entity"))

        afs_rev = _gval(pl, "revenue")
        afs_rev_py = _gval(pl, "revenue", idx=1)
        signals["afs_rev"] = abs(afs_rev) if afs_rev else None
        signals["afs_rev_py"] = abs(afs_rev_py) if afs_rev_py else None

        # EBITDA from AFS
        ebitda = None
        for ek in ["operating_profit", "operating_loss", "operating_profit_loss"]:
            ebitda = _gval(pl, ek)
            if ebitda is not None:
                for dk in ["depreciation", "depreciation_and_amortisation"]:
                    dep = _gval(pl, dk)
                    if dep is not None:
                        ebitda += abs(dep)
                        break
                break
        signals["afs_ebitda"] = ebitda

        fc = _gval(pl, "finance_costs")
        signals["afs_fc"] = abs(fc) if fc else None
        signals["asset_sale_proceeds"] = _gval(cf, "investing_activities", "proceeds_from_sale_of_investment_property")
        signals["asset_purchase_capex"] = _gval(cf, "investing_activities", "purchase_of_investment_property")

        te = _gval(bs, "equity_and_liabilities", "equity", "total_equity")
        te_py = _gval(bs, "equity_and_liabilities", "equity", "total_equity", idx=1)
        signals["afs_equity"] = te
        signals["afs_equity_py"] = te_py
        ta = _gval(bs, "assets", "total_assets")
        tl = _gval(bs, "equity_and_liabilities", "total_liabilities")
        if tl is None and ta is not None and te is not None:
            tl = ta - te
        signals["afs_assets"] = ta
        signals["afs_liabilities"] = tl
    else:
        signals["is_gc"] = False
        signals["is_neg_eq"] = False
        signals["is_dormant"] = False
        signals["is_holdco"] = False

    # ---------- Management account IS signals ----------
    if is_analysis:
        n_months = is_analysis.get("active_months", 0)
        signals["mgmt_active_months"] = n_months
        signals["mgmt_rev_total"] = sum(is_analysis.get("monthly_revenue", []))
        signals["mgmt_rev_mean"] = is_analysis.get("revenue_mean", 0)
        signals["mgmt_rev_slope"] = is_analysis.get("revenue_slope")
        signals["mgmt_rev_cv"] = is_analysis.get("revenue_cv", 0)
        signals["mgmt_ebitda_slope"] = is_analysis.get("ebitda_slope")
        signals["mgmt_events"] = len(is_analysis.get("event_months", []))

        ann_factor = 12 / n_months if n_months > 0 else 1.2
        signals["mgmt_rev_ann"] = signals["mgmt_rev_total"] * ann_factor
        ebitda_total = sum(is_analysis.get("monthly_ebitda", []))
        signals["mgmt_ebitda_ann"] = ebitda_total * ann_factor

        # Monthly DSCR
        dscrs = [d for d in is_analysis.get("monthly_dscr", []) if d is not None]
        signals["mgmt_dscr_avg"] = sum(dscrs) / len(dscrs) if dscrs else None
        signals["mgmt_dscr_min"] = min(dscrs) if dscrs else None
        signals["mgmt_dscr_median"] = is_analysis.get("dscr_median")
        signals["mgmt_dscr_cover_ratio"] = is_analysis.get("dscr_cover_ratio")
        signals["post_sale_start_month"] = is_analysis.get("post_sale_start_month")
        signals["post_sale_dscr_median"] = is_analysis.get("post_sale_dscr_median")
        signals["post_sale_dscr_cover_ratio"] = is_analysis.get("post_sale_dscr_cover_ratio")
        signals["post_sale_dscr_count"] = is_analysis.get("post_sale_dscr_count")

    # Prefer direct operating profit/loss from management JSON only if
    # monthly IS analysis was unavailable.
    if mgmt_data:
        m_pl = mgmt_data.get("statement_of_comprehensive_income", {})
        m_op_cy = None
        for key in ["operating_profit_loss", "operating_profit", "operating_loss", "gross_profit"]:
            item = m_pl.get(key)
            if isinstance(item, dict) and "values" in item:
                vals = item.get("values", [])
                if vals and vals[0] is not None:
                    m_op_cy = float(vals[0])
                    break
        if m_op_cy is not None and not is_analysis:
            mip = mgmt_data.get("metadata", {}).get("months_in_period", {})
            n_months = mip.get("current_year", 10)
            if not isinstance(n_months, (int, float)) or n_months <= 0:
                n_months = 10
            ann_factor = 12 / n_months
            signals["mgmt_ebitda_ann"] = m_op_cy * ann_factor

    # ---------- Management account BS signals ----------
    if bs_analysis:
        signals["mgmt_equity_cy"] = bs_analysis.get("equity_cy", 0)
        signals["mgmt_equity_py"] = bs_analysis.get("equity_py", 0)
        signals["mgmt_equity_cure"] = bs_analysis.get("equity_cure", False)
        signals["mgmt_debt_slope"] = bs_analysis.get("debt_slope")
        signals["mgmt_cash_slope"] = bs_analysis.get("cash_slope")
        signals["mgmt_ar_slope"] = bs_analysis.get("ar_slope")
        signals["mgmt_ap_slope"] = bs_analysis.get("ap_slope")
        signals["mgmt_assets_cy"] = bs_analysis.get("assets_cy", 0)

        # Update neg equity from mgmt if available
        if bs_analysis.get("equity_cy", 0) < 0:
            signals["is_neg_eq"] = True

    # ---------- Derived signals ----------
    has_revenue = (signals.get("afs_rev") and signals["afs_rev"] > 0) or (signals.get("mgmt_rev_ann") and signals["mgmt_rev_ann"] > 0)
    has_ebitda = (signals.get("afs_ebitda") and signals["afs_ebitda"] > 0) or (signals.get("mgmt_ebitda_ann") and signals["mgmt_ebitda_ann"] > 0)

    fc = signals.get("afs_fc") or 0
    best_ebitda = signals.get("mgmt_ebitda_ann") or signals.get("afs_ebitda") or 0
    covers_fc = best_ebitda > fc > 0

    # Override only when DSCR is consistently supportive (robust stats).
    # If disposal-like event happened, use post-sale DSCR only.
    mgmt_dscr_med = signals.get("mgmt_dscr_median")
    mgmt_dscr_cover_ratio = signals.get("mgmt_dscr_cover_ratio")
    sale_like_event = signals.get("post_sale_start_month") is not None
    if (sale_like_event and signals.get("post_sale_dscr_median") is not None and
            (signals.get("post_sale_dscr_count") or 0) >= 3):
        mgmt_dscr_med = signals.get("post_sale_dscr_median")
        mgmt_dscr_cover_ratio = signals.get("post_sale_dscr_cover_ratio")
    if (mgmt_dscr_med is not None and mgmt_dscr_med >= 1.0 and
            mgmt_dscr_cover_ratio is not None and mgmt_dscr_cover_ratio >= 0.7):
        covers_fc = True
        has_ebitda = True

    # Revenue trajectory
    rev_improving = False
    rev_declining = False
    if signals.get("mgmt_rev_ann") and signals.get("afs_rev") and signals["afs_rev"] > 0:
        pct = _pct_change(signals["afs_rev"], signals["mgmt_rev_ann"])
        signals["rev_pct_change"] = pct
        if pct is not None:
            rev_improving = pct > 2
            rev_declining = pct < -5
    elif signals.get("afs_rev") and signals.get("afs_rev_py") and signals["afs_rev_py"] > 0:
        pct = _pct_change(signals["afs_rev_py"], signals["afs_rev"])
        signals["rev_pct_change"] = pct
        if pct is not None:
            rev_improving = pct > 2
            rev_declining = pct < -10

    # EBITDA trajectory
    ebitda_improving = False
    if signals.get("mgmt_ebitda_ann") and signals.get("afs_ebitda"):
        ebitda_improving = signals["mgmt_ebitda_ann"] > signals["afs_ebitda"] * 1.02
    elif signals.get("mgmt_ebitda_slope") is not None:
        ebitda_improving = signals["mgmt_ebitda_slope"] > 0

    # Equity trajectory
    equity_improving = False
    if signals.get("mgmt_equity_cure"):
        equity_improving = True
    elif signals.get("mgmt_equity_cy") and signals.get("mgmt_equity_py"):
        equity_improving = signals["mgmt_equity_cy"] > signals["mgmt_equity_py"]
    elif signals.get("afs_equity") and signals.get("afs_equity_py"):
        equity_improving = signals["afs_equity"] > signals["afs_equity_py"]

    # Deleveraging / collections proxy
    deleveraging = signals.get("mgmt_debt_slope") is not None and signals["mgmt_debt_slope"] < 0
    collections_stress = False
    ar_slope = signals.get("mgmt_ar_slope")
    cash_slope = signals.get("mgmt_cash_slope")
    if ar_slope is not None:
        # AR build while cash weak/declining is a proxy for collections pressure.
        collections_stress = ar_slope > 0 and (cash_slope is None or cash_slope <= 0)

    signals["has_revenue"] = has_revenue
    signals["has_ebitda"] = has_ebitda
    signals["covers_fc"] = covers_fc
    signals["rev_improving"] = rev_improving
    signals["rev_declining"] = rev_declining
    signals["ebitda_improving"] = ebitda_improving
    signals["equity_improving"] = equity_improving
    signals["deleveraging"] = deleveraging
    signals["collections_stress"] = collections_stress

    # ---------- Primary-vs-secondary rule ladder ----------
    afs_assets = signals.get("afs_assets")
    afs_liabilities = signals.get("afs_liabilities")
    afs_equity = signals.get("afs_equity")
    afs_ebitda = signals.get("afs_ebitda")
    afs_fc = signals.get("afs_fc")

    primary_bs_clear = False
    if isinstance(afs_assets, (int, float)) and isinstance(afs_liabilities, (int, float)):
        primary_bs_clear = afs_assets > afs_liabilities
    elif isinstance(afs_equity, (int, float)):
        primary_bs_clear = afs_equity > 0

    primary_cover_clear = False
    if isinstance(afs_ebitda, (int, float)):
        if isinstance(afs_fc, (int, float)) and afs_fc > 0:
            primary_cover_clear = afs_ebitda > afs_fc
        else:
            primary_cover_clear = afs_ebitda > 0

    primary_on_track = primary_bs_clear and primary_cover_clear

    sec_neg = 0
    if rev_declining:
        sec_neg += 1
    if collections_stress:
        sec_neg += 1
    dscr_for_risk = signals.get("mgmt_dscr_median")
    if (signals.get("post_sale_start_month") is not None and
            signals.get("post_sale_dscr_median") is not None and
            (signals.get("post_sale_dscr_count") or 0) >= 3):
        dscr_for_risk = signals.get("post_sale_dscr_median")
    if dscr_for_risk is not None and dscr_for_risk < 1.0:
        sec_neg += 1
    if signals.get("mgmt_ebitda_ann") is not None and signals["mgmt_ebitda_ann"] < 0:
        sec_neg += 1
    if signals.get("mgmt_ebitda_ann") is not None and isinstance(afs_ebitda, (int, float)) and afs_ebitda > 0:
        if signals["mgmt_ebitda_ann"] < afs_ebitda * 0.9:
            sec_neg += 1

    sec_pos = 0
    if rev_improving:
        sec_pos += 1
    if ebitda_improving:
        sec_pos += 1
    if signals.get("mgmt_dscr_avg") is not None and signals["mgmt_dscr_avg"] >= 1.0:
        sec_pos += 1
    if not collections_stress:
        sec_pos += 1

    deteriorating_secondary = sec_neg >= 2
    mixed_signals = sec_neg > 0 and sec_pos > 0 and not primary_on_track

    signals["primary_bs_clear"] = primary_bs_clear
    signals["primary_cover_clear"] = primary_cover_clear
    signals["primary_on_track"] = primary_on_track
    signals["deteriorating_secondary"] = deteriorating_secondary
    signals["mixed_signals"] = mixed_signals

    # ---------- Classification decision tree ----------
    if signals["is_dormant"]:
        stage, detail = "dormant", "Shell entity — no trading activity."
    elif signals["is_holdco"]:
        stage, detail = "holding", "Investment vehicle — no direct operations."
    elif primary_on_track and not deteriorating_secondary:
        stage, detail = "cash_generating", "AFS confirms A > L and EBITDA covers debt service burden."
    elif primary_on_track and deteriorating_secondary:
        stage, detail = "stabilising", "AFS is strong, but management accounts indicate deterioration. Monitor closely."
    elif signals["is_gc"] and not has_ebitda and not rev_improving:
        stage, detail = "distressed", "Going concern, no positive EBITDA, revenue not improving."
    elif signals["is_neg_eq"] and not has_ebitda and not rev_improving:
        if has_revenue and not rev_declining:
            stage, detail = "early_stage", "A > L gap closing. Revenue present but EBITDA not yet positive."
        else:
            stage, detail = "stalled", "Negative equity, no EBITDA, revenue absent or declining."
    elif signals["is_gc"] and has_revenue and (has_ebitda or ebitda_improving):
        if covers_fc:
            stage, detail = "cash_generating", "EBITDA covers finance costs despite GC flag."
        elif has_ebitda:
            stage, detail = "growth", "GC flag but EBITDA positive, recovering."
        else:
            stage, detail = "early_stage", "GC flag, revenue present, trajectory improving."
    elif signals["is_neg_eq"] and has_ebitda:
        if covers_fc:
            stage, detail = "stabilising", "Negative equity (acquisition debt) but EBITDA covers finance costs."
        elif rev_improving or ebitda_improving:
            stage, detail = "early_stage", "Negative equity, EBITDA positive and improving."
        else:
            stage, detail = "stabilising", "Negative equity but EBITDA positive."
    elif signals["is_neg_eq"] and has_revenue:
        if rev_improving:
            stage, detail = "early_stage", "Negative equity, revenue present and growing."
        else:
            stage, detail = "stalled", "Negative equity, revenue present but not improving."
    elif mixed_signals:
        stage, detail = "growth", "Signals are mixed between AFS and management trend proxies; escalate to management report/valuation."
    elif collections_stress and not covers_fc:
        stage, detail = "stalled", "Collections pressure (AR build-up) with insufficient debt-service cover."
    elif covers_fc:
        stage, detail = "cash_generating", "EBITDA exceeds finance costs. Self-sustaining."
    elif has_ebitda:
        stage, detail = "growth", "Positive EBITDA, building towards covering finance costs."
    elif has_revenue:
        stage, detail = "revenue_only", "Revenue flowing but limited profitability."
    else:
        stage, detail = "unknown", "Insufficient data to classify."

    # Confidence scoring (0-1): how much data backs this classification
    data_points = sum([
        bool(signals.get("afs_rev")),
        bool(signals.get("afs_ebitda")),
        bool(signals.get("afs_equity")),
        bool(signals.get("mgmt_rev_ann")),
        bool(signals.get("mgmt_ebitda_ann")),
        bool(bs_analysis),
        bool(is_analysis and is_analysis.get("active_months", 0) >= 6),
    ])
    confidence = min(data_points / 7, 1.0)
    if primary_on_track and not deteriorating_secondary:
        confidence = max(confidence, 0.85)
    if primary_on_track and deteriorating_secondary:
        confidence = max(confidence, 0.75)
    if mixed_signals:
        confidence = min(confidence, 0.65)

    info = LIFECYCLE_STAGES[stage]
    return {
        "stage": stage,
        "label": info["label"],
        "color": info["color"],
        "detail": detail,
        "severity": info["severity"],
        "confidence": round(confidence, 2),
        "signals": signals,
    }


def generate_story(
    entity_name: str,
    lifecycle: dict,
    is_analysis: Optional[dict] = None,
    bs_analysis: Optional[dict] = None,
) -> list:
    """Generate narrative story paragraphs for ECA assessment.

    Returns list of markdown strings.
    """
    sig = lifecycle.get("signals", {})
    stage = lifecycle["stage"]
    color = lifecycle["color"]
    story = []

    # ── Opening: lifecycle context ──
    openers = {
        "cash_generating": f"**{entity_name}** is a self-sustaining, cash-generating property investment. EBITDA comfortably covers finance costs.",
        "growth": f"**{entity_name}** is in a growth phase — generating positive EBITDA but not yet fully covering finance costs.",
        "stabilising": f"**{entity_name}** is stabilising. {'Negative equity reflects acquisition debt structure, not operational distress. ' if sig.get('is_neg_eq') else ''}"
                        f"EBITDA is positive {'and improving.' if sig.get('ebitda_improving') else 'but flat.'}",
        "early_stage": f"**{entity_name}** is in an early stage of its investment lifecycle. "
                       f"{'Revenue is present and ' + ('growing.' if sig.get('rev_improving') else 'building.') if sig.get('has_revenue') else 'Revenue not yet established.'}",
        "stalled": f"**{entity_name}** is stalled — {'declining' if sig.get('rev_declining') else 'stagnant'} revenue and no meaningful EBITDA generation.",
        "distressed": f"**{entity_name}** is in distress. Going concern qualification by auditors, insufficient EBITDA to service debt.",
        "revenue_only": f"**{entity_name}** generates revenue but profitability is limited. Operating costs absorb most income.",
        "holding": f"**{entity_name}** is a holding entity — value lies in subsidiaries.",
        "dormant": f"**{entity_name}** is a dormant shell entity with no trading activity.",
        "unknown": f"**{entity_name}** — insufficient data to assess.",
    }
    story.append(openers.get(stage, f"**{entity_name}** — lifecycle stage: {lifecycle['label']}."))

    # Input coverage + proxy caveat
    avail = sig.get("inputs_available", 0)
    exp = sig.get("inputs_expected", 4)
    if avail < exp:
        caveat = f"Input coverage is {avail}/{exp}."
        if sig.get("uses_occupancy_proxy"):
            caveat += " Occupancy/lease quality inferred via rental, AR/AP and debt-service proxies (management report missing)."
        if sig.get("uses_asset_value_proxy"):
            caveat += " Asset-base strength inferred from accounting carrying values (external valuation missing)."
        story.append(caveat)
    if sig.get("mixed_signals"):
        story.append("AFS and management-account trend proxies are mixed. Next evidence step: management report + external valuation.")
    if sig.get("deteriorating_secondary"):
        story.append("Management-account trend layer indicates deterioration against AFS baseline; put entity on watchlist.")

    # ── Revenue trajectory ──
    if sig.get("mgmt_rev_ann") and sig.get("afs_rev") and sig["afs_rev"] > 0:
        pct = sig.get("rev_pct_change", 0)
        m_rev = sig["mgmt_rev_ann"]
        a_rev = sig["afs_rev"]
        if sig["rev_improving"]:
            story.append(f"Revenue trajectory is **positive**: annualised management accounts show R{m_rev/1e6:.1f}M "
                         f"vs FY AFS R{a_rev/1e6:.1f}M ({pct:+.0f}%).")
        elif sig["rev_declining"]:
            story.append(f"Revenue is **declining**: management accounts annualise to R{m_rev/1e6:.1f}M "
                         f"vs FY AFS R{a_rev/1e6:.1f}M ({pct:+.0f}%). Occupancy or rental rate erosion suspected.")
        else:
            story.append(f"Revenue is **stable** at R{m_rev/1e6:.1f}M annualised vs R{a_rev/1e6:.1f}M FY ({pct:+.0f}%).")

    # ── Asset disposal signal (AFS cash flow) ──
    sale_proceeds = sig.get("asset_sale_proceeds")
    afs_rev = sig.get("afs_rev") or 0
    if sale_proceeds and sale_proceeds > 0:
        sale_ratio = (sale_proceeds / afs_rev) if afs_rev > 0 else None
        if stage in ("distressed", "stalled") or (sale_ratio is not None and sale_ratio > 0.5):
            story.append(
                f"Asset sale proceeds of R{sale_proceeds/1e6:.1f}M indicate **disposal-led liquidity**. "
                "Treat this as one-off support until recurring EBITDA covers debt service."
            )
        else:
            story.append(
                f"Asset sale proceeds of R{sale_proceeds/1e6:.1f}M are present. "
                "Separate one-off disposal cash from recurring operating performance."
            )

    # ── IS monthly signals ──
    if is_analysis:
        active = is_analysis.get("active_months", 0)
        rev_cv = is_analysis.get("revenue_cv", 0)
        if active >= 6 and rev_cv > 0.3:
            story.append(f"Revenue is **volatile** (CV={rev_cv:.0%}) — indicates tenant churn or seasonal dependency.")
        elif active >= 6 and rev_cv < 0.1:
            story.append(f"Revenue is **stable month-to-month** (CV={rev_cv:.0%}) — strong tenant base with predictable income.")

        # Event detection
        events = is_analysis.get("event_months", [])
        for mi, etype, mag in events:
            month = MONTH_LABELS[mi] if mi < len(MONTH_LABELS) else f"M{mi+1}"
            if etype == "large_other_income":
                story.append(f"Significant other income of R{mag/1e6:.1f}M in {month} — likely property revaluation or disposal gain.")

        # DSCR
        dscr_med = sig.get("mgmt_dscr_median")
        dscr_min = sig.get("mgmt_dscr_min")
        dscr_cover_ratio = sig.get("mgmt_dscr_cover_ratio")
        if (sig.get("post_sale_start_month") is not None and
                sig.get("post_sale_dscr_median") is not None and
                (sig.get("post_sale_dscr_count") or 0) >= 3):
            dscr_med = sig.get("post_sale_dscr_median")
            dscr_cover_ratio = sig.get("post_sale_dscr_cover_ratio")
            story.append("DSCR assessment is based on **post-sale months** to remove one-off disposal distortion.")
        if dscr_med is not None:
            _ratio_txt = f"; months >=1.0x: {dscr_cover_ratio:.0%}" if dscr_cover_ratio is not None else ""
            if dscr_med >= 1.5:
                story.append(f"Monthly DSCR median is **{dscr_med:.2f}x**{_ratio_txt} — comfortable debt service coverage.")
            elif dscr_med >= 1.0:
                story.append(f"Monthly DSCR median is **{dscr_med:.2f}x**{_ratio_txt} — marginal, limited headroom.")
            else:
                story.append(f"Monthly DSCR median is **{dscr_med:.2f}x**{_ratio_txt} — **cannot service debt** from operations "
                             f"(worst month: {dscr_min:.2f}x).")

    # ── BS trajectory ──
    if bs_analysis:
        # Equity cure
        if bs_analysis.get("equity_cure"):
            eq_py = bs_analysis.get("equity_py", 0)
            eq_cy = bs_analysis.get("equity_cy", 0)
            story.append(f"**Equity cure achieved**: from R{eq_py/1e6:.1f}M to R{eq_cy/1e6:.1f}M — "
                         "significant balance sheet transformation.")
        elif sig.get("is_neg_eq"):
            eq = bs_analysis.get("equity_cy", 0)
            if sig.get("equity_improving"):
                story.append(f"Equity is negative (R{eq/1e6:.1f}M) but **improving**. "
                             "Structural — resolves with property revaluation if EBITDA sustains.")
            else:
                story.append(f"Equity is negative (R{eq/1e6:.1f}M) and not improving. "
                             f"{'Positive EBITDA suggests this is structural (acquisition debt).' if sig.get('has_ebitda') else 'No EBITDA to support recovery.'}")

        # Deleveraging
        if sig.get("deleveraging"):
            debt_slope = bs_analysis.get("debt_slope", 0)
            story.append(f"Active **deleveraging**: debt reducing by ~R{abs(debt_slope)/1e6:.1f}M/month.")
        elif sig.get("mgmt_debt_slope") and sig["mgmt_debt_slope"] > 0:
            story.append("Debt is **increasing** — new borrowings or capitalised interest growing the debt stack.")

        # Cash position
        cash_slope = bs_analysis.get("cash_slope")
        if cash_slope is not None:
            m_cash = bs_analysis.get("monthly_cash", [])
            last_cash = _last_nonzero(m_cash)
            if cash_slope < 0 and last_cash is not None:
                story.append(f"Cash position **declining** at ~R{abs(cash_slope)/1e3:.0f}k/month. "
                             f"Current: R{last_cash/1e6:.1f}M.")
            elif cash_slope > 0 and last_cash is not None:
                story.append(f"Cash position **building** at ~R{abs(cash_slope)/1e3:.0f}k/month. "
                             f"Current: R{last_cash/1e6:.1f}M.")
        ar_slope = bs_analysis.get("ar_slope")
        if ar_slope is not None and ar_slope > 0:
            story.append("Trade receivables are trending up; monitor arrears/collections versus rental growth.")

        # D/E trajectory
        de = bs_analysis.get("de_trajectory", [])
        if len(de) >= 3:
            de_active = [d for d in de if d is not None]
            if len(de_active) >= 2:
                de_first = de_active[0]
                de_last = de_active[-1]
                if de_first > 5 and de_last < de_first * 0.5:
                    story.append(f"D/E ratio improved dramatically: {de_first:.1f}x → {de_last:.1f}x.")
                elif de_last > 5:
                    story.append(f"Highly leveraged at {de_last:.1f}x D/E. Equity thin relative to debt stack.")

    # ── Conclusion ──
    conclusions = {
        "cash_generating": f"**Conclusion**: {entity_name} supports the guarantor portfolio. No material concerns.",
        "growth": f"**Conclusion**: {entity_name} is building coverage. Monitor quarterly management accounts.",
        "stabilising": f"**Conclusion**: {entity_name} is recovering. Independent revaluation needed to confirm equity.",
        "early_stage": f"**Conclusion**: {entity_name} is building. Limited current contribution but not a drag.",
        "revenue_only": f"**Conclusion**: {entity_name} has limited contribution. Upside if occupancy improves.",
        "stalled": f"**Conclusion**: {entity_name} requires management intervention. Stalled trajectory reduces guarantor strength.",
        "distressed": f"**Conclusion**: {entity_name} is a **negative factor**. ECA should factor in potential write-down.",
        "holding": f"**Conclusion**: {entity_name} — assess underlying subsidiaries for value.",
        "dormant": f"**Conclusion**: {entity_name} — no financial contribution.",
    }
    story.append(conclusions.get(stage, f"**Conclusion**: {entity_name} — insufficient data."))

    return story


def analyse_entity(entity_name: str, afs_data: Optional[dict], mgmt_data: Optional[dict]) -> dict:
    """Full analysis pipeline for a single entity.

    Returns:
      - lifecycle: classification result
      - is_analysis: IS monthly analysis (if mgmt data available)
      - bs_analysis: BS trajectory analysis (if mgmt data available)
      - story: list of narrative paragraphs
    """
    is_analysis = analyse_is_monthly(mgmt_data) if mgmt_data and mgmt_data.get("general_ledger_detail") else None
    bs_analysis = analyse_bs_trajectory(mgmt_data) if mgmt_data and mgmt_data.get("statement_of_financial_position") else None

    lifecycle = classify_lifecycle(afs_data, mgmt_data, is_analysis, bs_analysis)
    story = generate_story(entity_name, lifecycle, is_analysis, bs_analysis)

    return {
        "entity": entity_name,
        "lifecycle": lifecycle,
        "is_analysis": is_analysis,
        "bs_analysis": bs_analysis,
        "story": story,
    }


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Analyse all management account JSONs and print results."""
    import re_extract_mgmt_accounts as extractor

    print("=" * 80)
    print("Guarantor Financial Analysis Engine")
    print("=" * 80)

    for base, xlsx, jname, grp in extractor.FILE_MAP:
        json_path = base / jname
        if not json_path.exists():
            print(f"\n  SKIP: {jname} — not found")
            continue

        with open(json_path, "r") as f:
            data = json.load(f)

        entity = data.get("metadata", {}).get("entity", {}).get("legal_name", jname)
        result = analyse_entity(entity, afs_data=None, mgmt_data=data)
        lc = result["lifecycle"]

        print(f"\n{'='*60}")
        print(f"  {entity}")
        print(f"  Stage: {lc['label']} ({lc['color']}) — Confidence: {lc['confidence']:.0%}")
        print(f"  {lc['detail']}")

        if result["is_analysis"]:
            ia = result["is_analysis"]
            print(f"  IS: {ia['active_months']} months, Rev mean R{ia['revenue_mean']/1e6:.2f}M/mo, "
                  f"CV={ia['revenue_cv']:.0%}, Slope={ia['revenue_slope']}")

        if result["bs_analysis"]:
            ba = result["bs_analysis"]
            print(f"  BS: Assets R{ba['assets_cy']/1e6:.1f}M, Equity R{ba['equity_cy']/1e6:.1f}M, "
                  f"Debt slope={ba['debt_slope']}, Cash slope={ba['cash_slope']}")

        print(f"  Story:")
        for s in result["story"]:
            print(f"    {s[:120]}")


if __name__ == "__main__":
    main()
