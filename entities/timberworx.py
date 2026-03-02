"""Timberworx entity module — operating model + full entity orchestration.

Three revenue streams:
1. CoE lease (capital-recovery × occupancy ramp, stops from Y4 when CoE sold to LLC)
2. SETA-accredited training programs (also stops from Y4)
3. Timber sales (continues permanently; labor-only cost model)

CoE sale to LLC at Y4 with 10% premium (one-time revenue).
O&M: R180k fixed + 5% variable of revenue (stops from Y4).

build_twx_operating_model(cfg, inputs) -> list[dict]
build_twx_entity(cfg, inputs)          -> EntityResult
"""

from __future__ import annotations

from engine.config import ModelConfig, ScenarioInputs
from engine.types import EntityResult
from engine.currency import ZAR
from engine.facility import build_entity_schedule, build_schedule, extract_facility_vectors
from engine.loop import run_entity_loop, build_annual, to_annual, _WATERFALL_STOCK_KEYS
from engine.pnl import build_semi_annual_pnl, extract_tax_vector
from engine.waterfall import compute_entity_waterfall
from engine.periods import (
    total_periods, total_years, annual_month_range,
    construction_period_labels, construction_end_index, repayment_start_month,
    semi_index_to_facility_period,
)


# ── CoE rent helper (local copy) ─────────────────────────────────────────────

def _compute_coe_rent_monthly_eur(cfg: ModelConfig, om_overhead_pct: float = 2.0):
    """Compute CoE monthly rent (EUR) using capital-recovery method.

    Returns (monthly_rent_eur, annual_rent_eur, wacc, coe_capex).
    """
    sr_rate = cfg.sr_facility_rate
    mz_rate = cfg.mz_facility_rate
    wacc = 0.85 * sr_rate + 0.15 * mz_rate
    total_yield = wacc + (om_overhead_pct / 100.0)
    coe_items = cfg.assets["assets"].get("coe", {}).get("line_items", [])
    coe_capex = float(coe_items[0].get("budget", 0)) if coe_items else 0.0
    annual_rent = coe_capex * total_yield
    return annual_rent / 12.0, annual_rent, wacc, coe_capex


# ── Public API ───────────────────────────────────────────────────────────────

