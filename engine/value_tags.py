"""Value type tagging — classify every computed value by accounting category.

Each column in a DataFrame belongs to one ValueType (what it IS) and has a
unit (what it's measured in). This enables:
- UI auto-coloring: revenue=green, expense=red, balance=blue, ratio=grey
- DAG type-checking: prevent mixing volumes with EUR amounts
- Formula audit trails: show what category each input/output belongs to

Primary lookup: column registry (config/columns.json via engine.registry).
Fallback: prefix matching for columns not yet in the registry.

Usage:
    from engine.value_tags import tag_dataframe, ValueType

    df = pd.DataFrame(entity.annual)
    tagged = tag_dataframe(df)
    # tagged.attrs["col_tags"] = {"rev_total": ValueType.REVENUE, ...}
    # tagged.attrs["col_units"] = {"rev_total": "EUR", ...}

    # UI can then:
    for col in tagged.columns:
        vtype = tagged.attrs["col_tags"].get(col, ValueType.OTHER)
        color = VTYPE_COLORS[vtype]
"""

from __future__ import annotations

from enum import Enum


class ValueType(str, Enum):
    """Accounting category for a computed value."""
    REVENUE     = "revenue"      # Income streams (P&L top line)
    EXPENSE     = "expense"      # Costs, opex, COGS (P&L deductions)
    EBITDA      = "ebitda"       # Earnings aggregates
    DEPRECIATION = "depreciation"
    INTEREST    = "interest"     # Finance costs
    TAX         = "tax"          # Tax charges
    PROFIT      = "profit"       # PAT, PBT, EBIT
    ASSET       = "asset"        # BS: fixed assets, cash, reserves
    LIABILITY   = "liability"    # BS: debt, swap ZAR leg
    EQUITY      = "equity"       # BS: shareholder equity, retained earnings
    CF_OPS      = "cf_ops"       # Operating cash flow
    CF_INVEST   = "cf_invest"    # Investing cash flow (capex, grants)
    CF_FINANCE  = "cf_finance"   # Financing cash flow (debt service, equity)
    CF_NET      = "cf_net"       # Net cash flow
    VOLUME      = "volume"       # Physical quantities (MLD, m3, kWh, units)
    RATE        = "rate"         # Price per unit (ZAR/kL, EUR/kWh)
    RATIO       = "ratio"        # Dimensionless ratios (DSCR, %, share)
    PERIOD      = "period"       # Time indices (year, month, period)
    RESERVE     = "reserve"      # Reserve balances (DSRA, ops reserve, FD)
    ACCELERATION = "acceleration" # Debt prepayments
    DIVIDEND    = "dividend"     # Distributions
    OTHER       = "other"        # Unclassified


# ── Family → ValueType mapping ───────────────────────────────────────
# Maps registry family strings to ValueType enum values.

_FAMILY_TO_VTYPE: dict[str, ValueType] = {
    "revenue":      ValueType.REVENUE,
    "expense":      ValueType.EXPENSE,
    "ebitda":       ValueType.EBITDA,
    "depreciation": ValueType.DEPRECIATION,
    "interest":     ValueType.INTEREST,
    "tax":          ValueType.TAX,
    "profit":       ValueType.PROFIT,
    "asset":        ValueType.ASSET,
    "liability":    ValueType.LIABILITY,
    "equity":       ValueType.EQUITY,
    "cf_ops":       ValueType.CF_OPS,
    "cf_invest":    ValueType.CF_INVEST,
    "cf_finance":   ValueType.CF_FINANCE,
    "cf_net":       ValueType.CF_NET,
    "volume":       ValueType.VOLUME,
    "ratio":        ValueType.RATIO,
    "period":       ValueType.PERIOD,
    "reserve":      ValueType.RESERVE,
    "acceleration": ValueType.ACCELERATION,
    "dividend":     ValueType.DIVIDEND,
}


# ── UI Color Map ──────────────────────────────────────────────────────

