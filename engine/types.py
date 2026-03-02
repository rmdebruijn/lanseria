"""Data shapes for the calculation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


# ── Facility ────────────────────────────────────────────────────

class FacilityRow(TypedDict):
    period: int
    month: int
    year: float
    opening: float
    draw_down: float
    idc: float          # interest during construction (capitalised)
    interest: float     # cash interest (repayment phase)
    grant_accel: float  # grant-funded acceleration (negative = reduction)
    scheduled_p: float  # scheduled principal repayment (negative)
    acceleration: float # waterfall-driven acceleration (negative)
    movement: float
    closing: float


# ── P&L ─────────────────────────────────────────────────────────

class PnlRow(TypedDict):
    index: int
    month: int
    revenue: float
    opex: float
    ebitda: float
    depreciation: float
    ebit: float
    interest_expense: float
    fd_income: float
    pbt: float
    tax: float
    pat: float
    tax_loss_pool: float


# ── Cash Flow ───────────────────────────────────────────────────

class CashFlowRow(TypedDict):
    index: int
    month: int
    cash_from_ops: float        # EBITDA - Tax + Grants + FD income
    debt_service: float         # sr_interest + sr_sched_p + mz_interest + mz_sched_p + swap_zar
    cash_after_ds: float        # cash_from_ops - debt_service
    grants: float
    equity: float
    drawdowns: float
    capex: float
    grant_acceleration: float
    acceleration_sr: float
    acceleration_mz: float
    acceleration_zar: float
    reserve_fills: float
    reserve_releases: float
    net_cash: float


# ── Waterfall ───────────────────────────────────────────────────

class WaterfallRow(TypedDict):
    index: int
    month: int
    ebitda: float
    tax: float
    ie_half_sr: float
    ie_half_mz: float
    sr_pi: float
    mz_pi: float
    sr_prin_sched: float
    mz_prin_sched: float
    sr_grant_accel: float
    swap_leg_scheduled: float
    ds_cash: float
    # Typed cash inflows
    dtic_grant: float
    iic_grant: float
    specials: float
    pre_rev_hedge: float
    mezz_draw: float
    eur_leg_repayment: float
    cash_available: float
    surplus: float
    deficit: float
    # Balances
    sr_ic_bal: float
    mz_ic_bal: float
    swap_leg_bal: float
    # Reserves
    ops_reserve_interest: float
    ops_reserve_fill: float
    ops_reserve_bal: float
    ops_reserve_target: float
    opco_dsra_fill: float
    opco_dsra_release: float
    opco_dsra_bal: float
    opco_dsra_target: float
    od_lent: float
    od_received: float
    od_repaid: float
    od_interest: float
    od_bal: float
    entity_fd_interest: float
    entity_fd_fill: float
    entity_fd_bal: float
    free_surplus: float
    # Acceleration
    sr_accel_entity: float
    mz_accel_entity: float
    swap_leg_accel: float
    od_accel: float
    # Mezz Dividend Reserve
    mz_div_opening_basis: float
    mz_div_accrual: float
    mz_div_liability_bal: float
    mz_div_fd_interest: float
    mz_div_fd_fill: float
    mz_div_fd_bal: float
    mz_div_payout: bool
    mz_div_payout_amount: float


# ── Balance Sheet ───────────────────────────────────────────────

class BalanceSheetRow(TypedDict):
    year: int
    fixed_assets: float
    reserves_total: float
    ops_reserve: float
    opco_dsra: float
    mz_div_fd: float
    entity_fd: float
    swap_eur: float
    total_assets: float
    sr_debt: float
    mz_debt: float
    swap_zar: float
    total_debt: float
    equity_sh: float
    retained_earnings: float
    total_equity: float


# ── Swap ────────────────────────────────────────────────────────

@dataclass
class SwapSchedule:
    eur_amount: float
    zar_amount: float
    eur_rate: float
    zar_rate: float
    eur_amount_idc: float  # EUR amount after IDC capitalisation
    tenor: int = 0
    start_month: int = 0
    p_constant_zar: float = 0.0
    zar_amount_idc: float = 0.0
    schedule: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to plain dict for display code compatibility."""
        return {
            "eur_amount": self.eur_amount,
            "zar_amount": self.zar_amount,
            "eur_rate": self.eur_rate,
            "zar_rate": self.zar_rate,
            "eur_amount_idc": self.eur_amount_idc,
            "tenor": self.tenor,
            "start_month": self.start_month,
            "p_constant_zar": self.p_constant_zar,
            "zar_amount_idc": self.zar_amount_idc,
            "schedule": self.schedule,
        }


# ── Entity Result ───────────────────────────────────────────────

