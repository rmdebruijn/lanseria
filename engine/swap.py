"""Cross-currency swap schedules (NWL + LanRED).

Swap notional sizing:
    NWL carries the hedge for the COMBINED SCLCA Senior facility because
    it is the senior asset with best cash flow. The minimum notional is
    2×(P+I) SCLCA loan M24 — the sum of ALL entities' (NWL + TWX + LanRED)
    first Senior IC P+I at M24, doubled to cover 12 months pre-revenue.
    The maximum is the local content ceiling.

    The min is computed deterministically by borrowing the construction-phase
    formula from FacilityState (drawdowns × pro_rata, IDC compounding,
    grant reduction at C3) but at the IIC FACILITY rate (4.70%), NOT the
    IC rate (5.20%). No acceleration is applied — this is a vanilla
    forward calculation to M24. The swap module runs this independently;
    it does not read from FacilityState.

    LanRED (Brownfield only) has a separate swap sized to its full
    senior_portion — 100% local content, no min/max slider.
    TWX has no swap.

Internal calculations use EUR/ZAR typed amounts.
Dict output uses .value for serialisation compatibility.
"""

from __future__ import annotations

from engine.config import ModelConfig
from engine.currency import EUR, ZAR
from engine.periods import (
    repayment_start_month, total_periods, period_start_month,
    construction_period_labels,
)


# ── Swap notional bounds (NWL only) ─────────────────────────────


def compute_nwl_swap_bounds(cfg: ModelConfig) -> dict:
    """Deterministic NWL swap notional bounds: min and max.

    NWL is the senior asset with best cash flow and carries the hedge
    for the entire SCLCA Senior facility (all entities combined).

    Min = 2×(P+I) SCLCA loan M24:
        Borrows the construction-phase formula from FacilityState
        (drawdowns × pro_rata + IDC compounding - grants at C3) but runs
        it at the IIC FACILITY rate (4.70%), not the IC rate (5.20%).
        Sums P+I at M24 across NWL + LanRED + TWX. No waterfall
        acceleration — pure forward calculation from inputs.

    Max = local content ceiling (NWL Civil + WSP) from waterfall config.

    Preferred = configurable default within [min, max]. Falls back to min
        if not set in config. The UI slider sits between min and max.

    Both min and max are deterministic from config alone — no loop output
    needed, no chicken-and-egg. The swap notional is known at M0.

    Returns:
        dict with keys: min, max, per_entity (breakdown), preferred,
        sum_pi_m24, facility_rate, repayments
    """
    sr_detail = cfg.financing["loan_detail"]["senior"]
    drawdown_schedule = sr_detail["drawdown_schedule"]
    construction_periods = construction_period_labels()
    facility_rate = cfg.sr_facility_rate           # 4.70% (IIC rate)
    repayments = cfg.sr_repayments                 # 14
    total_sr = cfg.total_senior()

    # Grant acceleration at C3 (period 2) — facility level
    grant_accel_raw = sr_detail.get("prepayment_periods", {})  # {"2": 3236004}

    per_entity: dict[str, dict] = {}
    sum_pi = 0.0

    for entity_key, entity_data in cfg.entity_loans().items():
        sr_portion = entity_data["senior_portion"]
        pro_rata = sr_portion / total_sr if total_sr > 0 else 0.0

        # Entity-specific grant allocation
        grant_alloc = sr_detail.get("prepayment_allocation", {})
        entity_grant_pct = grant_alloc.get(entity_key, 0.0)

        # Run construction phase: drawdowns + IDC at facility rate - grants
        balance = 0.0
        for idx, period in enumerate(construction_periods):
            opening = balance
            idc = opening * facility_rate / 2.0
            dd = (
                drawdown_schedule[idx] * pro_rata
                if idx < len(drawdown_schedule) else 0.0
            )
            # Grant acceleration (same formula as FacilityState)
            accel = 0.0
            if grant_accel_raw and str(period) in grant_accel_raw:
                accel = grant_accel_raw[str(period)] * entity_grant_pct
            balance = opening + dd + idc - accel

        # M24 opening balance → P_constant and first interest
        p_constant = balance / repayments if repayments > 0 else 0.0
        interest_m24 = balance * facility_rate / 2.0
        pi_m24 = p_constant + interest_m24

        per_entity[entity_key] = {
            "balance_m24": balance,
            "p_constant": p_constant,
            "interest_m24": interest_m24,
            "pi_m24": pi_m24,
        }
        sum_pi += pi_m24

    swap_min = 2.0 * sum_pi

    # Max: local content ceiling from waterfall config
    swap_cfg = cfg.waterfall.get("nwl_swap", {})
    swap_max = swap_cfg.get("local_content_ceiling_eur", swap_min)

    # Preferred: configurable default within [min, max]
    preferred = swap_cfg.get("preferred_notional_eur", None)
    if preferred is None:
        preferred = swap_min  # default to min
    preferred = max(swap_min, min(swap_max, preferred))

    return {
        "min": swap_min,
        "max": swap_max,
        "preferred": preferred,
        "per_entity": per_entity,
        "sum_pi_m24": sum_pi,
        "facility_rate": facility_rate,
        "repayments": repayments,
    }


