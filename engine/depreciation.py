"""Section 12C accelerated depreciation (40/20/20/20).

Two modes:
1. Single-curve (legacy): apply one 40/20/20/20 curve to the full
   depreciable base starting at a fixed period.
2. Per-tranche (new): each construction drawdown tranche gets its own
   40/20/20/20 curve starting from the period AFTER delivery.
"""

from __future__ import annotations

from engine.formulas import calc_s12c_depreciation
from engine.periods import year_index


def build_s12c_schedule(depreciable_base: float, num_years: int = 10,
                        start_year_index: int = 1) -> list[float]:
    """Build annual depreciation vector (10 years).

    S12C starts from start_year_index (default 1 = Y2, after COD at M18).
    Returns list of 10 annual depreciation amounts.
    """
    schedule = []
    s12c_year = 0
    for yi in range(num_years):
        if yi >= start_year_index:
            depr = calc_s12c_depreciation(depreciable_base, s12c_year)
            s12c_year += 1
        else:
            depr = 0.0
        schedule.append(depr)
    return schedule


def build_s12c_semi_annual(depreciable_base: float, num_periods: int = 20,
                           start_semi_index: int = 1) -> list[float]:
    """Build semi-annual depreciation vector (20 periods).

    Matches app.py L3306-3312 exactly:
        if si >= 1:
            _s12c_pcts = {0: 0.40, 1: 0.20, 2: 0.20, 3: 0.20}
            _sa_depr = depreciable_base * _s12c_pcts.get(yi, 0.0) / 2

    yi = si // 2 (annual year index, 0-based).
    The S12C lookup key IS yi directly (not offset).
    Each semi-annual amount = annual_pct * base / 2.
    """
    schedule = []
    for si in range(num_periods):
        if si >= start_semi_index:
            yi = year_index(si)
            # S12C table uses yi directly as the lookup key
            annual = calc_s12c_depreciation(depreciable_base, yi)
            schedule.append(annual / 2.0)
        else:
            schedule.append(0.0)
    return schedule


# ── Per-tranche S12C depreciation ─────────────────────────────────

_S12C_ANNUAL_PCTS = [0.40, 0.20, 0.20, 0.20]  # 4-year curve


def build_tranche_s12c_vector(
    draw_amounts: list[float],
    n_periods: int = 20,
) -> list[float]:
    """Build semi-annual S12C vector with per-tranche curves.

    Each construction tranche (delivered at semi-annual index hi=T) starts
    its own 40/20/20/20 S12C curve from hi=T+1.  Within each S12C annual
    year the annual depreciation amount is split equally across the two
    semi-annual periods of that year.

    The S12C "annual year" for a target period *hi* relative to tranche *T*
    is::

        s12c_year = (hi - T - 1) // 2      (0-based)

    This means:
        - Tranche T=0 (delivered C1, M0-M6):
          hi=1 -> s12c_yr=0 (40%), hi=2 -> yr=0, hi=3 -> yr=1 (20%), ...
        - Tranche T=3 (delivered C4, M18-M24):
          hi=4 -> s12c_yr=0 (40%), hi=5 -> yr=0, ...

    Conservation guarantee::

        sum(vector) == sum(draw_amounts)

    Each tranche's full 100% is exhausted over 4 annual years (8 semi-
    annual periods).

    Args:
        draw_amounts: Per-construction-period draw amounts (entity-level,
                      already pro-rata'd).  Length = number of construction
                      periods (typically 4).
        n_periods:    Total semi-annual periods (default 20).

    Returns:
        List of *n_periods* semi-annual S12C depreciation amounts.
    """
    vector = [0.0] * n_periods

    for tranche_hi, amount in enumerate(draw_amounts):
        if amount <= 0:
            continue
        for hi in range(tranche_hi + 1, n_periods):
            s12c_year = (hi - tranche_hi - 1) // 2
            if s12c_year >= len(_S12C_ANNUAL_PCTS):
                break
            vector[hi] += amount * _S12C_ANNUAL_PCTS[s12c_year] / 2.0

    return vector
