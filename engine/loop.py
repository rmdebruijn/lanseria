"""One Big Loop — period-by-period entity engine.

Single-pass sequential loop over 20 semi-annual periods.
No convergence iterations needed: within a single period, Opening is fixed
(= previous Closing), so Interest and P_constant are deterministic.
Acceleration at period N reduces Closing(N), which becomes Opening(N+1).

Execution order per period:
    1. Opening balances (carried from previous period)
    2. Ops model (EBITDA — already computed upstream, just read)
    3. Facility compute (Interest, P_constant from Opening)
    4. Asset depreciation (S12C / straight-line)
    5. P&L (EBITDA - Depr - IE → PBT → Tax → PAT)
    6. Waterfall (cash allocation: reserves, acceleration, entity FD)
    7. Facility finalize (apply acceleration → new Closing)
    8. Post-period (update DSRA target, set final balances)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.facility import FacilityState, FacilityPeriod
from engine.pnl import compute_period_pnl, PnlPeriod
from engine.reserves import (
    OpsReserve, OpcoDSRA, MezzDivFD, EntityFD,
    ReserveAccrual, total_fd_income,
)
from engine.waterfall import WaterfallState, waterfall_step
from engine.swap import extract_swap_vectors, build_swap_closing_bal
from engine.periods import (
    total_periods, total_years, construction_period_labels,
    period_start_month, year_index, annual_month_range,
    construction_end_index, repayment_start_month,
)


@dataclass
class LoopResult:
    """Complete output of run_entity_loop()."""
    sr_schedule: list[dict]       # 20-period senior facility schedule
    mz_schedule: list[dict]       # 20-period mezz facility schedule
    semi_annual_pl: list[dict]    # 20-period P&L rows (as dicts)
    semi_annual_tax: list[float]  # 20 tax values
    waterfall_semi: list[dict]    # 20-period waterfall rows

    @property
    def dataframes(self) -> dict:
        """Convert loop output to pandas DataFrames.

        Returns dict with keys: facility_sr, facility_mz, pnl, waterfall.
        Lazy import — pandas only loaded when this property is accessed.
        """
        import pandas as pd
        return {
            "facility_sr": pd.DataFrame(self.sr_schedule),
            "facility_mz": pd.DataFrame(self.mz_schedule),
            "pnl": pd.DataFrame(self.semi_annual_pl),
            "waterfall": pd.DataFrame(self.waterfall_semi),
        }


def run_entity_loop(
    entity_key: str,
    cfg,  # ModelConfig
    *,
    ops_annual: list[dict],
    ops_semi_annual: list[dict] | None,
    # Senior facility params
    sr_principal: float,
    total_sr: float,
    sr_repayments: int,
    sr_rate: float,
    sr_drawdowns: list[float],
    # Mezz facility params
    mz_principal: float,
    total_mz: float,
    mz_repayments: int,
    mz_rate: float,
    mz_drawdowns: list[float],
    # Construction
    construction_periods: list[int] | None = None,
    # P&L params
    depreciable_base: float = 0.0,
    tax_rate: float = 0.27,
    straight_line_base: float = 0.0,
    straight_line_life: int = 20,
    # Waterfall params
    cash_inflows: list[dict] | None = None,
    sweep_pct: float = 1.0,
    lanred_deficit_vector: list[float] | None = None,
    # Swap
    swap_sched: dict | None = None,
    fx_rate: float = 1.0,
    # Grant acceleration (construction phase)
    sr_grant_accel: dict[str, float] | None = None,
    # DSRA
    dsra_amount: float = 0.0,
    dsra_drawdown: float = 0.0,
    # IC overdraft received (LanRED only — from NWL lending)
    od_received_vector: list[float] | None = None,
) -> LoopResult:
    """Run the One Big Loop for a single entity.

    20 semi-annual periods, single pass, zero convergence iterations.
    Returns LoopResult with facility schedules, P&L, and waterfall output.
    """
    if construction_periods is None:
        construction_periods = construction_period_labels()

    n_periods = total_periods()

    # ── Init facilities (construction as batch) ──
    sr_fac = FacilityState(
        principal=sr_principal,
        total_principal=total_sr,
        repayments=sr_repayments,
        rate=sr_rate,
        drawdown_schedule=sr_drawdowns,
        construction_periods=construction_periods,
        grant_acceleration=sr_grant_accel,
        dsra_amount=dsra_amount,
    )
    mz_fac = FacilityState(
        principal=mz_principal,
        total_principal=total_mz,
        repayments=mz_repayments,
        rate=mz_rate,
        drawdown_schedule=mz_drawdowns,
        construction_periods=construction_periods,
        dsra_drawdown=dsra_drawdown,
    )

    # ── Init swap vectors (if swap active) ──
    swap_vectors = None
    if swap_sched is not None:
        swap_vectors = extract_swap_vectors(swap_sched, fx_rate)

    # ── Init waterfall state ──
    wf_state = WaterfallState()
    if swap_vectors is not None:
        wf_state.swap_leg_bal = swap_vectors["initial_bal"]

    # ── Init reserve assets ──
    fd_rate = cfg.fd_rate_eur                              # 3.5%
    ops_coverage = cfg.ops_reserve_coverage                # 1.0
    mz_div_rate = cfg.mz_div_gap_rate                      # 5.25%

    ops_reserve = OpsReserve(fd_rate, ops_coverage)
    opco_dsra = OpcoDSRA(fd_rate)
    mz_div_fd = MezzDivFD(fd_rate, mz_div_rate) if entity_key in ("nwl", "lanred", "timberworx") else None
    entity_fd = EntityFD(fd_rate)

    # ── Running accumulators ──
    tax_loss_pool = 0.0
    pnl_rows: list[dict] = []
    pnl_tax: list[float] = []
    wf_rows: list[dict] = []

    for hi in range(n_periods):
        # ── 1. Facility: compute period (Interest, Principal) ──
        sr_p = sr_fac.compute_period(hi)
        mz_p = mz_fac.compute_period(hi)

        # ── 2. Swap scheduled payment for this period ──
        swap_leg_scheduled = 0.0
        if swap_vectors is not None:
            swap_leg_scheduled = swap_vectors["scheduled_payment"][hi]

        # ── 2b. Reserve accrual (interest + targets — before P&L) ──
        # Get current opex for ops reserve target
        if ops_semi_annual and hi < len(ops_semi_annual):
            _cur_opex = (ops_semi_annual[hi].get("om_cost", 0)
                         + ops_semi_annual[hi].get("power_cost", 0)
                         + ops_semi_annual[hi].get("rent_cost", 0))
        else:
            _cur_yi = year_index(hi)
            _cur_op = ops_annual[_cur_yi] if ops_annual and _cur_yi < len(ops_annual) else {}
            _cur_opex = (_cur_op.get("om_cost", 0) + _cur_op.get("power_cost", 0)
                         + _cur_op.get("rent_cost", 0)) / 2

        # Next-period opex for look-ahead
        _next_opex_reserve = 0.0
        if (hi + 1) < n_periods:
            if ops_semi_annual and (hi + 1) < len(ops_semi_annual):
                _ns = ops_semi_annual[hi + 1]
                _next_opex_reserve = (_ns.get("om_cost", 0) + _ns.get("power_cost", 0)
                                      + _ns.get("rent_cost", 0))
            else:
                _nyi = year_index(hi + 1)
                _nop = ops_annual[_nyi] if ops_annual and _nyi < len(ops_annual) else {}
                _next_opex_reserve = (_nop.get("om_cost", 0) + _nop.get("power_cost", 0)
                                      + _nop.get("rent_cost", 0)) / 2

        ops_accrual = ops_reserve.accrue(_cur_opex, _next_opex_reserve)
        dsra_accrual = opco_dsra.accrue()
        entity_fd_accrual = entity_fd.accrue()
        mz_div_accrual = mz_div_fd.accrue(mz_fac.balance) if mz_div_fd else None

        fd_income = total_fd_income(ops_accrual, entity_fd_accrual, mz_div_accrual, dsra_accrual)

        # ── 3. P&L: compute period ──
        pnl, tax_loss_pool = compute_period_pnl(
            hi, ops_annual, ops_semi_annual,
            sr_interest=sr_p.interest,
            mz_interest=mz_p.interest,
            depreciable_base=depreciable_base,
            tax_rate=tax_rate,
            tax_loss_pool=tax_loss_pool,
            fd_income=fd_income,
            straight_line_base=straight_line_base,
            straight_line_life=straight_line_life,
        )

        # ── 4. Waterfall: allocate cash ──
        ci = cash_inflows[hi] if cash_inflows and hi < len(cash_inflows) else {}
        lanred_deficit = (
            abs(lanred_deficit_vector[hi])
            if lanred_deficit_vector and hi < len(lanred_deficit_vector)
            else 0.0
        )
        _od_received = (
            abs(od_received_vector[hi])
            if od_received_vector and hi < len(od_received_vector)
            else 0.0
        )

        wf_row = waterfall_step(
            hi, entity_key, cfg,
            ebitda=pnl.ebitda,
            opex=pnl.opex,
            tax=pnl.tax,
            next_opex=_next_opex_reserve,  # still passed for batch compat
            sr_interest=sr_p.interest,
            sr_principal=sr_p.principal,
            sr_pi=sr_p.pi,
            mz_interest=mz_p.interest,
            mz_principal=mz_p.principal,
            mz_pi=mz_p.pi,
            sr_pre_accel_closing=sr_p.pre_accel_closing,
            mz_pre_accel_closing=mz_p.pre_accel_closing,
            swap_leg_scheduled=swap_leg_scheduled,
            cash_inflows=ci,
            sweep_pct=sweep_pct,
            lanred_deficit=lanred_deficit,
            od_received=_od_received,
            # Reserve accrual results (pre-computed by reserve assets)
            ops_accrual=ops_accrual,
            dsra_accrual=dsra_accrual,
            entity_fd_accrual=entity_fd_accrual,
            mz_div_accrual=mz_div_accrual,
            mz_div_fd=mz_div_fd,
            # Reserve objects (waterfall updates balances after allocation)
            ops_reserve_obj=ops_reserve,
            dsra_obj=opco_dsra,
            entity_fd_obj=entity_fd,
            state=wf_state,
        )

        # ── 5. Facility finalize: apply acceleration ──
        sr_accel = wf_row["sr_accel_entity"]
        mz_accel = wf_row["mz_accel_entity"]

        sr_fac.finalize_period(hi, acceleration=sr_accel)
        mz_fac.finalize_period(hi, acceleration=mz_accel)

        # ── 6. Post-period: set actual closing balances ──
        wf_row["sr_ic_bal"] = sr_fac.balance
        wf_row["mz_ic_bal"] = mz_fac.balance

        # Update DSRA target for next period (1x next Sr P+I)
        opco_dsra.set_target(sr_fac.next_pi_estimate(), sr_fac.balance)
        wf_state.opco_dsra_target = opco_dsra.target

        # ── 7. Accumulate output ──
        pnl_dict = {
            "month": pnl.month, "rev": pnl.rev, "opex": pnl.opex,
            "ebitda": pnl.ebitda, "depr": pnl.depr, "ebit": pnl.ebit,
            "ie": pnl.ie, "fd_income": pnl.fd_income,
            "pbt": pnl.pbt, "tax": pnl.tax, "pat": pnl.pat,
            "tax_loss_pool": pnl.tax_loss_pool,
        }
        pnl_rows.append(pnl_dict)
        pnl_tax.append(pnl.tax)
        wf_rows.append(wf_row)

    # ── Post-loop: fix swap closing balances from schedule ──
    if swap_vectors is not None:
        swap_accel_vector = [r.get("swap_leg_accel", 0.0) for r in wf_rows]
        swap_closing = build_swap_closing_bal(swap_vectors, swap_accel_vector)
        for hi in range(len(wf_rows)):
            wf_rows[hi]["swap_leg_bal"] = swap_closing[hi]

    return LoopResult(
        sr_schedule=sr_fac.schedule,
        mz_schedule=mz_fac.schedule,
        semi_annual_pl=pnl_rows,
        semi_annual_tax=pnl_tax,
        waterfall_semi=wf_rows,
    )


# ── Semi-annual → annual aggregation ─────────────────────────────


# Stock keys: closing balances — take H2 value (end of year).
# Everything else is a flow — sum H1 + H2.
#
# These frozensets are the runtime truth. The column registry
# (config/columns.json) also marks these as nature="stock".
# At startup, validate_stock_keys() cross-checks they agree.
_WATERFALL_STOCK_KEYS = frozenset({
    "entity_fd_bal", "mz_div_fd_bal", "mz_div_liability_bal",
    "mz_div_opening_basis", "mz_div_payout",
    "mz_ic_bal", "od_bal", "opco_dsra_bal",
    "opco_dsra_target", "ops_reserve_bal", "ops_reserve_target",
    "sr_ic_bal", "swap_leg_bal", "cum_dividends",
})

_PNL_STOCK_KEYS = frozenset({
    "tax_loss_pool",
})

_FACILITY_STOCK_KEYS = frozenset({
    "Opening", "Closing",
})


def validate_stock_keys() -> list[str]:
    """Cross-check stock keys against column registry.

    Returns list of mismatch descriptions (empty = all good).
    Call at model startup to catch drift between code and registry.
    """
    from engine.registry import ColumnRegistry

    try:
        reg = ColumnRegistry.load()
    except (FileNotFoundError, OSError):
        return ["Column registry not found — skipping stock key validation"]

    issues: list[str] = []
    issues.extend(reg.validate_against_stock_keys(_WATERFALL_STOCK_KEYS))
    issues.extend(reg.validate_against_stock_keys(_PNL_STOCK_KEYS))
    issues.extend(reg.validate_against_stock_keys(_FACILITY_STOCK_KEYS))
    return issues


def to_annual(
    semi_rows: list[dict],
    stock_keys: frozenset[str] | set[str] = frozenset(),
) -> list[dict]:
    """Aggregate 20 semi-annual rows into 10 annual rows.

    Flow keys: sum(H1, H2).
    Stock keys: take H2 value.
    Non-numeric values: take H2 value.
    """
    n = len(semi_rows)
    annual: list[dict] = []
    for yi in range(n // 2):
        h1 = semi_rows[yi * 2]
        h2 = semi_rows[yi * 2 + 1]
        row: dict = {}
        all_keys = set(h1.keys()) | set(h2.keys())
        for k in all_keys:
            v1 = h1.get(k, 0)
            v2 = h2.get(k, 0)
            if k in stock_keys:
                row[k] = v2
            elif isinstance(v2, (int, float)) and isinstance(v1, (int, float)):
                row[k] = v1 + v2
            else:
                row[k] = v2  # non-numeric: take H2
        row["year"] = yi + 1
        annual.append(row)
    return annual


def build_annual(
    loop_result: LoopResult,
    ops_annual: list[dict],
    *,
    entity_equity: float,
    depreciable_base: float,
    tax_rate: float = 0.27,
    swap_sched: dict | None = None,
    swap_active: bool = False,
    fx_rate: float = 1.0,
    dtic_grant_entity: float = 0.0,
    ta_grant_entity: float = 0.0,
    gepf_grant_entity: float = 0.0,
    straight_line_base: float = 0.0,
    straight_line_life: int = 20,
) -> list[dict]:
    """Build 10 annual rows from loop output. Single source of truth.

    Merges: ops_annual + P&L annual + waterfall annual + facility annual.
    Derives: CF fields, BS fields, DSRA fields.

    P&L fields (rev, depr, ebit, ie, pbt, tax, pat) are READ from pnl_a
    (the annual aggregation of semi-annual P&L), NOT recalculated.
    Semi-annual P&L is the source of truth — it correctly:
    - Starts depreciation from hi>=1 using year_index(hi)
    - Excludes IDC from interest expense (only repayment-phase interest)
    - Carries tax losses forward across all 20 semi-annual periods

    BS approach (proven in check_bs_gap.py):
    - Fixed assets = min(cum_capex, depr_base) - cum_depr (no IDC in asset value)
    - Cash/reserve balance = running CF accumulator (_cash_bal)
    - This guarantees: Assets - Debt = Equity + CumPAT + CumGrants (zero gap)
    """
    from engine.currency import ZAR

    wf_a = to_annual(loop_result.waterfall_semi, _WATERFALL_STOCK_KEYS)
    pnl_a = to_annual(loop_result.semi_annual_pl, _PNL_STOCK_KEYS)
    sr_a = to_annual(loop_result.sr_schedule, _FACILITY_STOCK_KEYS)
    mz_a = to_annual(loop_result.mz_schedule, _FACILITY_STOCK_KEYS)

    # IDC totals from facility schedules (informational — not used for P&L ie)
    _idc_by_year: list[float] = [0.0] * total_years()
    for sched in [loop_result.sr_schedule, loop_result.mz_schedule]:
        for r in sched:
            idc_val = r.get("IDC", 0.0)
            if idc_val > 0:
                _yr = year_index(r["Period"])
                if 0 <= _yr < len(_idc_by_year):
                    _idc_by_year[_yr] += idc_val

    # Cash interest by year: interest from facility schedule WHERE Month >= repayment start
    _rep_start = repayment_start_month()
    _cash_ie_sr_by_year: list[float] = [0.0] * total_years()
    _cash_ie_mz_by_year: list[float] = [0.0] * total_years()
    for r in loop_result.sr_schedule:
        if r["Month"] >= _rep_start:
            _yr = year_index(r["Period"])
            if 0 <= _yr < len(_cash_ie_sr_by_year):
                _cash_ie_sr_by_year[_yr] += r.get("Interest", 0.0)
    for r in loop_result.mz_schedule:
        if r["Month"] >= _rep_start:
            _yr = year_index(r["Period"])
            if 0 <= _yr < len(_cash_ie_mz_by_year):
                _cash_ie_mz_by_year[_yr] += r.get("Interest", 0.0)

    # Total acceleration from facility schedule (Sr + Mz, for CF identity)
    _accel_by_year: list[float] = [0.0] * total_years()
    for sched in [loop_result.sr_schedule, loop_result.mz_schedule]:
        for r in sched:
            accel = abs(r.get("Acceleration", 0.0))
            if accel > 0:
                _yr = year_index(r["Period"])
                if 0 <= _yr < len(_accel_by_year):
                    _accel_by_year[_yr] += accel

    annual: list[dict] = []
    cum_pat = 0.0
    cum_grants = 0.0
    cum_capex = 0.0
    cum_idc = 0.0    # Capitalised IDC (IAS 23) — adds to asset cost and loan balance
    accumulated_depr = 0.0
    _cash_bal = 0.0  # Running cash/reserve accumulator (proven BS identity)

    for yi in range(total_years()):
        a: dict = {"year": yi + 1}
        w = wf_a[yi]
        p = pnl_a[yi]
        sr = sr_a[yi]
        mz = mz_a[yi]
        op = ops_annual[yi] if yi < len(ops_annual) else {}

        # ── Ops model (passthrough) ──
        for k, v in op.items():
            a[k] = v

        # ── Interest breakdown (informational + CF use) ──
        # ie_sr_all/ie_mz_all = ALL facility interest incl IDC (used by CF lines)
        # The P&L ie field comes from pnl_a and correctly EXCLUDES IDC
        a["ie_sr_all"] = sr.get("Interest", 0)  # All interest (including IDC)
        a["ie_mz_all"] = mz.get("Interest", 0)
        a["ie_sr"] = _cash_ie_sr_by_year[yi]  # Cash interest only (post-construction)
        a["ie_mz"] = _cash_ie_mz_by_year[yi]
        a["idc_sr"] = _idc_by_year[yi] * (sr.get("Interest", 0) / max(sr.get("Interest", 0) + mz.get("Interest", 0), 0.01)) if _idc_by_year[yi] > 0 else 0.0
        a["idc_mz"] = _idc_by_year[yi] - a["idc_sr"] if _idc_by_year[yi] > 0 else 0.0

        # Interest income from reserve FDs (actual waterfall accruals)
        a["ii_dsra"] = (w.get("ops_reserve_interest", 0)
                        + w.get("opco_dsra_interest", 0)
                        + w.get("entity_fd_interest", 0)
                        + w.get("mz_div_fd_interest", 0))

        # ── P&L: READ from pnl_a (semi-annual source of truth) ──
        # Bugs #30/#31/#32/#33: do NOT recalculate — read aggregated values
        a["rev"] = p.get("rev", 0)
        a["depr"] = p.get("depr", 0)
        accumulated_depr += a["depr"]

        a["ebitda"] = p.get("ebitda", 0)
        a["ebit"] = p.get("ebit", 0)

        # Swap interest (if active)
        swap_ds_i = 0.0
        swap_ds_p = 0.0
        swap_ds = 0.0
        swap_eur_interest_cash = 0.0
        if swap_active and swap_sched:
            y_start, y_end = annual_month_range(yi)
            _swap_schedule = swap_sched["schedule"]
            _eur_rate = swap_sched.get("eur_rate", 0.047)
            _semi_eur = _eur_rate / 2.0
            _rep_start_m = repayment_start_month()

            # EUR leg
            if y_end <= _rep_start_m:
                _eur_opening = (swap_sched["eur_amount"] if yi == 0
                                else annual[-1].get("swap_eur_bal", swap_sched["eur_amount"]))
                a["swap_eur_bal"] = _eur_opening * (1 + _semi_eur) ** 2
                a["swap_eur_interest"] = a["swap_eur_bal"] - _eur_opening
                swap_eur_interest_cash = 0.0
            else:
                a["swap_eur_bal"] = 0.0
                a["swap_eur_interest"] = 0.0
                swap_eur_interest_cash = 0.0

            # ZAR leg
            _zar_bal_end = swap_sched["zar_amount"]
            for _sr in _swap_schedule:
                if _sr["month"] < y_end:
                    _zar_bal_end = _sr["closing"]
            a["swap_zar_bal"] = _zar_bal_end

            swap_zar_interest = sum(
                r["interest"] for r in _swap_schedule if y_start <= r["month"] < y_end
            )
            swap_zar_principal = sum(
                r["principal"] for r in _swap_schedule
                if y_start <= r["month"] < y_end and r.get("phase") == "repayment"
            )
            swap_zar_interest_cash = sum(
                r["interest"] for r in _swap_schedule
                if y_start <= r["month"] < y_end and r.get("phase") == "repayment"
            )
            a["swap_zar_interest"] = swap_zar_interest
            a["swap_zar_interest_cash"] = swap_zar_interest_cash
            a["swap_zar_p"] = swap_zar_principal
            a["swap_zar_total"] = swap_zar_principal + swap_zar_interest_cash
            a["swap_eur_interest_cash"] = swap_eur_interest_cash

            swap_ds_i = ZAR(swap_zar_interest_cash).to_eur(fx_rate).value
            swap_ds_p = ZAR(swap_zar_principal).to_eur(fx_rate).value
            swap_ds = swap_ds_i + swap_ds_p
            a["cf_swap_ds_i"] = swap_ds_i
            a["cf_swap_ds_p"] = swap_ds_p
            a["cf_swap_ds"] = swap_ds
        else:
            a.update({
                "swap_eur_bal": 0.0, "swap_zar_bal": 0.0,
                "swap_eur_interest": 0.0, "swap_eur_interest_cash": 0.0,
                "swap_zar_interest": 0.0, "swap_zar_interest_cash": 0.0,
                "swap_zar_p": 0.0, "swap_zar_total": 0.0,
                "cf_swap_ds_i": 0.0, "cf_swap_ds_p": 0.0, "cf_swap_ds": 0.0,
            })

        # P&L: ie/pbt/tax/pat from semi-annual source of truth
        # ie excludes IDC (correctly — IDC is capitalised per IAS 23)
        a["ie"] = p.get("ie", 0)
        a["fd_income"] = p.get("fd_income", 0)
        a["pbt"] = p.get("pbt", 0)
        a["tax"] = p.get("tax", 0)
        a["pat"] = p.get("pat", 0)

        # ── CF: from waterfall annual (already aggregated) ──
        y_start, y_end = annual_month_range(yi)

        # Drawdowns
        a["cf_draw_sr"] = sr["Draw Down"]
        a["cf_draw_mz"] = mz["Draw Down"]
        a["cf_draw"] = a["cf_draw_sr"] + a["cf_draw_mz"]

        # Capex = sr drawdowns + mz construction drawdowns
        mz_constr_dd = sum(
            r["Draw Down"] for r in loop_result.mz_schedule
            if y_start <= r["Month"] < y_end and r["Period"] <= construction_end_index()
        )
        a["cf_capex"] = sr["Draw Down"] + mz_constr_dd
        cum_capex += a["cf_capex"]

        # IDC: capitalised into asset cost + loan balance (IAS 23), not in P&L
        a["cf_idc_sr"] = sr.get("IDC", 0)
        a["cf_idc_mz"] = mz.get("IDC", 0)
        a["cf_idc"] = a["cf_idc_sr"] + a["cf_idc_mz"]
        # Memo line for P&L display: IDC capitalised this year
        a["idc_memo"] = a["cf_idc"]

        # Cash interest & principal (post-construction only, for CF statement)
        a["cf_ie_sr"] = _cash_ie_sr_by_year[yi]
        a["cf_ie_mz"] = _cash_ie_mz_by_year[yi]
        a["cf_ie"] = a["cf_ie_sr"] + a["cf_ie_mz"]

        # Principal from facility schedule
        a["cf_pr_sr"] = abs(sr.get("Principle", 0))
        a["cf_pr_mz"] = abs(mz.get("Principle", 0))
        a["cf_pr"] = a["cf_pr_sr"] + a["cf_pr_mz"]
        a["cf_ds"] = a["cf_ie"] + a["cf_pr"]
        a["cf_tax"] = a["tax"]
        a["cf_ops"] = a["ebitda"] + a["ii_dsra"] - a["cf_tax"]
        a["cf_operating_pre_debt"] = a["ebitda"]
        a["cf_after_debt_service"] = a["cf_ops"] - a["cf_ds"] - swap_ds

        # Equity & grants
        a["cf_equity"] = entity_equity if yi == 0 else 0.0
        a["cf_grant_dtic"] = dtic_grant_entity if yi == 1 else 0.0
        a["cf_grant_iic"] = ta_grant_entity if yi == 1 else 0.0
        a["cf_grants"] = a["cf_grant_dtic"] + a["cf_grant_iic"]

        # Grant acceleration from facility schedule
        a["cf_grant_accel_sr"] = _accel_by_year[yi]
        a["cf_grant_accel"] = a["cf_grant_accel_sr"]

        # Waterfall acceleration (debt paydown from cash surplus)
        a["cf_accel_sr"] = w.get("sr_accel_entity", 0)
        a["cf_accel_mz"] = w.get("mz_accel_entity", 0)
        a["cf_sr_accel"] = a["cf_accel_sr"]
        a["cf_mz_accel"] = a["cf_accel_mz"]

        # Backward compat
        a["cf_prepay_sr"] = a["cf_grant_accel_sr"]
        a["cf_prepay"] = a["cf_grant_accel"]
        if a["cf_grant_accel"] > 0 and (dtic_grant_entity + gepf_grant_entity) > 0:
            _gs = dtic_grant_entity / (dtic_grant_entity + gepf_grant_entity)
            a["cf_grant_accel_dtic"] = a["cf_grant_accel"] * _gs
            a["cf_grant_accel_gepf"] = a["cf_grant_accel"] * (1.0 - _gs)
        else:
            a["cf_grant_accel_dtic"] = 0.0
            a["cf_grant_accel_gepf"] = 0.0
        a["cf_prepay_dtic"] = a["cf_grant_accel_dtic"]
        a["cf_prepay_gepf"] = a["cf_grant_accel_gepf"]

        # Waterfall reserve detail (informational, not used for BS)
        a["cf_ops_reserve_fill"] = w.get("ops_reserve_fill", 0)
        a["cf_opco_dsra_fill"] = w.get("opco_dsra_fill", 0)
        a["cf_opco_dsra_release"] = w.get("opco_dsra_release", 0)
        a["cf_mz_div_fd_fill"] = w.get("mz_div_fd_fill", 0)
        a["cf_entity_fd_fill"] = w.get("entity_fd_fill", 0)
        a["cf_swap_accel"] = w.get("swap_leg_accel", 0)
        a["cf_od_lent"] = w.get("od_lent", 0)
        a["cf_od_received"] = w.get("od_received", 0)
        a["cf_od_repaid"] = w.get("od_repaid", 0)
        a["cf_od_interest"] = w.get("od_interest", 0)
        a["wf_od_bal"] = w.get("od_bal", 0)
        a["cf_free_surplus"] = w.get("free_surplus", 0)

        # Waterfall reserve balances (informational)
        a["wf_ops_reserve"] = w.get("ops_reserve_bal", 0)
        a["wf_opco_dsra"] = w.get("opco_dsra_bal", 0)
        a["wf_mz_div_fd"] = w.get("mz_div_fd_bal", 0)
        a["wf_entity_fd"] = w.get("entity_fd_bal", 0)

        # Backward-compat: bs_ prefixed reserve balance keys (app.py L6704-6707)
        a["bs_ops_reserve"] = a["wf_ops_reserve"]
        a["bs_opco_dsra"] = a["wf_opco_dsra"]
        a["bs_mz_div_fd"] = a["wf_mz_div_fd"]
        a["bs_entity_fd"] = a["wf_entity_fd"]

        # Dividends (exit cash from entity)
        a["cf_dividend"] = w.get("dividend_paid", 0)
        a["cum_dividends"] = w.get("cum_dividends", 0)

        # ── CF net (running cash accumulator — proven BS identity) ──
        # Dividends EXIT cash (reduce reserves), so subtract them
        a["cf_net"] = (a["cf_equity"] + a["cf_draw"] - a["cf_capex"]
                       + a["cf_grants"] - a["cf_grant_accel"]
                       + a["cf_ops"] - a["cf_ie"] - a["cf_pr"]
                       - a["cf_dividend"])

        # Backward-compat: old-style DSRA/FD roll-forward keys (app.py L6711-6714)
        # Identity: dsra_opening + dsra_deposit + dsra_interest = dsra_bal
        a["dsra_opening"] = _cash_bal
        a["dsra_interest"] = a["ii_dsra"]
        a["dsra_deposit"] = a["cf_net"] - a["ii_dsra"]
        _cash_bal += a["cf_net"]
        a["dsra_bal"] = _cash_bal

        # ── BS ──
        # Fixed assets: capex + capitalised IDC - cumulative depreciation
        # IDC (IAS 23): borrowing costs during construction are capitalised into
        # the qualifying asset and into the loan balance. P&L ie correctly
        # excludes IDC; the asset cost must include it for BS identity to hold.
        cum_idc += a["cf_idc"]
        a["bs_fixed_assets"] = max(min(cum_capex + cum_idc, depreciable_base + cum_idc) - accumulated_depr, 0.0)

        # Cash / reserves: running CF accumulator (for BS identity)
        a["bs_dsra"] = _cash_bal
        # Total reserves for display: sum of 4 actual waterfall FD buckets
        # (never negative — each bucket is floor-guarded by the waterfall)
        a["bs_reserves_total"] = (a["wf_ops_reserve"]
                                  + a["wf_opco_dsra"]
                                  + a["wf_mz_div_fd"]
                                  + a["wf_entity_fd"])

        # Assets = fixed assets + cash (no swap in BS — handled separately)
        a["bs_assets"] = a["bs_fixed_assets"] + _cash_bal

        a["sr_closing"] = sr["Closing"]
        a["mz_closing"] = mz["Closing"]
        a["bs_sr"] = max(a["sr_closing"], 0)
        a["bs_mz"] = max(a["mz_closing"], 0)
        a["bs_debt"] = a["bs_sr"] + a["bs_mz"]

        a["bs_equity_sh"] = entity_equity
        a["bs_equity"] = a["bs_assets"] - a["bs_debt"]
        a["bs_retained"] = a["bs_equity"] - entity_equity

        cum_pat += a["pat"]
        cum_grants += a["cf_grants"]
        # RE check: CumPAT + CumGrants - CumDividends (dividends reduce RE)
        a["bs_retained_check"] = cum_pat + cum_grants - a.get("cum_dividends", 0)
        a["bs_gap"] = a["bs_retained"] - a["bs_retained_check"]

        # Swap detail (tracked separately — FX mismatch is informational)
        a["bs_swap_eur"] = a.get("swap_eur_bal", 0.0)
        a["bs_swap_liability"] = (
            ZAR(a.get("swap_zar_bal", 0.0)).to_eur(fx_rate).value
            if swap_active and fx_rate > 0 else 0.0
        )
        a["bs_swap_net"] = a["bs_swap_eur"] - a["bs_swap_liability"]

        annual.append(a)

    return annual