def build_nwl_swap_schedule(
    swap_amount_eur: float,
    fx_rate: float,
    cfg: ModelConfig,
    last_sr_month: int = 102,
) -> dict:
    """EUR->ZAR cross-currency swap schedule (NWL).

    EUR leg (asset): bullet delivery at M24. Compounds at IIC rate during grace.
    ZAR leg (liability): P_constant profile (constant principal + declining interest).
    """
    wf_cfg = cfg.waterfall
    swap_cfg = wf_cfg.get("nwl_swap", {})
    zar_rate = swap_cfg.get("zar_rate", 0.0969)
    start_month = swap_cfg.get("zar_leg_start_month", 36)
    eur_rate = cfg.sr_facility_rate  # 4.70%
    tenor = max(1, (last_sr_month - start_month) // 6 + 1)
    eur_notional = EUR(swap_amount_eur)
    zar_initial = eur_notional.to_zar(fx_rate)
    semi_rate_zar = zar_rate / 2.0
    semi_rate_eur = eur_rate / 2.0

    schedule = []

    # IDC phase: ZAR leg compounds from M0 to start_month
    grace_periods = start_month // 6
    zar_bal = zar_initial
    for gi in range(grace_periods):
        month = gi * 6
        opening = zar_bal
        interest = opening * semi_rate_zar
        zar_bal = opening + interest
        schedule.append({
            "period": gi, "month": month,
            "opening": opening.value, "interest": interest.value,
            "principal": 0.0, "payment": 0.0,
            "closing": zar_bal.value, "phase": "idc",
        })

    # EUR leg IDC: compounds from M0 to M24 (bullet delivery)
    eur_grace_periods = repayment_start_month() // 6  # 4
    eur_bal = eur_notional
    for _ in range(eur_grace_periods):
        eur_bal = eur_bal * (1 + semi_rate_eur)
    eur_amount_idc = eur_bal

    # Repayment phase: P_constant on IDC-inflated ZAR balance
    p_constant = zar_bal * (1.0 / tenor)
    for i in range(tenor):
        month = start_month + i * 6
        opening = zar_bal
        interest = opening * semi_rate_zar
        principal = p_constant
        payment = principal + interest
        zar_bal = opening - principal
        schedule.append({
            "period": start_month // 6 + i, "month": month,
            "opening": opening.value, "interest": interest.value,
            "principal": principal.value, "payment": payment.value,
            "closing": max(zar_bal.value, 0), "phase": "repayment",
        })

    return {
        "eur_amount": eur_notional.value,
        "eur_amount_idc": eur_amount_idc.value,
        "eur_rate": eur_rate,
        "zar_amount": zar_initial.value,
        "zar_amount_idc": zar_bal.value + p_constant.value * tenor,
        "zar_rate": zar_rate,
        "p_constant_zar": p_constant.value,
        "tenor": tenor,
        "start_month": start_month,
        "schedule": schedule,
    }


def build_lanred_swap_schedule(
    eur_amount: float,
    fx_rate: float,
    cfg: ModelConfig,
) -> dict:
    """LanRED EUR->ZAR swap schedule (Brownfield+ only).

    EUR leg: follows IC Senior schedule (14 semi-annual from M24).
    ZAR leg: P_constant profile, 28 semi-annual from M24.
    """
    wf_cfg = cfg.waterfall
    swap_cfg = wf_cfg.get("lanred_swap", {})
    zar_rate = swap_cfg.get("zar_rate", 0.0969)
    zar_repayments = swap_cfg.get("zar_leg_repayments", 28)
    start_month = swap_cfg.get("zar_leg_start_month", 24)
    eur_rate = cfg.sr_facility_rate  # 4.70%
    eur_notional = EUR(eur_amount)
    zar_initial = eur_notional.to_zar(fx_rate)
    semi_rate_zar = zar_rate / 2.0
    semi_rate_eur = eur_rate / 2.0

    schedule = []

    # IDC phase: ZAR leg compounds from M0 to start_month
    grace_periods = start_month // 6
    zar_bal = zar_initial
    for gi in range(grace_periods):
        month = gi * 6
        opening = zar_bal
        interest = opening * semi_rate_zar
        zar_bal = opening + interest
        schedule.append({
            "period": gi, "month": month,
            "opening": opening.value, "interest": interest.value,
            "principal": 0.0, "payment": 0.0,
            "closing": zar_bal.value, "phase": "idc",
        })

    # EUR leg IDC: compounds from M0 to M24
    eur_grace_periods = repayment_start_month() // 6
    eur_bal = eur_notional
    for _ in range(eur_grace_periods):
        eur_bal = eur_bal * (1 + semi_rate_eur)
    eur_amount_idc = eur_bal

    # Repayment phase: P_constant on IDC-inflated ZAR balance
    p_constant = zar_bal * (1.0 / zar_repayments)
    for i in range(zar_repayments):
        month = start_month + i * 6
        opening = zar_bal
        interest = opening * semi_rate_zar
        principal = p_constant
        payment = principal + interest
        zar_bal = opening - principal
        schedule.append({
            "period": start_month // 6 + i, "month": month,
            "opening": opening.value, "interest": interest.value,
            "principal": principal.value, "payment": payment.value,
            "closing": max(zar_bal.value, 0), "phase": "repayment",
        })

    return {
        "eur_amount": eur_notional.value,
        "eur_amount_idc": eur_amount_idc.value,
        "eur_rate": eur_rate,
        "zar_amount": zar_initial.value,
        "zar_amount_idc": zar_bal.value + p_constant.value * zar_repayments,
        "zar_rate": zar_rate,
        "p_constant_zar": p_constant.value,
        "tenor": zar_repayments,
        "start_month": start_month,
        "schedule": schedule,
    }


def extract_swap_vectors(
    swap_sched: dict,
    fx_rate: float,
    num_periods: int | None = None,
) -> dict:
    """Pre-build per-half-period vectors for waterfall to READ (not recompute).

    Maps each semi-annual period (by start_month) to the corresponding swap
    schedule row, extracting the EUR-equivalent payment and running balance.

    Swap payments are in ZAR; we convert to EUR at fx_rate for the waterfall.

    Returns:
        dict with keys: scheduled_payment, initial_bal
        scheduled_payment: list[float] of length num_periods (EUR equivalent)
        initial_bal: float — total ZAR payments converted to EUR (opening balance)
    """
    if num_periods is None:
        num_periods = total_periods()

    schedule = swap_sched.get("schedule", [])
    zar_fx = (swap_sched.get("zar_amount", 1)
              / max(swap_sched.get("eur_amount", 1), 1)
              ) if swap_sched.get("eur_amount", 0) > 0 else 1

    # Build lookup: start_month -> total payment (ZAR) for that period
    # A swap schedule row's "month" field corresponds to the start_month of
    # the semi-annual period it falls in.
    payment_by_month: dict[int, float] = {}
    for r in schedule:
        m = r["month"]
        payment_by_month[m] = payment_by_month.get(m, 0.0) + r["payment"]

    # Initial balance: sum of all ZAR payments (P+I) converted to EUR.
    # This is the total EUR-equivalent obligation that gets paid down over time.
    # Each scheduled payment (P+I in ZAR/FX) reduces this balance.
    zar_total_payments = sum(r["payment"] for r in schedule)
    initial_bal = zar_total_payments / zar_fx if zar_fx > 0 else 0.0

    # Build per-period vector
    scheduled_payment: list[float] = []
    for hi in range(num_periods):
        hm = period_start_month(hi)
        zar_due = payment_by_month.get(hm, 0.0)
        eur_equiv = zar_due / zar_fx if zar_fx > 0 else 0.0
        scheduled_payment.append(eur_equiv)

    return {
        "scheduled_payment": scheduled_payment,
        "initial_bal": initial_bal,
    }


def build_swap_closing_bal(
    swap_vectors: dict,
    acceleration: list[float],
    num_periods: int | None = None,
) -> list[float]:
    """Pre-compute per-period closing balances for the ZAR swap leg.

    Given the swap vectors (from extract_swap_vectors) and per-period
    acceleration amounts (from waterfall output), compute the closing
    balance at each semi-annual period.

    This allows the waterfall output to INDEX the swap closing balance
    rather than relying on its internal running accumulator.

    Args:
        swap_vectors: Output of extract_swap_vectors (has initial_bal,
            scheduled_payment).
        acceleration: Per-period acceleration amounts from waterfall
            (swap_leg_accel). Length must be >= num_periods.
        num_periods: Number of periods (default: total_periods()).

    Returns:
        list[float] of length num_periods -- closing balance per period.
    """
    if num_periods is None:
        num_periods = total_periods()

    bal = swap_vectors["initial_bal"]
    closing: list[float] = []

    for hi in range(num_periods):
        sched = swap_vectors["scheduled_payment"][hi] if hi < len(swap_vectors["scheduled_payment"]) else 0.0
        accel = acceleration[hi] if hi < len(acceleration) else 0.0

        # Scheduled payment reduces balance (capped at remaining balance)
        paid = min(sched, bal) if bal > 0.01 else 0.0
        bal -= paid

        # Acceleration further reduces balance
        accel_applied = min(accel, bal) if bal > 0.01 else 0.0
        bal -= accel_applied

        closing.append(max(bal, 0.0))

    return closing