@dataclass
class EntityResult:
    """Complete output for one entity."""
    entity_key: str
    annual: list[dict]              # 10 annual P&L/CF/BS dicts
    sr_schedule: list[dict]         # Senior IC schedule rows
    mz_schedule: list[dict]         # Mezz IC schedule rows
    waterfall_semi: list[dict]      # 20 semi-annual waterfall rows
    waterfall_annual: list[dict]    # 10 annual waterfall rows
    semi_annual_pl: list[dict]      # 20 semi-annual P&L rows
    semi_annual_tax: list[float]    # 20 tax values
    ops_annual: list[dict]          # 10 annual operating model rows
    ops_semi_annual: list[dict] | None  # 20 semi-annual ops (NWL only)
    registry: dict                  # Asset registry
    depreciable_base: float
    entity_equity: float
    swap_schedule: SwapSchedule | None
    swap_active: bool
    cash_inflows: list[dict] | None
    pre_revenue_hedge_total: float

    # -- Derived metrics (computed properties) --

    @property
    def total_revenue(self) -> float:
        return sum(a.get("rev_total", 0) for a in self.annual)

    @property
    def total_ebitda(self) -> float:
        return sum(a.get("ebitda", 0) for a in self.annual)

    @property
    def total_pat(self) -> float:
        return sum(a.get("pat", 0) for a in self.annual)

    @property
    def ebitda_margin(self) -> float:
        rev = self.total_revenue
        return (self.total_ebitda / rev * 100.0) if rev else 0.0

    @property
    def net_margin(self) -> float:
        rev = self.total_revenue
        return (self.total_pat / rev * 100.0) if rev else 0.0

    @property
    def dscr_values(self) -> list[float | None]:
        return [
            a["cf_ops"] / a["cf_ds"] if a.get("cf_ds", 0) > 0 else None
            for a in self.annual
        ]

    @property
    def dscr_min(self) -> float:
        vals = [v for v in self.dscr_values if v is not None]
        return min(vals) if vals else 0.0

    @property
    def dscr_avg(self) -> float:
        vals = [v for v in self.dscr_values if v is not None]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def dataframes(self) -> dict:
        """All entity data as pandas DataFrames.

        Returns dict with keys:
            annual, facility_sr, facility_mz, waterfall_semi, waterfall_annual,
            pnl_semi, ops_annual, + ops helper tables (ops_quantity, ops_revenue,
            ops_opex, and entity-specific extras).
        Views read these directly — no transformation needed.

        Each DataFrame has attrs populated:
            col_tags:   {col: ValueType}  — accounting category
            col_units:  {col: str}        — physical unit
            col_labels: {col: str}        — human-readable label (from registry)
        """
        import pandas as pd
        from engine.ops_tables import extract_ops_tables
        from engine.value_tags import tag_all_dataframes

        dfs = {
            "annual": pd.DataFrame(self.annual),
            "facility_sr": pd.DataFrame(self.sr_schedule),
            "facility_mz": pd.DataFrame(self.mz_schedule),
            "waterfall_semi": pd.DataFrame(self.waterfall_semi),
            "waterfall_annual": pd.DataFrame(self.waterfall_annual),
            "pnl_semi": pd.DataFrame(self.semi_annual_pl),
            "ops_annual": pd.DataFrame(self.ops_annual),
        }
        if self.ops_semi_annual:
            dfs["ops_semi"] = pd.DataFrame(self.ops_semi_annual)

        # Ops helper tables (quantity, revenue, opex — per entity)
        ops_tables = extract_ops_tables(
            self.entity_key, self.ops_annual, self.ops_semi_annual
        )
        dfs.update(ops_tables)

        # Tag all DataFrames with value types and units
        dfs = tag_all_dataframes(dfs)

        # Attach registry labels to all DataFrames
        try:
            from engine.registry import ColumnRegistry
            reg = ColumnRegistry.load()
            for df in dfs.values():
                if "col_labels" not in df.attrs:
                    labels = {}
                    for col in df.columns:
                        cdef = reg.get(col)
                        if cdef is not None:
                            labels[col] = cdef.label
                        else:
                            labels[col] = col
                    df.attrs["col_labels"] = labels
        except (FileNotFoundError, OSError, ImportError):
            pass  # Registry not available — tags still work via prefix fallback

        return dfs


# ── Model Result ────────────────────────────────────────────────

@dataclass
class ModelResult:
    """Complete output for the full model."""
    entities: dict[str, EntityResult]  # keyed by entity_key
    holding: dict | None = None        # SCLCA holding aggregation
    ic_semi: list[dict] | None = None  # 20 semi-annual IC aggregate

    @property
    def entity_dataframes(self) -> dict[str, dict]:
        """All entity DataFrames, keyed by entity_key.

        Usage: result.entity_dataframes["nwl"]["annual"]
        """
        return {k: v.dataframes for k, v in self.entities.items()}
