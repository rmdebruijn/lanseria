"""Ops helper data tables — separate DataFrames for quantity, revenue, and opex.

Each entity's operating model computes intermediates (volumes, rates, revenues
per stream, opex per category) that are embedded in ops_annual / ops_semi_annual
dicts. This module reshapes them into named DataFrames for UI display.

Column metadata (label, unit, fmt) comes from the column registry
(config/columns.json) when available, with hardcoded ColDef fallbacks
for columns not yet in the registry.

Usage:
    tables = extract_ops_tables("nwl", entity_result.ops_annual, entity_result.ops_semi_annual)
    # tables["quantity"]  → pd.DataFrame of volume/capacity metrics
    # tables["revenue"]   → pd.DataFrame of revenue streams
    # tables["opex"]      → pd.DataFrame of cost categories

All values are in EUR unless column name ends with _zar or _mld or _m3 etc.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Column Definitions ────────────────────────────────────────────────

@dataclass(frozen=True)
class ColDef:
    """Column definition for an ops table."""
    key: str         # dict key in ops_annual/ops_semi_annual
    label: str       # human-readable label for UI headers
    unit: str        # display unit (EUR, ZAR, MLD, m3, kWh, %, units, students)
    fmt: str = ""    # format hint: "money", "volume", "pct", "int", "rate"


# ── NWL Column Definitions ───────────────────────────────────────────

NWL_QUANTITY_COLS = [
    ColDef("vol_capacity_mld",        "Sewage Capacity",        "MLD",   "volume"),
    ColDef("vol_treated_mld",         "Sewage Treated",         "MLD",   "volume"),
    ColDef("vol_annual_m3",           "Annual Volume Treated",  "m3",    "volume"),
    ColDef("vol_reuse_annual_m3",     "Annual Reuse Volume",    "m3",    "volume"),
    ColDef("vol_brownfield_annual_m3","Annual Brownfield Volume","m3",   "volume"),
]

NWL_REVENUE_COLS = [
    ColDef("rev_greenfield_sewage",   "Greenfield Sewage",      "EUR",   "money"),
    ColDef("rev_brownfield_sewage",   "Brownfield Sewage",      "EUR",   "money"),
    ColDef("rev_sewage",              "Total Sewage",           "EUR",   "money"),
    ColDef("rev_greenfield_reuse",    "Greenfield Reuse",       "EUR",   "money"),
    ColDef("rev_construction",        "Construction Water",     "EUR",   "money"),
    ColDef("rev_agri",                "Agricultural Reuse",     "EUR",   "money"),
    ColDef("rev_reuse",               "Total Reuse",            "EUR",   "money"),
    ColDef("rev_operating",           "Operating Revenue",      "EUR",   "money"),
    ColDef("rev_bulk_services",       "Bulk Services",          "EUR",   "money"),
    ColDef("rev_total",               "Total Revenue",          "EUR",   "money"),
]

NWL_OPEX_COLS = [
    ColDef("om_cost",                 "O&M Cost",               "EUR",   "money"),
    ColDef("power_cost",              "Power Cost",             "EUR",   "money"),
    ColDef("rent_cost",               "CoE Rent",               "EUR",   "money"),
    ColDef("om_zar",                  "O&M Cost (ZAR)",         "ZAR",   "money"),
    ColDef("power_zar",               "Power Cost (ZAR)",       "ZAR",   "money"),
    ColDef("rent_zar",                "CoE Rent (ZAR)",         "ZAR",   "money"),
]


# ── LanRED Column Definitions ────────────────────────────────────────

LANRED_QUANTITY_COLS = [
    ColDef("installed_mwp",           "Installed Capacity",     "MWp",   "volume"),
    ColDef("bess_capacity_kwh",       "BESS Capacity",          "kWh",   "volume"),
    ColDef("bess_effective_kwh",      "BESS Effective",         "kWh",   "volume"),
    ColDef("generation_kwh",          "Annual Generation",      "kWh",   "volume"),
    ColDef("capacity_factor_pct",     "Capacity Factor",        "%",     "pct"),
    ColDef("ic_share_pct",            "IC NWL Share",           "%",     "pct"),
    ColDef("sc_share_pct",            "Smart City Share",       "%",     "pct"),
    ColDef("mkt_share_pct",           "Open Market Share",      "%",     "pct"),
]

LANRED_REVENUE_COLS = [
    ColDef("rev_ic_nwl",              "IC NWL Power",           "EUR",   "money"),
    ColDef("rev_smart_city",          "Smart City",             "EUR",   "money"),
    ColDef("rev_open_market",         "Open Market",            "EUR",   "money"),
    ColDef("rev_bess_arbitrage",      "BESS Arbitrage",         "EUR",   "money"),
    ColDef("rev_power_sales",         "Total Power Sales",      "EUR",   "money"),
    ColDef("rev_operating",           "Operating Revenue",      "EUR",   "money"),
    ColDef("rev_total",               "Total Revenue",          "EUR",   "money"),
]

LANRED_OPEX_COLS = [
    ColDef("om_cost",                 "O&M Cost",               "EUR",   "money"),
    ColDef("grid_cost",               "Grid Connection",        "EUR",   "money"),
    ColDef("power_cost",              "Power Purchased",        "EUR",   "money"),
]

# Brownfield+ has extra detail columns
LANRED_BF_DETAIL_COLS = [
    ColDef("rev_northlands_gross_zar","Northlands Revenue (ZAR)","ZAR",  "money"),
    ColDef("northlands_cogs_zar",     "Northlands COGS (ZAR)",  "ZAR",   "money"),
    ColDef("northlands_gross_profit_zar","Northlands GP (ZAR)", "ZAR",   "money"),
    ColDef("northlands_ins_zar",      "Insurance (ZAR)",        "ZAR",   "money"),
    ColDef("northlands_om_zar",       "O&M (ZAR)",              "ZAR",   "money"),
    ColDef("northlands_net_zar",      "Net Income (ZAR)",       "ZAR",   "money"),
]


# ── TimberWorx Column Definitions ────────────────────────────────────

TWX_QUANTITY_COLS = [
    ColDef("occupancy_pct",           "CoE Occupancy",          "%",     "pct"),
    ColDef("students",                "Training Students",      "students","int"),
    ColDef("timber_units",            "Timber Houses Built",    "units", "int"),
]

TWX_REVENUE_COLS = [
    ColDef("rev_lease",               "CoE Lease",              "EUR",   "money"),
    ColDef("rev_training",            "Training Revenue",       "EUR",   "money"),
    ColDef("rev_timber_gross",        "Timber Gross Revenue",   "EUR",   "money"),
    ColDef("rev_timber_sales",        "Timber Net Revenue",     "EUR",   "money"),
    ColDef("rev_coe_sale",            "CoE Sale Proceeds",      "EUR",   "money"),
    ColDef("rev_operating",           "Operating Revenue",      "EUR",   "money"),
    ColDef("rev_total",               "Total Revenue",          "EUR",   "money"),
]

TWX_OPEX_COLS = [
    ColDef("labor_cost",              "Timber Labor",           "EUR",   "money"),
    ColDef("om_cost",                 "O&M Cost",               "EUR",   "money"),
]


# ── Registry ──────────────────────────────────────────────────────────

_TABLE_DEFS: dict[str, dict[str, list[ColDef]]] = {
    "nwl": {
        "quantity": NWL_QUANTITY_COLS,
        "revenue":  NWL_REVENUE_COLS,
        "opex":     NWL_OPEX_COLS,
    },
    "lanred": {
        "quantity": LANRED_QUANTITY_COLS,
        "revenue":  LANRED_REVENUE_COLS,
        "opex":     LANRED_OPEX_COLS,
    },
    "timberworx": {
        "quantity": TWX_QUANTITY_COLS,
        "revenue":  TWX_REVENUE_COLS,
        "opex":     TWX_OPEX_COLS,
    },
}


# ── Extraction ────────────────────────────────────────────────────────


def _build_table(
    rows: list[dict],
    cols: list[ColDef],
    index_key: str = "year",
) -> "pd.DataFrame":
    """Build a DataFrame from ops rows using column definitions.

    Columns that don't exist in the source rows are filled with 0.0.
    """
    import pandas as pd

    data = []
    for row in rows:
        d = {index_key: row.get(index_key, row.get("month", 0))}
        for col in cols:
            d[col.key] = row.get(col.key, 0.0)
        data.append(d)

    df = pd.DataFrame(data)
    if index_key in df.columns:
        df = df.set_index(index_key)

    # Attach metadata: column labels and units as DataFrame attrs
    # Registry-enriched: prefer registry metadata, fall back to ColDef
    col_labels = {}
    col_units = {}
    col_fmts = {}
    try:
        from engine.registry import ColumnRegistry
        reg = ColumnRegistry.load()
    except (FileNotFoundError, OSError, ImportError):
        reg = None

    for c in cols:
        if reg is not None:
            rcol = reg.get(c.key)
            if rcol is not None:
                col_labels[c.key] = rcol.label
                col_units[c.key] = rcol.unit
                col_fmts[c.key] = rcol.fmt
                continue
        col_labels[c.key] = c.label
        col_units[c.key] = c.unit
        col_fmts[c.key] = c.fmt

    df.attrs["col_labels"] = col_labels
    df.attrs["col_units"]  = col_units
    df.attrs["col_fmts"]   = col_fmts

    return df


def extract_ops_tables(
    entity_key: str,
    ops_annual: list[dict],
    ops_semi_annual: list[dict] | None = None,
) -> dict[str, "pd.DataFrame"]:
    """Extract ops helper tables for a given entity.

    Returns dict with keys: "quantity", "revenue", "opex".
    For NWL, also adds "quantity_semi", "revenue_semi", "opex_semi" if
    ops_semi_annual is provided.

    For LanRED Brownfield+, adds "brownfield_detail" with site-level ZAR data.
    """
    defs = _TABLE_DEFS.get(entity_key, {})
    if not defs:
        return {}

    result = {}

    # Annual tables
    for table_name, cols in defs.items():
        result[f"ops_{table_name}"] = _build_table(ops_annual, cols, index_key="year")

    # Semi-annual tables (NWL only — others don't have semi-annual ops)
    if ops_semi_annual and entity_key == "nwl":
        # Semi-annual has "month" as index, not "year"
        # Only revenue and opex columns are in semi-annual (not all quantity cols)
        semi_rev_cols = [c for c in defs.get("revenue", [])
                         if c.key in (ops_semi_annual[0] if ops_semi_annual else {})]
        semi_opex_cols = [c for c in defs.get("opex", [])
                          if c.key in (ops_semi_annual[0] if ops_semi_annual else {})]
        if semi_rev_cols:
            result["ops_revenue_semi"] = _build_table(
                ops_semi_annual, semi_rev_cols, index_key="month"
            )
        if semi_opex_cols:
            result["ops_opex_semi"] = _build_table(
                ops_semi_annual, semi_opex_cols, index_key="month"
            )

    # LanRED Brownfield+ detail
    if entity_key == "lanred" and ops_annual:
        # Detect brownfield+ by checking for northlands keys
        if ops_annual[0].get("rev_northlands_gross_zar", 0) > 0:
            result["ops_brownfield_detail"] = _build_table(
                ops_annual, LANRED_BF_DETAIL_COLS, index_key="year"
            )

    return result


def get_table_column_labels(entity_key: str) -> dict[str, dict[str, str]]:
    """Get column labels for all ops tables of an entity.

    Returns: {"quantity": {"vol_capacity_mld": "Sewage Capacity", ...}, ...}
    Used by UI to display human-readable headers.
    """
    defs = _TABLE_DEFS.get(entity_key, {})
    return {
        table_name: {c.key: c.label for c in cols}
        for table_name, cols in defs.items()
    }


def get_table_column_units(entity_key: str) -> dict[str, dict[str, str]]:
    """Get column units for all ops tables of an entity.

    Returns: {"quantity": {"vol_capacity_mld": "MLD", ...}, ...}
    """
    defs = _TABLE_DEFS.get(entity_key, {})
    return {
        table_name: {c.key: c.unit for c in cols}
        for table_name, cols in defs.items()
    }
