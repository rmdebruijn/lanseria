"""Semi-annual P&L with tax loss carry-forward.

compute_period_pnl(): per-period P&L for the One Big Loop.
    Interest expense is a PARAMETER (from FacilityState for this period's
    actual Opening balance), not looked up from a completed schedule.

build_semi_annual_pnl(): batch builder for standalone display / sensitivity.
    Interest expense reads FROM the facility schedule (single source of truth).
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.formulas import calc_tax
from engine.periods import period_start_month, repayment_start_month, year_index


# ── Per-period P&L calculator (for One Big Loop) ─────────────────


@dataclass
class PnlPeriod:
    """Output of compute_period_pnl()."""
    month: int
    rev: float
    opex: float
    ebitda: float
    depr: float
    ebit: float
    ie: float           # Interest expense (sr + mz)
    fd_income: float    # FD interest income (ops reserve + entity FD + mezz div FD)
    pbt: float
    tax: float
    pat: float
    tax_loss_pool: float


def compute_period_pnl(
    hi: int,
    ops_annual: list[dict],
    ops_semi_annual: list[dict] | None,
    sr_interest: float,
    mz_interest: float,
    depreciable_base: float,
    tax_rate: float,
    tax_loss_pool: float,
    *,
    fd_income: float = 0.0,
    straight_line_base: float = 0.0,
    straight_line_life: int = 20,
    depr_vector: list[float] | None = None,
) -> tuple[PnlPeriod, float]:
    """Compute a single period's P&L.

    Interest expense comes from FacilityState (this period's actual Opening
    balance), not from a completed schedule lookup.

    Args:
        hi: Semi-annual period index (0-19).
        ops_annual: 10 annual ops dicts (fallback if ops_semi_annual not provided).
        ops_semi_annual: 20 semi-annual ops dicts (preferred source).
        sr_interest: Senior IC interest for this period (from FacilityState).
        mz_interest: Mezz IC interest for this period (from FacilityState).
        depreciable_base: Total depreciable base (S12C + straight-line).
        tax_rate: Corporate tax rate (e.g. 0.27).
        tax_loss_pool: Accumulated assessed loss carried from previous period.
        straight_line_base: Portion of depreciable base under straight-line depreciation.
        straight_line_life: Straight-line asset life in years.
        depr_vector: Pre-computed per-tranche S12C depreciation vector (20 semi-annual
            amounts).  When provided, ``depr_vector[hi]`` is used for the S12C
            portion instead of the single-curve inline calculation.  The
            straight-line portion is always computed independently.

    Returns:
        (PnlPeriod, new_tax_loss_pool)
    """
    yi = year_index(hi)
    half_month = period_start_month(hi)
    s12c_base = depreciable_base - straight_line_base
    sl_annual = straight_line_base / straight_line_life if straight_line_life > 0 else 0.0

    # Revenue + COGS
    if ops_semi_annual and hi < len(ops_semi_annual):
        s = ops_semi_annual[hi]
        rev = s.get("rev_total", 0)
        opex = s.get("om_cost", 0) + s.get("power_cost", 0) + s.get("rent_cost", 0)
    else:
        op = ops_annual[yi] if ops_annual and yi < len(ops_annual) else {}
        rev = op.get("rev_total", 0) / 2
        opex = (op.get("om_cost", 0) + op.get("power_cost", 0) + op.get("rent_cost", 0)) / 2

    ebitda = rev - opex

    # Depreciation: per-tranche S12C vector (preferred) or single-curve fallback
    if depr_vector is not None and hi < len(depr_vector):
        depr_s12c = depr_vector[hi]
    elif hi >= 1:
        # Legacy single-curve: starts hi >= 1, keyed by annual year
        s12c_pcts = {0: 0.40, 1: 0.20, 2: 0.20, 3: 0.20}
        depr_s12c = s12c_base * s12c_pcts.get(yi, 0.0) / 2
    else:
        depr_s12c = 0.0

    # Straight-line portion (unchanged, independent of tranche vector)
    if hi >= 1 and yi < straight_line_life:
        depr_sl = sl_annual / 2
    else:
        depr_sl = 0.0

    depr = depr_s12c + depr_sl

    # Interest expense: direct from FacilityState (only repayment phase)
    ie = sr_interest + mz_interest

    ebit = ebitda - depr
    pbt = ebit - ie + fd_income

    # Tax with loss carry-forward
    tax, new_tax_loss_pool = calc_tax(pbt, tax_rate, tax_loss_pool)

    pat = pbt - tax

    period = PnlPeriod(
        month=half_month, rev=rev, opex=opex, ebitda=ebitda,
        depr=depr, ebit=ebit, ie=ie, fd_income=fd_income,
        pbt=pbt, tax=tax, pat=pat,
        tax_loss_pool=new_tax_loss_pool,
    )
    return period, new_tax_loss_pool


def build_semi_annual_pnl(
    ops_annual: list[dict],
    ops_semi_annual: list[dict] | None,
    sr_schedule: list[dict],
    mz_schedule: list[dict],
    depreciable_base: float,
    tax_rate: float = 0.27,
    num_periods: int = 20,
    *,
    straight_line_base: float = 0.0,
    straight_line_life: int = 20,
    depr_vector: list[float] | None = None,
) -> list[dict]:
    """Build 20-period semi-annual P&L with loss carry-forward.

    Revenue/opex from ops model. Interest from facility schedules.
    Depreciation:
        - S12C 40/20/20/20 on (depreciable_base - straight_line_base)
        - Straight-line on straight_line_base over straight_line_life years
    When straight_line_base == 0 (default), all depreciation is S12C.

    Args:
        depr_vector: Pre-computed per-tranche S12C depreciation vector.
            When provided, ``depr_vector[si]`` replaces the inline S12C
            calculation.  Straight-line portion is computed independently.

    Returns list of 20 dicts with keys:
        month, rev, opex, ebitda, depr, ebit, ie, pbt, tax, pat, tax_loss_pool
    """
    s12c_base = depreciable_base - straight_line_base
    sl_annual = straight_line_base / straight_line_life if straight_line_life > 0 else 0.0

    rows = []
    tax_loss_pool = 0.0

    for si in range(num_periods):
        yi = year_index(si)
        half_month = period_start_month(si)  # M0, M6, M12, ..., M114

        # Revenue + COGS
        if ops_semi_annual and si < len(ops_semi_annual):
            s = ops_semi_annual[si]
            rev = s.get("rev_total", 0)
            opex = s.get("om_cost", 0) + s.get("power_cost", 0) + s.get("rent_cost", 0)
        else:
            op = ops_annual[yi] if ops_annual and yi < len(ops_annual) else {}
            rev = op.get("rev_total", 0) / 2
            opex = (op.get("om_cost", 0) + op.get("power_cost", 0) + op.get("rent_cost", 0)) / 2

        ebitda = rev - opex

        # Depreciation: per-tranche S12C vector (preferred) or single-curve fallback
        if depr_vector is not None and si < len(depr_vector):
            depr_s12c = depr_vector[si]
        elif si >= 1:
            # Legacy single-curve: starts si >= 1, keyed by annual year
            s12c_pcts = {0: 0.40, 1: 0.20, 2: 0.20, 3: 0.20}
            depr_s12c = s12c_base * s12c_pcts.get(yi, 0.0) / 2
        else:
            depr_s12c = 0.0

        # Straight-line portion (unchanged, independent of tranche vector)
        if si >= 1 and yi < straight_line_life:
            depr_sl = sl_annual / 2
        else:
            depr_sl = 0.0

        depr = depr_s12c + depr_sl

        # Interest expense from IC schedules (only M24+ — IDC is capitalised)
        ie = 0.0
        if half_month >= repayment_start_month():
            for r in sr_schedule:
                if r["Month"] == half_month:
                    ie += r["Interest"]
                    break
            for r in mz_schedule:
                if r["Month"] == half_month:
                    ie += r["Interest"]
                    break

        ebit = ebitda - depr
        pbt = ebit - ie

        # Tax with loss carry-forward
        tax, tax_loss_pool = calc_tax(pbt, tax_rate, tax_loss_pool)

        pat = pbt - tax
        rows.append({
            "month": half_month, "rev": rev, "opex": opex,
            "ebitda": ebitda, "depr": depr, "ebit": ebit,
            "ie": ie, "pbt": pbt, "tax": tax, "pat": pat,
            "tax_loss_pool": tax_loss_pool,
        })

    return rows


def extract_tax_vector(semi_annual_pl: list[dict]) -> list[float]:
    """Extract semi-annual tax vector for waterfall engine."""
    return [p["tax"] for p in semi_annual_pl]
