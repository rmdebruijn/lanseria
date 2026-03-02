"""NWL entity module — operating model and full entity calculation.

Extracted from app.py _build_nwl_operating_annual_model() (L2409-2667)
and build_sub_annual_model('nwl') (L3164-3816).

No Streamlit imports. All UI-driven values come from ScenarioInputs.
"""

from __future__ import annotations

import math

from engine.config import ModelConfig, ScenarioInputs, load_config
from engine.facility import build_schedule, build_entity_schedule, extract_facility_vectors
from engine.loop import run_entity_loop, build_annual, to_annual, _WATERFALL_STOCK_KEYS
from engine.pnl import build_semi_annual_pnl, extract_tax_vector
from engine.waterfall import compute_entity_waterfall
from engine.swap import build_nwl_swap_schedule, extract_swap_vectors, compute_nwl_swap_bounds
from engine.types import EntityResult
from engine.currency import EUR, ZAR
from engine.periods import (
    total_periods, total_years, annual_month_range,
    construction_period_labels, repayment_start_month,
    semi_index_to_facility_period, period_start_month,
)


# ---------------------------------------------------------------------------
# Helper: piecewise-linear interpolation/extrapolation
# ---------------------------------------------------------------------------

def _extrapolate_piecewise_linear(
    base_months: list[int],
    base_values: list[float],
    target_months: list[int],
    floor: float | None = None,
) -> list[float]:
    """Piecewise-linear interpolation/extrapolation on semi-annual anchors."""
    if not base_months or not base_values or len(base_months) != len(base_values):
        return [0.0 for _ in target_months]

    pairs = sorted(zip(base_months, base_values), key=lambda x: x[0])
    xs = [int(p[0]) for p in pairs]
    ys = [float(p[1]) for p in pairs]

    if len(xs) >= 2:
        left_dx = xs[1] - xs[0]
        left_slope = ((ys[1] - ys[0]) / left_dx) if left_dx else 0.0
        right_dx = xs[-1] - xs[-2]
        right_slope = ((ys[-1] - ys[-2]) / right_dx) if right_dx else 0.0
    else:
        left_slope = 0.0
        right_slope = 0.0

    out = []
    for t in target_months:
        if t <= xs[0]:
            v = ys[0] + left_slope * (t - xs[0])
        elif t >= xs[-1]:
            v = ys[-1] + right_slope * (t - xs[-1])
        else:
            v = ys[-1]
            for i in range(len(xs) - 1):
                x0, x1 = xs[i], xs[i + 1]
                if x0 <= t <= x1:
                    y0, y1 = ys[i], ys[i + 1]
                    ratio = (t - x0) / (x1 - x0) if x1 != x0 else 0.0
                    v = y0 + (y1 - y0) * ratio
                    break
        if floor is not None:
            v = max(v, floor)
        out.append(v)
    return out


def _month_to_year_idx(month: int) -> int | None:
    """Map month 0..119 to year index 0..9 (start-month convention).

    M0-M11 → Y0, M12-M23 → Y1, … M108-M119 → Y9.
    """
    if month < 0:
        return None
    idx = month // 12
    return idx if 0 <= idx < 10 else None


def _month_to_semi_idx(m: int) -> int | None:
    """Map month 0..119 to semi-annual index 0..19 (start-month convention).

    M0-M5 → 0 (C1), M6-M11 → 1 (C2), M12-M17 → 2 (C3), …
    """
    if m < 0:
        return None
    si = m // 6
    return si if 0 <= si < 20 else None


# ---------------------------------------------------------------------------
# CoE rent helper
# ---------------------------------------------------------------------------

def compute_coe_rent_monthly_eur(
    cfg: ModelConfig,
    om_overhead_pct: float = 2.0,
) -> tuple[float, float, float, float]:
    """CoE monthly rent = CoE_building_CapEx x (WACC + O&M) / 12.

    Returns (monthly_eur, annual_eur, wacc, coe_capex).
    """
    sr_rate = cfg.sr_facility_rate   # e.g. 4.70%
    mz_rate = cfg.mz_facility_rate   # e.g. 14.25%
    wacc = 0.85 * sr_rate + 0.15 * mz_rate
    total_yield = wacc + (om_overhead_pct / 100.0)
    coe_items = cfg.assets["assets"].get("coe", {}).get("line_items", [])
    coe_capex = float(coe_items[0].get("budget", 0)) if coe_items else 0.0
    annual_rent = coe_capex * total_yield
    return annual_rent / 12.0, annual_rent, wacc, coe_capex


# ---------------------------------------------------------------------------
# Asset registry helpers (mirrors app.py L582-787)
# ---------------------------------------------------------------------------

def _asset_life_years(delivery: str, category: str) -> int:
    delivery_l = (delivery or "").lower()
    category_l = (category or "").lower()
    if "mabr" in delivery_l:
        return 10
    if "balance of plant" in delivery_l or "civils" in delivery_l or "owners engineer" in delivery_l:
        return 20
    if "solar" in delivery_l:
        return 25
    if "battery" in delivery_l or "bess" in delivery_l or "li-ion" in delivery_l:
        return 10
    if "panel equipment" in delivery_l or "panel machine" in delivery_l:
        return 10
    if "centre of excellence" in delivery_l or "center of excellence" in delivery_l:
        return 20
    if category_l in {"water", "solar", "coe"}:
        return 20
    return 20


