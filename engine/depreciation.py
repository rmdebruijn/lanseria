"""Section 12C accelerated depreciation (40/20/20/20)."""

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