def build_twx_operating_model(cfg: ModelConfig, inputs: ScenarioInputs) -> list[dict]:
    """Build Timberworx 10-year annual operating model in EUR.

    Revenue streams:
    1. CoE lease  — capital-recovery method with occupancy ramp
    2. Training   — fee + SETA subsidy per student, throughput ramp
    3. Timber     — units × price (escalated), labor-only cost
    Costs: fixed O&M + variable % of revenue (stops from CoE sale year).

    Returns list of 10 annual dicts.
    """
    twx_cfg = cfg.operations.get("timberworx", {})
    lease_cfg = twx_cfg.get("coe_lease", {})
    training_cfg = twx_cfg.get("training_programs", {})
    sales_cfg = twx_cfg.get("timber_sales", {})
    om_cfg = twx_cfg.get("om", {})

    # CoE sale to LLC
    coe_sale_cfg = twx_cfg.get("coe_sale_to_llc", {})
    coe_sale_enabled = coe_sale_cfg.get("enabled", False)
    coe_sale_year = int(coe_sale_cfg.get("sale_year", 4))
    coe_sale_premium_pct = float(coe_sale_cfg.get("premium_pct", 10.0)) / 100.0

    # CoE lease parameters
    om_pct = float(lease_cfg.get("om_overhead_pct", 2.0))
    monthly_rent_eur, _annual_rent, _wacc, _capex = _compute_coe_rent_monthly_eur(cfg, om_pct)
    monthly_rental_zar = monthly_rent_eur * cfg.fx_rate
    lease_escalation = float(lease_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    lease_start_month = int(lease_cfg.get("start_month", 24))
    occupancy_ramp = lease_cfg.get(
        "occupancy_ramp", [0.30, 0.50, 0.65, 0.75, 0.80, 0.85, 0.90, 0.90, 0.95, 0.95]
    )

    # Training parameters
    training_fee_zar = float(training_cfg.get("fee_per_student_zar", 15000))
    seta_subsidy_zar = float(training_cfg.get("seta_subsidy_per_student_zar", 8000))
    training_throughput = training_cfg.get(
        "throughput_students_per_year", [12, 24, 36, 45, 50, 55, 60, 60, 65, 65]
    )
    training_escalation = float(training_cfg.get("annual_escalation_pct", 7.0)) / 100.0
    training_start_month = int(training_cfg.get("start_month", 18))

    # Timber sales parameters
    sales_enabled = sales_cfg.get("enabled", True)
    units_per_year = sales_cfg.get("units_per_year", [0, 50, 120, 200, 280, 350, 420, 500, 580, 650])
    price_per_unit_zar = float(sales_cfg.get("price_per_unit_zar", 100000))
    sales_escalation = float(sales_cfg.get("annual_price_escalation_pct", 5.0)) / 100.0
    sales_start_month = int(sales_cfg.get("start_month", 36))
    # Labor: R130k/month Phase 1 basis (52 houses/year = ~1/week) → R30k/house
    _labor_monthly_p1 = float(sales_cfg.get("labor_monthly_phase1_zar", 130000))
    _p1_houses_per_month = 52.0 / 12.0
    labor_per_house_zar = _labor_monthly_p1 / _p1_houses_per_month
    labor_escalation = float(sales_cfg.get("labor_escalation_pct", 5.0)) / 100.0

    # O&M parameters
    om_fixed_annual_zar = float(om_cfg.get("fixed_annual_zar", 180000))
    om_variable_pct = float(om_cfg.get("variable_pct_of_revenue", 5.0)) / 100.0
    om_indexation = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start_month = int(om_cfg.get("opex_start_month", 24))

    fx = cfg.fx_rate
    annual_rows = []

    for yi in range(total_years()):
        year = yi + 1
        y_start, y_end = annual_month_range(yi)  # 0-based: (0,12), (12,24), ...

        # CoE status: sold from coe_sale_year onwards (inclusive)
        coe_sold = coe_sale_enabled and year > coe_sale_year
        coe_sale_this_year = coe_sale_enabled and year == coe_sale_year
        coe_gone = coe_sold or coe_sale_this_year  # True from Y4 onwards

        # 1. CoE Lease Revenue (stops from sale year)
        if y_end > lease_start_month and not coe_gone:
            years_from_lease_start = max((y_start - lease_start_month) / 12.0, 0.0)
            lease_rate_indexed = monthly_rental_zar * ((1.0 + lease_escalation) ** years_from_lease_start)
            occupancy = occupancy_ramp[yi] if yi < len(occupancy_ramp) else occupancy_ramp[-1]
            months_lease = (y_end - lease_start_month) if y_start <= lease_start_month < y_end else 12
            rev_lease_zar = lease_rate_indexed * months_lease * occupancy
        else:
            rev_lease_zar = 0.0

        # CoE one-time sale proceeds (Y4 only): CoE CapEx × (1 + premium)
        rev_coe_sale_eur = _capex * (1.0 + coe_sale_premium_pct) if coe_sale_this_year else 0.0

        # 2. Training Revenue (needs CoE — stops from sale year)
        if y_end > training_start_month and not coe_gone:
            years_from_training_start = max((y_start - training_start_month) / 12.0, 0.0)
            fee_indexed = training_fee_zar * ((1.0 + training_escalation) ** years_from_training_start)
            subsidy_indexed = seta_subsidy_zar * ((1.0 + training_escalation) ** years_from_training_start)
            students_this_year = (training_throughput[yi]
                                  if yi < len(training_throughput) else training_throughput[-1])
            # Pro-rate for partial year
            if y_start <= training_start_month < y_end:
                months_training = (y_end - training_start_month)
                students_this_year = students_this_year * months_training / 12.0
            rev_training_zar = students_this_year * (fee_indexed + subsidy_indexed)
        else:
            rev_training_zar = 0.0
            students_this_year = 0

        # 3. Timber Sales Revenue (service model: labor-only cost)
        if sales_enabled and y_end > sales_start_month:
            years_from_sales_start = max((y_start - sales_start_month) / 12.0, 0.0)
            unit_price_indexed = price_per_unit_zar * ((1.0 + sales_escalation) ** years_from_sales_start)
            units_this_year = (units_per_year[yi]
                               if yi < len(units_per_year) else units_per_year[-1])
            # Pro-rate for partial year
            if y_start <= sales_start_month < y_end:
                months_sales = (y_end - sales_start_month)
                units_this_year = units_this_year * months_sales / 12.0
            rev_timber_gross_zar = units_this_year * unit_price_indexed
            labor_indexed = labor_per_house_zar * ((1.0 + labor_escalation) ** years_from_sales_start)
            labor_cost_zar = units_this_year * labor_indexed
            rev_timber_net_zar = rev_timber_gross_zar - labor_cost_zar
        else:
            rev_timber_gross_zar = 0.0
            labor_cost_zar = 0.0
            rev_timber_net_zar = 0.0
            units_this_year = 0

        # Operating revenue total (excl. one-time CoE sale)
        rev_total_zar = rev_lease_zar + rev_training_zar + rev_timber_net_zar

        # O&M Costs (CoE facility — stops from sale year)
        if y_end > om_start_month and not coe_gone:
            years_from_om_start = max((y_start - om_start_month) / 12.0, 0.0)
            om_fixed_indexed = om_fixed_annual_zar * ((1.0 + om_indexation) ** years_from_om_start)
            if y_start <= om_start_month < y_end:
                months_om = (y_end - om_start_month)
                om_fixed_indexed = om_fixed_indexed * months_om / 12.0
            om_variable_zar = rev_total_zar * om_variable_pct
            om_total_zar = om_fixed_indexed + om_variable_zar
        else:
            om_total_zar = 0.0

        # Convert to EUR
        rev_lease = ZAR(rev_lease_zar).to_eur(fx).value
        rev_training = ZAR(rev_training_zar).to_eur(fx).value
        rev_timber = ZAR(rev_timber_net_zar).to_eur(fx).value
        rev_operating = ZAR(rev_total_zar).to_eur(fx).value
        rev_total_with_sale = rev_operating + rev_coe_sale_eur
        om_cost = ZAR(om_total_zar).to_eur(fx).value

        # Students display (0 when CoE gone or training not started)
        students_display = (
            int(students_this_year) if y_end > training_start_month and not coe_gone else 0
        )

        annual_rows.append({
            "year": year,
            "rev_lease": rev_lease,
            "rev_training": rev_training,
            "rev_timber_gross": ZAR(rev_timber_gross_zar).to_eur(fx).value,
            "rev_timber_sales": rev_timber,
            "rev_coe_sale": rev_coe_sale_eur,
            "rev_operating": rev_operating,
            "rev_total": rev_total_with_sale,
            "labor_cost": ZAR(labor_cost_zar).to_eur(fx).value,
            "om_cost": om_cost,
            "power_cost": 0.0,
            "rent_cost": 0.0,
            "occupancy_pct": (occupancy_ramp[yi] if yi < len(occupancy_ramp) else occupancy_ramp[-1]) * 100.0,
            "students": students_display,
            "timber_units": units_this_year,
            "coe_sold": coe_gone,
        })

    return annual_rows


def build_twx_entity(cfg: ModelConfig, inputs: ScenarioInputs) -> EntityResult:
    """Full Timberworx entity orchestration.

    Steps:
    1. Build vanilla IC schedules (senior + mezz)
    2. Build annual operating model
    3. Derive depreciable_base from total_loan
    4. Build semi-annual P&L with tax loss carry-forward
    5. No swap for Timberworx
    6. Convergence loop: up to 5 iterations, EUR 100 tolerance
    7. Patch annual from waterfall
    8. Return EntityResult
    """
    entity_key = "timberworx"
    entity_data = cfg.entity_loans()[entity_key]

    # ── 1. Vanilla IC schedules ──
    sr_schedule = build_entity_schedule(entity_key, cfg, debt_type="senior")
    mz_schedule = build_entity_schedule(entity_key, cfg, debt_type="mezz")

    # ── 2. Operating model ──
    ops_annual = build_twx_operating_model(cfg, inputs)
    ops_semi_annual = None  # TWX uses annual/2 fallback

    # ── 3. Depreciable base (total_loan as proxy) ──
    depreciable_base = entity_data.get("total_loan", 0.0)

    # Split depreciation: building (coe_001) -> straight-line 20yr, equipment (coe_002) -> S12C
    coe_items = cfg.assets["assets"].get("coe", {}).get("line_items", [])
    building_budget = 0.0
    equipment_budget = 0.0
    for item in coe_items:
        item_id = item.get("id", "")
        delivery = (item.get("delivery", "") or "").lower()
        if item_id == "coe_001" or "centre" in delivery or "center" in delivery:
            building_budget += float(item.get("budget", 0))
        else:
            equipment_budget += float(item.get("budget", 0))
    total_asset_budget = building_budget + equipment_budget
    if total_asset_budget > 0:
        straight_line_base = depreciable_base * (building_budget / total_asset_budget)
    else:
        straight_line_base = 0.0
    straight_line_life = 20  # S13 real estate: 20-year useful life
    s12c_base = depreciable_base - straight_line_base

    # ── 5. No swap for Timberworx ──
    swap_active = False
    swap_schedule_obj = None

    # ── Pre-revenue hedge total (indexes NWL swap bounds) ──
    # TWX has no swap. The pre_revenue_hedge_total is the NWL-carried
    # combined 2×(P+I) SCLCA loan M24, used only as pass-through.
    from engine.swap import compute_nwl_swap_bounds
    _swap_bounds = compute_nwl_swap_bounds(cfg)
    pre_revenue_hedge_total = _swap_bounds["min"]

    # No cash inflows for TWX (no DTIC/IIC grants)
    cash_inflows = None

    # ── 6. Convergence loop ──
    total_sr = cfg.total_senior()
    total_mz = cfg.total_mezz()
    sr_principal = entity_data["senior_portion"]
    mz_principal = entity_data.get("mezz_portion", 0.0)
    sr_drawdowns = cfg.financing["loan_detail"]["senior"]["drawdown_schedule"]
    mz_amount_eur = cfg.structure["sources"]["mezzanine"]["amount_eur"]
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    construction_periods = construction_period_labels()

    sweep_pct = 1.0

    # ── 6. One Big Loop (single pass, no convergence) ──
    loop_result = run_entity_loop(
        entity_key, cfg,
        ops_annual=ops_annual,
        ops_semi_annual=ops_semi_annual,
        sr_principal=sr_principal,
        total_sr=total_sr,
        sr_repayments=cfg.sr_repayments,
        sr_rate=cfg.sr_ic_rate,
        sr_drawdowns=sr_drawdowns,
        mz_principal=mz_principal,
        total_mz=total_mz,
        mz_repayments=cfg.mz_repayments,
        mz_rate=cfg.mz_ic_rate,
        mz_drawdowns=mz_drawdowns,
        construction_periods=construction_periods,
        depreciable_base=depreciable_base,
        tax_rate=cfg.tax_rate,
        straight_line_base=straight_line_base,
        straight_line_life=straight_line_life,
        cash_inflows=cash_inflows,
        sweep_pct=sweep_pct,
    )
    sr_schedule = loop_result.sr_schedule
    mz_schedule = loop_result.mz_schedule
    waterfall_semi = loop_result.waterfall_semi
    semi_annual_pl = loop_result.semi_annual_pl
    semi_annual_tax = loop_result.semi_annual_tax

    # ── 7. Build annual rows (single pass, single source of truth) ──
    waterfall_annual = to_annual(waterfall_semi, _WATERFALL_STOCK_KEYS)
    entity_equity = cfg.equity_twx
    annual = build_annual(
        loop_result, ops_annual,
        entity_equity=entity_equity,
        depreciable_base=depreciable_base,
        straight_line_base=straight_line_base,
        straight_line_life=straight_line_life,
    )

    # ── 8. Return EntityResult ──
    registry = {"assets": [], "total_depr_base": depreciable_base}

    return EntityResult(
        entity_key=entity_key,
        annual=annual,
        sr_schedule=sr_schedule,
        mz_schedule=mz_schedule,
        waterfall_semi=waterfall_semi,
        waterfall_annual=waterfall_annual,
        semi_annual_pl=semi_annual_pl,
        semi_annual_tax=semi_annual_tax,
        ops_annual=ops_annual,
        ops_semi_annual=ops_semi_annual,
        registry=registry,
        depreciable_base=depreciable_base,
        entity_equity=entity_equity,
        swap_schedule=swap_schedule_obj,
        swap_active=swap_active,
        cash_inflows=cash_inflows,
        pre_revenue_hedge_total=pre_revenue_hedge_total,
    )

