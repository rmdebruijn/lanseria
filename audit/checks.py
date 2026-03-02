"""Pure audit check functions for the SCLCA financial model.

Each function takes model data and returns a list of check result tuples:
    (section: str, name: str, expected: float, actual: float, delta: float, passed: bool)

All checks read from engine output (EntityResult / ModelResult), NOT from app.py.

Field name convention (post-rename):
    swap_leg_scheduled, swap_leg_accel, swap_leg_bal
    cf_swap_ds, cf_swap_ds_i, cf_swap_ds_p
    bs_swap_liability, cf_swap_accel
"""

from __future__ import annotations

TOLERANCE = 1.0  # EUR


# ── Helper ────────────────────────────────────────────────────────

def _check(results: list, section: str, name: str,
           expected: float, actual: float, tolerance: float = TOLERANCE) -> None:
    """Append a single check result to the results list."""
    delta = abs(expected - actual)
    ok = delta <= tolerance
    results.append((section, name, expected, actual, delta, ok))


# ── Classification ────────────────────────────────────────────────

def classify_check(section: str, name: str) -> str:
    """Return 'arithmetic' or 'model_design' for a check.

    Model design gaps are known structural limitations, not bugs:
    - BS RE != CumPAT + Grants (construction timing, negative DSRA)
    - DSRA identity when DSRA balance is negative
    - IC operational recon (NWL power vs LanRED rev, NWL rent vs TWX rev)
    - SCLCA BS RE != CumNI (DSRA/FEC timing)
    """
    if "RE = CumPAT" in name or "RE = Cum NI" in name:
        return "model_design"
    if "DSRA = CF DSRA" in name or "DSRA Open+Dep+Int" in name:
        return "model_design"
    if "NWL power = LanRED" in name or "NWL rent = TWX" in name:
        return "model_design"
    if "peak balance" in name:
        return "model_design"
    return "arithmetic"


# ── Entity P&L ────────────────────────────────────────────────────

def check_entity_pnl(entity_key: str, annual: list[dict],
                     tax_rate: float = 0.27) -> list[tuple]:
    """P&L identity checks: Rev-OpEx=EBITDA, PBT calc, Tax, PAT."""
    results: list[tuple] = []
    sec = entity_key.upper()

    for a in annual:
        y = a["year"]

        # Rev - OpEx = EBITDA
        expected_ebitda = (a.get("rev_total", 0.0)
                          - a.get("om_cost", 0.0)
                          - a.get("power_cost", 0.0)
                          - a.get("rent_cost", 0.0))
        _check(results, sec, f"Y{y} P&L: Rev - OpEx = EBITDA",
               expected_ebitda, a["ebitda"])

        # EBITDA - Depr - IE + II_DSRA = PBT
        expected_pbt = (a["ebitda"] - a["depr"] - a["ie"]
                        + a.get("ii_dsra", 0.0))
        _check(results, sec, f"Y{y} P&L: EBITDA - Depr - IE + II = PBT",
               expected_pbt, a["pbt"])

        # Tax = max(PBT, 0) * tax_rate
        expected_tax = max(a["pbt"] * tax_rate, 0.0)
        _check(results, sec, f"Y{y} P&L: Tax = max(PBT,0)*27%",
               expected_tax, a["tax"])

        # PBT - Tax = PAT
        _check(results, sec, f"Y{y} P&L: PBT - Tax = PAT",
               a["pbt"] - a["tax"], a["pat"])

    return results


# ── Entity Cash Flow ──────────────────────────────────────────────

def check_entity_cf(entity_key: str, annual: list[dict]) -> list[tuple]:
    """CF checks: DSRA identity, CF ops, CF net = reserve change."""
    results: list[tuple] = []
    sec = entity_key.upper()

    for a in annual:
        y = a["year"]

        # DSRA: Opening + Deposit + Interest = Closing
        dsra_expected = (a["dsra_opening"] + a["dsra_deposit"]
                         + a["dsra_interest"])
        _check(results, sec, f"Y{y} CF: DSRA Open+Dep+Int = Close",
               dsra_expected, a["dsra_bal"])

        # CF Ops = EBITDA + II_DSRA - Tax
        cf_ops_expected = (a["ebitda"] + a.get("ii_dsra", 0.0)
                           - a["cf_tax"])
        _check(results, sec, f"Y{y} CF: CF Ops = EBITDA + II - Tax",
               cf_ops_expected, a["cf_ops"])

        # CF Net = change in reserves (dsra_bal - dsra_opening)
        cf_net_expected = a["dsra_bal"] - a["dsra_opening"]
        _check(results, sec, f"Y{y} CF: Net = reserve change",
               cf_net_expected, a["cf_net"])

    # Sum(CF Net) = DSRA Y10 balance
    _check(results, sec, "CF: Sum(CF Net) = DSRA Y10 bal",
           sum(a["cf_net"] for a in annual), annual[-1]["dsra_bal"])

    return results