VTYPE_COLORS: dict[ValueType, str] = {
    ValueType.REVENUE:      "#2e7d32",   # green
    ValueType.EXPENSE:      "#c62828",   # red
    ValueType.EBITDA:       "#1565c0",   # blue
    ValueType.DEPRECIATION: "#6a1b9a",   # purple
    ValueType.INTEREST:     "#e65100",   # orange
    ValueType.TAX:          "#ad1457",   # pink
    ValueType.PROFIT:       "#00695c",   # teal
    ValueType.ASSET:        "#1565c0",   # blue
    ValueType.LIABILITY:    "#c62828",   # red
    ValueType.EQUITY:       "#2e7d32",   # green
    ValueType.CF_OPS:       "#2e7d32",   # green
    ValueType.CF_INVEST:    "#e65100",   # orange
    ValueType.CF_FINANCE:   "#1565c0",   # blue
    ValueType.CF_NET:       "#00695c",   # teal
    ValueType.VOLUME:       "#37474f",   # blue-grey
    ValueType.RATE:         "#4e342e",   # brown
    ValueType.RATIO:        "#546e7a",   # grey
    ValueType.PERIOD:       "#757575",   # grey
    ValueType.RESERVE:      "#0277bd",   # light blue
    ValueType.ACCELERATION: "#ef6c00",   # dark orange
    ValueType.DIVIDEND:     "#558b2f",   # light green
    ValueType.OTHER:        "#9e9e9e",   # grey
}


# ── Prefix Fallback ──────────────────────────────────────────────────
# Used ONLY when a column is not in the registry. Kept for backward
# compatibility with columns generated at runtime that haven't been
# registered yet.

_PREFIX_TAGS: list[tuple[str, ValueType, str]] = [
    ("rev_",              ValueType.REVENUE,      "EUR"),
    ("om_cost",           ValueType.EXPENSE,      "EUR"),
    ("power_cost",        ValueType.EXPENSE,      "EUR"),
    ("rent_cost",         ValueType.EXPENSE,      "EUR"),
    ("grid_cost",         ValueType.EXPENSE,      "EUR"),
    ("labor_cost",        ValueType.EXPENSE,      "EUR"),
    ("opex",              ValueType.EXPENSE,      "EUR"),
    ("om_zar",            ValueType.EXPENSE,      "ZAR"),
    ("power_zar",         ValueType.EXPENSE,      "ZAR"),
    ("rent_zar",          ValueType.EXPENSE,      "ZAR"),
    ("ebitda",            ValueType.EBITDA,       "EUR"),
    ("depr",              ValueType.DEPRECIATION, "EUR"),
    ("ie_",               ValueType.INTEREST,     "EUR"),
    ("ie",                ValueType.INTEREST,     "EUR"),
    ("ii_",               ValueType.INTEREST,     "EUR"),
    ("interest",          ValueType.INTEREST,     "EUR"),
    ("fd_income",         ValueType.INTEREST,     "EUR"),
    ("tax",               ValueType.TAX,          "EUR"),
    ("ebit",              ValueType.PROFIT,       "EUR"),
    ("pbt",               ValueType.PROFIT,       "EUR"),
    ("pat",               ValueType.PROFIT,       "EUR"),
    ("bs_",               ValueType.ASSET,        "EUR"),
    ("cf_ops",            ValueType.CF_OPS,       "EUR"),
    ("cf_operating",      ValueType.CF_OPS,       "EUR"),
    ("cf_capex",          ValueType.CF_INVEST,    "EUR"),
    ("cf_grant",          ValueType.CF_INVEST,    "EUR"),
    ("cf_",               ValueType.CF_FINANCE,   "EUR"),
    ("vol_",              ValueType.VOLUME,       ""),
    ("generation_kwh",    ValueType.VOLUME,       "kWh"),
    ("installed_mwp",     ValueType.VOLUME,       "MWp"),
    ("bess_",             ValueType.VOLUME,       "kWh"),
    ("dscr",              ValueType.RATIO,        "x"),
    ("llcr",              ValueType.RATIO,        "x"),
    ("plcr",              ValueType.RATIO,        "x"),
    ("ops_reserve",       ValueType.RESERVE,      "EUR"),
    ("opco_dsra",         ValueType.RESERVE,      "EUR"),
    ("entity_fd",         ValueType.RESERVE,      "EUR"),
    ("mz_div",            ValueType.RESERVE,      "EUR"),
    ("wf_",               ValueType.RESERVE,      "EUR"),
    ("sr_accel",          ValueType.ACCELERATION, "EUR"),
    ("mz_accel",          ValueType.ACCELERATION, "EUR"),
    ("swap_leg_accel",    ValueType.ACCELERATION, "EUR"),
    ("od_accel",          ValueType.ACCELERATION, "EUR"),
    ("dividend",          ValueType.DIVIDEND,     "EUR"),
    ("cum_dividend",      ValueType.DIVIDEND,     "EUR"),
    ("od_",               ValueType.LIABILITY,    "EUR"),
    ("swap_",             ValueType.LIABILITY,     "EUR"),
    ("sr_",               ValueType.LIABILITY,    "EUR"),
    ("mz_",               ValueType.LIABILITY,    "EUR"),
    ("surplus",           ValueType.CF_NET,       "EUR"),
    ("deficit",           ValueType.CF_NET,       "EUR"),
    ("cash_available",    ValueType.CF_NET,       "EUR"),
    ("free_surplus",      ValueType.CF_NET,       "EUR"),
    ("rev",               ValueType.REVENUE,      "EUR"),
    ("year",              ValueType.PERIOD,       ""),
    ("month",             ValueType.PERIOD,       ""),
    ("period",            ValueType.PERIOD,       ""),
    ("index",             ValueType.PERIOD,       ""),
]

