"""SCLCA holding company aggregation.

SCLCA (SC Lanseria Capital Advisors) is the parent entity that:
- Lends IC (intercompany) to NWL, LanRED, and Timberworx
- Earns IC interest income = sum of entity interest expense
- Pays external debt service on senior + mezz

build_sclca_holding(entities, cfg) -> dict
"""

from __future__ import annotations

from engine.config import ModelConfig
from engine.types import EntityResult
from engine.periods import (
    total_years, total_periods, period_start_month, annual_month_range,
    repayment_start_month,
)


def build_sclca_holding(
    entities: dict[str, EntityResult],
    cfg: ModelConfig,
) -> dict:
    """Aggregate entity results into SCLCA holding-company view.

    P&L:
        IC interest income (II) = sum of each entity's interest expense (ie_sr + ie_mz)
        Net Interest Income (NI) = II - External interest expense (IE)

    Cash Flow:
        draw_net = 0 (pass-through: SCLCA draws and on-lends simultaneously)
        grant_accel_net = 0 (pass-through)

    Balance Sheet:
        Assets  = IC loans to subsidiaries (sum sr_ic_bal + mz_ic_bal) + DSRA
        Liabilities = Senior debt + Mezz debt
        Equity  = A - L; RE = Cumulative NI; DSRA = CF DSRA closing

    Returns:
        dict with keys 'annual' (10 annual rows), 'sr_schedule', 'mz_schedule',
        'waterfall_semi', 'waterfall_annual', 'ic_interest_income', 'net_interest'.
    """
    n_years = total_years()
    n_semi = total_periods()

    # ── Aggregate entity IC schedules (SCLCA sees sum of all entities) ──
    # SCLCA's SR and MZ outstanding = sum of entity closing balances
    entity_keys = list(entities.keys())

    # ── Build annual holding rows ──
    annual: list[dict] = []
    cum_ni = 0.0
    dsra_bal = 0.0

    for yi in range(n_years):
        y_start, y_end = annual_month_range(yi)
        a: dict = {"year": yi + 1}

        # ── IC interest income = sum of entity interest expense ──
        ii_sr = 0.0
        ii_mz = 0.0
        for ek, er in entities.items():
            yr = er.annual[yi] if yi < len(er.annual) else {}
            ii_sr += yr.get("ie_sr", 0.0)
            ii_mz += yr.get("ie_mz", 0.0)

        a["ii_sr"] = ii_sr
        a["ii_mz"] = ii_mz
        a["ii_total"] = ii_sr + ii_mz

        # ── External interest expense (on the SCLCA facility — same schedule) ──
        # SCLCA borrows from senior + mezz lenders; interest = facility-level interest
        # The entity IC income should closely match the external IE paid upward.
        # For holding-level P&L: IE = sum of entity IE (mirrored at holding)
        # External Sr IE and Mz IE (facility perspective: no IC margin at holding level)
        ie_sr_ext = 0.0
        ie_mz_ext = 0.0
        for ek, er in entities.items():
            _rep_start = repayment_start_month()
            for r in er.sr_schedule:
                if y_start <= r["Month"] < y_end and r["Month"] >= _rep_start:
                    ie_sr_ext += r["Interest"]
            for r in er.mz_schedule:
                if y_start <= r["Month"] < y_end and r["Month"] >= _rep_start:
                    ie_mz_ext += r["Interest"]

        a["ie_sr"] = ie_sr_ext
        a["ie_mz"] = ie_mz_ext
        a["ie"] = ie_sr_ext + ie_mz_ext

        # ── P&L: Net Interest Income ──
        # At holding level: NI = IC interest income - (external IE already paid by entities)
        # Holding earns the IC margin spread only
        ic_margin = cfg.ic_margin
        a["ic_margin_income"] = a["ii_total"] - a["ie"]
        a["ebitda"] = a["ic_margin_income"]
        a["depr"] = 0.0  # Holding company: no depreciable assets
        a["ebit"] = a["ebitda"]
        # FD interest income: sum of engine-computed ii_dsra from each subsidiary
        a["ii_dsra"] = sum(
            er.annual[yi].get("ii_dsra", 0.0)
            for er in entities.values() if yi < len(er.annual)
        )
        a["pbt"] = a["ebit"] + a["ii_dsra"]
        a["tax"] = max(a["pbt"] * cfg.tax_rate, 0.0)
        a["pat"] = a["pbt"] - a["tax"]
        a["ni"] = a["pat"]  # Net interest margin retained

        # ── IC loan balances (assets on SCLCA BS = IC outstanding to subsidiaries) ──
        # Use waterfall-sourced closing balances from entity annual rows
        ic_sr_bal = 0.0
        ic_mz_bal = 0.0
        for ek, er in entities.items():
            yr = er.annual[yi] if yi < len(er.annual) else {}
            ic_sr_bal += yr.get("bs_sr", 0.0)
            ic_mz_bal += yr.get("bs_mz", 0.0)

        a["ic_sr_bal"] = ic_sr_bal
        a["ic_mz_bal"] = ic_mz_bal
        a["ic_loans_total"] = ic_sr_bal + ic_mz_bal

        # ── External debt liabilities (SCLCA owes senior + mezz lenders) ──
        # Mirror entity IC balances: SCLCA lends what it borrows
        a["sr_debt"] = ic_sr_bal  # External Senior = sum entity Sr IC
        a["mz_debt"] = ic_mz_bal  # External Mezz = sum entity Mz IC

        # ── DSRA (entity FD reserves roll up to holding for display) ──
        dsra_all = 0.0
        for ek, er in entities.items():
            wf_yr = er.waterfall_annual[yi] if yi < len(er.waterfall_annual) else {}
            dsra_all += wf_yr.get("entity_fd_bal", 0.0) + wf_yr.get("opco_dsra_bal", 0.0)

        a["dsra_closing"] = dsra_all

        # ── Cash Flow: pass-through structure ──
        a["cf_draw_net"] = 0.0     # SCLCA draws = on-lends simultaneously
        a["cf_grant_accel_net"] = 0.0   # Grant acceleration passes through from entities
        a["cf_prepay_net"] = 0.0       # Backward-compat alias
        a["cf_ii"] = a["ii_total"]
        a["cf_ie"] = a["ie"]
        a["cf_net_interest"] = a["cf_ii"] - a["cf_ie"]
        a["cf_tax"] = a["tax"]
        a["cf_ops"] = a["cf_net_interest"] + a["ii_dsra"] - a["cf_tax"]

        # ── BS: A = L + E ──
        a["dsra_opening"] = dsra_bal
        a["dsra_interest"] = a["ii_dsra"]  # Engine-sourced; mirrors entity loop pattern
        a["dsra_deposit"] = a["cf_ops"] - a["ii_dsra"]
        dsra_bal += a["cf_ops"]
        a["dsra_bal"] = dsra_bal

        total_assets = a["ic_loans_total"] + max(dsra_bal, 0.0)
        total_liabilities = a["sr_debt"] + a["mz_debt"]
        equity = total_assets - total_liabilities

        cum_ni += a["ni"]

        a["bs_assets"] = total_assets
        a["bs_liabilities"] = total_liabilities
        a["bs_equity"] = equity
        a["bs_re"] = cum_ni           # Retained earnings = cumulative NI
        a["bs_dsra"] = max(dsra_bal, 0.0)
        a["bs_gap"] = equity - cum_ni  # Should tend to 0 when model is balanced

        annual.append(a)

    # ── D1: Aggregate facility schedules ──
    sr_schedule_agg: list[dict] = []
    mz_schedule_agg: list[dict] = []
    for ek, er in entities.items():
        sr_schedule_agg.extend(er.sr_schedule)
        mz_schedule_agg.extend(er.mz_schedule)

    # ── D2: Consolidated DSCR ──
    dscr_values: list[float | None] = []
    for yi in range(n_years):
        total_cf_ops = sum(
            er.annual[yi].get("cf_ops", 0)
            for er in entities.values() if yi < len(er.annual)
        )
        total_ds = sum(
            er.annual[yi].get("cf_ds", 0) + er.annual[yi].get("cf_swap_ds", 0)
            for er in entities.values() if yi < len(er.annual)
        )
        dscr_values.append(total_cf_ops / total_ds if total_ds > 0 else None)

    dscr_numeric = [d for d in dscr_values if d is not None]
    dscr_min = min(dscr_numeric) if dscr_numeric else None
    dscr_avg = sum(dscr_numeric) / len(dscr_numeric) if dscr_numeric else None

    # ── D3: Consolidated view with IC elimination ──
    consolidated: list[dict] = []
    for yi in range(n_years):
        c: dict = {"year": yi + 1}

        # Sum entity P&L items
        c["rev_total"] = sum(
            er.annual[yi].get("rev_total", 0)
            for er in entities.values() if yi < len(er.annual)
        )
        c["ebitda"] = sum(
            er.annual[yi].get("ebitda", 0)
            for er in entities.values() if yi < len(er.annual)
        )

        # IC elimination: NWL→LanRED power is IC revenue for LanRED, cost for NWL
        # At consolidated level, these cancel out
        lr = entities.get("lanred")
        ic_rev_elim = 0.0
        if lr and yi < len(lr.annual):
            ic_rev_elim = lr.annual[yi].get("rev_ic_nwl", 0.0)

        # TWX CoE rent: NWL pays rent to TWX → IC at group level
        twx = entities.get("timberworx")
        ic_rent_elim = 0.0
        if twx and yi < len(twx.annual):
            ic_rent_elim = twx.annual[yi].get("rev_lease", 0.0)

        c["ic_revenue_elim"] = ic_rev_elim + ic_rent_elim
        c["cons_rev"] = c["rev_total"] - c["ic_revenue_elim"]
        c["cons_ebitda"] = c["ebitda"] - c["ic_revenue_elim"]

        # Interest: only external (IC interest income = IC interest expense → nets to 0)
        c["ie_external"] = annual[yi].get("ie", 0)  # SCLCA external IE
        c["ii_dsra"] = sum(
            er.annual[yi].get("ii_dsra", 0)
            for er in entities.values() if yi < len(er.annual)
        )

        # BS: sum entity assets, eliminate IC loans
        c["cons_assets"] = sum(
            er.annual[yi].get("bs_assets", 0)
            for er in entities.values() if yi < len(er.annual)
        )
        # IC loan elimination: SCLCA asset = entity liability
        c["ic_loan_elim"] = annual[yi].get("ic_loans_total", 0)
        c["cons_assets_net"] = c["cons_assets"] - c["ic_loan_elim"]

        # External debt = SCLCA's sr_debt + mz_debt
        c["cons_sr_debt"] = annual[yi].get("sr_debt", 0)
        c["cons_mz_debt"] = annual[yi].get("mz_debt", 0)
        c["cons_debt"] = c["cons_sr_debt"] + c["cons_mz_debt"]

        # OD elimination: NWL asset = LanRED liability → nets to 0
        nwl_er = entities.get("nwl")
        nwl_od = 0.0
        if nwl_er and yi < len(nwl_er.waterfall_annual):
            nwl_od = nwl_er.waterfall_annual[yi].get("od_bal", 0)
        c["ic_od_elim"] = nwl_od

        c["cons_equity"] = c["cons_assets_net"] - c["cons_debt"]
        c["dscr"] = dscr_values[yi]

        consolidated.append(c)

    # ── Semi-annual aggregate waterfall (20 rows — sum of entity waterfalls) ──
    waterfall_semi: list[dict] = []
    # D4: Keys where naive sum double-counts (NWL asset + LanRED liability)
    _od_net_keys = frozenset({"od_bal"})
    for hi in range(n_semi):
        row: dict = {}
        for ek, er in entities.items():
            if hi < len(er.waterfall_semi):
                wf = er.waterfall_semi[hi]
                for k, v in wf.items():
                    if isinstance(v, (int, float)):
                        row[k] = row.get(k, 0.0) + v
                    elif isinstance(v, bool):
                        row[k] = row.get(k, False) or v
                    else:
                        row[k] = v
        # D4: Replace summed od_bal with net (should be ~0 after IC elimination)
        nwl_er = entities.get("nwl")
        lr_er = entities.get("lanred")
        nwl_od_semi = nwl_er.waterfall_semi[hi].get("od_bal", 0) if nwl_er and hi < len(nwl_er.waterfall_semi) else 0
        lr_od_semi = lr_er.waterfall_semi[hi].get("od_bal", 0) if lr_er and hi < len(lr_er.waterfall_semi) else 0
        row["od_bal_nwl"] = nwl_od_semi
        row["od_bal_lanred"] = lr_od_semi
        row["od_bal_net"] = 0.0  # NWL asset = LanRED liability → nets to 0 at group level
        waterfall_semi.append(row)

    # ── Annual waterfall (aggregated) ──
    waterfall_annual: list[dict] = []
    for yi in range(n_years):
        row: dict = {}
        for ek, er in entities.items():
            if yi < len(er.waterfall_annual):
                wf = er.waterfall_annual[yi]
                for k, v in wf.items():
                    if isinstance(v, (int, float)):
                        row[k] = row.get(k, 0.0) + v
                    elif isinstance(v, bool):
                        row[k] = row.get(k, False) or v
                    else:
                        row[k] = v
        # D4: OD net at annual level
        nwl_od_ann = nwl_er.waterfall_annual[yi].get("od_bal", 0) if nwl_er and yi < len(nwl_er.waterfall_annual) else 0
        lr_od_ann = lr_er.waterfall_annual[yi].get("od_bal", 0) if lr_er and yi < len(lr_er.waterfall_annual) else 0
        row["od_bal_nwl"] = nwl_od_ann
        row["od_bal_lanred"] = lr_od_ann
        row["od_bal_net"] = 0.0
        waterfall_annual.append(row)

    # ── IC semi-annual aggregate (20 periods) ──
    ic_semi: list[dict] = []
    for hi in range(n_semi):
        half_month = period_start_month(hi)
        ic_sr = 0.0
        ic_mz = 0.0
        for ek, er in entities.items():
            for r in er.sr_schedule:
                if r["Month"] == half_month:
                    ic_sr += r["Interest"] + abs(r.get("Principle", 0))
            for r in er.mz_schedule:
                if r["Month"] == half_month:
                    ic_mz += r["Interest"] + abs(r.get("Principle", 0))
        ic_semi.append({
            "period": hi + 1,
            "month": half_month,
            "ic_sr_pi": ic_sr,
            "ic_mz_pi": ic_mz,
            "ic_total_pi": ic_sr + ic_mz,
        })

    return {
        "annual": annual,
        "sr_schedule": sr_schedule_agg,
        "mz_schedule": mz_schedule_agg,
        "waterfall_semi": waterfall_semi,
        "waterfall_annual": waterfall_annual,
        "ic_semi": ic_semi,
        "dscr_values": dscr_values,
        "dscr_min": dscr_min,
        "dscr_avg": dscr_avg,
        "consolidated": consolidated,
        "total_ic_interest_income": sum(a["ii_total"] for a in annual),
        "total_net_interest": sum(a["ic_margin_income"] for a in annual),
        "entity_keys": entity_keys,
    }