# ── Entity Balance Sheet ──────────────────────────────────────────

def check_entity_bs(entity_key: str, annual: list[dict],
                    depreciable_base: float) -> list[tuple]:
    """BS checks: A=L+E, RE=CumPAT+Grants, DSRA, fixed assets."""
    results: list[tuple] = []
    sec = entity_key.upper()

    for a in annual:
        y = a["year"]

        # Assets = Debt + Equity
        _check(results, sec, f"Y{y} BS: Assets = Debt + Equity",
               a["bs_debt"] + a["bs_equity"], a["bs_assets"])

        # RE = CumPAT + Grants (model_design — known gap)
        _check(results, sec, f"Y{y} BS: RE = CumPAT + Grants",
               a["bs_retained_check"], a["bs_retained"])

        # BS DSRA = CF DSRA closing (model_design — known gap)
        _check(results, sec, f"Y{y} BS: DSRA = CF DSRA",
               a["dsra_bal"], a["bs_dsra"])

        # Fixed assets = max(min(cum_capex, depr_base) - acc_depr, 0)
        yi = y - 1  # 0-indexed
        acc_depr = sum(annual[i]["depr"] for i in range(y))
        cum_capex = sum(annual[i].get("cf_capex", 0) for i in range(y))
        expected_fa = max(min(cum_capex, depreciable_base) - acc_depr, 0)
        _check(results, sec, f"Y{y} BS: Fixed Assets = Base - AccDepr",
               expected_fa, a["bs_fixed_assets"])

    return results


# ── Entity Facility ───────────────────────────────────────────────

def check_entity_facility(entity_key: str, sr_schedule: list[dict],
                          mz_schedule: list[dict],
                          waterfall_semi: list[dict],
                          annual: list[dict] | None = None) -> list[tuple]:
    """Facility checks: Y10 closing=0, interest reconcile, sum repaid=sum drawn."""
    results: list[tuple] = []
    sec = entity_key.upper()

    # Y10 closing = 0 (fully amortised)
    sr_last = sr_schedule[-1] if sr_schedule else {}
    mz_last = mz_schedule[-1] if mz_schedule else {}
    _check(results, sec, "Fac: Senior IC Y10 closing = 0",
           0.0, abs(sr_last.get("Closing", 0)))
    _check(results, sec, "Fac: Mezz IC Y10 closing = 0",
           0.0, abs(mz_last.get("Closing", 0)))

    # Sum(waterfall interest) = Sum(P&L interest expense)
    # Both are sourced from the waterfall (single source of truth).
    # The annual ie_sr/ie_mz are patched from the waterfall in Pass 2,
    # so this verifies consistency between WF aggregation and P&L patching.
    # NOTE: We do NOT compare against the raw facility schedule Interest
    # column, because that includes IDC (capitalised, not P&L) and is
    # based on the vanilla schedule (before acceleration reshapes it).
    wf_ie_sr = sum(w.get("ie_half_sr", 0) for w in waterfall_semi)
    wf_ie_mz = sum(w.get("ie_half_mz", 0) for w in waterfall_semi)
    if annual is not None:
        pl_ie_sr = sum(a["ie_sr"] for a in annual)
        pl_ie_mz = sum(a["ie_mz"] for a in annual)
    else:
        # Fallback: compare against facility schedule M24+ (less precise)
        pl_ie_sr = sum(r["Interest"] for r in sr_schedule if r["Month"] >= 24)
        pl_ie_mz = sum(r["Interest"] for r in mz_schedule if r["Month"] >= 24)
    _check(results, sec, "Fac: Sum(WF SR interest) = P&L IE(SR)",
           wf_ie_sr, pl_ie_sr)
    _check(results, sec, "Fac: Sum(WF MZ interest) = P&L IE(MZ)",
           wf_ie_mz, pl_ie_mz)

    # Sum(principal + accel) = Sum(drawn + IDC)
    wf_sr_outflows = sum(
        w.get("sr_prin_sched", 0)
        + w.get("sr_accel_entity", 0)
        for w in waterfall_semi
    )
    wf_sr_inflows = 0.0
    for r in sr_schedule:
        if r["Month"] < 24:
            wf_sr_inflows += abs(r.get("Draw Down", 0)) + abs(r.get("Interest", 0))
    _check(results, sec, "Fac: Sum(SR repaid) = Sum(SR drawn+IDC)",
           wf_sr_inflows, wf_sr_outflows, tolerance=2.0)

    return results