def _build_entity_asset_base(entity_key: str, assets_cfg: dict) -> dict:
    """Build assets + services allocation for an entity (no fees)."""
    entity_map = {
        "nwl": {"assets": ["water"], "services": ["esg"]},
        "lanred": {"assets": ["solar"], "services": []},
        "timberworx": {"assets": ["coe"], "services": []},
    }
    ecfg = entity_map.get(entity_key, {"assets": [], "services": []})

    service_items: list[dict] = []
    asset_items: list[dict] = []

    for cat in ecfg["assets"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            delivery = item.get("delivery", "")
            if cat == "water" and "owners engineer" in (delivery or "").lower():
                service_items.append({
                    "id": item.get("id", ""),
                    "service": delivery or item.get("company", "Service"),
                    "cost": float(item.get("budget", 0)),
                })
                continue
            asset_items.append({
                "id": item.get("id", ""),
                "category": cat,
                "asset": delivery or item.get("company", "Asset"),
                "base_cost": float(item.get("budget", 0)),
            })

    for cat in ecfg["services"]:
        for item in assets_cfg.get(cat, {}).get("line_items", []):
            service_items.append({
                "id": item.get("id", ""),
                "service": item.get("delivery", item.get("company", "Service")),
                "cost": float(item.get("budget", 0)),
            })

    service_total = sum(s["cost"] for s in service_items)
    base_total = sum(a["base_cost"] for a in asset_items)

    for a in asset_items:
        share = (a["base_cost"] / base_total) if base_total else 0
        a["alloc_services"] = service_total * share
        a["alloc_fees"] = 0.0
        a["depr_base"] = a["base_cost"] + a["alloc_services"]
        a["life"] = _asset_life_years(a["asset"], a["category"])
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0

    fee_base = sum(a["depr_base"] for a in asset_items)

    return {
        "assets": asset_items,
        "services": service_items,
        "service_total": service_total,
        "base_total": base_total,
        "fee_base": fee_base,
    }


def _compute_project_fees(fees_cfg: dict, project_debt_base: float, project_capex_base: float) -> dict:
    fee_rows = []
    for fee in fees_cfg.get("fees", []):
        basis = fee.get("rate_basis", "")
        if basis == "debt":
            base_amount = project_debt_base
        elif basis == "capex":
            base_amount = project_capex_base
        else:
            base_amount = 0.0
        amount = base_amount * fee.get("rate", 0)
        fee_rows.append({**fee, "base_amount": base_amount, "amount": amount})
    return {"fees": fee_rows, "total": sum(f["amount"] for f in fee_rows)}


def _compute_entity_fees(fees_cfg: dict, entity_assets_base: float) -> dict:
    fee_rows = []
    for fee in fees_cfg.get("fees", []):
        basis = fee.get("rate_basis", "")
        base = (entity_assets_base * 0.85 if basis == "debt"
                else entity_assets_base if basis == "capex" else 0.0)
        amount = round(base * fee.get("rate", 0))
        fee_rows.append({**fee, "base_amount": base, "amount": amount})
    return {"fees": fee_rows, "total": sum(f["amount"] for f in fee_rows)}


def _build_asset_registry(entity_key: str, cfg: ModelConfig) -> dict:
    """Build asset registry with allocated fees for an entity."""
    assets_cfg = cfg.assets["assets"]
    fees_cfg = cfg.fees

    base = _build_entity_asset_base(entity_key, assets_cfg)
    fee_base = base["fee_base"]

    entity_data = cfg.entity_loans()[entity_key]
    fee_total = entity_data["fees_allocated"]

    entity_fees = _compute_entity_fees(fees_cfg, fee_base)

    # Distribute fees across asset line items pro-rata by depr_base weight
    for a in base["assets"]:
        a_share = (a["depr_base"] / fee_base) if fee_base else 0
        a["alloc_fees"] = fee_total * a_share
        a["depr_base"] = a["depr_base"] + a["alloc_fees"]
        a["annual_depr"] = a["depr_base"] / a["life"] if a["life"] else 0

    return {
        **base,
        "fee_rows": entity_fees["fees"],
        "fee_total": fee_total,
        "fee_alloc": fee_total,
    }


# ---------------------------------------------------------------------------
# NWL Operating Model
# ---------------------------------------------------------------------------

def build_nwl_operating_model(
    cfg: ModelConfig,
    inputs: ScenarioInputs,
) -> tuple[list[dict], list[dict]]:
    """Build NWL 10-year annual and 20-period semi-annual operating model (EUR).

    Returns (ops_annual, ops_semi_annual).
    """
    fx_rate = cfg.fx_rate
    ops_cfg = cfg.operations.get("nwl", {})
    on_ramp_cfg = ops_cfg.get("on_ramp", {})
    greenfield_cfg = ops_cfg.get("greenfield", {})
    brownfield_cfg = ops_cfg.get("brownfield", {})
    bulk_cfg = ops_cfg.get("bulk_services", {})
    om_cfg = ops_cfg.get("om", {})
    srv_cfg = ops_cfg.get("sewerage_revenue_sharing", {})
    power_cfg = ops_cfg.get("power", {})
    rent_cfg = ops_cfg.get("coe_rent", {})

    months_semi = [period_start_month(si) for si in range(total_periods())]  # M0, M6, M12, ..., M114 (20 canonical periods)
    month_to_idx = {m: i for i, m in enumerate(months_semi)}

    # ── Sewage capacity ramp (from on_ramp.rows) ──
    ramp_rows = on_ramp_cfg.get("rows", [])
    cap_points = [
        (int(r.get("period_months", 0)), r.get("capacity_available_mld"))
        for r in ramp_rows
    ]
    cap_points = [(m, float(v)) for m, v in cap_points if v is not None]
    if not any(m == 6 for m, _ in cap_points):
        cap_points.append((6, 0.0))
    if not any(m == 12 for m, _ in cap_points):
        cap_points.append((12, 0.0))
    cap_points = sorted(cap_points, key=lambda x: x[0])
    cap_months = [m for m, _ in cap_points]
    cap_vals = [v for _, v in cap_points]
    sewage_capacity = _extrapolate_piecewise_linear(cap_months, cap_vals, months_semi, floor=0.0)

    # ── Demand vectors (piecewise-linear from 10 semi-annual anchors M18-M72) ──
    demand_months = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    piped_sewage_base = [float(x) for x in greenfield_cfg.get("piped_sewage_topcos_mld", [0.0] * 10)]
    construction_base = [float(x) for x in greenfield_cfg.get("construction_water_demand_topcos_mld", [0.0] * 10)]
    latent_base = [float(x) for x in brownfield_cfg.get("latent_demand_quantified", [0.0] * 10)]

    piped_sewage_demand = _extrapolate_piecewise_linear(demand_months, piped_sewage_base, months_semi, floor=0.0)
    construction_demand = _extrapolate_piecewise_linear(demand_months, construction_base, months_semi, floor=0.0)
    latent_demand = _extrapolate_piecewise_linear(demand_months, latent_base, months_semi, floor=0.0)

    # ── ScenarioInputs parameters ──
    annual_growth_pct = inputs.nwl_greenfield_growth_pct
    brine_pct = inputs.nwl_greenfield_brine_pct
    sewage_rate_2025 = inputs.nwl_greenfield_sewage_rate_2025
    water_rate_2025 = inputs.nwl_greenfield_water_rate_2025
    reuse_ratio = inputs.nwl_greenfield_reuse_ratio

    srv_joburg_price = inputs.nwl_srv_joburg_price
    srv_growth_pct = inputs.nwl_srv_growth_pct
    srv_transport_r_km = inputs.nwl_srv_transport_r_km
    srv_truck_capacity_m3 = max(inputs.nwl_srv_truck_capacity_m3, 1.0)
    srv_nwl_distance_km = inputs.nwl_srv_nwl_distance_km
    srv_gov_distance_km = inputs.nwl_srv_gov_distance_km
    srv_saving_to_market_pct = inputs.nwl_srv_saving_to_market_pct

    # ── Volume calculations ──
    sewage_sold = [min(cap, dem) for cap, dem in zip(sewage_capacity, piped_sewage_demand)]
    overflow_brownfield = [max(cap - sold, 0.0) for cap, sold in zip(sewage_capacity, sewage_sold)]
    reuse_capacity = [cap * (1.0 - brine_pct / 100.0) for cap in sewage_capacity]
    reuse_topcos_demand = [sold * reuse_ratio for sold in sewage_sold]
    reuse_sold_topcos = [min(cap, dem) for cap, dem in zip(reuse_capacity, reuse_topcos_demand)]
    reuse_after_topcos = [max(cap - sold, 0.0) for cap, sold in zip(reuse_capacity, reuse_sold_topcos)]
    reuse_sold_construction = [min(rem, dem) for rem, dem in zip(reuse_after_topcos, construction_demand)]
    reuse_overflow_agri = [
        max(cap - sold1 - sold2, 0.0)
        for cap, sold1, sold2 in zip(reuse_capacity, reuse_sold_topcos, reuse_sold_construction)
    ]
    brownfield_served = [min(cap, dem) for cap, dem in zip(overflow_brownfield, latent_demand)]

    # ── Rate schedules ──
    growth_factor = 1.0 + (annual_growth_pct / 100.0)
    sewage_rates = [sewage_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    water_rates = [water_rate_2025 * (growth_factor ** (m / 12.0)) for m in months_semi]
    agri_base = float(brownfield_cfg.get("agri_base_2025_r_per_kl", 37.70))
    agri_rates = [agri_base * (growth_factor ** (m / 12.0)) for m in months_semi]

    # Honeysucker / sewerage revenue sharing rates
    srv_processing_fee_truck = srv_joburg_price * srv_truck_capacity_m3
    srv_transport_nwl = srv_transport_r_km * srv_nwl_distance_km
    srv_transport_gov = srv_transport_r_km * srv_gov_distance_km
    srv_saving_per_m3_transport = (srv_transport_gov - srv_transport_nwl) / srv_truck_capacity_m3
    srv_market_price = max(srv_saving_per_m3_transport * (srv_saving_to_market_pct / 100.0), 0.0)
    srv_growth_factor = 1.0 + (srv_growth_pct / 100.0)
    honeysucker_rates = [srv_market_price * (srv_growth_factor ** (m / 12.0)) for m in months_semi]

    # ── Revenue vectors (ZAR, semi-annual; 1 MLD x 365/2 x 1000 kL) ──
    half_year_kl_per_mld = 1000.0 * 365.0 / 2.0
    rev_gf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(sewage_sold, sewage_rates)]
    rev_bf_sewage_zar = [v * half_year_kl_per_mld * p for v, p in zip(brownfield_served, honeysucker_rates)]
    rev_gf_reuse_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_topcos, water_rates)]
    rev_construction_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_sold_construction, water_rates)]
    rev_agri_zar = [v * half_year_kl_per_mld * p for v, p in zip(reuse_overflow_agri, agri_rates)]

    # ── Bulk services revenue (lump-sum at M12) ──
    rev_bulk_zar_year = [0.0] * 10
    rev_bulk_zar_semi = [0.0] * 20
    for row in bulk_cfg.get("rows", []):
        amount = float(row.get("price_zar", 0.0))
        if amount <= 0.0:
            continue
        yi = _month_to_year_idx(12)
        if yi is not None:
            rev_bulk_zar_year[yi] += amount
        si = _month_to_semi_idx(12)
        if si is not None:
            rev_bulk_zar_semi[si] += amount

    # ── O&M cost (month-by-month accumulation) ──
    om_monthly_fee = float(om_cfg.get("flat_fee_per_month_zar", 0.0))
    om_index_pa = float(om_cfg.get("annual_indexation_pa", 0.0))
    om_start_month = int(om_cfg.get("opex_start_month", 12))
    om_zar_year = [0.0] * 10
    om_zar_semi = [0.0] * 20
    for mi in range(120):  # M0..M119 (0-based months matching _month_to_year/semi_idx)
        if mi < om_start_month:
            continue
        yi = _month_to_year_idx(mi)
        years_from_start = (mi - om_start_month) / 12.0
        monthly_cost = om_monthly_fee * ((1.0 + om_index_pa) ** years_from_start)
        if yi is not None:
            om_zar_year[yi] += monthly_cost
        si = _month_to_semi_idx(mi)
        if si is not None:
            om_zar_semi[si] += monthly_cost

    # ── Power cost (IC from LanRED at Eskom -10%) ──
    power_kwh_per_m3 = inputs.nwl_power_kwh_per_m3
    eskom_base = inputs.nwl_power_eskom_base
    ic_discount = inputs.nwl_power_ic_discount
    power_rate = eskom_base * (1.0 - ic_discount / 100.0)
    power_escalation = inputs.nwl_power_escalation / 100.0
    power_start_month = int(power_cfg.get("start_month", 18))
    power_zar_year = [0.0] * 10
    power_zar_semi = [0.0] * 20
    for mi in range(120):  # M0..M119 (0-based months)
        if mi < power_start_month:
            continue
        yi = _month_to_year_idx(mi)
        # Interpolate capacity at this month
        cap_mld = 0.0
        for ci in range(len(cap_months) - 1):
            if cap_months[ci] <= mi <= cap_months[ci + 1]:
                frac = (mi - cap_months[ci]) / max(cap_months[ci + 1] - cap_months[ci], 1)
                cap_mld = cap_vals[ci] + frac * (cap_vals[ci + 1] - cap_vals[ci])
                break
        else:
            if cap_months and mi >= cap_months[-1]:
                cap_mld = cap_vals[-1]
        volume_m3_per_day = cap_mld * 1000.0
        kwh_per_day = volume_m3_per_day * power_kwh_per_m3
        years_from_start = (mi - power_start_month) / 12.0
        rate_indexed = power_rate * ((1.0 + power_escalation) ** years_from_start)
        power_monthly = kwh_per_day * rate_indexed * 30.44  # avg days/month
        if yi is not None:
            power_zar_year[yi] += power_monthly
        si = _month_to_semi_idx(mi)
        if si is not None:
            power_zar_semi[si] += power_monthly

    # ── CoE rent (capital-recovery: CapEx x (WACC + O&M)) ──
    rent_om_pct = float(rent_cfg.get("om_overhead_pct", 2.0))
    rent_monthly_eur, _rent_annual_eur, _rent_wacc, _rent_coe_capex = compute_coe_rent_monthly_eur(cfg, rent_om_pct)
    rent_monthly_zar = rent_monthly_eur * fx_rate
    rent_esc_pct = float(rent_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    rent_start_month = int(rent_cfg.get("start_month", 24))
    rent_zar_year = [0.0] * 10
    rent_zar_semi = [0.0] * 20
    for mi in range(120):  # M0..M119 (0-based months)
        if mi < rent_start_month:
            continue
        yi = _month_to_year_idx(mi)
        years_from_start = (mi - rent_start_month) / 12.0
        rent_indexed = rent_monthly_zar * ((1.0 + rent_esc_pct) ** years_from_start)
        if yi is not None:
            rent_zar_year[yi] += rent_indexed
        si = _month_to_semi_idx(mi)
        if si is not None:
            rent_zar_semi[si] += rent_indexed

    # ── Build 10 annual rows ──
    annual_rows: list[dict] = []
    for yi in range(total_years()):
        # Each annual year contains two canonical semi-annual periods
        i1 = yi * 2
        i2 = yi * 2 + 1
        semi_idx = [i1, i2]

        def ysum(arr: list[float]) -> float:
            return sum(arr[i] for i in semi_idx) if semi_idx else 0.0

        gf_sewage_eur = ZAR(ysum(rev_gf_sewage_zar)).to_eur(fx_rate).value
        bf_sewage_eur = ZAR(ysum(rev_bf_sewage_zar)).to_eur(fx_rate).value
        gf_reuse_eur = ZAR(ysum(rev_gf_reuse_zar)).to_eur(fx_rate).value
        construction_eur = ZAR(ysum(rev_construction_zar)).to_eur(fx_rate).value
        agri_eur = ZAR(ysum(rev_agri_zar)).to_eur(fx_rate).value
        bulk_eur = ZAR(rev_bulk_zar_year[yi]).to_eur(fx_rate).value
        om_eur = ZAR(om_zar_year[yi]).to_eur(fx_rate).value

        vol_capacity_avg = sum(sewage_capacity[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_treated_avg = sum(sewage_sold[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_annual_m3 = vol_treated_avg * 1000.0 * 365.0
        vol_reuse_avg = (
            sum(reuse_sold_topcos[i] + reuse_sold_construction[i] + reuse_overflow_agri[i] for i in semi_idx)
            / len(semi_idx) if semi_idx else 0.0
        )
        vol_brownfield_avg = sum(brownfield_served[i] for i in semi_idx) / len(semi_idx) if semi_idx else 0.0
        vol_reuse_annual_m3 = vol_reuse_avg * 1000.0 * 365.0
        vol_brownfield_annual_m3 = vol_brownfield_avg * 1000.0 * 365.0

        rent_eur = ZAR(rent_zar_year[yi]).to_eur(fx_rate).value

        annual_rows.append({
            "year": yi + 1,
            "rev_greenfield_sewage": gf_sewage_eur,
            "rev_brownfield_sewage": bf_sewage_eur,
            "rev_sewage": gf_sewage_eur + bf_sewage_eur,
            "rev_greenfield_reuse": gf_reuse_eur,
            "rev_construction": construction_eur,
            "rev_agri": agri_eur,
            "rev_reuse": gf_reuse_eur + construction_eur + agri_eur,
            "rev_operating": gf_sewage_eur + bf_sewage_eur + gf_reuse_eur + construction_eur + agri_eur,
            "rev_bulk_services": bulk_eur,
            "rev_total": gf_sewage_eur + bf_sewage_eur + gf_reuse_eur + construction_eur + agri_eur + bulk_eur,
            "om_cost": om_eur,
            "power_cost": ZAR(power_zar_year[yi]).to_eur(fx_rate).value,
            "rent_cost": rent_eur,
            "vol_capacity_mld": vol_capacity_avg,
            "vol_treated_mld": vol_treated_avg,
            "vol_annual_m3": vol_annual_m3,
            "vol_reuse_annual_m3": vol_reuse_annual_m3,
            "vol_brownfield_annual_m3": vol_brownfield_annual_m3,
            "power_zar": power_zar_year[yi],
            "om_zar": om_zar_year[yi],
            "rent_zar": rent_zar_year[yi],
        })

    # ── Build 20 semi-annual rows ──
    semi_annual_rows: list[dict] = []
    for si in range(total_periods()):
        _s_gf_sew = ZAR(rev_gf_sewage_zar[si]).to_eur(fx_rate).value
        _s_bf_sew = ZAR(rev_bf_sewage_zar[si]).to_eur(fx_rate).value
        _s_gf_reu = ZAR(rev_gf_reuse_zar[si]).to_eur(fx_rate).value
        _s_constr = ZAR(rev_construction_zar[si]).to_eur(fx_rate).value
        _s_agri = ZAR(rev_agri_zar[si]).to_eur(fx_rate).value
        _s_bulk = ZAR(rev_bulk_zar_semi[si]).to_eur(fx_rate).value
        _s_rev_op = _s_gf_sew + _s_bf_sew + _s_gf_reu + _s_constr + _s_agri
        _s_rev_tot = _s_rev_op + _s_bulk
        _s_om = ZAR(om_zar_semi[si]).to_eur(fx_rate).value
        _s_pow = ZAR(power_zar_semi[si]).to_eur(fx_rate).value
        _s_rent = ZAR(rent_zar_semi[si]).to_eur(fx_rate).value
        semi_annual_rows.append({
            "month": months_semi[si],
            "rev_operating": _s_rev_op,
            "rev_bulk_services": _s_bulk,
            "rev_total": _s_rev_tot,
            "om_cost": _s_om,
            "power_cost": _s_pow,
            "rent_cost": _s_rent,
        })

    return annual_rows, semi_annual_rows


# ---------------------------------------------------------------------------
# Full NWL Entity
# ---------------------------------------------------------------------------

def build_nwl_entity(cfg: ModelConfig, inputs: ScenarioInputs) -> EntityResult:
    """Orchestrate the full NWL entity calculation.

    Mirrors app.py build_sub_annual_model('nwl') L3164-3816.

    Steps:
    1. Build vanilla SR/MZ IC schedules
    2. Build NWL operating model
    3. Compute depreciable base from asset registry
    4. Build semi-annual P&L with loss carry-forward
    5. Build swap schedule if enabled
    6. Construct cash_inflows (DTIC grant at M12, pre-rev hedge at M24)
    7. Run convergence loop (up to 5 iterations)
    8. Patch annual entries from waterfall
    9. Return EntityResult
    """
    entity_key = "nwl"
    fx_rate = cfg.fx_rate

    entity_data = cfg.entity_loans()[entity_key]
    sr_detail = cfg.financing["loan_detail"]["senior"]
    mezz_cfg = cfg.structure["sources"]["mezzanine"]

    sr_principal = entity_data["senior_portion"]
    mz_principal = entity_data["mezz_portion"]
    total_sr = cfg.total_senior()
    total_mz = cfg.total_mezz()

    sr_drawdowns = sr_detail["drawdown_schedule"]
    sr_periods = construction_period_labels()
    mz_amount_eur = mezz_cfg["amount_eur"]
    mz_drawdowns = [mz_amount_eur, 0, 0, 0]
    mz_periods = construction_period_labels()

    sr_rate = cfg.sr_ic_rate   # 5.20%
    mz_rate = cfg.mz_ic_rate   # 14.75%

    # Grant-funded acceleration (entity-specific allocation)
    grant_alloc = sr_detail.get("prepayment_allocation", {})
    entity_grant_pct = grant_alloc.get(entity_key, 0.0) if grant_alloc else 0.0
    sr_grant_accel_raw = sr_detail.get("prepayment_periods", {})
    sr_grant_accel = (
        {k: v * entity_grant_pct for k, v in sr_grant_accel_raw.items()}
        if entity_grant_pct > 0 else None
    )

    # Pre-revenue hedge sizing: indexes compute_nwl_swap_bounds()
    # 2×(P+I) SCLCA loan M24 — deterministic from config, same formula
    # as FacilityState construction but at IIC facility rate (4.70%).
    _swap_bounds = compute_nwl_swap_bounds(cfg)
    pre_revenue_hedge_total = _swap_bounds["min"]

    # ── Step 1: Vanilla IC schedules ──
    sr_schedule = build_schedule(
        sr_principal, total_sr, cfg.sr_repayments, sr_rate,
        sr_drawdowns, sr_periods, sr_grant_accel,
    )
    mz_schedule = build_schedule(
        mz_principal, total_mz, cfg.mz_repayments, mz_rate,
        mz_drawdowns, mz_periods,
    )

    # ── Step 2: Operating model ──
    ops_annual, ops_semi_annual = build_nwl_operating_model(cfg, inputs)

    # ── Step 3: Asset registry + depreciable base ──
    registry = _build_asset_registry(entity_key, cfg)
    depr_assets = registry["assets"]
    depreciable_base = sum(a["depr_base"] for a in depr_assets)

    # ── Entity equity and grants ──
    entity_equity = cfg.equity_nwl
    financing = cfg.financing
    dtic_grant_total = financing.get("prepayments", {}).get("dtic_grant", {}).get("amount_eur", 0)
    dtic_grant_entity = dtic_grant_total * entity_grant_pct
    ta_grant_total = financing.get("prepayments", {}).get("invest_int_ta", {}).get("amount_eur", 0)
    ta_grant_entity = ta_grant_total * entity_grant_pct
    gepf_grant_total = financing.get("prepayments", {}).get("gepf_bulk_services", {}).get("amount_eur", 0)
    gepf_grant_entity = gepf_grant_total * entity_grant_pct

    # ── Step 5: Swap schedule ──
    swap_active = inputs.nwl_swap_enabled
    swap_sched: dict | None = None
    if swap_active:
        # Swap notional: indexes bounds from compute_nwl_swap_bounds()
        _swap_min = _swap_bounds["min"]
        _swap_max = _swap_bounds["max"]
        if inputs.nwl_swap_notional is not None:
            _swap_eur = float(inputs.nwl_swap_notional)
        else:
            _swap_eur = _swap_bounds["preferred"]
        _swap_eur = max(_swap_min, min(_swap_max, _swap_eur))

        _last_sr = max(
            (r["Month"] for r in sr_schedule if r["Month"] >= repayment_start_month() and abs(r.get("Principle", 0)) > 0),
            default=102,
        )
        swap_sched = build_nwl_swap_schedule(_swap_eur, fx_rate, cfg, last_sr_month=_last_sr)

    # ── Step 6: Cash inflows ──
    cash_inflows: list[dict] = [{} for _ in range(total_periods())]
    # M12 = semi-annual index 2 (C3): DTIC grant + IIC TA grant + GEPF bulk services
    cash_inflows[2] = {
        "dtic_grant": dtic_grant_entity,
        "iic_grant": ta_grant_entity,
        "gepf_bulk": gepf_grant_entity,
    }
    # M24 = semi-annual index 4 (R1): EUR leg repayment (swap) OR mezz draw (FEC)
    if swap_active:
        cash_inflows[4] = {"eur_leg_repayment": pre_revenue_hedge_total}
    else:
        cash_inflows[4] = {"mezz_draw": pre_revenue_hedge_total}

    sweep_pct = inputs.nwl_cash_sweep_pct / 100.0

    # LanRED deficit vector for OD lending (if available)
    lanred_deficit_vector = getattr(inputs, "_lanred_deficit_vector", None)

    # ── Step 7: One Big Loop (single pass, no convergence) ──
    # FEC mode: CC second drawdown funds Sr IC prepay at R1 (M24).
    # dsra_amount triggers FacilityState's built-in prepay logic:
    # P1 = prepay dsra_amount, P2 = interest-only, P3+ = recalc P_constant.
    _sr_dsra_amount = pre_revenue_hedge_total if not swap_active else 0.0
    # Mezz draw: FEC mode injects pre_revenue_hedge as additional Mezz IC
    _mz_dsra_drawdown = pre_revenue_hedge_total if not swap_active else 0.0

    loop_result = run_entity_loop(
        entity_key, cfg,
        ops_annual=ops_annual,
        ops_semi_annual=ops_semi_annual,
        sr_principal=sr_principal,
        total_sr=total_sr,
        sr_repayments=cfg.sr_repayments,
        sr_rate=sr_rate,
        sr_drawdowns=sr_drawdowns,
        mz_principal=mz_principal,
        total_mz=total_mz,
        mz_repayments=cfg.mz_repayments,
        mz_rate=mz_rate,
        mz_drawdowns=mz_drawdowns,
        construction_periods=sr_periods,
        depreciable_base=depreciable_base,
        tax_rate=cfg.tax_rate,
        cash_inflows=cash_inflows,
        sweep_pct=sweep_pct,
        lanred_deficit_vector=lanred_deficit_vector,
        swap_sched=swap_sched if swap_active else None,
        fx_rate=fx_rate,
        sr_grant_accel=sr_grant_accel,
        dsra_amount=_sr_dsra_amount,
        dsra_drawdown=_mz_dsra_drawdown,
    )
    sr_schedule = loop_result.sr_schedule
    mz_schedule = loop_result.mz_schedule
    wf_semi = loop_result.waterfall_semi
    semi_annual_pl = loop_result.semi_annual_pl
    semi_annual_tax = loop_result.semi_annual_tax

    wf_annual = to_annual(wf_semi, _WATERFALL_STOCK_KEYS)

    # ── Build annual rows (single pass, single source of truth) ──
    annual = build_annual(
        loop_result, ops_annual,
        entity_equity=entity_equity,
        depreciable_base=depreciable_base,
        swap_sched=swap_sched,
        swap_active=swap_active,
        fx_rate=fx_rate,
        dtic_grant_entity=dtic_grant_entity,
        ta_grant_entity=ta_grant_entity,
        gepf_grant_entity=gepf_grant_entity,
    )

    # ── Step 9: Build SwapSchedule wrapper for EntityResult ──
    from engine.types import SwapSchedule
    swap_result: SwapSchedule | None = None
    if swap_active and swap_sched:
        swap_result = SwapSchedule(
            eur_amount=swap_sched["eur_amount"],
            zar_amount=swap_sched["zar_amount"],
            eur_rate=swap_sched["eur_rate"],
            zar_rate=swap_sched["zar_rate"],
            eur_amount_idc=swap_sched["eur_amount_idc"],
            tenor=swap_sched.get("tenor", 0),
            start_month=swap_sched.get("start_month", 0),
            p_constant_zar=swap_sched.get("p_constant_zar", 0.0),
            zar_amount_idc=swap_sched.get("zar_amount_idc", 0.0),
            schedule=swap_sched["schedule"],
        )

    return EntityResult(
        entity_key=entity_key,
        annual=annual,
        sr_schedule=sr_schedule,
        mz_schedule=mz_schedule,
        waterfall_semi=wf_semi,
        waterfall_annual=wf_annual,
        semi_annual_pl=semi_annual_pl,
        semi_annual_tax=semi_annual_tax,
        ops_annual=ops_annual,
        ops_semi_annual=ops_semi_annual,
        registry=registry,
        depreciable_base=depreciable_base,
        entity_equity=entity_equity,
        swap_schedule=swap_result,
        swap_active=swap_active,
        cash_inflows=cash_inflows,
        pre_revenue_hedge_total=pre_revenue_hedge_total,
    )


# ---------------------------------------------------------------------------
# NWL Sensitivity Calculator
# ---------------------------------------------------------------------------

def build_nwl_sensitivity(
    cfg: ModelConfig,
    *,
    sewage_rate_factor: float = 1.0,
    water_rate_factor: float = 1.0,
    piped_delay_months: int = 0,
    ramp_delay_months: int = 0,
    honey_share_pct: float = 40.0,
) -> list[dict]:
    """Recompute NWL revenue/EBITDA with sensitivity overrides.

    Returns 10 annual dicts with rev breakdown and ebitda.
    Extracted from app.py _nwl_sens_calc (~L9012).
    """
    fx_rate = cfg.fx_rate
    ops_cfg = cfg.operations.get("nwl", {})
    gf_cfg = ops_cfg.get("greenfield", {})
    bf_cfg = ops_cfg.get("brownfield", {})
    ramp_cfg = ops_cfg.get("on_ramp", {})
    srv_cfg = ops_cfg.get("sewerage_revenue_sharing", {})
    om_cfg = ops_cfg.get("om", {})
    pw_cfg = ops_cfg.get("power", {})
    rent_cfg = ops_cfg.get("coe_rent", {})
    bulk_cfg = ops_cfg.get("bulk_services", {})

    months_semi = [period_start_month(si) for si in range(total_periods())]  # M0, M6, ..., M114

    # --- Capacity ramp (with optional delay) ---
    ramp_rows = ramp_cfg.get("rows", [])
    cap_pts = [(int(r.get("period_months", 0)), r.get("capacity_available_mld"))
               for r in ramp_rows]
    cap_pts = [(m, float(v)) for m, v in cap_pts if v is not None]
    if ramp_delay_months > 0:
        cap_pts = [(m + ramp_delay_months, v) for m, v in cap_pts]
    if not any(m <= 6 for m, _ in cap_pts):
        cap_pts.append((6, 0.0))
    if not any(m == 12 for m, _ in cap_pts):
        cap_pts.append((12, 0.0))
    cap_pts = sorted(cap_pts, key=lambda x: x[0])
    cap_m = [m for m, _ in cap_pts]
    cap_v = [v for _, v in cap_pts]
    sewage_cap = _extrapolate_piecewise_linear(cap_m, cap_v, months_semi, floor=0.0)

    # --- Demand schedules ---
    demand_months_base = [18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    piped_base = [float(x) for x in gf_cfg.get("piped_sewage_topcos_mld", [0.0] * 10)]
    construction_base = [float(x) for x in gf_cfg.get("construction_water_demand_topcos_mld", [0.0] * 10)]
    latent_base = [float(x) for x in bf_cfg.get("latent_demand_quantified", [0.0] * 10)]

    piped_months_shifted = [m + piped_delay_months for m in demand_months_base]

    piped_demand = _extrapolate_piecewise_linear(piped_months_shifted, piped_base, months_semi, floor=0.0)
    construction_demand = _extrapolate_piecewise_linear(demand_months_base, construction_base, months_semi, floor=0.0)
    latent_demand = _extrapolate_piecewise_linear(demand_months_base, latent_base, months_semi, floor=0.0)

    # --- Volume calculations ---
    sewage_sold = [min(c, d) for c, d in zip(sewage_cap, piped_demand)]
    overflow_bf = [max(c - s, 0.0) for c, s in zip(sewage_cap, sewage_sold)]
    brine_pct = float(gf_cfg.get("brine_pct_default", 10.0))
    reuse_ratio = float(gf_cfg.get("reuse_ratio_default", 0.80))
    reuse_cap = [c * (1.0 - brine_pct / 100.0) for c in sewage_cap]
    reuse_topcos_dem = [s * reuse_ratio for s in sewage_sold]
    reuse_sold_topcos = [min(c, d) for c, d in zip(reuse_cap, reuse_topcos_dem)]
    reuse_after = [max(c - s, 0.0) for c, s in zip(reuse_cap, reuse_sold_topcos)]
    reuse_sold_constr = [min(r, d) for r, d in zip(reuse_after, construction_demand)]
    reuse_overflow_agri = [max(c - s1 - s2, 0.0) for c, s1, s2
                           in zip(reuse_cap, reuse_sold_topcos, reuse_sold_constr)]
    bf_served = [min(o, d) for o, d in zip(overflow_bf, latent_demand)]

    # --- Rates with tariff sensitivity ---
    growth = 1.0 + float(gf_cfg.get("annual_growth_pct_default", 7.7)) / 100.0
    base_sewage = float(gf_cfg.get("sewage_rate_2025_r_per_kl", 46.40)) * sewage_rate_factor
    base_water = float(gf_cfg.get("water_rate_2025_r_per_kl", 62.05)) * water_rate_factor
    agri_base = float(bf_cfg.get("agri_base_2025_r_per_kl", 37.70))
    sewage_r = [base_sewage * (growth ** (m / 12.0)) for m in months_semi]
    water_r = [base_water * (growth ** (m / 12.0)) for m in months_semi]
    agri_r = [agri_base * (growth ** (m / 12.0)) for m in months_semi]

    # --- Honeysucker rate with sharing override ---
    transport_km = float(srv_cfg.get("transport_r_per_km_default", 28.0))
    truck_cap = max(float(srv_cfg.get("truck_capacity_m3_default", 10.0)), 1.0)
    nwl_dist = float(srv_cfg.get("nwl_roundtrip_km_default", 10.0))
    gov_dist = float(srv_cfg.get("gov_roundtrip_km_default", 100.0))
    saving_per_m3 = (gov_dist - nwl_dist) * transport_km / truck_cap
    market_price = max(saving_per_m3 * (honey_share_pct / 100.0), 0.0)
    srv_growth = 1.0 + float(srv_cfg.get("growth_pct_default", 7.7)) / 100.0
    honey_r = [market_price * (srv_growth ** (m / 12.0)) for m in months_semi]

    # --- Revenue (semi-annual, then aggregate to annual) ---
    hyk = 1000.0 * 365.0 / 2.0
    rev_gf_s = [v * hyk * p for v, p in zip(sewage_sold, sewage_r)]
    rev_bf_s = [v * hyk * p for v, p in zip(bf_served, honey_r)]
    rev_reuse = [v * hyk * p for v, p in zip(reuse_sold_topcos, water_r)]
    rev_constr = [v * hyk * p for v, p in zip(reuse_sold_constr, water_r)]
    rev_agri = [v * hyk * p for v, p in zip(reuse_overflow_agri, agri_r)]

    # Bulk services (unaffected by sensitivity)
    bulk_yr = [0.0] * 10
    for row in bulk_cfg.get("rows", []):
        amt = float(row.get("price_zar", 0.0))
        rp = max(float(row.get("receipt_period", 12.0)), 0.0)
        if amt <= 0:
            continue
        if rp == 0.0:
            bi = _month_to_year_idx(12)
            if bi is not None:
                bulk_yr[bi] += amt
            continue
        for mi in range(120):  # M0..M119 (0-based)
            if 13 <= mi < 13 + rp:
                bi = _month_to_year_idx(mi)
                if bi is not None:
                    bulk_yr[bi] += amt / rp

    # O&M cost
    om_fee = float(om_cfg.get("flat_fee_per_month_zar", 0.0))
    om_idx = float(om_cfg.get("annual_indexation_pa", 0.0))
    om_start = int(om_cfg.get("opex_start_month", 12))
    om_yr = [0.0] * 10
    for mi in range(120):  # M0..M119 (0-based)
        yi = _month_to_year_idx(mi)
        if yi is None or mi < om_start:
            continue
        om_yr[yi] += om_fee * ((1.0 + om_idx) ** ((mi - om_start) / 12.0))

    # Power cost
    pw_kwh = float(pw_cfg.get("kwh_per_m3", 0.4))
    esk_base = float(pw_cfg.get("eskom_base_rate_r_per_kwh", 2.81))
    ic_disc = float(pw_cfg.get("ic_discount_pct", 10.0))
    pw_rate = esk_base * (1.0 - ic_disc / 100.0)
    pw_esc = float(pw_cfg.get("annual_escalation_pct", 10.0)) / 100.0
    pw_start = int(pw_cfg.get("start_month", 18))
    pw_yr = [0.0] * 10
    for mi in range(120):  # M0..M119 (0-based)
        yi = _month_to_year_idx(mi)
        if yi is None or mi < pw_start:
            continue
        c_mld = 0.0
        for ci in range(len(cap_m) - 1):
            if cap_m[ci] <= mi <= cap_m[ci + 1]:
                frac = (mi - cap_m[ci]) / max(cap_m[ci + 1] - cap_m[ci], 1)
                c_mld = cap_v[ci] + frac * (cap_v[ci + 1] - cap_v[ci])
                break
        else:
            if mi >= cap_m[-1]:
                c_mld = cap_v[-1]
        vol_m3 = c_mld * 1000.0
        rate_i = pw_rate * ((1.0 + pw_esc) ** ((mi - pw_start) / 12.0))
        pw_yr[yi] += vol_m3 * pw_kwh * rate_i * 30.44

    # CoE rent
    rent_om_pct = float(rent_cfg.get("om_overhead_pct", 2.0))
    _r_monthly, _, _, _ = compute_coe_rent_monthly_eur(cfg, rent_om_pct)
    _r_monthly_zar = _r_monthly * fx_rate
    rent_esc = float(rent_cfg.get("annual_escalation_pct", 5.0)) / 100.0
    rent_start = int(rent_cfg.get("start_month", 24))
    rent_yr = [0.0] * 10
    for mi in range(120):  # M0..M119 (0-based)
        yi = _month_to_year_idx(mi)
        if yi is None or mi < rent_start:
            continue
        rent_yr[yi] += _r_monthly_zar * ((1.0 + rent_esc) ** ((mi - rent_start) / 12.0))

    # --- Aggregate to annual EUR dicts ---
    month_to_idx = {m: i for i, m in enumerate(months_semi)}
    result = []
    for yi in range(total_years()):
        m1, m2 = yi * 12, yi * 12 + 6  # H1 and H2 start months (0-based)
        si = [month_to_idx[m1], month_to_idx[m2]] if m1 in month_to_idx and m2 in month_to_idx else []

        def _ys(arr, _si=si):
            return sum(arr[i] for i in _si) if _si else 0.0

        gfs = _ys(rev_gf_s) / fx_rate
        bfs = _ys(rev_bf_s) / fx_rate
        reu = _ys(rev_reuse) / fx_rate
        con = _ys(rev_constr) / fx_rate
        agr = _ys(rev_agri) / fx_rate
        blk = bulk_yr[yi] / fx_rate
        om_e = om_yr[yi] / fx_rate
        pw_e = pw_yr[yi] / fx_rate
        rn_e = rent_yr[yi] / fx_rate
        rev = gfs + bfs + reu + con + agr + blk
        ebitda = rev - om_e - pw_e - rn_e
        result.append({
            'year': yi + 1,
            'rev_greenfield_sewage': gfs,
            'rev_brownfield_sewage': bfs,
            'rev_reuse': reu,
            'rev_construction': con,
            'rev_agri': agr,
            'rev_bulk': blk,
            'rev_total': rev,
            'om_cost': om_e,
            'power_cost': pw_e,
            'rent_cost': rn_e,
            'ebitda': ebitda,
        })
    return result
