#!/usr/bin/env python3
"""Check BS gap for all subsidiaries — standalone, no Streamlit."""
import json, math
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"

def load_config(name):
    with open(CONFIG_DIR / f"{name}.json") as f:
        return json.load(f)

# Load all configs
proj_cfg = load_config("project")
params = proj_cfg.get('model_parameters', {})
fx = proj_cfg['project']['fx_rates']['EUR_ZAR']
eq_cfg = params.get('equity_in_subsidiaries', {})

INTERCOMPANY_MARGIN = params.get('intercompany_margin', 0.005)
DSRA_RATE = params.get('dsra_rate', 0.09)
FX_RATE = fx
EQUITY_NWL = eq_cfg.get('nwl_pct', 0.93) * eq_cfg.get('nwl_base_zar', 1000000) / fx
EQUITY_LANRED = eq_cfg.get('lanred_pct', 1.0) * eq_cfg.get('lanred_base_zar', 1000000) / fx
EQUITY_TWX = eq_cfg.get('timberworx_pct', 0.05) * eq_cfg.get('timberworx_base_zar', 1000000) / fx

structure = load_config("structure")
financing = load_config("financing")
operations_config = load_config("operations")

# === Helpers (copied from app.py) ===

def _state_float(key, default):
    return float(default)

def _asset_life_years(delivery, category):
    d = (delivery or "").lower()
    if "solar" in d:
        return 25
    if "battery" in d or "bess" in d or "li-ion" in d:
        return 10
    if "panel" in d:
        return 10
    if "mabr" in d:
        return 10
    if "coe" in d or "centre" in d or "center" in d or category == "coe":
        return 9
    return 9

def _month_to_year_idx(month):
    if month < 1: return None
    idx = math.ceil(month / 12) - 1
    return idx if 0 <= idx < 10 else None

def _extrapolate_piecewise_linear(base_months, base_values, target_months, floor=None):
    result = []
    for t in target_months:
        if t <= base_months[0]:
            val = base_values[0]
        elif t >= base_months[-1]:
            val = base_values[-1]
        else:
            for i in range(len(base_months) - 1):
                if base_months[i] <= t <= base_months[i+1]:
                    span = base_months[i+1] - base_months[i]
                    frac = (t - base_months[i]) / span if span else 0
                    val = base_values[i] + frac * (base_values[i+1] - base_values[i])
                    break
        if floor is not None:
            val = max(val, floor)
        result.append(val)
    return result

def compute_coe_rent_monthly_eur(om_overhead_pct=2.0):
    assets_cfg = load_config("assets")["assets"]
    coe_items = assets_cfg.get("coe", {}).get("line_items", [])
    coe_building = 0.0
    for item in coe_items:
        d = (item.get("delivery","") or "").lower()
        if "centre" in d or "center" in d or "coe" in d:
            coe_building = float(item.get("budget", 0))
            break
    if coe_building <= 0:
        coe_building = sum(float(i.get("budget",0)) for i in coe_items)
    sr_rate = structure['sources']['senior_debt']['interest']['rate']
    mz_rate = structure['sources']['mezzanine']['interest']['total_rate']
    wacc = 0.85 * sr_rate + 0.15 * mz_rate
    total_yield = wacc + om_overhead_pct / 100.0
    annual_rent = coe_building * total_yield
    monthly_rent = annual_rent / 12.0
    return monthly_rent, annual_rent, wacc, total_yield

def build_simple_ic_schedule(principal, total_principal, repayments, rate,
                             drawdown_schedule, periods, prepayments=None,
                             dsra_amount=0.0, dsra_drawdown=0.0):
    rows, balance = [], 0.0
    pro_rata = principal / total_principal if total_principal else 0
    for idx, period in enumerate(periods):
        month = (period + 4) * 6
        opening = balance
        idc = opening * rate / 2
        draw_down = drawdown_schedule[idx] * pro_rata if idx < len(drawdown_schedule) else 0
        prepay = prepayments.get(str(period), 0) if prepayments else 0
        movement = draw_down + idc - prepay
        balance = opening + movement
        rows.append({"Period": period, "Month": month, "Year": month/12, "Opening": opening,
                      "Draw Down": draw_down, "Interest": idc, "Prepayment": -prepay,
                      "Principle": 0, "Repayment": 0, "Movement": movement, "Closing": balance})

    if dsra_amount > 0:
        dsra_balance_after = balance - dsra_amount
        p_per_after_dsra = dsra_balance_after / (repayments - 2) if repayments > 2 else 0
    elif dsra_drawdown > 0:
        total_after_dsra = balance + dsra_drawdown
        p_per = total_after_dsra / repayments if repayments > 0 else 0
    else:
        p_per = balance / repayments if repayments > 0 else 0

    for i in range(1, repayments + 1):
        month = 18 + (i * 6)
        opening = balance
        interest = opening * rate / 2
        if dsra_amount > 0:
            if i == 1: principle, draw_down = -dsra_amount, 0
            elif i == 2: principle, draw_down = 0, 0
            else: principle, draw_down = -p_per_after_dsra, 0
            movement = principle
        elif dsra_drawdown > 0:
            draw_down = dsra_drawdown if i == 1 else 0
            principle = -p_per
            movement = draw_down + principle
        else:
            draw_down, principle = 0, -p_per
            movement = principle
        balance = opening + movement
        rows.append({"Period": i, "Month": month, "Year": month/12, "Opening": opening,
                      "Draw Down": draw_down, "Interest": interest, "Prepayment": 0,
                      "Principle": principle, "Repayment": principle - interest,
                      "Movement": movement, "Closing": balance})
    return rows