# ── Entity Waterfall Consistency ──────────────────────────────────

def check_entity_waterfall_consistency(entity_key: str, annual: list[dict],
                                       waterfall_semi: list[dict]) -> list[tuple]:
    """Horizontal checks: P&L/CF/BS all read from waterfall consistently."""
    results: list[tuple] = []
    sec = f"{entity_key.upper()} Tabs"

    if not waterfall_semi:
        return results

    n_years = min(10, len(annual))
    n_semi = len(waterfall_semi)

    # --- Balance >= 0 checks (all half-periods) ---
    for hi in range(n_semi):
        w = waterfall_semi[hi]
        _check(results, sec, f"H{hi+1} Fac: SR bal >= 0",
               0.0, min(w.get("sr_ic_bal", 0), 0), tolerance=0.01)
        _check(results, sec, f"H{hi+1} Fac: MZ bal >= 0",
               0.0, min(w.get("mz_ic_bal", 0), 0), tolerance=0.01)

    # --- P&L <-> Waterfall ---
    for yi in range(n_years):
        a = annual[yi]
        y = yi + 1
        h1 = waterfall_semi[yi * 2] if yi * 2 < n_semi else {}
        h2 = waterfall_semi[yi * 2 + 1] if yi * 2 + 1 < n_semi else {}

        # Interest expense
        wf_ie_sr = h1.get("ie_half_sr", 0) + h2.get("ie_half_sr", 0)
        wf_ie_mz = h1.get("ie_half_mz", 0) + h2.get("ie_half_mz", 0)
        _check(results, sec, f"Y{y} P&L<>WF: ie_sr", wf_ie_sr, a["ie_sr"])
        _check(results, sec, f"Y{y} P&L<>WF: ie_mz", wf_ie_mz, a["ie_mz"])

    # --- CF <-> Waterfall ---
    for yi in range(n_years):
        a = annual[yi]
        y = yi + 1
        h1 = waterfall_semi[yi * 2] if yi * 2 < n_semi else {}
        h2 = waterfall_semi[yi * 2 + 1] if yi * 2 + 1 < n_semi else {}

        # Scheduled principal
        wf_sr_prin = h1.get("sr_prin_sched", 0) + h2.get("sr_prin_sched", 0)
        wf_mz_prin = h1.get("mz_prin_sched", 0) + h2.get("mz_prin_sched", 0)
        _check(results, sec, f"Y{y} CF<>WF: cf_pr_sr", wf_sr_prin, a["cf_pr_sr"])
        _check(results, sec, f"Y{y} CF<>WF: cf_pr_mz", wf_mz_prin, a["cf_pr_mz"])

        # Acceleration
        wf_sr_accel = h1.get("sr_accel_entity", 0) + h2.get("sr_accel_entity", 0)
        wf_mz_accel = h1.get("mz_accel_entity", 0) + h2.get("mz_accel_entity", 0)
        _check(results, sec, f"Y{y} CF<>WF: accel_sr",
               wf_sr_accel, a.get("cf_accel_sr", 0))
        _check(results, sec, f"Y{y} CF<>WF: accel_mz",
               wf_mz_accel, a.get("cf_accel_mz", 0))

    # --- BS <-> Waterfall ---
    for yi in range(n_years):
        a = annual[yi]
        y = yi + 1
        h2 = waterfall_semi[yi * 2 + 1] if yi * 2 + 1 < n_semi else {}

        # IC closing balances
        _check(results, sec, f"Y{y} BS<>WF: sr_closing",
               h2.get("sr_ic_bal", 0), a["bs_sr"])
        _check(results, sec, f"Y{y} BS<>WF: mz_closing",
               h2.get("mz_ic_bal", 0), a["bs_mz"])

        # Reserve balances
        _check(results, sec, f"Y{y} BS<>WF: ops_reserve",
               h2.get("ops_reserve_bal", 0), a["bs_ops_reserve"])
        _check(results, sec, f"Y{y} BS<>WF: opco_dsra",
               h2.get("opco_dsra_bal", 0), a["bs_opco_dsra"])
        _check(results, sec, f"Y{y} BS<>WF: mz_div_fd",
               h2.get("mz_div_fd_bal", 0), a["bs_mz_div_fd"])
        _check(results, sec, f"Y{y} BS<>WF: entity_fd",
               h2.get("entity_fd_bal", 0), a["bs_entity_fd"])

    # --- Facilities: full amortisation ---
    if n_semi >= 20:
        w_last = waterfall_semi[-1]
        _check(results, sec, "Fac<>WF: SR IC Y10 = 0",
               0.0, w_last["sr_ic_bal"], tolerance=1.0)
        _check(results, sec, "Fac<>WF: MZ IC Y10 = 0",
               0.0, w_last["mz_ic_bal"], tolerance=1.0)

    return results


