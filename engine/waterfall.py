"""Entity surplus cascade allocator.

The waterfall is a pure CASH ALLOCATION engine. It:
1. READS pre-computed values (EBITDA, tax, interest, principal from upstream)
2. ALLOCATES surplus cash (reserves, acceleration, entity FD, etc.)
3. MAINTAINS running accumulators for allocation decisions (caps, targets)

Two interfaces:
  - waterfall_step(): single-period allocator for the One Big Loop.
    Takes explicit parameters. Mutates WaterfallState.
  - compute_entity_waterfall(): batch allocator for standalone/sensitivity.
    Reads from pre-built vectors. Returns 20-period list.

Acceleration amounts are the waterfall's OUTPUT, applied to facilities
by the caller (FacilityState.finalize_period in the One Big Loop,
or convergence rebuild in the batch interface).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.config import ModelConfig
from engine.facility import get_next_sr_pi
from engine.periods import total_periods, total_years, period_start_month, year_index
from engine.swap import build_swap_closing_bal

if TYPE_CHECKING:
    from engine.reserves import (
        ReserveAccrual, OpsReserve, OpcoDSRA, MezzDivFD, EntityFD,
    )


# ── Per-period waterfall allocator (for One Big Loop) ─────────────


@dataclass
class WaterfallState:
    """Running accumulators carried across periods."""
    ops_reserve_bal: float = 0.0
    opco_dsra_bal: float = 0.0
    opco_dsra_target: float = 0.0
    entity_fd_bal: float = 0.0
    od_bal: float = 0.0
    mz_div_liability_bal: float = 0.0
    mz_div_fd_bal: float = 0.0
    mz_div_payout_done: bool = False
    swap_leg_bal: float = 0.0
    cum_dividends: float = 0.0


def waterfall_step(
    hi: int,
    entity_key: str,
    cfg: ModelConfig,
    *,
    # From P&L / ops
    ebitda: float,
    opex: float,
    tax: float,
    # Next period opex (for reserve target look-ahead)
    next_opex: float,
    # From FacilityState
    sr_interest: float,
    sr_principal: float,
    sr_pi: float,
    mz_interest: float,
    mz_principal: float,
    mz_pi: float,
    sr_pre_accel_closing: float,
    mz_pre_accel_closing: float,
    # Swap
    swap_leg_scheduled: float = 0.0,
    # Cash inflows
    cash_inflows: dict | None = None,
    # Sweep percentage
    sweep_pct: float = 1.0,
    # LanRED deficit (NWL only)
    lanred_deficit: float = 0.0,
    # IC overdraft received (LanRED only)
    od_received: float = 0.0,
    # Reserve accrual results (from reserve assets — pre-computed)
    # When provided, waterfall uses these instead of computing interest/targets
    ops_accrual: "ReserveAccrual | None" = None,
    dsra_accrual: "ReserveAccrual | None" = None,
    entity_fd_accrual: "ReserveAccrual | None" = None,
    mz_div_accrual: "ReserveAccrual | None" = None,
    mz_div_fd: "MezzDivFD | None" = None,
    # Reserve objects (for waterfall to update balances after allocation)
    ops_reserve_obj: "OpsReserve | None" = None,
    dsra_obj: "OpcoDSRA | None" = None,
    entity_fd_obj: "EntityFD | None" = None,
    # State
    state: WaterfallState | None = None,
) -> dict:
    """Single-period waterfall allocation.

    Mutates state. Returns output row dict (same keys as compute_entity_waterfall).
    sr/mz_pre_accel_closing: facility closing BEFORE acceleration (from FacilityState).
    The actual closing (after acceleration) is set by the caller after finalize_period().
    """
    if state is None:
        state = WaterfallState()

    ops_reserve_coverage = cfg.ops_reserve_coverage        # 1.0
    fd_interest_rate = cfg.fd_rate_eur / 2.0               # 3.5% / 2
    od_rate = cfg.od_rate / 2.0                            # 10% / 2
    mz_div_rate = cfg.mz_div_gap_rate / 2.0               # 5.25% / 2

    accel_rate_sr = cfg.sr_ic_rate                         # 5.20%
    accel_rate_mz = cfg.cc_irr_target                      # 20%
    accel_rate_swap = cfg.zar_swap_rate                    # 9.69%

    half_month = period_start_month(hi)

    # Working copies of facility balances (for allocation decisions)
    sr_ic_bal = sr_pre_accel_closing
    mz_ic_bal = mz_pre_accel_closing

    ie_half_sr = sr_interest
    ie_half_mz = mz_interest
    ie_half = ie_half_sr + ie_half_mz
    ds_cash = sr_pi + mz_pi

    # Swap scheduled
    swap_sched_applied = 0.0
    if state.swap_leg_bal > 0.01 and swap_leg_scheduled > 0:
        swap_sched_applied = min(swap_leg_scheduled, state.swap_leg_bal)
        state.swap_leg_bal -= swap_sched_applied
    ds_cash += swap_sched_applied

    # Cash inflows
    ci = cash_inflows or {}
    dtic_grant = ci.get("dtic_grant", 0)
    iic_grant = ci.get("iic_grant", 0)
    gepf_bulk = ci.get("gepf_bulk", 0)
    mezz_draw = ci.get("mezz_draw", 0)
    eur_leg = ci.get("eur_leg_repayment", 0)
    pre_rev_hedge = mezz_draw + eur_leg

    # Tag sources as special
    special_cash = dtic_grant + gepf_bulk + pre_rev_hedge
    if half_month == 6:
        special_cash += ebitda
    normal_cash = iic_grant
    if half_month != 6:
        normal_cash += ebitda

    # Mezz draw increases Mezz IC balance
    if mezz_draw > 0:
        mz_ic_bal += mezz_draw

    pbt = ebitda - ie_half

    # Split tax proportionally
    total_gross = special_cash + normal_cash
    if total_gross > 0 and tax > 0:
        special_tax = tax * (special_cash / total_gross)
        normal_tax = tax - special_tax
    else:
        special_tax = 0
        normal_tax = tax

    special_pool = max(special_cash - special_tax, 0)
    normal_pool = max(normal_cash - normal_tax, 0)
    cash_available = special_pool + normal_pool

    special_to_sr_pi = min(special_pool, sr_pi)
    special_after_pi = special_pool - special_to_sr_pi

    remaining_ds = ds_cash - special_to_sr_pi
    net = normal_pool - max(remaining_ds, 0)

    remaining = max(net, 0)
    deficit = min(net, 0)

    mz_opening_for_div_accrual = mz_ic_bal

    # ── Mezz Dividend Reserve ──
    # When reserve objects are provided, use them; otherwise inline (batch compat)
    mz_div_applies = entity_key in ("nwl", "lanred", "timberworx")
    _mz_div_accrual_val = 0.0
    mz_div_payout_flag = False
    mz_div_payout_amount = 0.0

    if mz_div_fd is not None:
        # Reserve object path: accrual already computed by caller
        _mz_div_accrual_val = mz_div_fd.div_accrual
        if mz_div_fd.should_payout(mz_ic_bal):
            mz_div_payout_flag = True
            mz_div_payout_amount = mz_div_fd.payout()
    elif mz_div_applies:
        # Inline path (batch interface backward compat)
        if not state.mz_div_payout_done:
            if mz_opening_for_div_accrual > 0.01:
                _mz_div_accrual_val = mz_opening_for_div_accrual * mz_div_rate
                state.mz_div_liability_bal += _mz_div_accrual_val
            if mz_ic_bal <= 0.01 and state.mz_div_liability_bal > 0.01:
                mz_div_payout_flag = True
                state.mz_div_payout_done = True
        if mz_div_payout_flag:
            mz_div_payout_amount = state.mz_div_fd_bal
            state.mz_div_fd_bal = 0.0
            state.mz_div_liability_bal = 0.0

    # ── Cascade allocation ──
    # Interest and targets: from reserve objects when provided, inline otherwise
    if ops_accrual is not None:
        ops_reserve_interest = ops_accrual.interest
        ops_reserve_target = ops_accrual.target
        # Reserve object already applied interest to its balance
        state.ops_reserve_bal = ops_accrual.balance_after_interest
    else:
        ops_reserve_interest = state.ops_reserve_bal * fd_interest_rate
        state.ops_reserve_bal += ops_reserve_interest
        if opex < 0.01 and next_opex > 0:
            ops_reserve_target = next_opex * ops_reserve_coverage
        else:
            ops_reserve_target = opex * ops_reserve_coverage

    if dsra_accrual is not None:
        opco_dsra_interest = dsra_accrual.interest
        opco_dsra_target = dsra_accrual.target
        state.opco_dsra_bal = dsra_accrual.balance_after_interest
    else:
        opco_dsra_interest = state.opco_dsra_bal * fd_interest_rate
        state.opco_dsra_bal += opco_dsra_interest
        opco_dsra_target = state.opco_dsra_target

    if mz_div_accrual is not None:
        mz_div_fd_interest = mz_div_accrual.interest
        state.mz_div_fd_bal = mz_div_accrual.balance_after_interest
    else:
        mz_div_fd_interest = state.mz_div_fd_bal * fd_interest_rate
        state.mz_div_fd_bal += mz_div_fd_interest

    if entity_fd_accrual is not None:
        entity_fd_interest = entity_fd_accrual.interest
        state.entity_fd_bal = entity_fd_accrual.balance_after_interest
    else:
        entity_fd_interest = state.entity_fd_bal * fd_interest_rate
        state.entity_fd_bal += entity_fd_interest

    ops_reserve_fill = 0.0
    opco_dsra_fill = 0.0
    opco_dsra_release = 0.0
    od_lent = 0.0
    od_received_val = od_received  # from parameter (C3)
    od_repaid = 0.0
    od_interest = 0.0
    mz_div_fd_fill_val = 0.0
    mz_accel_entity = 0.0
    swap_leg_accel = 0.0
    sr_accel_entity = 0.0
    od_accel = 0.0

    # Special pool -> Sr IC accel (grant-funded — NOT gated on DSRA)
    if special_after_pi > 0 and sr_ic_bal > 0.01:
        sr_accel_entity = min(special_after_pi, sr_ic_bal)
        sr_ic_bal -= sr_accel_entity

    # Step 1: Ops Reserve — allocate gap
    ops_reserve_gap = max(ops_reserve_target - state.ops_reserve_bal, 0)
    ops_reserve_fill = min(remaining, ops_reserve_gap)
    state.ops_reserve_bal += ops_reserve_fill
    if ops_reserve_obj is not None:
        ops_reserve_obj.fill(ops_reserve_fill)
    remaining -= ops_reserve_fill

    # Step 2: OpCo DSRA — allocate gap
    opco_dsra_gap = max(opco_dsra_target - state.opco_dsra_bal, 0)
    opco_dsra_fill = min(remaining, opco_dsra_gap)
    opco_dsra_release = (
        max(state.opco_dsra_bal - opco_dsra_target, 0)
        if state.opco_dsra_bal > opco_dsra_target else 0
    )
    state.opco_dsra_bal += opco_dsra_fill - opco_dsra_release
    if dsra_obj is not None:
        dsra_obj.fill(opco_dsra_fill)
        if opco_dsra_release > 0:
            dsra_obj.release(opco_dsra_release)
    remaining -= opco_dsra_fill
    remaining += opco_dsra_release

    # Step 3: Overdraft lending (NWL) or receiving (LanRED)
    if entity_key == "nwl" and lanred_deficit > 0 and remaining > 0:
        od_lent = min(remaining, lanred_deficit)
        od_interest_on_existing = state.od_bal * od_rate
        state.od_bal += od_lent + od_interest_on_existing
        od_interest = od_interest_on_existing
        remaining -= od_lent

    if entity_key == "lanred":
        # Interest on OPENING balance (before injection) — mirrors NWL timing
        od_interest = state.od_bal * od_rate
        state.od_bal += od_interest
        # THEN inject OD received (from NWL lending via IC plugin)
        if od_received_val > 0:
            state.od_bal += od_received_val
            remaining += od_received_val

    # Step 4: Mezz Dividend FD fill
    if mz_div_applies and not mz_div_payout_flag and _mz_div_accrual_val > 0 and remaining > 0:
        if mz_div_fd is not None:
            fd_fill_gap = mz_div_fd.liability - mz_div_fd.balance
            fd_fill_gap = max(fd_fill_gap, 0)
            mz_div_fd_fill_val = min(remaining, fd_fill_gap)
            mz_div_fd.fill(mz_div_fd_fill_val)
            state.mz_div_fd_bal = mz_div_fd.balance
            state.mz_div_liability_bal = mz_div_fd.liability
        else:
            fd_fill_gap = max(state.mz_div_liability_bal - state.mz_div_fd_bal, 0)
            mz_div_fd_fill_val = min(remaining, fd_fill_gap)
            state.mz_div_fd_bal += mz_div_fd_fill_val
        remaining -= mz_div_fd_fill_val

    # Surplus acceleration — GATED on DSRA funding level (B1)
    # Grant-funded Sr accel (special pool above) is NOT gated.
    # This block handles: Mezz, OD, ZAR swap leg, Sr — ranked by rate
    # descending (Mezz 20% > OD 10% > ZAR swap 9.69% > Sr 5.20%).
    dsra_funded = (state.opco_dsra_bal >= opco_dsra_target - 0.01) or opco_dsra_target < 0.01
    if dsra_funded and remaining > 0:
        accel_targets = []
        if mz_ic_bal > 0.01:
            accel_targets.append(("mz", accel_rate_mz, mz_ic_bal))
        if state.od_bal > 0.01:
            accel_targets.append(("od", cfg.od_rate, state.od_bal))
        if state.swap_leg_bal > 0.01:
            accel_targets.append(("swap", accel_rate_swap, state.swap_leg_bal))
        if sr_ic_bal > 0.01:
            accel_targets.append(("sr", accel_rate_sr, sr_ic_bal))
        accel_targets.sort(key=lambda t: t[1], reverse=True)

        for akey, arate, abal in accel_targets:
            if remaining <= 0:
                break
            apay = min(remaining * sweep_pct, abal)
            if akey == "mz":
                mz_accel_entity = apay
                mz_ic_bal -= apay
            elif akey == "od":
                od_accel = apay
                state.od_bal -= apay
            elif akey == "swap":
                swap_leg_accel = apay
                state.swap_leg_bal -= apay
            elif akey == "sr":
                sr_accel_entity += apay
                sr_ic_bal -= apay
            remaining -= apay

    # Overdraft repayment (LanRED only)
    if entity_key == "lanred" and state.od_bal > 0.01 and remaining > 0:
        od_repaid = min(remaining, state.od_bal)
        state.od_bal -= od_repaid
        remaining -= od_repaid

    # Entity FD: after ALL debt = 0
    entity_fd_fill = 0.0
    all_debt_zero = (mz_ic_bal <= 0.01 and sr_ic_bal <= 0.01
                     and state.od_bal <= 0.01 and state.swap_leg_bal <= 0.01)
    if all_debt_zero and remaining > 0:
        entity_fd_fill = remaining
        state.entity_fd_bal += entity_fd_fill
        if entity_fd_obj is not None:
            entity_fd_obj.fill(entity_fd_fill)
        remaining -= entity_fd_fill

    # Dividends: extract cash from entity FD (exits the entity)
    div_cfg = cfg.waterfall.get("dividends", {})
    dividend_paid = 0.0
    if (div_cfg.get("enabled", False)
            and hi >= div_cfg.get("start_period", 10)
            and state.entity_fd_bal > 0.01):
        div_pct = div_cfg.get("pct", 0.0)
        div_eligible = True
        if div_cfg.get("all_debt_must_be_zero", True) and not all_debt_zero:
            div_eligible = False
        if div_eligible and div_pct > 0:
            dividend_paid = state.entity_fd_bal * div_pct
            state.entity_fd_bal -= dividend_paid
            if entity_fd_obj is not None:
                entity_fd_obj.withdraw(dividend_paid)
            state.cum_dividends += dividend_paid

    free_surplus = remaining

    # Build output row
    return {
        "ebitda": ebitda, "tax": tax, "ds_cash": ds_cash,
        "sr_pi": sr_pi, "mz_pi": mz_pi,
        "mz_prin_sched": mz_principal, "sr_prin_sched": sr_principal,
        "swap_leg_scheduled": swap_sched_applied,
        "mz_accel_entity": mz_accel_entity,
        "sr_accel_entity": sr_accel_entity,
        "swap_leg_accel": swap_leg_accel,
        "ie_half_sr": ie_half_sr, "ie_half_mz": ie_half_mz,
        "ie_year": ie_half, "pbt": pbt,
        "surplus": max(cash_available - ds_cash, 0),
        "deficit": deficit,
        "dtic_grant": dtic_grant,
        "iic_grant": iic_grant,
        "gepf_bulk": gepf_bulk,
        "specials": special_cash,
        "pre_rev_hedge": pre_rev_hedge,
        "mezz_draw": mezz_draw,
        "eur_leg_repayment": eur_leg,
        "cash_available": cash_available,
        # Placeholder — overwritten by caller after finalize_period
        "mz_ic_bal": mz_ic_bal,
        "sr_ic_bal": sr_ic_bal,
        "swap_leg_bal": state.swap_leg_bal,
        "ops_reserve_interest": ops_reserve_interest,
        "ops_reserve_fill": ops_reserve_fill,
        "ops_reserve_bal": state.ops_reserve_bal,
        "ops_reserve_target": ops_reserve_target,
        "opco_dsra_interest": opco_dsra_interest,
        "opco_dsra_fill": opco_dsra_fill,
        "opco_dsra_release": opco_dsra_release,
        "opco_dsra_bal": state.opco_dsra_bal,
        "opco_dsra_target": opco_dsra_target,
        "od_lent": od_lent,
        "od_received": od_received_val,
        "od_repaid": od_repaid,
        "od_accel": od_accel,
        "od_interest": od_interest,
        "od_bal": state.od_bal,
        "entity_fd_interest": entity_fd_interest,
        "entity_fd_fill": entity_fd_fill,
        "entity_fd_bal": state.entity_fd_bal,
        "dividend_paid": dividend_paid,
        "cum_dividends": state.cum_dividends,
        "free_surplus": free_surplus,
        "mz_div_opening_basis": mz_opening_for_div_accrual,
        "mz_div_accrual": _mz_div_accrual_val,
        "mz_div_liability_bal": state.mz_div_liability_bal if mz_div_fd is None else mz_div_fd.liability,
        "mz_div_fd_interest": mz_div_fd_interest,
        "mz_div_fd_fill": mz_div_fd_fill_val,
        "mz_div_fd_bal": state.mz_div_fd_bal if mz_div_fd is None else mz_div_fd.balance,
        "mz_div_payout": mz_div_payout_flag,
        "mz_div_payout_amount": mz_div_payout_amount,
    }


# Keys whose annual value = H2 closing (point-in-time balances, not flows)
WF_BALANCE_KEYS = frozenset({
    "mz_ic_bal", "sr_ic_bal", "swap_leg_bal",
    "ops_reserve_bal", "ops_reserve_target",
    "opco_dsra_bal", "opco_dsra_target",
    "od_bal", "entity_fd_bal",
    "mz_div_liability_bal", "mz_div_fd_bal",
    "cum_dividends",
})

# Keys whose annual value = H1 opening (start-of-year snapshot)
WF_OPENING_KEYS = frozenset({
    "mz_div_opening_basis",
})

# Keys whose annual value = logical-OR of halves (boolean flags)
WF_BOOL_KEYS = frozenset({
    "mz_div_payout",
})


def compute_entity_waterfall(
    entity_key: str,
    ops_annual: list[dict],
    entity_sr_sched: list[dict],
    entity_mz_sched: list[dict],
    cfg: ModelConfig,
    *,
    sr_vectors: dict,
    mz_vectors: dict,
    semi_annual_tax: list[float],
    semi_annual_pl: list[dict] | None = None,
    swap_vectors: dict | None = None,
    lanred_deficit_vector: list[float] | None = None,
    nwl_swap_schedule: dict | None = None,
    lanred_swap_schedule: dict | None = None,
    sweep_pct: float = 1.0,
    ops_semi_annual: list[dict] | None = None,
    cash_inflows: list[dict] | None = None,
) -> list[dict]:
    """Entity surplus computation with INDEX-based reads.

    Full entity-level cascade (20 semi-annual periods).
    Reads EBITDA, opex, interest, principal, and balances from pre-computed
    source tables. Returns list of 20 semi-annual dicts with full cascade
    breakdown.

    Args:
        semi_annual_pl: 20-period P&L (from build_semi_annual_pnl). When
            provided, EBITDA and opex are indexed from here. When None,
            falls back to ops_semi_annual/ops_annual (legacy callers).
        swap_vectors: Pre-computed swap payment vectors (from
            extract_swap_vectors). When provided, swap leg payments are
            indexed from here. When None, falls back to inline iteration
            of raw swap schedule (legacy callers).
    """
    ops_reserve_coverage = cfg.ops_reserve_coverage        # 1.0
    fd_interest_rate = cfg.fd_rate_eur / 2.0               # 3.5% / 2
    od_rate = cfg.od_rate / 2.0                            # 10% / 2
    mz_div_rate = cfg.mz_div_gap_rate / 2.0               # 5.25% / 2

    rows = []

    # State
    ops_reserve_bal = 0.0
    opco_dsra_bal = 0.0
    entity_fd_bal = 0.0
    od_bal_entity = 0.0
    mz_div_applies = entity_key in ("nwl", "lanred", "timberworx")
    mz_div_liability_bal = 0.0
    mz_div_fd_bal = 0.0
    mz_div_payout_done = False
    cum_dividends = 0.0

    # ZAR Rand Leg running balance — INDEX from swap_vectors if available
    if swap_vectors is not None:
        swap_leg_bal = swap_vectors["initial_bal"]
    else:
        # Legacy fallback: compute from raw swap schedule
        zar_swap_sched = None
        if entity_key == "nwl" and nwl_swap_schedule:
            zar_swap_sched = nwl_swap_schedule
        elif entity_key == "lanred" and lanred_swap_schedule:
            zar_swap_sched = lanred_swap_schedule
        swap_leg_bal = 0.0
        if zar_swap_sched:
            zar_total_payments = sum(r["payment"] for r in zar_swap_sched.get("schedule", []))
            zar_fx = (zar_swap_sched.get("zar_amount", 1)
                      / max(zar_swap_sched.get("eur_amount", 1), 1)
                      ) if zar_swap_sched.get("eur_amount", 0) > 0 else 1
            swap_leg_bal = zar_total_payments / zar_fx if zar_fx > 0 else 0

    # Acceleration rates (used for priority sorting only)
    accel_rate_sr = cfg.sr_ic_rate                         # 5.20%
    accel_rate_mz = cfg.cc_irr_target                      # 20%
    accel_rate_swap = cfg.zar_swap_rate                    # 9.69%

    for hi in range(total_periods()):
        yi = year_index(hi)
        half_month = period_start_month(hi)

        # Read IC balances from facility vectors (fresh each iteration)
        sr_ic_bal = sr_vectors["closing_bal"][hi]
        mz_ic_bal = mz_vectors["closing_bal"][hi]

        # ── INDEX: EBITDA from semi-annual P&L ──
        if semi_annual_pl is not None and hi < len(semi_annual_pl):
            ebitda = semi_annual_pl[hi]["ebitda"]
        elif ops_semi_annual and hi < len(ops_semi_annual):
            # Legacy fallback: recalculate from ops (only used by old callers)
            s = ops_semi_annual[hi]
            ebitda = (s.get("rev_total", 0) - s.get("om_cost", 0)
                      - s.get("power_cost", 0) - s.get("rent_cost", 0))
        else:
            ops = ops_annual[yi] if yi < len(ops_annual) else {}
            ebitda = (ops.get("rev_total", 0) - ops.get("om_cost", 0)
                      - ops.get("power_cost", 0) - ops.get("rent_cost", 0)) / 2.0

        # ── INDEX: Semi-annual opex from P&L (for reserve target) ──
        if semi_annual_pl is not None and hi < len(semi_annual_pl):
            semi_ops_cost = semi_annual_pl[hi]["opex"]
        elif ops_semi_annual and hi < len(ops_semi_annual):
            # Legacy fallback
            s_ops = ops_semi_annual[hi]
            semi_ops_cost = (s_ops.get("om_cost", 0) + s_ops.get("power_cost", 0)
                             + s_ops.get("rent_cost", 0))
        else:
            ops = ops_annual[yi] if yi < len(ops_annual) else {}
            semi_ops_cost = (ops.get("om_cost", 0) + ops.get("power_cost", 0)
                             + ops.get("rent_cost", 0)) / 2.0

        # ── INDEX: Interest, principal, P+I from facility vectors ──
        ie_half_sr = sr_vectors["interest"][hi]
        ie_half_mz = mz_vectors["interest"][hi]
        sr_prin_sched = sr_vectors["principal"][hi]
        sr_pi = sr_vectors["pi"][hi]
        mz_prin_sched = mz_vectors["principal"][hi]
        mz_pi = mz_vectors["pi"][hi]

        ie_half = ie_half_sr + ie_half_mz
        ds_cash = sr_pi + mz_pi

        # ── INDEX: ZAR Rand Leg scheduled service from swap vectors ──
        swap_leg_scheduled = 0.0
        if swap_vectors is not None and swap_leg_bal > 0.01:
            swap_leg_scheduled = min(swap_vectors["scheduled_payment"][hi], swap_leg_bal)
            swap_leg_bal -= swap_leg_scheduled
        elif swap_vectors is None:
            # Legacy fallback: iterate raw swap schedule
            zar_swap_sched_legacy = None
            if entity_key == "nwl" and nwl_swap_schedule:
                zar_swap_sched_legacy = nwl_swap_schedule
            elif entity_key == "lanred" and lanred_swap_schedule:
                zar_swap_sched_legacy = lanred_swap_schedule
            if zar_swap_sched_legacy and swap_leg_bal > 0.01:
                zar_due_half = 0.0
                half_m_start = period_start_month(hi)
                for r in zar_swap_sched_legacy.get("schedule", []):
                    if r["month"] == half_m_start:
                        zar_due_half += r["payment"]
                zar_fx_h = (zar_swap_sched_legacy.get("zar_amount", 1)
                            / max(zar_swap_sched_legacy.get("eur_amount", 1), 1)
                            ) if zar_swap_sched_legacy.get("eur_amount", 0) > 0 else 1
                swap_leg_scheduled = min(zar_due_half / zar_fx_h if zar_fx_h > 0 else 0, swap_leg_bal)
                swap_leg_bal -= swap_leg_scheduled
        ds_cash += swap_leg_scheduled

        # Cash inflows
        ci = cash_inflows[hi] if cash_inflows and hi < len(cash_inflows) else {}
        dtic_grant = ci.get("dtic_grant", 0)
        iic_grant = ci.get("iic_grant", 0)
        gepf_bulk = ci.get("gepf_bulk", 0)
        mezz_draw = ci.get("mezz_draw", 0)
        eur_leg = ci.get("eur_leg_repayment", 0)
        pre_rev_hedge = mezz_draw + eur_leg

        # Tag sources as special
        special_cash = dtic_grant + gepf_bulk + pre_rev_hedge
        if half_month == 6:  # C2 period: EBITDA treated as special cash
            special_cash += ebitda
        normal_cash = iic_grant
        if half_month != 6:  # Non-C2 periods: EBITDA is normal cash
            normal_cash += ebitda

        # Mezz draw increases Mezz IC balance (local modification for this period)
        if mezz_draw > 0:
            mz_ic_bal += mezz_draw

        # ── INDEX: Tax from P&L (required, no fallback) ──
        tax = semi_annual_tax[hi]
        pbt = ebitda - ie_half  # display only

        # Split tax proportionally
        total_gross = special_cash + normal_cash
        if total_gross > 0 and tax > 0:
            special_tax = tax * (special_cash / total_gross)
            normal_tax = tax - special_tax
        else:
            special_tax = 0
            normal_tax = tax

        special_pool = max(special_cash - special_tax, 0)
        normal_pool = max(normal_cash - normal_tax, 0)
        cash_available = special_pool + normal_pool

        # Special pool -> Sr IC P+I first, then accel
        special_to_sr_pi = min(special_pool, sr_pi)
        special_after_pi = special_pool - special_to_sr_pi

        remaining_ds = ds_cash - special_to_sr_pi
        net = normal_pool - max(remaining_ds, 0)

        remaining = max(net, 0)
        deficit = min(net, 0)

        # Save opening Mezz IC balance for dividend accrual
        mz_opening_for_div_accrual = mz_ic_bal

        # IC balances already reflect scheduled principal (read from closing_bal).
        # Only acceleration (computed below) further reduces them.

        # Mezz Dividend Reserve
        mz_div_accrual = 0.0
        mz_div_fd_fill = 0.0
        mz_div_payout = False
        mz_div_payout_amount = 0.0
        if mz_div_applies and not mz_div_payout_done:
            if mz_opening_for_div_accrual > 0.01:
                mz_div_accrual = mz_opening_for_div_accrual * mz_div_rate
                mz_div_liability_bal += mz_div_accrual
            if mz_ic_bal <= 0.01 and mz_div_liability_bal > 0.01:
                mz_div_payout = True
                mz_div_payout_done = True

        if mz_div_applies and mz_div_payout:
            mz_div_payout_amount = mz_div_fd_bal
            mz_div_fd_bal = 0.0
            mz_div_liability_bal = 0.0

        # Cascade allocation
        ops_reserve_interest = ops_reserve_bal * fd_interest_rate
        ops_reserve_bal += ops_reserve_interest

        # Ops reserve target — INDEX from P&L for look-ahead too
        if semi_ops_cost < 0.01 and (hi + 1) < total_periods():
            if semi_annual_pl is not None and (hi + 1) < len(semi_annual_pl):
                next_ops_cost = semi_annual_pl[hi + 1]["opex"]
            elif ops_semi_annual and (hi + 1) < len(ops_semi_annual):
                next_ops = ops_semi_annual[hi + 1]
                next_ops_cost = (next_ops.get("om_cost", 0) + next_ops.get("power_cost", 0)
                                 + next_ops.get("rent_cost", 0))
            else:
                next_ops_cost = 0.0
            ops_reserve_target = next_ops_cost * ops_reserve_coverage
        else:
            ops_reserve_target = semi_ops_cost * ops_reserve_coverage

        ops_reserve_fill = 0.0
        next_sr_pi_val = get_next_sr_pi(entity_sr_sched, half_month)
        opco_dsra_target = min(next_sr_pi_val, sr_ic_bal) if sr_ic_bal > 0.01 else 0.0
        opco_dsra_interest = opco_dsra_bal * fd_interest_rate
        opco_dsra_bal += opco_dsra_interest
        opco_dsra_fill = 0.0
        opco_dsra_release = 0.0
        od_lent = 0.0
        od_received = 0.0
        od_repaid = 0.0
        od_interest = 0.0
        mz_div_fd_interest = mz_div_fd_bal * fd_interest_rate
        mz_div_fd_bal += mz_div_fd_interest
        mz_div_fd_fill_val = 0.0
        mz_accel_entity = 0.0
        swap_leg_accel = 0.0
        sr_accel_entity = 0.0
        od_accel = 0.0

        # Special pool -> Sr IC accel
        if special_after_pi > 0 and sr_ic_bal > 0.01:
            sr_accel_entity = min(special_after_pi, sr_ic_bal)
            sr_ic_bal -= sr_accel_entity

        # Step 1: Ops Reserve FD
        ops_reserve_gap = max(ops_reserve_target - ops_reserve_bal, 0)
        ops_reserve_fill = min(remaining, ops_reserve_gap)
        ops_reserve_bal += ops_reserve_fill
        remaining -= ops_reserve_fill

        # Step 2: OpCo DSRA
        opco_dsra_gap = max(opco_dsra_target - opco_dsra_bal, 0)
        opco_dsra_fill = min(remaining, opco_dsra_gap)
        opco_dsra_release = max(opco_dsra_bal - opco_dsra_target, 0) if opco_dsra_bal > opco_dsra_target else 0
        opco_dsra_bal += opco_dsra_fill - opco_dsra_release
        remaining -= opco_dsra_fill
        remaining += opco_dsra_release

        # Step 3: LanRED overdraft lending (NWL only)
        if entity_key == "nwl" and lanred_deficit_vector is not None:
            lanred_deficit = abs(lanred_deficit_vector[hi]) if hi < len(lanred_deficit_vector) else 0
            if lanred_deficit > 0 and remaining > 0:
                od_lent = min(remaining, lanred_deficit)
                od_interest_on_existing = od_bal_entity * od_rate
                od_bal_entity += od_lent + od_interest_on_existing
                od_interest = od_interest_on_existing
                remaining -= od_lent

        if entity_key == "lanred":
            od_received = 0.0
            od_interest = od_bal_entity * od_rate
            od_bal_entity += od_interest

        # Step 4: Mezz Dividend FD fill
        if mz_div_applies and not mz_div_payout and mz_div_accrual > 0 and remaining > 0:
            fd_fill_gap = max(mz_div_liability_bal - mz_div_fd_bal, 0)
            mz_div_fd_fill_val = min(remaining, fd_fill_gap)
            mz_div_fd_bal += mz_div_fd_fill_val
            remaining -= mz_div_fd_fill_val

        # Surplus acceleration — GATED on DSRA funding level
        # Grant-funded Sr accel (special pool above) is NOT gated.
        # This block handles: Mezz, OD, ZAR swap leg, Sr — ranked by rate
        # descending (Mezz 20% > OD 10% > ZAR swap 9.69% > Sr 5.20%).
        dsra_funded = (opco_dsra_bal >= opco_dsra_target - 0.01) or opco_dsra_target < 0.01
        if dsra_funded and remaining > 0:
            accel_targets = []
            if mz_ic_bal > 0.01:
                accel_targets.append(("mz", accel_rate_mz, mz_ic_bal))
            if od_bal_entity > 0.01:
                accel_targets.append(("od", cfg.od_rate, od_bal_entity))
            if swap_leg_bal > 0.01:
                accel_targets.append(("swap", accel_rate_swap, swap_leg_bal))
            if sr_ic_bal > 0.01:
                accel_targets.append(("sr", accel_rate_sr, sr_ic_bal))
            accel_targets.sort(key=lambda t: t[1], reverse=True)

            for akey, arate, abal in accel_targets:
                if remaining <= 0:
                    break
                apay = min(remaining * sweep_pct, abal)
                if akey == "mz":
                    mz_accel_entity = apay
                    mz_ic_bal -= apay
                elif akey == "od":
                    od_accel = apay
                    od_bal_entity -= apay
                elif akey == "swap":
                    swap_leg_accel = apay
                    swap_leg_bal -= apay
                elif akey == "sr":
                    sr_accel_entity += apay
                    sr_ic_bal -= apay
                remaining -= apay

        # Overdraft repayment (LanRED only)
        if entity_key == "lanred" and od_bal_entity > 0.01 and remaining > 0:
            od_repaid = min(remaining, od_bal_entity)
            od_bal_entity -= od_repaid
            remaining -= od_repaid

        # Entity FD: after ALL debt = 0
        entity_fd_interest = entity_fd_bal * fd_interest_rate
        entity_fd_bal += entity_fd_interest
        entity_fd_fill = 0.0
        all_debt_zero = (mz_ic_bal <= 0.01 and sr_ic_bal <= 0.01
                         and od_bal_entity <= 0.01 and swap_leg_bal <= 0.01)
        if all_debt_zero and remaining > 0:
            entity_fd_fill = remaining
            entity_fd_bal += entity_fd_fill
            remaining -= entity_fd_fill

        # Dividends: extract cash from entity FD (exits the entity)
        div_cfg = cfg.waterfall.get("dividends", {})
        dividend_paid = 0.0
        if (div_cfg.get("enabled", False)
                and hi >= div_cfg.get("start_period", 10)
                and entity_fd_bal > 0.01):
            div_pct = div_cfg.get("pct", 0.0)
            div_eligible = True
            if div_cfg.get("all_debt_must_be_zero", True) and not all_debt_zero:
                div_eligible = False
            if div_eligible and div_pct > 0:
                dividend_paid = entity_fd_bal * div_pct
                entity_fd_bal -= dividend_paid
                cum_dividends += dividend_paid

        free_surplus = remaining

        rows.append({
            "ebitda": ebitda, "tax": tax, "ds_cash": ds_cash,
            "sr_pi": sr_pi, "mz_pi": mz_pi,
            "mz_prin_sched": mz_prin_sched, "sr_prin_sched": sr_prin_sched,
            "swap_leg_scheduled": swap_leg_scheduled,
            "mz_accel_entity": mz_accel_entity,
            "sr_accel_entity": sr_accel_entity,
            "swap_leg_accel": swap_leg_accel,
            "ie_half_sr": ie_half_sr, "ie_half_mz": ie_half_mz,
            "ie_year": ie_half, "pbt": pbt,
            "surplus": max(cash_available - ds_cash, 0),
            "deficit": deficit,
            "dtic_grant": dtic_grant,
            "iic_grant": iic_grant,
            "gepf_bulk": gepf_bulk,
            "specials": special_cash,
            "pre_rev_hedge": pre_rev_hedge,
            "mezz_draw": mezz_draw,
            "eur_leg_repayment": eur_leg,
            "cash_available": cash_available,
            "mz_ic_bal": mz_vectors["closing_bal"][hi],
            "sr_ic_bal": sr_vectors["closing_bal"][hi],
            "swap_leg_bal": swap_leg_bal,
            "ops_reserve_interest": ops_reserve_interest,
            "ops_reserve_fill": ops_reserve_fill,
            "ops_reserve_bal": ops_reserve_bal,
            "ops_reserve_target": ops_reserve_target,
            "opco_dsra_interest": opco_dsra_interest,
            "opco_dsra_fill": opco_dsra_fill,
            "opco_dsra_release": opco_dsra_release,
            "opco_dsra_bal": opco_dsra_bal,
            "opco_dsra_target": opco_dsra_target,
            "od_lent": od_lent,
            "od_received": od_received,
            "od_repaid": od_repaid,
            "od_accel": od_accel,
            "od_interest": od_interest,
            "od_bal": od_bal_entity,
            "entity_fd_interest": entity_fd_interest,
            "entity_fd_fill": entity_fd_fill,
            "entity_fd_bal": entity_fd_bal,
            "dividend_paid": dividend_paid,
            "cum_dividends": cum_dividends,
            "free_surplus": free_surplus,
            "mz_div_opening_basis": mz_opening_for_div_accrual,
            "mz_div_accrual": mz_div_accrual,
            "mz_div_liability_bal": mz_div_liability_bal,
            "mz_div_fd_interest": mz_div_fd_interest,
            "mz_div_fd_fill": mz_div_fd_fill_val,
            "mz_div_fd_bal": mz_div_fd_bal,
            "mz_div_payout": mz_div_payout,
            "mz_div_payout_amount": mz_div_payout_amount,
        })

    # ── Post-loop: INDEX swap_leg_bal from swap schedule ──
    # The waterfall used a running accumulator during allocation, but the
    # OUTPUT balances must come from the indexed schedule (FLOW.md canon).
    if swap_vectors is not None:
        swap_accel_vector = [r.get("swap_leg_accel", 0.0) for r in rows]
        swap_closing = build_swap_closing_bal(swap_vectors, swap_accel_vector)
        for hi in range(len(rows)):
            rows[hi]["swap_leg_bal"] = swap_closing[hi]

    return rows


def aggregate_to_annual(wf_semi: list[dict]) -> list[dict]:
    """Aggregate 20 semi-annual waterfall dicts into 10 annual dicts.

    Flow fields: sum of H1 + H2.
    Balance fields (closing): take H2 value.
    Opening fields: take H1 value.
    Boolean fields: logical OR.
    """
    annual = []
    for yi in range(total_years()):
        h1 = wf_semi[yi * 2]
        h2 = wf_semi[yi * 2 + 1]
        agg = {}
        for key in h2.keys():
            v1 = h1.get(key, 0)
            v2 = h2.get(key, 0)
            if key in WF_BOOL_KEYS:
                agg[key] = bool(v1) or bool(v2)
            elif key in WF_BALANCE_KEYS:
                agg[key] = v2
            elif key in WF_OPENING_KEYS:
                agg[key] = v1
            else:
                if isinstance(v2, bool):
                    agg[key] = bool(v1) or bool(v2)
                elif isinstance(v2, (int, float)):
                    agg[key] = v1 + v2
                else:
                    agg[key] = v2
        annual.append(agg)
    return annual