def _build_entity_asset_base(entity_key, assets_cfg):
    entity_map = {"nwl": {"assets": ["water"], "services": ["esg"]},
                  "lanred": {"assets": ["solar"], "services": []},
                  "timberworx": {"assets": ["coe"], "services": []}}
    cfg = entity_map.get(entity_key, {"assets": [], "services": []})
    service_items, asset_items = [], []
    for cat in cfg["assets"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            delivery = item.get("delivery", "")
            if cat == "water" and "owners engineer" in (delivery or "").lower():
                service_items.append({"cost": float(item.get("budget", 0))})
                continue
            asset_items.append({"category": cat, "asset": delivery or "Asset",
                                "base_cost": float(item.get("budget", 0))})
    for cat in cfg["services"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            service_items.append({"cost": float(item.get("budget", 0))})
    service_total = sum(s["cost"] for s in service_items)
    base_total = sum(a["base_cost"] for a in asset_items)
    for a in asset_items:
        share = (a["base_cost"] / base_total) if base_total else 0
        a["alloc_services"] = service_total * share
        a["depr_base"] = a["base_cost"] + a["alloc_services"]
        a["life"] = _asset_life_years(a["asset"], a["category"])
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0
    fee_base = sum(a["depr_base"] for a in asset_items)
    return {"assets": asset_items, "fee_base": fee_base}

def build_asset_registry(entity_key, assets_cfg, fees_cfg, project_fee_rows, project_asset_base, project_debt_base):
    base = _build_entity_asset_base(entity_key, assets_cfg)
    fee_base = base["fee_base"]
    entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
    fee_total = entity_data['fees_allocated']
    for a in base["assets"]:
        a_share = (a["depr_base"] / fee_base) if fee_base else 0
        a["alloc_fees"] = fee_total * a_share
        a["depr_base"] += a["alloc_fees"]
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0
    return base

def compute_project_fees(fees_cfg, project_debt_base, project_capex_base):
    fee_rows = []
    for fee in fees_cfg.get("fees", []):
        basis = fee.get("rate_basis", "")
        base_amount = project_debt_base if basis == "debt" else (project_capex_base if basis == "capex" else 0.0)
        amount = base_amount * fee.get("rate", 0)
        fee_rows.append({**fee, "base_amount": base_amount, "amount": amount})
    return {"fees": fee_rows, "total": sum(f["amount"] for f in fee_rows)}

# === Operating models (copied from app.py, _state_float returns defaults) ===

def _build_nwl_operating_annual_model():
    cfg = operations_config.get("nwl", {})
    on_ramp_cfg = cfg.get("on_ramp", {})
    greenfield_cfg = cfg.get("greenfield", {})
    brownfield_cfg = cfg.get("brownfield", {})
    bulk_cfg = cfg.get("bulk_services", {})
    om_cfg = cfg.get("om", {})
    srv_cfg = cfg.get("sewerage_revenue_sharing", {})
    months_semi = list(range(6, 121, 6))
    month_to_idx = {m: i for i, m in enumerate(months_semi)}
    ramp_rows = on_ramp_cfg.get("rows", [])
    cap_points = [(int(r.get("period_months", 0)), r.get("capacity_available_mld")) for r in ramp_rows]
    cap_points = [(m, float(v)) for m, v in cap_points if v is not None]
    if not any(m == 6 for m, _ in cap_points): cap_points.append((6, 0.0))
    if not any(m == 12 for m, _ in cap_points): cap_points.append((12, 0.0))
    cap_points = sorted(cap_points, key=lambda x: x[0])
    cap_months = [m for m, _ in cap_points]
    cap_vals = [v for _, v in cap_points]
    sewage_capacity = _extrapolate_piecewise_linear(cap_months, cap_vals, months_semi, floor=0.0)
    demand_months = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    piped_sewage_base = [float(x) for x in greenfield_cfg.get("piped_sewage_topcos_mld", [0.0]*10)]
    construction_base = [float(x) for x in greenfield_cfg.get("construction_water_demand_topcos_mld", [0.0]*10)]
    latent_base = [float(x) for x in brownfield_cfg.get("latent_demand_quantified", [0.0]*10)]
    piped_sewage_demand = _extrapolate_piecewise_linear(demand_months, piped_sewage_base, months_semi, floor=0.0)
    construction_demand = _extrapolate_piecewise_linear(demand_months, construction_base, months_semi, floor=0.0)
    latent_demand = _extrapolate_piecewise_linear(demand_months, latent_base, months_semi, floor=0.0)
    annual_growth_pct = greenfield_cfg.get("annual_growth_pct_default", 7.7)
    brine_pct = greenfield_cfg.get("brine_pct_default", 10.0)
    sewage_rate_2025 = greenfield_cfg.get("sewage_rate_2025_r_per_kl", 46.40)
    water_rate_2025 = greenfield_cfg.get("water_rate_2025_r_per_kl", 62.05)
    reuse_ratio = greenfield_cfg.get("reuse_ratio_default", 0.80)
    sewage_sold = [min(cap, dem) for cap, dem in zip(sewage_capacity, piped_sewage_demand)]
    overflow_brownfield = [max(cap - sold, 0.0) for cap, sold in zip(sewage_capacity, sewage_sold)]
    reuse_capacity = [cap * (1.0 - brine_pct / 100.0) for cap in sewage_capacity]
    reuse_topcos_demand = [sold * reuse_ratio for sold in sewage_sold]
    reuse_sold_topcos = [min(cap, dem) for cap, dem in zip(reuse_capacity, reuse_topcos_demand)]
    reuse_after_topcos = [max(cap - sold, 0.0) for cap, sold in zip(reuse_capacity, reuse_sold_topcos)]
    reuse_sold_construction = [min(rem, dem) for rem, dem in zip(reuse_after_topcos, construction_demand)]
    reuse_overflow_agri = [max(cap - s1 - s2, 0.0) for cap, s1, s2 in zip(reuse_capacity, reuse_sold_topcos, reuse_sold_construction)]
    brownfield_served = [min(cap, dem) for cap, dem in zip(overflow_brownfield, latent_demand)]
    growth_factor = 1.0 + (annual_growth_pct / 100.0)
    sewage_rates = [sewage_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    water_rates = [water_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    agri_base = float(brownfield_cfg.get("agri_base_2025_r_per_kl", 37.70))
    agri_rates = [agri_base * (growth_factor ** (m / 12.0)) for m in months_semi]
    srv_joburg_price = srv_cfg.get("joburg_price_r_per_kl_default", 46.40)
    srv_growth_pct = srv_cfg.get("growth_pct_default", 7.70)
    srv_transport_r_km = srv_cfg.get("transport_r_per_km_default", 28.0)
    srv_truck_capacity_m3 = max(srv_cfg.get("truck_capacity_m3_default", 10.0), 1.0)
    srv_nwl_distance_km = srv_cfg.get("nwl_roundtrip_km_default", 10.0)
    srv_gov_distance_km = srv_cfg.get("gov_roundtrip_km_default", 100.0)
    srv_saving_to_market_pct = srv_cfg.get("saving_to_market_pct_default", 40.0)
    srv_processing_fee_truck = srv_joburg_price * srv_truck_capacity_m3
    srv_transport_nwl = srv_transport_r_km * srv_nwl_distance_km
    srv_transport_gov = srv_transport_r_km * srv_gov_distance_km
    srv_saving_per_m3_transport = (srv_transport_gov - srv_transport_nwl) / srv_truck_capacity_m3
    srv_market_price = max(srv_saving_per_m3_transport * (srv_saving_to_market_pct / 100.0), 0.0)
    srv_growth_factor = 1.0 + (srv_growth_pct / 100.0)
    honeysucker_rates = [srv_market_price * (srv_growth_factor ** (m / 12.0)) for m in months_semi]
    half_year_kl_per_mld = 1000.0 * 365.0 / 2.0
    rev_gf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(sewage_sold, sewage_rates)]
    rev_bf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(brownfield_served, honeysucker_rates)]
    rev_gf_reuse_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_topcos, water_rates)]
    rev_construction_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_construction, water_rates)]
    rev_agri_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_overflow_agri, agri_rates)]
    rev_bulk_zar_year = [0.0]*10
    for row in bulk_cfg.get("rows", []):
        amount = float(row.get("price_zar", 0.0))
        receipt_period = max(float(row.get("receipt_period", 12.0)), 0.0)
        if amount <= 0.0: continue
        if receipt_period == 0.0:
            yi = _month_to_year_idx(12)
            if yi is not None: rev_bulk_zar_year[yi] += amount
            continue
        start_m = 13; end_m = start_m + receipt_period
        for mi in range(1, 121):
            if start_m <= mi < end_m:
                yi = _month_to_year_idx(mi)
                if yi is not None: rev_bulk_zar_year[yi] += amount / receipt_period
    om_monthly_fee = float(om_cfg.get("flat_fee_per_month_zar", 0.0))
    om_index_pa = float(om_cfg.get("annual_indexation_pa", 0.0))
    om_start_month = int(om_cfg.get("opex_start_month", 12))
    om_zar_year = [0.0]*10
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < om_start_month: continue
        monthly_cost = om_monthly_fee * ((1.0 + om_index_pa) ** ((mi - om_start_month) / 12.0))
        om_zar_year[yi] += monthly_cost
    power_cfg = cfg.get("power", {})
    power_kwh_per_m3 = float(power_cfg.get("kwh_per_m3", 0.4))
    eskom_base = float(power_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
    ic_discount = float(power_cfg.get("ic_discount_pct", 10.0))
    power_rate = eskom_base * (1.0 - ic_discount / 100.0)
    power_escalation = float(power_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    power_start_month = int(power_cfg.get("start_month", 18))
    power_zar_year = [0.0]*10
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < power_start_month: continue
        cap_mld = 0.0
        for ci in range(len(cap_months) - 1):
            if cap_months[ci] <= mi <= cap_months[ci + 1]:
                frac = (mi - cap_months[ci]) / max(cap_months[ci + 1] - cap_months[ci], 1)
                cap_mld = cap_vals[ci] + frac * (cap_vals[ci + 1] - cap_vals[ci])
                break
        else:
            if mi >= cap_months[-1]: cap_mld = cap_vals[-1]
        volume_m3_per_day = cap_mld * 1000.0
        kwh_per_day = volume_m3_per_day * power_kwh_per_m3
        rate_indexed = power_rate * ((1.0 + power_escalation) ** ((mi - power_start_month) / 12.0))
        power_zar_year[yi] += kwh_per_day * rate_indexed * 30.44
    rent_cfg = cfg.get("coe_rent", {})
    rent_om_pct = float(rent_cfg.get("om_overhead_pct", 2.0))
    rent_monthly_eur, _, _, _ = compute_coe_rent_monthly_eur(rent_om_pct)
    rent_monthly_zar = rent_monthly_eur * FX_RATE
    rent_esc_pct = float(rent_cfg.get("annual_escalation_pct", 7.0)) / 100.0
    rent_start_month = int(rent_cfg.get("start_month", 24))
    rent_zar_year = [0.0]*10
    for mi in range(1, 121):
        yi = _month_to_year_idx(mi)
        if yi is None or mi < rent_start_month: continue
        rent_indexed = rent_monthly_zar * ((1.0 + rent_esc_pct) ** ((mi - rent_start_month) / 12.0))
        rent_zar_year[yi] += rent_indexed
    annual_rows = []
    for yi in range(10):
        m1, m2 = 6 + yi * 12, 12 + yi * 12
        i1, i2 = month_to_idx.get(m1), month_to_idx.get(m2)
        semi_idx = [i1, i2] if i1 is not None and i2 is not None else []
        def ysum(arr, si=semi_idx): return sum(arr[i] for i in si) if si else 0.0
        gf_sewage_eur = ysum(rev_gf_sewage_zar) / FX_RATE
        bf_sewage_eur = ysum(rev_bf_sewage_zar) / FX_RATE
        gf_reuse_eur = ysum(rev_gf_reuse_zar) / FX_RATE
        construction_eur = ysum(rev_construction_zar) / FX_RATE
        agri_eur = ysum(rev_agri_zar) / FX_RATE
        bulk_eur = rev_bulk_zar_year[yi] / FX_RATE
        om_eur = om_zar_year[yi] / FX_RATE
        rent_eur = rent_zar_year[yi] / FX_RATE
        annual_rows.append({
            "year": yi+1,
            "rev_total": gf_sewage_eur + bf_sewage_eur + gf_reuse_eur + construction_eur + agri_eur + bulk_eur,
            "om_cost": om_eur, "power_cost": power_zar_year[yi] / FX_RATE, "rent_cost": rent_eur,
        })
    return annual_rows

def _build_lanred_operating_annual_model():
    lanred_cfg = operations_config.get("lanred", {})
    solar_cfg = lanred_cfg.get("solar_capacity", {})
    power_sales_cfg = lanred_cfg.get("power_sales", {})
    om_cfg = lanred_cfg.get("om", {})
    grid_cfg = lanred_cfg.get("grid_connection", {})
    installed_mwp = float(solar_cfg.get("installed_mwp", 1.2))
    capacity_factor_base = float(solar_cfg.get("capacity_factor_pct", 21.5)) / 100.0
    solar_degradation_pa = float(solar_cfg.get("degradation_pa_pct", 0.5)) / 100.0
    cod_month = int(solar_cfg.get("cod_month", 18))
    ic_nwl_cfg = power_sales_cfg.get("ic_nwl", {})
    eskom_base = float(ic_nwl_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
    ic_discount = float(ic_nwl_cfg.get("ic_discount_pct", 10.0))
    ic_rate = eskom_base * (1.0 - ic_discount / 100.0)
    ic_escalation = float(ic_nwl_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    ic_share = float(ic_nwl_cfg.get("share_of_generation_pct", 100.0)) / 100.0
    om_fixed_annual_zar = float(om_cfg.get("fixed_annual_zar", 120000))
    om_variable_r_kwh = float(om_cfg.get("variable_r_per_kwh", 0.05))
    om_indexation = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start_month = int(om_cfg.get("opex_start_month", 18))
    grid_monthly_zar = float(grid_cfg.get("monthly_availability_charge_zar", 5000))
    grid_escalation = float(grid_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    grid_start_month = int(grid_cfg.get("start_month", 18))
    annual_rows = []
    for yi in range(10):
        y_start, y_end = yi * 12 + 1, (yi + 1) * 12
        years_since_cod = max((y_start - cod_month) / 12.0, 0.0)
        cf_adj = capacity_factor_base * ((1.0 - solar_degradation_pa) ** years_since_cod)
        if y_start < cod_month <= y_end:
            hours = (y_end - cod_month + 1) * 30.44 * 24
        elif y_end < cod_month: hours = 0.0
        else: hours = 365.25 * 24
        gen_kwh = installed_mwp * 1000 * cf_adj * hours
        ic_rate_indexed = ic_rate * ((1.0 + ic_escalation) ** max((y_start - cod_month)/12.0, 0.0))
        rev_total = gen_kwh * ic_share * ic_rate_indexed / FX_RATE
        om_cost = 0.0
        if y_end >= om_start_month:
            om_fixed = om_fixed_annual_zar * ((1.0 + om_indexation) ** max((y_start - om_start_month)/12.0, 0.0))
            om_cost = (om_fixed + gen_kwh * om_variable_r_kwh) / FX_RATE
        grid_cost = 0.0
        if y_end >= grid_start_month:
            gm = grid_monthly_zar * ((1.0 + grid_escalation) ** max((y_start - grid_start_month)/12.0, 0.0))
            months_grid = (y_end - grid_start_month + 1) if y_start < grid_start_month <= y_end else 12
            grid_cost = gm * months_grid / FX_RATE
        annual_rows.append({"year": yi+1, "rev_total": rev_total, "om_cost": om_cost + grid_cost,
                            "power_cost": 0.0, "rent_cost": 0.0})
    return annual_rows

def _build_twx_operating_annual_model():
    twx_cfg = operations_config.get("timberworx", {})
    lease_cfg = twx_cfg.get("coe_lease", {})
    training_cfg = twx_cfg.get("training_programs", {})
    sales_cfg = twx_cfg.get("timber_sales", {})
    om_cfg = twx_cfg.get("om", {})
    om_pct = float(lease_cfg.get("om_overhead_pct", 2.0))
    monthly_rent_eur, _, _, _ = compute_coe_rent_monthly_eur(om_pct)
    monthly_rental_zar = monthly_rent_eur * FX_RATE
    lease_esc = float(lease_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    lease_start = int(lease_cfg.get("start_month", 24))
    occ_ramp = lease_cfg.get("occupancy_ramp", [0.30,0.50,0.65,0.75,0.80,0.85,0.90,0.90,0.95,0.95])
    tr_fee = float(training_cfg.get("fee_per_student_zar", 15000))
    tr_sub = float(training_cfg.get("seta_subsidy_per_student_zar", 8000))
    tr_throughput = training_cfg.get("throughput_students_per_year", [120,240,360,450,500,550,600,600,650,650])
    tr_esc = float(training_cfg.get("annual_escalation_pct", 7.0)) / 100.0
    tr_start = int(training_cfg.get("start_month", 30))
    sales_enabled = sales_cfg.get("enabled", True)
    units_py = sales_cfg.get("units_per_year", [0,50,120,200,280,350,420,500,580,650])
    price_pu = float(sales_cfg.get("price_per_unit_zar", 85000))
    cogs_pct = float(sales_cfg.get("cogs_pct", 65.0)) / 100.0
    sales_esc = float(sales_cfg.get("annual_price_escalation_pct", 6.0)) / 100.0
    sales_start = int(sales_cfg.get("start_month", 36))
    om_fixed = float(om_cfg.get("fixed_annual_zar", 180000))
    om_var_pct = float(om_cfg.get("variable_pct_of_revenue", 5.0)) / 100.0
    om_idx = float(om_cfg.get("annual_indexation_pa", 0.05))
    om_start = int(om_cfg.get("opex_start_month", 24))
    annual_rows = []
    for yi in range(10):
        y_start, y_end = yi*12+1, (yi+1)*12
        rev_lease_zar = 0.0
        if y_end >= lease_start:
            lr = monthly_rental_zar * ((1.0 + lease_esc) ** max((y_start - lease_start)/12.0, 0.0))
            occ = occ_ramp[yi] if yi < len(occ_ramp) else occ_ramp[-1]
            ml = (y_end - lease_start + 1) if y_start < lease_start <= y_end else 12
            rev_lease_zar = lr * ml * occ
        rev_tr_zar = 0.0
        if y_end >= tr_start:
            fi = tr_fee * ((1.0 + tr_esc) ** max((y_start - tr_start)/12.0, 0.0))
            si = tr_sub * ((1.0 + tr_esc) ** max((y_start - tr_start)/12.0, 0.0))
            stu = tr_throughput[yi] if yi < len(tr_throughput) else tr_throughput[-1]
            if y_start < tr_start <= y_end: stu = stu * (y_end - tr_start + 1) / 12.0
            rev_tr_zar = stu * (fi + si)
        rev_timber_zar = 0.0
        if sales_enabled and y_end >= sales_start:
            ppi = price_pu * ((1.0 + sales_esc) ** max((y_start - sales_start)/12.0, 0.0))
            units = units_py[yi] if yi < len(units_py) else units_py[-1]
            if y_start < sales_start <= y_end: units = units * (y_end - sales_start + 1) / 12.0
            rev_timber_zar = units * ppi * (1 - cogs_pct)
        rev_total_zar = rev_lease_zar + rev_tr_zar + rev_timber_zar
        om_cost_zar = 0.0
        if y_end >= om_start:
            omf = om_fixed * ((1.0 + om_idx) ** max((y_start - om_start)/12.0, 0.0))
            if y_start < om_start <= y_end: omf = omf * (y_end - om_start + 1) / 12.0
            om_cost_zar = omf + rev_total_zar * om_var_pct
        annual_rows.append({"year": yi+1, "rev_total": rev_total_zar / FX_RATE,
                            "om_cost": om_cost_zar / FX_RATE, "power_cost": 0.0, "rent_cost": 0.0})
    return annual_rows

# === Main model builder (copied from app.py build_sub_annual_model) ===

def build_sub_annual_model(entity_key):
    entity_data = structure['uses']['loans_to_subsidiaries'][entity_key]
    senior_cfg = structure['sources']['senior_debt']
    mezz_cfg = structure['sources']['mezzanine']
    sr_rate = senior_cfg['interest']['rate'] + INTERCOMPANY_MARGIN
    mz_rate = mezz_cfg['interest']['total_rate'] + INTERCOMPANY_MARGIN
    sr_repayments = senior_cfg['repayments']
    mz_repayments = mezz_cfg.get('repayments', 10)
    sr_principal = entity_data['senior_portion']
    mz_principal = entity_data['mezz_portion']
    total_sr = sum(l['senior_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
    total_mz = sum(l['mezz_portion'] for l in structure['uses']['loans_to_subsidiaries'].values())
    sr_detail = financing['loan_detail']['senior']
    sr_drawdowns = sr_detail['drawdown_schedule']
    sr_periods = [-4, -3, -2, -1]
    sr_prepayments_raw = sr_detail.get('prepayment_periods', {})
    prepay_alloc = sr_detail.get('prepayment_allocation', {})
    entity_prepay_pct = prepay_alloc.get(entity_key, 0.0) if prepay_alloc else 0.0
    sr_prepayments = {k: v * entity_prepay_pct for k, v in sr_prepayments_raw.items()} if entity_prepay_pct > 0 else None
    _sr_detail_fac = financing['loan_detail']['senior']
    _sr_bal_fac = (_sr_detail_fac['loan_drawdown_total'] + _sr_detail_fac['rolled_up_interest_idc']
                   - _sr_detail_fac['grant_proceeds_to_early_repayment'] - _sr_detail_fac['gepf_bulk_proceeds'])
    _sr_rate_fac = structure['sources']['senior_debt']['interest']['rate']
    _sr_num_fac = structure['sources']['senior_debt']['repayments']
    _sr_p_fac = _sr_bal_fac / _sr_num_fac
    _sr_i_m24 = _sr_bal_fac * _sr_rate_fac / 2
    dsra_amount_total = 2 * (_sr_p_fac + _sr_i_m24)
    entity_dsra = dsra_amount_total * {'nwl': 1.0}.get(entity_key, 0.0)
    sr_schedule = build_simple_ic_schedule(sr_principal, total_sr, sr_repayments, sr_rate, sr_drawdowns, sr_periods, sr_prepayments, dsra_amount=entity_dsra)
    mz_amount_eur = mezz_cfg['amount_eur']
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    mz_periods = [-4, -3, -2, -1]
    mz_schedule = build_simple_ic_schedule(mz_principal, total_mz, mz_repayments, mz_rate, mz_drawdowns, mz_periods, dsra_drawdown=entity_dsra)
    assets_cfg = load_config("assets")["assets"]
    fees_cfg = load_config("fees")
    project_asset_base = sum(_build_entity_asset_base(k, assets_cfg)["fee_base"] for k in ["nwl","lanred","timberworx"])
    project_debt_base = structure['sources']['senior_debt']['amount']
    project_fees = compute_project_fees(fees_cfg, project_debt_base, project_asset_base)
    registry = build_asset_registry(entity_key, assets_cfg, fees_cfg, project_fees["fees"], project_asset_base, project_debt_base)
    depr_assets = registry["assets"]
    depreciable_base_total = sum(a["depr_base"] for a in depr_assets)
    if entity_key == "nwl": ops_annual = _build_nwl_operating_annual_model()
    elif entity_key == "lanred": ops_annual = _build_lanred_operating_annual_model()
    elif entity_key == "timberworx": ops_annual = _build_twx_operating_annual_model()
    else: ops_annual = None
    _equity_map = {'nwl': EQUITY_NWL, 'lanred': EQUITY_LANRED, 'timberworx': EQUITY_TWX}
    entity_equity = _equity_map.get(entity_key, 0.0)
    ta_grant_total = financing.get('prepayments', {}).get('invest_int_ta', {}).get('amount_eur', 0)
    ta_grant_entity = ta_grant_total * entity_prepay_pct
    dtic_grant_total = financing.get('prepayments', {}).get('dtic_grant', {}).get('amount_eur', 0)
    dtic_grant_entity = dtic_grant_total * entity_prepay_pct
    gepf_prepay_total = financing.get('prepayments', {}).get('gepf_bulk_services', {}).get('amount_eur', 0)
    gepf_prepay_entity = gepf_prepay_total * entity_prepay_pct

    annual = []
    accumulated_depr = 0.0
    cumulative_pat = 0.0
    _cum_grants = 0.0
    _dsra_fd_bal = 0.0
    _cum_capex = 0.0
    for yi in range(10):
        a = {'year': yi + 1}
        y_start = yi * 12
        y_end = y_start + 12
        sr_interest = 0.0; sr_princ_paid = 0.0; sr_closing = sr_principal
        for r in sr_schedule:
            if y_start <= r['Month'] < y_end:
                sr_interest += r['Interest']
                sr_princ_paid += abs(r['Principle'])
            if r['Month'] < y_end:
                sr_closing = r['Closing']
        mz_interest = 0.0; mz_princ_paid = 0.0; mz_closing = mz_principal
        for r in mz_schedule:
            if y_start <= r['Month'] < y_end:
                mz_interest += r['Interest']
                mz_princ_paid += abs(r['Principle'])
            if r['Month'] < y_end:
                mz_closing = r['Closing']
        a['ie_sr'] = sr_interest; a['ie_mz'] = mz_interest; a['ie'] = sr_interest + mz_interest
        if yi >= 1:
            a['depr'] = sum(x["annual_depr"] for x in depr_assets if yi <= x["life"])
        else:
            a['depr'] = 0.0
        accumulated_depr += a['depr']
        op = ops_annual[yi] if ops_annual else {}
        for k, v in op.items(): a[k] = v
        a['ebitda'] = a.get('rev_total', 0.0) - a.get('om_cost', 0.0) - a.get('power_cost', 0.0) - a.get('rent_cost', 0.0)
        a['ebit'] = a['ebitda'] - a['depr']
        a['ii_dsra'] = _dsra_fd_bal * DSRA_RATE if _dsra_fd_bal > 0 else 0.0
        a['pbt'] = a['ebit'] - a['ie'] + a['ii_dsra']
        a['tax'] = max(a['pbt'] * 0.27, 0.0)
        a['pat'] = a['pbt'] - a['tax']
        a['cf_draw_sr'] = sum(r['Draw Down'] for r in sr_schedule if y_start <= r['Month'] < y_end)
        a['cf_draw_mz'] = sum(r['Draw Down'] for r in mz_schedule if y_start <= r['Month'] < y_end)
        a['cf_draw'] = a['cf_draw_sr'] + a['cf_draw_mz']
        a['cf_capex'] = a['cf_draw_sr'] + sum(r['Draw Down'] for r in mz_schedule if y_start <= r['Month'] < y_end and r['Period'] < 0)
        _cum_capex += a['cf_capex']
        a['cf_prepay_sr'] = sum(abs(r.get('Prepayment', 0)) for r in sr_schedule if y_start <= r['Month'] < y_end)
        a['cf_prepay'] = a['cf_prepay_sr']
        if a['cf_prepay'] > 0 and (dtic_grant_entity + gepf_prepay_entity) > 0:
            _prepay_dtic_share = dtic_grant_entity / (dtic_grant_entity + gepf_prepay_entity)
            a['cf_prepay_dtic'] = a['cf_prepay'] * _prepay_dtic_share
            a['cf_prepay_gepf'] = a['cf_prepay'] * (1.0 - _prepay_dtic_share)
        else:
            a['cf_prepay_dtic'] = 0.0; a['cf_prepay_gepf'] = 0.0
        a['cf_ie_sr'] = sum(r['Interest'] for r in sr_schedule if y_start <= r['Month'] < y_end and r['Month'] >= 24)
        a['cf_ie_mz'] = sum(r['Interest'] for r in mz_schedule if y_start <= r['Month'] < y_end and r['Month'] >= 24)
        a['cf_ie'] = a['cf_ie_sr'] + a['cf_ie_mz']
        a['cf_pr_sr'] = sr_princ_paid; a['cf_pr_mz'] = mz_princ_paid
        a['cf_pr'] = sr_princ_paid + mz_princ_paid
        a['cf_ds'] = a['cf_ie'] + a['cf_pr']
        a['cf_tax'] = a['tax']
        a['cf_ops'] = a['ebitda'] + a['ii_dsra'] - a['cf_tax']
        a['cf_equity'] = entity_equity if yi == 0 else 0.0
        a['cf_grant_dtic'] = dtic_grant_entity if yi == 1 else 0.0
        a['cf_grant_iic'] = ta_grant_entity if yi == 1 else 0.0
        a['cf_grants'] = a['cf_grant_dtic'] + a['cf_grant_iic']
        a['cf_net'] = (a['cf_equity'] + a['cf_draw'] - a['cf_capex'] + a['cf_grants'] - a['cf_prepay']
                       + a['cf_ops'] - a['cf_ie'] - a['cf_pr'])
        cumulative_pat += a['pat']
        _dsra_fd_bal = _dsra_fd_bal + a['cf_net']
        _cum_grants += a['cf_grants']
        a['bs_fixed_assets'] = max(min(_cum_capex, depreciable_base_total) - accumulated_depr, 0)
        a['bs_dsra'] = _dsra_fd_bal
        a['bs_assets'] = a['bs_fixed_assets'] + a['bs_dsra']
        a['bs_sr'] = max(sr_closing, 0)
        a['bs_mz'] = max(mz_closing, 0)
        a['bs_debt'] = a['bs_sr'] + a['bs_mz']
        a['bs_equity_sh'] = entity_equity
        a['bs_equity'] = a['bs_assets'] - a['bs_debt']
        a['bs_retained'] = a['bs_equity'] - a['bs_equity_sh']
        a['bs_retained_check'] = cumulative_pat + _cum_grants
        a['bs_gap'] = a['bs_retained'] - (cumulative_pat + _cum_grants)
        annual.append(a)

    return {"annual": annual, "sr_schedule": sr_schedule, "mz_schedule": mz_schedule,
            "depreciable_base": depreciable_base_total, "entity_equity": entity_equity}


# === Run ===
print("=" * 100)
print("BS GAP CHECK - All Subsidiaries")
print("=" * 100)

for entity in ["nwl", "lanred", "timberworx"]:
    try:
        result = build_sub_annual_model(entity)
        annual = result["annual"]
        print(f"\n{'='*60}")
        print(f"  {entity.upper()}")
        print(f"{'='*60}")
        print(f"{'Yr':>3} {'BS Gap':>12} {'RE(BS)':>14} {'CumPAT+G':>14} {'FixedAssets':>14} {'DSRA':>14} {'SrClose':>14} {'MzClose':>14}")
        for a in annual:
            gap = a['bs_gap']
            marker = " ***" if abs(gap) >= 1.0 else ""
            print(f"{a['year']:>3} {gap:>12,.0f} {a['bs_retained']:>14,.0f} {a['bs_retained_check']:>14,.0f} "
                  f"{a['bs_fixed_assets']:>14,.0f} {a['bs_dsra']:>14,.0f} {a['bs_sr']:>14,.0f} {a['bs_mz']:>14,.0f}{marker}")

        total_idc_sr = sum(r['Interest'] for r in result['sr_schedule'] if r['Period'] < 0)
        total_idc_mz = sum(r['Interest'] for r in result['mz_schedule'] if r['Period'] < 0)
        print(f"\n  Sr IC IDC: €{total_idc_sr:,.0f}  |  Mz IC IDC: €{total_idc_mz:,.0f}  |  Total IDC: €{total_idc_sr + total_idc_mz:,.0f}")
        print(f"  Depreciable base: €{result['depreciable_base']:,.0f}  |  Entity equity: €{result['entity_equity']:,.0f}")

        # Max gap
        max_gap = max(abs(a['bs_gap']) for a in annual)
        print(f"  MAX ABSOLUTE GAP: €{max_gap:,.0f}")
    except Exception as e:
        print(f"\n--- {entity.upper()} --- ERROR: {e}")
        import traceback; traceback.print_exc()