# ── SCLCA Holding ─────────────────────────────────────────────────

def check_sclca(holding: dict, entities: dict) -> list[tuple]:
    """SCLCA P&L/CF/BS checks."""
    results: list[tuple] = []
    sec = "SCLCA"
    annual = holding["annual"]

    for a in annual:
        y = a["year"]

        # P&L: IC margin = II_total - IE
        _check(results, sec, f"Y{y} P&L: II - IE = IC margin",
               a["ii_total"] - a["ie"], a["ic_margin_income"])

        # BS: A = L + E
        _check(results, sec, f"Y{y} BS: A = L + E",
               a["bs_liabilities"] + a["bs_equity"], a["bs_assets"])

        # BS: RE = Cum NI (model_design -- known gap)
        _check(results, sec, f"Y{y} BS: RE = Cum NI",
               a["bs_re"], a["bs_equity"])

    return results


# ── IC Reconciliation ─────────────────────────────────────────────

def check_ic_reconciliation(holding: dict, entities: dict) -> list[tuple]:
    """IC recon: SCLCA income=sub expense, balances match."""
    results: list[tuple] = []
    sec = "IC Recon"
    sclca_ann = holding["annual"]
    entity_keys = list(entities.keys())

    for yi in range(10):
        y = yi + 1
        sa = sclca_ann[yi]

        # Sum entity IE (SR, MZ) for this year
        sub_ie_sr = 0.0
        sub_ie_mz = 0.0
        sub_bs_sr = 0.0
        sub_bs_mz = 0.0
        sub_pr = 0.0
        for ek in entity_keys:
            er = entities[ek]
            ea = er.annual[yi]
            sub_ie_sr += ea["ie_sr"]
            sub_ie_mz += ea["ie_mz"]
            sub_bs_sr += ea["bs_sr"]
            sub_bs_mz += ea["bs_mz"]
            sub_pr += (ea.get("cf_pr", 0)
                       + ea.get("cf_accel_sr", 0)
                       + ea.get("cf_accel_mz", 0)
                       + ea.get("cf_grant_accel", ea.get("cf_prepay", 0)))

        # IC Senior interest: SCLCA income = sum(entity IE senior)
        _check(results, sec, f"Y{y}: IC Sr Interest: SCLCA = Subs",
               sa["ii_sr"], sub_ie_sr)

        # IC Mezz interest: SCLCA income = sum(entity IE mezz)
        _check(results, sec, f"Y{y}: IC Mz Interest: SCLCA = Subs",
               sa["ii_mz"], sub_ie_mz)

        # IC Senior balance: SCLCA receivable = sum(entity BS senior)
        _check(results, sec, f"Y{y}: IC Sr Bal: SCLCA = Subs",
               sa["ic_sr_bal"], sub_bs_sr)

        # IC Mezz balance: SCLCA receivable = sum(entity BS mezz)
        _check(results, sec, f"Y{y}: IC Mz Bal: SCLCA = Subs",
               sa["ic_mz_bal"], sub_bs_mz)

    # IC Operating recon: NWL power_cost = LanRED rev (model_design)
    if "nwl" in entities and "lanred" in entities:
        nwl_ann = entities["nwl"].annual
        lr_ann = entities["lanred"].annual
        for yi in range(10):
            y = yi + 1
            nwl_pwr = nwl_ann[yi].get("power_cost", 0)
            lr_rev = lr_ann[yi].get("rev_total", 0)
            if nwl_pwr > 0 or lr_rev > 0:
                _check(results, sec, f"Y{y}: NWL power = LanRED rev",
                       nwl_pwr, lr_rev)

    # IC Operating recon: NWL rent = TWX rev (model_design)
    if "nwl" in entities and "timberworx" in entities:
        nwl_ann = entities["nwl"].annual
        twx_ann = entities["timberworx"].annual
        for yi in range(10):
            y = yi + 1
            nwl_rent = nwl_ann[yi].get("rent_cost", 0)
            twx_rev = twx_ann[yi].get("rev_total", 0)
            if nwl_rent > 0 or twx_rev > 0:
                _check(results, sec, f"Y{y}: NWL rent = TWX rev",
                       nwl_rent, twx_rev)

    return results
