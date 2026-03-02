"""LanRED entity module — operating model + full entity orchestration.

Two operating scenarios:
- Brownfield+: Northlands portfolio (5 sites, contracted tenant PPAs)
- Greenfield:  Solar PV + BESS (4 revenue streams)

build_lanred_operating_model(cfg, inputs) -> list[dict]
build_lanred_entity(cfg, inputs)          -> EntityResult
"""

from __future__ import annotations

from engine.config import ModelConfig, ScenarioInputs
from engine.types import EntityResult, SwapSchedule
from engine.currency import EUR, ZAR
from engine.facility import build_entity_schedule, build_schedule, extract_facility_vectors
from engine.loop import run_entity_loop, build_annual, to_annual, _WATERFALL_STOCK_KEYS
from engine.pnl import build_semi_annual_pnl, extract_tax_vector
from engine.waterfall import compute_entity_waterfall
from engine.swap import build_lanred_swap_schedule, extract_swap_vectors
from engine.periods import (
    total_periods, total_years, annual_month_range,
    construction_period_labels, construction_end_index, repayment_start_month,
    semi_index_to_facility_period,
)


# ── CoE rent helper (local copy — mirrors compute_coe_rent_monthly_eur in app.py) ──

def _compute_coe_rent_monthly_eur(cfg: ModelConfig, om_overhead_pct: float = 2.0):
    """Compute CoE monthly rent (EUR) using capital-recovery method.

    Rent = CoE_building_CapEx × (WACC + O&M overhead) / 12
    WACC = 85% × Senior facility rate + 15% × Mezz facility rate
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


# ── Operating model helpers ──────────────────────────────────────────────────

def _build_lanred_brownfield_model(cfg: ModelConfig) -> list[dict]:
    """Brownfield+ operating model: Northlands portfolio (5 sites).

    Revenue, COGS, insurance, O&M all escalate independently.
    Converts ZAR totals to EUR at cfg.fx_rate.
    """
    bf_cfg = cfg.operations["lanred"]["brownfield_plus"]
    np_cfg = bf_cfg["northlands_portfolio"]
    sites = np_cfg["sites"]

    total_monthly_rev = sum(s["monthly_income_zar"] for s in sites)
    total_monthly_cogs = sum(s["monthly_cogs_zar"] for s in sites)
    total_monthly_ins = sum(s["monthly_insurance_zar"] for s in sites)
    total_monthly_om = sum(s["monthly_om_zar"] for s in sites)
    rev_esc = np_cfg["revenue_escalation_pct"] / 100.0
    cost_esc = np_cfg["cost_escalation_pct"] / 100.0

    fx = cfg.fx_rate
    annual_rows = []
    for yi in range(total_years()):
        year = yi + 1
        rev_zar = total_monthly_rev * 12 * ((1 + rev_esc) ** yi)
        cogs_zar = total_monthly_cogs * 12 * ((1 + cost_esc) ** yi)
        ins_zar = total_monthly_ins * 12 * ((1 + cost_esc) ** yi)
        om_zar = total_monthly_om * 12 * ((1 + cost_esc) ** yi)
        gross_profit_zar = rev_zar - cogs_zar
        net_zar = gross_profit_zar - ins_zar - om_zar

        rev_eur = ZAR(rev_zar).to_eur(fx).value
        om_eur = ZAR(ins_zar + om_zar).to_eur(fx).value
        power_cost_eur = ZAR(cogs_zar).to_eur(fx).value

        annual_rows.append({
            "year": year,
            "rev_power_sales": rev_eur,
            "rev_operating": rev_eur,
            "rev_total": rev_eur,
            "om_cost": om_eur,
            "power_cost": power_cost_eur,
            "rent_cost": 0.0,
            # Brownfield-specific detail (for display)
            "rev_northlands_gross_zar": rev_zar,
            "northlands_cogs_zar": cogs_zar,
            "northlands_gross_profit_zar": gross_profit_zar,
            "northlands_ins_zar": ins_zar,
            "northlands_om_zar": om_zar,
            "northlands_net_zar": net_zar,
            # Zero out greenfield-specific keys for P&L compatibility
            "rev_ic_nwl": 0.0,
            "rev_smart_city": 0.0,
            "rev_open_market": 0.0,
            "rev_bess_arbitrage": 0.0,
            "ic_share_pct": 0.0,
            "sc_share_pct": 0.0,
            "mkt_share_pct": 0.0,
            # Portfolio-level capacity summary
            "installed_mwp": sum(s.get("pv_kwp", 0) for s in sites) / 1000.0,
            "bess_capacity_kwh": sum(s.get("bess_kwh", 0) for s in sites),
            "bess_effective_kwh": 0.0,
            "generation_kwh": 0.0,
            "capacity_factor_pct": 0.0,
            "grid_cost": 0.0,
        })
    return annual_rows


def _build_lanred_greenfield_model(cfg: ModelConfig, inputs: ScenarioInputs) -> list[dict]:
    """Greenfield solar + BESS operating model.

    Four revenue streams:
    1. IC NWL power sales (demand-driven share)
    2. Smart City tenant off-take
    3. Open market sales (residual capacity)
    4. BESS TOU arbitrage

    PV and BESS capacities derived from assets budget + bess_alloc_pct slider.
    """
    lanred_cfg = cfg.operations.get("lanred", {})
    solar_cfg = lanred_cfg.get("solar_capacity", {})
    bess_cfg = lanred_cfg.get("battery_storage", {})
    power_sales_cfg = lanred_cfg.get("power_sales", {})
    om_cfg = lanred_cfg.get("om", {})
    grid_cfg = lanred_cfg.get("grid_connection", {})
    nwl_cfg = cfg.operations.get("nwl", {})

    # ── Derive PV/BESS capacity from asset budget + slider ──
    solar_assets = cfg.assets["assets"].get("solar", {})
    solar_items = solar_assets.get("line_items", [])
    total_solar_budget = solar_assets.get("total", 2908809.0)

    # Default BESS % from assets (items with 'battery'/'bess'/'li-ion' in delivery)
    bess_from_assets = sum(
        li.get("budget", 0) for li in solar_items
        if any(k in li.get("delivery", "").lower() for k in ("bess", "battery", "li-ion"))
    )
    default_bess_pct = round(bess_from_assets / total_solar_budget * 100) if total_solar_budget > 0 else 14

    bess_pct = inputs.lanred_bess_alloc_pct / 100.0
    bess_budget = total_solar_budget * bess_pct
    pv_budget = total_solar_budget - bess_budget

    cost_per_kwp = float(solar_cfg.get("cost_per_kwp_eur", 850))
    installed_kwp = pv_budget / cost_per_kwp if cost_per_kwp > 0 else 0.0
    installed_mwp = installed_kwp / 1000.0

    capacity_factor_base = float(solar_cfg.get("capacity_factor_pct", 21.5)) / 100.0
    solar_degradation_pa = float(solar_cfg.get("degradation_pa_pct", 0.5)) / 100.0
    cod_month = int(solar_cfg.get("cod_month", 18))

    # ── BESS capacity ──
    cost_per_kwh_bess = float(bess_cfg.get("cost_per_kwh_eur", 364))
    bess_capacity_kwh = bess_budget / cost_per_kwh_bess if cost_per_kwh_bess > 0 else 0.0
    bess_usable_pct = float(bess_cfg.get("usable_capacity_pct", 90.0)) / 100.0
    bess_rt_eff = float(bess_cfg.get("roundtrip_efficiency_pct", 85.0)) / 100.0
    bess_degradation_pa = float(bess_cfg.get("degradation_pa_pct", 2.0)) / 100.0

    # ── Stream 1: IC NWL (demand-driven) ──
    ic_nwl_cfg = power_sales_cfg.get("ic_nwl", {})
    eskom_base = float(ic_nwl_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
    ic_discount = float(ic_nwl_cfg.get("ic_discount_pct", 10.0))
    ic_rate = eskom_base * (1.0 - ic_discount / 100.0)
    ic_escalation = float(ic_nwl_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    ic_demand_driven = ic_nwl_cfg.get("demand_driven", False)
    ic_start_month = int(ic_nwl_cfg.get("start_month", 18))

    # NWL power demand from on-ramp schedule
    nwl_power_cfg = nwl_cfg.get("power", {})
    kwh_per_m3 = float(nwl_power_cfg.get("kwh_per_m3", 0.4))
    nwl_on_ramp = nwl_cfg.get("on_ramp", {}).get("rows", [])

    # ── Stream 2: Smart City off-take ──
    sc_cfg = power_sales_cfg.get("smart_city_offtake", {})
    sc_enabled = sc_cfg.get("enabled", False)
    sc_joburg_tariff = float(sc_cfg.get("joburg_business_tariff_r_per_kwh", 2.289))
    sc_discount = float(sc_cfg.get("discount_pct", 10.0))
    sc_rate = sc_joburg_tariff * (1.0 - sc_discount / 100.0)
    sc_escalation = float(sc_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    sc_start_month = int(sc_cfg.get("start_month", 36))
    sc_share_by_year = [s / 100.0 for s in sc_cfg.get(
        "share_of_generation_pct_by_year", [0, 0, 15, 25, 30, 35, 40, 45, 50, 50]
    )]

    # ── Stream 3: Open market (residual) ──
    mkt_cfg = power_sales_cfg.get("open_market", {})
    mkt_enabled = mkt_cfg.get("enabled", False)
    mkt_rate = float(mkt_cfg.get("rate_r_per_kwh", 1.50))
    mkt_escalation = float(mkt_cfg.get("annual_escalation_pct", 8.0)) / 100.0
    mkt_start_month = int(mkt_cfg.get("start_month", 36))

    # ── Stream 4: BESS TOU arbitrage ──
    arb_cfg = power_sales_cfg.get("bess_arbitrage", {})
    arb_enabled = arb_cfg.get("enabled", False)
    arb_escalation = float(arb_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    arb_start_month = int(arb_cfg.get("start_month", 18))
    arb_solar_cost = float(arb_cfg.get("solar_charge_cost_r_per_kwh", 0.10))

    hd_cfg = arb_cfg.get("high_demand_season", {})
    ld_cfg = arb_cfg.get("low_demand_season", {})
    if "high_demand_season" in arb_cfg:
        hd_peak_rate = float(hd_cfg.get("peak_rate_r_per_kwh", 7.04))
        hd_offpeak_rate = float(hd_cfg.get("offpeak_rate_r_per_kwh", 1.02))
        hd_months = int(hd_cfg.get("months", 3))
        ld_peak_rate = float(ld_cfg.get("peak_rate_r_per_kwh", 2.00))
        ld_offpeak_rate = float(ld_cfg.get("offpeak_rate_r_per_kwh", 1.59))
        ld_months = int(ld_cfg.get("months", 9))
    else:
        hd_peak_rate = float(arb_cfg.get("peak_rate_r_per_kwh", 7.04))
        hd_offpeak_rate = float(arb_cfg.get("offpeak_rate_r_per_kwh", 1.02))
        hd_months = 3
        ld_peak_rate = hd_peak_rate
        ld_offpeak_rate = hd_offpeak_rate
        ld_months = 9

    # ── O&M costs ──
    om_fixed_annual_zar = float(om_cfg.get("fixed_annual_zar", 120000))
    om_variable_r_kwh = float(om_cfg.get("variable_r_per_kwh", 0.05))
    om_indexation = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start_month = int(om_cfg.get("opex_start_month", 18))

    # ── Grid connection costs ──
    grid_monthly_zar = float(grid_cfg.get("monthly_availability_charge_zar", 5000))
    grid_escalation = float(grid_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    grid_start_month = int(grid_cfg.get("start_month", 18))

    fx = cfg.fx_rate
    annual_rows = []

    for yi in range(total_years()):
        year = yi + 1
        y_start, y_end = annual_month_range(yi)  # 0-based: (0,12), (12,24), ...

        # Solar generation with degradation
        years_since_cod = max((y_start - cod_month) / 12.0, 0.0)
        capacity_factor_adj = capacity_factor_base * ((1.0 - solar_degradation_pa) ** years_since_cod)

        if y_start <= cod_month < y_end:
            hours_operating = (y_end - cod_month) * 30.44 * 24
        elif y_end <= cod_month:
            hours_operating = 0.0
        else:
            hours_operating = 365.25 * 24

        annual_generation_kwh = installed_mwp * 1000.0 * capacity_factor_adj * hours_operating
        years_from_cod = max((y_start - cod_month) / 12.0, 0.0)

        # Stream 1: IC NWL
        if ic_demand_driven and annual_generation_kwh > 0:
            _nwl_mld = 0.0
            for _row in nwl_on_ramp:
                if _row.get("period_months", 0) < y_end:
                    _cap = _row.get("capacity_available_mld")
                    if _cap is not None:
                        _nwl_mld = _cap
            _nwl_annual_kwh = _nwl_mld * 1000.0 * kwh_per_m3 * 365.25
            ic_share = min(_nwl_annual_kwh / annual_generation_kwh, 1.0)
        else:
            ic_share = 0.0

        if y_end > ic_start_month and annual_generation_kwh > 0:
            ic_rate_indexed = ic_rate * ((1.0 + ic_escalation) ** years_from_cod)
            ic_kwh = annual_generation_kwh * ic_share
            rev_ic_nwl_zar = ic_kwh * ic_rate_indexed
        else:
            ic_share = 0.0
            rev_ic_nwl_zar = 0.0

        # Stream 2: Smart City off-take
        if sc_enabled and y_end > sc_start_month:
            sc_share = sc_share_by_year[yi] if yi < len(sc_share_by_year) else sc_share_by_year[-1]
            years_from_sc_start = max((y_start - sc_start_month) / 12.0, 0.0)
            sc_rate_indexed = sc_rate * ((1.0 + sc_escalation) ** years_from_sc_start)
            sc_kwh = annual_generation_kwh * sc_share
            rev_sc_zar = sc_kwh * sc_rate_indexed
        else:
            sc_share = 0.0
            rev_sc_zar = 0.0

        # Stream 3: Open market (residual)
        if mkt_enabled and y_end > mkt_start_month:
            mkt_share = max(1.0 - ic_share - sc_share, 0.0)
            years_from_mkt_start = max((y_start - mkt_start_month) / 12.0, 0.0)
            mkt_rate_indexed = mkt_rate * ((1.0 + mkt_escalation) ** years_from_mkt_start)
            mkt_kwh = annual_generation_kwh * mkt_share
            rev_mkt_zar = mkt_kwh * mkt_rate_indexed
        else:
            mkt_share = 0.0
            rev_mkt_zar = 0.0

        # Stream 4: BESS TOU arbitrage (2-cycle seasonal model)
        if arb_enabled and y_end > arb_start_month:
            _bess_years = max((y_start - cod_month) / 12.0, 0.0)
            _bess_eff_capacity = (bess_capacity_kwh * bess_usable_pct
                                  * ((1.0 - bess_degradation_pa) ** _bess_years))
            _esc = (1.0 + arb_escalation) ** _bess_years
            if y_start <= arb_start_month < y_end:
                _operating_frac = (y_end - arb_start_month) / 12.0
            else:
                _operating_frac = 1.0

            # High Demand season (hd_months, 2 cycles/day)
            _hd_c1_spread = (hd_peak_rate * _esc * bess_rt_eff) - (hd_offpeak_rate * _esc)
            _hd_c1_days = hd_months * 30.4 * _operating_frac
            _hd_c1_rev = _bess_eff_capacity * max(_hd_c1_spread, 0) * _hd_c1_days
            _hd_c2_spread = (hd_peak_rate * _esc * bess_rt_eff) - (arb_solar_cost * _esc)
            _hd_c2_rev = _bess_eff_capacity * max(_hd_c2_spread, 0) * _hd_c1_days

            # Low Demand season (ld_months, 1 cycle/day solar -> peak)
            _ld_c2_spread = (ld_peak_rate * _esc * bess_rt_eff) - (arb_solar_cost * _esc)
            _ld_c2_days = ld_months * 30.4 * _operating_frac
            _ld_c2_rev = _bess_eff_capacity * max(_ld_c2_spread, 0) * _ld_c2_days

            rev_bess_arb_zar = _hd_c1_rev + _hd_c2_rev + _ld_c2_rev
        else:
            rev_bess_arb_zar = 0.0
            _bess_eff_capacity = 0.0

        # O&M costs
        if y_end > om_start_month:
            years_from_om_start = max((y_start - om_start_month) / 12.0, 0.0)
            om_fixed_indexed = om_fixed_annual_zar * ((1.0 + om_indexation) ** years_from_om_start)
            om_variable_zar = annual_generation_kwh * om_variable_r_kwh
            om_total_zar = om_fixed_indexed + om_variable_zar
        else:
            om_total_zar = 0.0

        # Grid connection costs
        if y_end > grid_start_month:
            years_from_grid_start = max((y_start - grid_start_month) / 12.0, 0.0)
            grid_monthly_indexed = grid_monthly_zar * ((1.0 + grid_escalation) ** years_from_grid_start)
            months_grid = (y_end - grid_start_month) if y_start <= grid_start_month < y_end else 12
            grid_annual_zar = grid_monthly_indexed * months_grid
        else:
            grid_annual_zar = 0.0

        # Convert to EUR
        rev_ic_nwl = ZAR(rev_ic_nwl_zar).to_eur(fx).value
        rev_sc = ZAR(rev_sc_zar).to_eur(fx).value
        rev_mkt = ZAR(rev_mkt_zar).to_eur(fx).value
        rev_bess = ZAR(rev_bess_arb_zar).to_eur(fx).value
        rev_total = rev_ic_nwl + rev_sc + rev_mkt + rev_bess
        om_cost = ZAR(om_total_zar).to_eur(fx).value
        grid_cost = ZAR(grid_annual_zar).to_eur(fx).value

        annual_rows.append({
            "year": year,
            "installed_mwp": installed_mwp,
            "bess_capacity_kwh": bess_capacity_kwh,
            "bess_effective_kwh": _bess_eff_capacity,
            "generation_kwh": annual_generation_kwh,
            "capacity_factor_pct": capacity_factor_adj * 100.0,
            "rev_ic_nwl": rev_ic_nwl,
            "rev_smart_city": rev_sc,
            "rev_open_market": rev_mkt,
            "rev_bess_arbitrage": rev_bess,
            "ic_share_pct": ic_share * 100.0,
            "sc_share_pct": sc_share * 100.0,
            "mkt_share_pct": mkt_share * 100.0,
            "rev_power_sales": rev_total,
            "rev_operating": rev_total,
            "rev_total": rev_total,
            "om_cost": om_cost + grid_cost,
            "grid_cost": grid_cost,
            "power_cost": 0.0,
            "rent_cost": 0.0,
        })

    return annual_rows


# ── Public API ───────────────────────────────────────────────────────────────

def build_lanred_operating_model(cfg: ModelConfig, inputs: ScenarioInputs) -> list[dict]:
    """Build LanRED 10-year annual operating model.

    Routes to Brownfield+ or Greenfield model based on inputs.lanred_scenario.
    Returns list of 10 annual dicts compatible with engine.pnl / engine.waterfall.
    """
    if inputs.lanred_scenario == "Brownfield+":
        return _build_lanred_brownfield_model(cfg)
    return _build_lanred_greenfield_model(cfg, inputs)


def build_lanred_entity(cfg: ModelConfig, inputs: ScenarioInputs) -> EntityResult:
    """Full LanRED entity orchestration.

    Steps:
    1. Build vanilla IC schedules (senior + mezz)
    2. Build annual operating model
    3. Derive depreciable_base from total_loan
    4. Build semi-annual P&L with tax loss carry-forward
    5. Build swap schedule (Brownfield+ only, if enabled)
    6. Convergence loop: up to 5 iterations, EUR 100 tolerance
    7. Patch annual from waterfall
    8. Return EntityResult
    """
    entity_key = "lanred"
    entity_data = cfg.entity_loans()[entity_key]

    # ── 1. Vanilla IC schedules ──
    sr_schedule = build_entity_schedule(entity_key, cfg, debt_type="senior")
    mz_schedule = build_entity_schedule(entity_key, cfg, debt_type="mezz")

    # ── 2. Operating model ──
    ops_annual = build_lanred_operating_model(cfg, inputs)
    ops_semi_annual = None  # LanRED uses annual/2 fallback (no semi-annual ops model)

    # ── 3. Depreciable base (total_loan as proxy) ──
    depreciable_base = entity_data.get("total_loan", 0.0)

    # ── 5. Swap schedule (Brownfield+ only) ──
    swap_active = inputs.lanred_swap_enabled
    swap_schedule_obj: SwapSchedule | None = None
    swap_sched_dict: dict | None = None

    if swap_active and inputs.lanred_scenario != "Greenfield":
        eur_notional = entity_data.get("senior_portion", 0.0)
        swap_sched_dict = build_lanred_swap_schedule(eur_notional, cfg.fx_rate, cfg)
        swap_schedule_obj = SwapSchedule(
            eur_amount=swap_sched_dict["eur_amount"],
            zar_amount=swap_sched_dict["zar_amount"],
            eur_rate=swap_sched_dict["eur_rate"],
            zar_rate=swap_sched_dict["zar_rate"],
            eur_amount_idc=swap_sched_dict["eur_amount_idc"],
            tenor=swap_sched_dict.get("tenor", 0),
            start_month=swap_sched_dict.get("start_month", 0),
            p_constant_zar=swap_sched_dict.get("p_constant_zar", 0.0),
            zar_amount_idc=swap_sched_dict.get("zar_amount_idc", 0.0),
            schedule=swap_sched_dict["schedule"],
        )

    # ── Pre-revenue hedge total (indexes NWL swap bounds) ──
    # LanRED itself has no min/max hedge — its swap is sized to full
    # senior_portion (100% local content for Brownfield). But the
    # pre_revenue_hedge_total is the NWL-carried combined value, used
    # only for cash_inflows pass-through if needed.
    from engine.swap import compute_nwl_swap_bounds
    _swap_bounds = compute_nwl_swap_bounds(cfg)
    pre_revenue_hedge_total = _swap_bounds["min"]

    # LanRED has no grants; cash_inflows is None (no special DTIC/IIC events)
    cash_inflows = None

    # ── 6. Convergence loop ──
    entity_sr_data = cfg.entity_loans()[entity_key]
    total_sr = cfg.total_senior()
    total_mz = cfg.total_mezz()
    sr_principal = entity_sr_data["senior_portion"]
    mz_principal = entity_sr_data.get("mezz_portion", 0.0)
    sr_drawdowns = cfg.financing["loan_detail"]["senior"]["drawdown_schedule"]
    mz_amount_eur = cfg.structure["sources"]["mezzanine"]["amount_eur"]
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    construction_periods = construction_period_labels()

    sweep_pct = 1.0  # LanRED: full sweep (no slider in entity module)

    # IC overdraft received from NWL (set by orchestrator IC plugin)
    od_received_vector = getattr(inputs, "_nwl_od_lent_vector", None)

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
        cash_inflows=cash_inflows,
        sweep_pct=sweep_pct,
        swap_sched=swap_sched_dict if swap_active else None,
        fx_rate=cfg.fx_rate,
        od_received_vector=od_received_vector,
    )
    sr_schedule = loop_result.sr_schedule
    mz_schedule = loop_result.mz_schedule
    waterfall_semi = loop_result.waterfall_semi
    semi_annual_pl = loop_result.semi_annual_pl
    semi_annual_tax = loop_result.semi_annual_tax

    # ── 7. Build annual rows (single pass, single source of truth) ──
    waterfall_annual = to_annual(waterfall_semi, _WATERFALL_STOCK_KEYS)
    entity_equity = cfg.equity_lanred
    annual = build_annual(
        loop_result, ops_annual,
        entity_equity=entity_equity,
        depreciable_base=depreciable_base,
        swap_sched=swap_sched_dict,
        swap_active=swap_active,
        fx_rate=cfg.fx_rate,
    )

    # ── 8. Return EntityResult ──
    # Build minimal registry
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