_ZAR_SUFFIXES = ("_zar",)


def _tag_column_fallback(col_name: str) -> tuple[ValueType, str]:
    """Fallback: classify by prefix matching when column not in registry."""
    col_lower = col_name.lower()
    for prefix, vtype, unit in _PREFIX_TAGS:
        if col_lower.startswith(prefix) or col_lower == prefix:
            actual_unit = unit
            if any(col_lower.endswith(sfx) for sfx in _ZAR_SUFFIXES):
                actual_unit = "ZAR"
            return vtype, actual_unit
    return ValueType.OTHER, ""


def _tag_column(col_name: str) -> tuple[ValueType, str]:
    """Classify a column: registry first, prefix fallback second."""
    # Lazy import to avoid circular dependency at module load time
    from engine.registry import ColumnRegistry

    try:
        reg = ColumnRegistry.load()
    except (FileNotFoundError, OSError):
        # Registry not available — use prefix fallback only
        return _tag_column_fallback(col_name)

    col = reg.get(col_name)
    if col is not None:
        vtype = _FAMILY_TO_VTYPE.get(col.family, ValueType.OTHER)
        return vtype, col.unit

    # Not in registry — fall back to prefix matching
    return _tag_column_fallback(col_name)


def tag_columns(columns: list[str]) -> dict[str, tuple[ValueType, str]]:
    """Tag a list of column names.

    Returns: {col_name: (ValueType, unit)}
    """
    return {col: _tag_column(col) for col in columns}


def tag_dataframe(df: "pd.DataFrame") -> "pd.DataFrame":
    """Attach value type tags and units to a DataFrame's attrs.

    Non-destructive: returns the same DataFrame with attrs populated.
    Sets:
        df.attrs["col_tags"]  = {col: ValueType, ...}
        df.attrs["col_units"] = {col: unit_str, ...}
    """
    tags = tag_columns(list(df.columns))
    df.attrs["col_tags"]  = {col: vtype for col, (vtype, _) in tags.items()}
    df.attrs["col_units"] = {col: unit for col, (_, unit) in tags.items()}
    return df


def tag_all_dataframes(dfs: dict[str, "pd.DataFrame"]) -> dict[str, "pd.DataFrame"]:
    """Tag all DataFrames in a dict (e.g. from EntityResult.dataframes).

    Returns the same dict with all DFs tagged.
    """
    return {name: tag_dataframe(df) for name, df in dfs.items()}
