"""Period timeline from periods.json."""

from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache
from typing import NamedTuple

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class Period(NamedTuple):
    index: int
    label: str
    start_month: int
    end_month: int
    phase: str
    year: int
    year_fraction: float


@lru_cache(maxsize=1)
def load_periods() -> list[Period]:
    """Load the 20-period timeline from periods.json."""
    with open(_CONFIG_DIR / "periods.json", "r") as f:
        data = json.load(f)
    return [Period(**p) for p in data["periods"]]


@lru_cache(maxsize=1)
def load_periods_meta() -> dict:
    """Load metadata (construction_end_index, total_periods, etc.)."""
    with open(_CONFIG_DIR / "periods.json", "r") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if k != "periods"}


def total_periods() -> int:
    return load_periods_meta()["total_periods"]


def total_years() -> int:
    return len(load_periods_meta()["years"])


def construction_end_index() -> int:
    return load_periods_meta()["construction_end_index"]


def repayment_start_index() -> int:
    return load_periods_meta()["repayment_start_index"]


def is_construction(index: int) -> bool:
    return index <= construction_end_index()


def is_repayment(index: int) -> bool:
    meta = load_periods_meta()
    return meta["repayment_start_index"] <= index <= meta["repayment_end_index"]


def half_month(index: int) -> int:
    """The end-of-period month for a semi-annual index: (index + 1) * 6."""
    return (index + 1) * 6


def year_index(semi_index: int) -> int:
    """Annual index (0-based) for a given semi-annual index."""
    return semi_index // 2


def periods_for_year(year: int) -> list[Period]:
    """Return the two semi-annual periods belonging to an annual year (1-based)."""
    return [p for p in load_periods() if p.year == year]


def annual_month_range(yi: int) -> tuple[int, int]:
    """Return (y_start, y_end) month range for annual index yi (0-based)."""
    return yi * 12, (yi + 1) * 12


def construction_period_labels() -> list[int]:
    """Return construction period indices [0, 1, 2, 3]."""
    return list(range(construction_end_index() + 1))


def repayment_start_month() -> int:
    """Month at which repayment begins (e.g. 24)."""
    periods = load_periods()
    idx = repayment_start_index()
    return periods[idx].start_month


def n_construction() -> int:
    """Number of construction periods."""
    return construction_end_index() + 1


def end_month(hi: int) -> int:
    """End month for semi-annual index hi."""
    periods = load_periods()
    return periods[hi].end_month


def semi_index_to_facility_period(hi: int) -> int:
    """Map semi-annual waterfall index to facility period index (canonical 0-19)."""
    return hi


def period_start_month(index: int) -> int:
    """Start month for a canonical period index (0-19)."""
    return load_periods()[index].start_month


def period_lookup(index: int) -> dict:
    """Return display fields for a canonical period index.

    >>> period_lookup(4)
    {'index': 4, 'label': 'R1', 'month': 24, 'year': 2.0, 'phase': 'repayment'}
    """
    p = load_periods()[index]
    return {
        "index": p.index,
        "label": p.label,
        "month": p.start_month,
        "year": p.start_month / 12,
        "phase": p.phase,
    }
