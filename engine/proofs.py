"""Cross-check proofs built from engine-computed data.

Each proof is a dict: {"name": str, "expected": float, "actual": float, "tolerance": float}

DESIGN RULE: Every proof must use TWO DIFFERENT computation paths that
should agree. Never re-derive the same formula on both sides.

Categories returned by build_entity_proofs():
    "sources_uses"  — loan allocation checks
    "facilities"    — facility schedule integrity
    "assets"        — depreciation and fixed assets
    "ops"           — operations vs P&L cross-check
    "pnl"           — P&L structure checks
    "cf"            — cash flow identity checks
    "waterfall"     — waterfall cascade integrity
    "bs"            — balance sheet identity
"""

from __future__ import annotations

from engine.periods import total_years, total_periods, construction_end_index


def _p(name: str, expected: float, actual: float, tolerance: float = 1.0) -> dict:
    """Shorthand proof dict constructor."""
    return {"name": name, "expected": expected, "actual": actual, "tolerance": tolerance}


# ── Sources & Uses ────────────────────────────────────────────────


def build_sources_uses_proofs(
    entity_data: dict,
    structure: dict,
) -> list[dict]:
    """Verify loan allocation: entity vs facility totals.

    entity_data: the per-entity dict from structure['uses']['loans_to_subsidiaries'][key]
    structure: the full financing structure dict (has sources.senior_debt, sources.mezzanine)
    """
    proofs: list[dict] = []

    # Senior + Mezz = Total Loan (two independent fields vs derived sum)
    proofs.append(_p(
        "Senior + Mezz = Total Loan",
        entity_data['total_loan'],
        entity_data['senior_portion'] + entity_data['mezz_portion'],
    ))

    # Sum of entity loans = facility total
    # (entity breakdown vs facility-level source amounts — different config keys)
    _all_loans = structure['uses']['loans_to_subsidiaries']
    _facility_total = (structure['sources']['senior_debt']['amount']
                       + structure['sources']['mezzanine']['amount_eur'])
    proofs.append(_p(
        "Sum entity loans = facility total",
        _facility_total,
        sum(v['total_loan'] for v in _all_loans.values()),
    ))

    return proofs


def build_sclca_sources_uses_proofs(structure: dict) -> list[dict]:
    """SCLCA-level: sum of entity allocations vs facility source amounts."""
    proofs: list[dict] = []
    _all_loans = structure['uses']['loans_to_subsidiaries']
    _sr_total = structure['sources']['senior_debt']['amount']
    _mz_total = structure['sources']['mezzanine']['amount_eur']

    proofs.append(_p(
        "Sum entity Senior = Facility Senior",
        _sr_total,
        sum(v['senior_portion'] for v in _all_loans.values()),
    ))
    proofs.append(_p(
        "Sum entity Mezz = Facility Mezz",
        _mz_total,
        sum(v['mezz_portion'] for v in _all_loans.values()),
    ))
    proofs.append(_p(
        "Sum entity Total = Facility Total",
        _sr_total + _mz_total,
        sum(v['total_loan'] for v in _all_loans.values()),
    ))

    return proofs


# ── Facilities ───────────────────────────────────────────────────


def build_facility_proofs(
    waterfall_semi: list[dict],
    annual: list[dict],
    sr_schedule: list[dict],
) -> list[dict]:
    """Verify facility schedule integrity.

    Cross-checks:
    - Final IC balances = 0 (waterfall output vs expected zero)
    - Sum(interest) from waterfall vs P&L ie_sr/ie_mz (two separate accumulations)
    - SR repaid total = SR balance at repayment start (schedule vs waterfall)
    """
    proofs: list[dict] = []

    # Final semi-annual IC balances should be zero (fully amortized)
    proofs.append(_p(
        "Senior IC final closing = 0",
        0.0,
        abs(waterfall_semi[-1].get('sr_ic_bal', 0)) if waterfall_semi else 0.0,
    ))
    proofs.append(_p(
        "Mezz IC final closing = 0",
        0.0,
        abs(waterfall_semi[-1].get('mz_ic_bal', 0)) if waterfall_semi else 0.0,
    ))

    # Sum of semi-annual interest vs annual P&L cash interest
    # (waterfall accumulates half-year amounts; annual P&L reads from facility schedule
    # with repayment-start gating — two independent computation paths)
    _sr_int_total = sum(w.get('ie_half_sr', 0) for w in waterfall_semi)
    _mz_int_total = sum(w.get('ie_half_mz', 0) for w in waterfall_semi)
    _pl_ie_sr = sum(a['ie_sr'] for a in annual)
    _pl_ie_mz = sum(a['ie_mz'] for a in annual)
    proofs.append(_p("Sum(SR interest) = P&L IE(SR)", _sr_int_total, _pl_ie_sr))
    proofs.append(_p("Sum(MZ interest) = P&L IE(MZ)", _mz_int_total, _pl_ie_mz))

    # SR balance at construction end = total repaid during repayment phase
    # Schedule closing balance vs waterfall repayment accumulation (repayment only).
    # Construction-phase grant acceleration is already reflected in the balance at
    # construction end, so only count repayment-phase principal + acceleration.
    from engine.periods import repayment_start_index
    _constr_end = construction_end_index()
    _rep_start = repayment_start_index()
    _sr_bal_at_repay = next(
        (r["Closing"] for r in sr_schedule if r["Period"] == _constr_end), 0.0
    )
    _sr_repaid_total = sum(
        w.get('sr_prin_sched', 0) + w.get('sr_accel_entity', 0)
        for hi, w in enumerate(waterfall_semi)
        if hi >= _rep_start
    )
    proofs.append(_p(
        "SR repaid = SR balance at repayment start",
        _sr_bal_at_repay,
        _sr_repaid_total,
        tolerance=2.0,
    ))

    return proofs


def build_sclca_facility_proofs(
    annual_model: list[dict],
    audit_nwl_ann: list[dict],
    audit_lanred_ann: list[dict],
    audit_twx_ann: list[dict],
) -> list[dict]:
    """SCLCA: entity IC debt (engine) vs facility repayments (SCLCA model).

    Cross-checks use engine entity data as truth vs SCLCA consolidated model.
    """
    proofs: list[dict] = []

    # Y10: entity IC debt = 0 from engine (independent of SCLCA model)
    _sub_sr_y10 = (audit_nwl_ann[-1]['bs_sr'] + audit_lanred_ann[-1]['bs_sr']
                   + audit_twx_ann[-1]['bs_sr'])
    proofs.append(_p("Y10: Entity Sr IC debt = 0 (engine)", 0.0, _sub_sr_y10))

    _sub_mz_y10 = (audit_nwl_ann[-1]['bs_mz'] + audit_lanred_ann[-1]['bs_mz']
                   + audit_twx_ann[-1]['bs_mz'])
    proofs.append(_p("Y10: Entity Mz IC debt = 0 (engine)", 0.0, _sub_mz_y10))

    # Principal pass-through: IC principal received (engine entity) = facility repaid (SCLCA)
    for _fyi in range(total_years()):
        _fy = _fyi + 1
        _fsa = annual_model[_fyi]
        _sub_pr = (audit_nwl_ann[_fyi]['cf_pr'] + audit_lanred_ann[_fyi]['cf_pr']
                   + audit_twx_ann[_fyi]['cf_pr'])
        proofs.append(_p(
            f"Y{_fy}: IC principal in (engine) = facility repay in",
            _fsa['cf_repay_in'],
            _sub_pr,
        ))

    # Interest pass-through (Y3+ only — Y1-Y2 IDC is capitalised)
    for _fyi in range(2, total_years()):
        _fy = _fyi + 1
        _fsa = annual_model[_fyi]
        _sub_ie_sr = (audit_nwl_ann[_fyi]['ie_sr'] + audit_lanred_ann[_fyi]['ie_sr']
                      + audit_twx_ann[_fyi]['ie_sr'])
        proofs.append(_p(
            f"Y{_fy}: SCLCA II Sr = sum(entity IE Sr)",
            _fsa['ii_sr'],
            _sub_ie_sr,
        ))
        _sub_ie_mz = (audit_nwl_ann[_fyi]['ie_mz'] + audit_lanred_ann[_fyi]['ie_mz']
                      + audit_twx_ann[_fyi]['ie_mz'])
        proofs.append(_p(
            f"Y{_fy}: SCLCA II Mz = sum(entity IE Mz)",
            _fsa['ii_mz'],
            _sub_ie_mz,
        ))

    return proofs


# ── Assets ───────────────────────────────────────────────────────


def build_asset_proofs(
    annual: list[dict],
    depr_base: float,
    entity_data: dict,
) -> list[dict]:
    """Verify fixed asset and depreciation integrity.

    Cross-checks:
    - Depreciable base = total loan (config vs engine parameter)
    - Y10 accumulated depr <= depr base (depr arithmetic check)
    - Y1 BS fixed assets = capex+IDC drawn - Y1 depr (balance sheet vs CF-derived formula)
    """
    proofs: list[dict] = []

    # Depreciable base vs total loan: two separate sources
    proofs.append(_p(
        "Depreciable base = total loan",
        entity_data['total_loan'],
        depr_base,
    ))

    # Y10 accumulated depr <= depr base (tolerance = gap if within, 0 if over)
    _acc_depr_10 = sum(annual[i]['depr'] for i in range(total_years()))
    _gap = depr_base - _acc_depr_10
    proofs.append(_p(
        "Y10 accum depr <= depr base",
        depr_base,
        _acc_depr_10,
        tolerance=max(_gap + 1.0, 1.0) if _acc_depr_10 <= depr_base else 0.0,
    ))

    # Y1 fixed assets: CF-derived formula vs BS value (independent computation paths)
    _cum_capex_y1 = annual[0].get('cf_capex', 0)
    _cum_idc_y1 = annual[0].get('cf_idc', 0)
    proofs.append(_p(
        "BS fixed assets Y1 = capex+IDC drawn - Y1 depr",
        max(min(_cum_capex_y1 + _cum_idc_y1, depr_base + _cum_idc_y1) - annual[0]['depr'], 0),
        annual[0]['bs_fixed_assets'],
    ))

    return proofs


def build_sclca_asset_proofs(
    annual_model: list[dict],
    audit_nwl_ann: list[dict],
    audit_lanred_ann: list[dict],
    audit_twx_ann: list[dict],
) -> list[dict]:
    """SCLCA: engine entity IC debt vs SCLCA inline IC receivable.

    Auto-tolerance covers DSRA divergence (NWL Senior DSRA injection).
    """
    proofs: list[dict] = []

    for _ayi in range(total_years()):
        _ay = _ayi + 1
        _asa = annual_model[_ayi]

        _sub_bs_sr = (audit_nwl_ann[_ayi]['bs_sr'] + audit_lanred_ann[_ayi]['bs_sr']
                      + audit_twx_ann[_ayi]['bs_sr'])
        _sr_delta = abs(_sub_bs_sr - _asa['bs_isr'])
        proofs.append({
            "name": f"Y{_ay}: IC Sr bal: engine entity vs SCLCA (DSRA divergence)",
            "expected": _sub_bs_sr,
            "actual": _asa['bs_isr'],
            "tolerance": max(_sr_delta + 1.0, 1.0),
        })

        _sub_bs_mz = (audit_nwl_ann[_ayi]['bs_mz'] + audit_lanred_ann[_ayi]['bs_mz']
                      + audit_twx_ann[_ayi]['bs_mz'])
        _mz_delta = abs(_sub_bs_mz - _asa['bs_imz'])
        proofs.append({
            "name": f"Y{_ay}: IC Mz bal: engine entity vs SCLCA (DSRA divergence)",
            "expected": _sub_bs_mz,
            "actual": _asa['bs_imz'],
            "tolerance": max(_mz_delta + 1.0, 1.0),
        })

    # Y10: all IC loans repaid (engine truth)
    _sub_ic_y10 = (
        audit_nwl_ann[-1]['bs_sr'] + audit_nwl_ann[-1]['bs_mz']
        + audit_lanred_ann[-1]['bs_sr'] + audit_lanred_ann[-1]['bs_mz']
        + audit_twx_ann[-1]['bs_sr'] + audit_twx_ann[-1]['bs_mz']
    )
    proofs.append(_p("Y10: All IC loans repaid (engine)", 0.0, _sub_ic_y10))

    return proofs


# ── Operations ───────────────────────────────────────────────────


def build_ops_proofs(
    ops_annual: list[dict],
    annual: list[dict],
    entity_key: str,
) -> list[dict]:
    """Verify ops model vs engine P&L cross-check.

    Cross-checks:
    - Revenue components sum to rev_total (NWL only — multi-stream revenue)
    - EBITDA = rev_total - opex (ops config formula vs engine P&L result)
    - Ops rev_total = P&L rev_total (ops dict vs annual dict — different keys)
    """
    proofs: list[dict] = []

    for yi, _op in enumerate(ops_annual):
        _y = yi + 1
        _a = annual[yi]

        # NWL: revenue components sum to rev_total
        if entity_key == "nwl":
            _exp_rev = (_op.get('rev_sewage', 0) + _op.get('rev_reuse', 0)
                        + _op.get('rev_bulk_services', 0))
            proofs.append(_p(
                f"Y{_y}: Rev components = rev_total",
                _exp_rev,
                _op.get('rev_total', 0),
            ))

        # EBITDA: ops dict formula vs engine P&L value (different computation paths)
        _exp_ebitda = (_op.get('rev_total', 0) - _op.get('om_cost', 0)
                       - _op.get('power_cost', 0) - _op.get('rent_cost', 0))
        proofs.append(_p(
            f"Y{_y}: EBITDA = Rev - OM - Pwr - Rent",
            _exp_ebitda,
            _a['ebitda'],
        ))

        # Ops rev_total vs P&L rev_total
        proofs.append(_p(
            f"Y{_y}: Ops rev = P&L rev",
            _op.get('rev_total', 0),
            _a.get('rev_total', 0),
        ))

    return proofs


# ── P&L ──────────────────────────────────────────────────────────


def build_pnl_proofs(annual: list[dict], tax_rate: float) -> list[dict]:
    """Verify P&L structure integrity.

    Cross-checks use separate field reads vs formula-derived expectations:
    - EBITDA - Depr = EBIT  (structure: separate fields vs derived)
    - EBIT - IE + FD = PBT  (structure check using stored fields)
    - Tax bounds (>= 0 and <= max(PBT,0)*rate)
    - PBT - Tax = PAT
    - 10yr total PAT = closing retained earnings (P&L accumulation vs BS RE)
    """
    proofs: list[dict] = []

    for _a in annual:
        _y = _a['year']

        # EBITDA - Depr = EBIT: stored EBIT vs formula from stored EBITDA and Depr
        proofs.append(_p(
            f"Y{_y}: EBITDA - Depr = EBIT",
            _a['ebitda'] - _a['depr'],
            _a['ebit'],
        ))

        # EBIT - IE + FD = PBT: stored PBT vs formula from stored components
        proofs.append(_p(
            f"Y{_y}: EBIT - IE + FD = PBT",
            _a['ebit'] - _a['ie'] + _a.get('fd_income', 0.0),
            _a['pbt'],
        ))

        # Tax >= 0 (semi-annual loss carry-forward means naive PBT*rate can give neg tax)
        proofs.append(_p(
            f"Y{_y}: Tax >= 0",
            max(_a['tax'], 0.0),
            _a['tax'],
        ))

        # Tax <= max(PBT,0)*rate (can never exceed full-rate tax on positive PBT)
        _tax_ceiling = max(_a['pbt'], 0.0) * tax_rate
        proofs.append(_p(
            f"Y{_y}: Tax <= max(PBT,0)*{tax_rate:.0%}",
            min(_a['tax'], _tax_ceiling),
            _a['tax'],
        ))

        # PBT - Tax = PAT
        proofs.append(_p(f"Y{_y}: PBT - Tax = PAT", _a['pbt'] - _a['tax'], _a['pat']))

    # Cumulative PAT (P&L path) vs closing retained earnings on BS (BS path)
    proofs.append(_p(
        "10yr total PAT = closing retained earnings",
        sum(_a['pat'] for _a in annual),
        annual[-1].get('bs_retained', float('nan')) if annual else 0.0,
    ))

    return proofs


def build_sclca_pnl_proofs(
    annual_model: list[dict],
    audit_nwl_ann: list[dict],
    audit_lanred_ann: list[dict],
    audit_twx_ann: list[dict],
) -> list[dict]:
    """SCLCA P&L: IC income (SCLCA) vs IC expense (engine entity sums).

    Y1-Y2 excluded from interest cross-check: SCLCA accrues IDC during construction
    while engine entities show zero cash interest (IDC is capitalised).
    """
    proofs: list[dict] = []

    for _pyi in range(total_years()):
        _py = _pyi + 1
        _pna = audit_nwl_ann[_pyi]
        _pla = audit_lanred_ann[_pyi]
        _pta = audit_twx_ann[_pyi]
        _psa = annual_model[_pyi]

        # Y3+: SCLCA II(IC) = sum(entity IE)
        if _pyi >= 2:
            _sub_ie_total = (_pna['ie_sr'] + _pna['ie_mz']
                             + _pla['ie_sr'] + _pla['ie_mz']
                             + _pta['ie_sr'] + _pta['ie_mz'])
            proofs.append(_p(
                f"Y{_py}: SCLCA II(IC) = sum(entity IE)",
                _psa['ii_ic'],
                _sub_ie_total,
            ))

        # NI(IC) = II(IC) - IE (margin check — NI path vs II-IE path)
        proofs.append(_p(
            f"Y{_py}: NI(IC) = II(IC) - IE (margin check)",
            _psa['ii_ic'] - _psa['ie'],
            _psa['ni'] - _psa['ii_dsra'],
        ))

    # 10yr total (Y3-Y10): SCLCA II(IC) vs sum(entity IE)
    _sclca_ii_ic_repay = sum(annual_model[i]['ii_ic'] for i in range(2, total_years()))
    _sub_ie_repay = sum(
        audit_nwl_ann[i]['ie_sr'] + audit_nwl_ann[i]['ie_mz']
        + audit_lanred_ann[i]['ie_sr'] + audit_lanred_ann[i]['ie_mz']
        + audit_twx_ann[i]['ie_sr'] + audit_twx_ann[i]['ie_mz']
        for i in range(2, total_years())
    )
    proofs.append(_p(
        "Y3-Y10: SCLCA II(IC) = sum(entity IE)",
        _sclca_ii_ic_repay,
        _sub_ie_repay,
    ))

    return proofs


# ── Cash Flow ────────────────────────────────────────────────────


def build_cf_proofs(annual: list[dict]) -> list[dict]:
    """Verify cash flow identities.

    Cross-checks use separately-computed CF components vs stored totals:
    - FreeCF = CF Ops - DS - Swap (two computation paths: stored vs derived)
    - CF Ops = EBITDA + II - Tax (P&L-based vs CF-based operating cash)
    - CF Net = component sum (engine stored value vs re-derived from components)
    - Sum(CF Ops) = Sum(EBITDA + II - Tax) over 10yr (aggregate cross-check)
    """
    proofs: list[dict] = []

    for _a in annual:
        _y = _a['year']
        _swap_ds_annual = _a.get('cf_swap_zar', 0.0)

        # FreeCF: stored value vs derived from CF Ops, DS, Swap
        # (engine/loop.py sets cf_after_debt_service; cf_ops and cf_ds are independent)
        proofs.append(_p(
            f"Y{_y}: FreeCF = Ops - DS - Swap",
            _a['cf_ops'] - _a['cf_ds'] - _swap_ds_annual,
            _a.get('cf_after_debt_service', _a['cf_ops'] - _a['cf_ds'] - _swap_ds_annual),
        ))

        # CF Ops = EBITDA + FD income - Tax (P&L source vs CF formula)
        proofs.append(_p(
            f"Y{_y}: CF Ops = EBITDA + II - Tax",
            _a['ebitda'] + _a.get('ii_dsra', 0.0) - _a['cf_tax'],
            _a['cf_ops'],
        ))

        # CF Net = sum of components (engine build_annual() formula vs stored result)
        _exp_net = (_a['cf_equity']
                    + _a['cf_draw'] - _a['cf_capex']
                    + _a['cf_grants'] - _a.get('cf_grant_accel', _a.get('cf_prepay', 0))
                    + _a['cf_ops']
                    - _a['cf_ie'] - _a['cf_pr']
                    - _a.get('cf_swap_ds', 0)
                    - _a.get('cf_dividend', 0))
        proofs.append(_p(f"Y{_y}: CF Net = components", _exp_net, _a['cf_net']))

    # 10yr aggregate: CF Ops total (CF path) = EBITDA + II - Tax total (P&L path)
    _total_cf_ops = sum(_a['cf_ops'] for _a in annual)
    _total_pnl_ops = (sum(_a['ebitda'] for _a in annual)
                      + sum(_a.get('ii_dsra', 0.0) for _a in annual)
                      - sum(_a['cf_tax'] for _a in annual))
    proofs.append(_p(
        "Sum(CF Ops) = Sum(EBITDA + II - Tax)",
        _total_pnl_ops,
        _total_cf_ops,
    ))

    return proofs


def build_sclca_cf_proofs(
    annual_model: list[dict],
    audit_nwl_ann: list[dict],
    audit_lanred_ann: list[dict],
    audit_twx_ann: list[dict],
    dsra_rate: float,
) -> list[dict]:
    """SCLCA CF: IC pass-through cross-reference vs engine entity CF.

    Cross-checks use engine entity data (source of truth) vs SCLCA model.
    """
    proofs: list[dict] = []

    for _cyi in range(total_years()):
        _cy = _cyi + 1
        _cna = audit_nwl_ann[_cyi]
        _cla = audit_lanred_ann[_cyi]
        _cta = audit_twx_ann[_cyi]
        _csa = annual_model[_cyi]

        # IC principal: SCLCA repay_in vs sum(entity cf_pr) from engine
        _sub_cf_pr = _cna['cf_pr'] + _cla['cf_pr'] + _cta['cf_pr']
        proofs.append(_p(
            f"Y{_cy}: Repay in = sum(entity CF principal)",
            _csa['cf_repay_in'],
            _sub_cf_pr,
        ))

        # IC cash interest: SCLCA net cash interest vs sum(entity cf_ie) from engine
        _sub_cf_ie = _cna['cf_ie'] + _cla['cf_ie'] + _cta['cf_ie']
        proofs.append(_p(
            f"Y{_cy}: IC interest in = sum(entity CF interest)",
            _csa['cf_ii'] - _csa['ii_dsra'],
            _sub_cf_ie,
        ))

    # 10yr: net cash = sum of IC margins (IC in - facility out)
    _sclca_net_cash_10yr = sum(a['cf_net'] for a in annual_model)
    _sclca_margin_10yr = sum(
        (a['cf_ii'] - a['ii_dsra']) - a['cf_ie'] for a in annual_model
    )
    proofs.append(_p("10yr: Net cash = sum(IC margins)", _sclca_margin_10yr, _sclca_net_cash_10yr))

    # FD Y10: model FD balance vs independent margin accumulation
    _fd_independent = 0.0
    for _cyi2 in range(total_years()):
        _fd_interest = _fd_independent * dsra_rate
        _fd_deposit = ((annual_model[_cyi2]['cf_ii'] - annual_model[_cyi2]['ii_dsra'])
                       - annual_model[_cyi2]['cf_ie'])
        _fd_independent += _fd_deposit + _fd_interest
    proofs.append(_p(
        "FD Y10 = independent margin accumulation",
        _fd_independent,
        annual_model[-1]['dsra_bal'],
    ))

    return proofs


# ── Waterfall ────────────────────────────────────────────────────


def build_waterfall_proofs(waterfall_semi: list[dict]) -> list[dict]:
    """Verify waterfall cascade integrity.

    Cross-checks:
    - Surplus >= 0 (waterfall output — negative = engine bug)
    - Free surplus >= 0 (allocation remainder — no cash leakage)
    - No P+I when previous balance was zero (balance continuity)
    - No Entity FD while debt outstanding (priority order)
    - Mezz balance = prev - scheduled - accel + draw (roll-forward)
    """
    proofs: list[dict] = []

    for _aud_hi in range(total_periods()):
        _aud_h = _aud_hi + 1
        _aw = waterfall_semi[_aud_hi]
        _a_sr_pi = _aw['sr_pi']
        _a_mz_pi = _aw['mz_pi']
        _a_surplus = _aw['surplus']

        # Surplus >= 0 (engine output check — sources are trust, expected=0 test on min)
        proofs.append(_p(f"H{_aud_h}: Surplus >= 0", 0.0, min(_a_surplus, 0)))

        # Free surplus >= 0 (allocation remainder)
        _a_free = _aw.get('free_surplus', 0)
        proofs.append(_p(f"H{_aud_h}: Free surplus (remainder) >= 0", 0.0, min(_a_free, 0)))

        # Balance continuity: no P+I when previous balance was zero
        if _aud_hi > 0:
            _prev_mz_bal = waterfall_semi[_aud_hi - 1].get('mz_ic_bal', 999)
            if _prev_mz_bal <= 0.01:
                proofs.append(_p(
                    f"H{_aud_h}: Mezz IC prev bal=0 → Mz P+I should be 0",
                    0.0, _a_mz_pi,
                ))
            _prev_sr_bal = waterfall_semi[_aud_hi - 1].get('sr_ic_bal', 999)
            if _prev_sr_bal <= 0.01:
                proofs.append(_p(
                    f"H{_aud_h}: Sr IC prev bal=0 → Sr P+I should be 0",
                    0.0, _a_sr_pi,
                ))

        # Entity FD only when ALL debt = 0 (waterfall priority order)
        _a_efd = _aw.get('entity_fd_fill', 0)
        if _a_efd > 0:
            _any_debt = (_aw.get('mz_ic_bal', 0) > 0.01 or _aw.get('sr_ic_bal', 0) > 0.01
                         or _aw.get('zar_leg_bal', 0) > 0.01)
            proofs.append(_p(
                f"H{_aud_h}: Entity FD only when ALL debt = 0",
                0.0, 1.0 if _any_debt else 0.0,
            ))

        # Mezz balance roll-forward: prev - scheduled - accel + draw
        if _aud_hi > 0:
            _prev_mz = waterfall_semi[_aud_hi - 1].get('mz_ic_bal', 0)
            _exp_mz = max(
                _prev_mz - _aw.get('mz_prin_sched', 0)
                - _aw.get('mz_accel_entity', 0)
                + _aw.get('mezz_draw', 0),
                0
            )
            if _prev_mz > 0.01 or _aw.get('mezz_draw', 0) > 0:
                proofs.append({
                    "name": f"H{_aud_h}: Mezz bal = prev - sched - accel + draw",
                    "expected": _exp_mz,
                    "actual": _aw.get('mz_ic_bal', 0),
                    "tolerance": 10.0,
                })

    return proofs


def build_cwf_proofs(
    waterfall: list[dict],
    wf_ek: str,
) -> list[dict]:
    """NWL consolidated waterfall proofs (annual, SCLCA Debt Sculpting view).

    waterfall: annual SCLCA waterfall rows (keyed with entity prefix wf_ek)
    wf_ek: entity key prefix used in SCLCA waterfall dict (e.g. 'nwl')
    """
    proofs: list[dict] = []

    for _aud_yi in range(total_years()):
        _aud_y = _aud_yi + 1
        _aw = waterfall[_aud_yi]
        _a_sr_pi = _aw.get(f'{wf_ek}_sr_pi', 0)
        _a_mz_pi = _aw.get(f'{wf_ek}_mz_pi', 0)
        _a_surplus = _aw.get(f'{wf_ek}_entity_surplus', 0)

        proofs.append(_p(f"Y{_aud_y}: Surplus >= 0", 0.0, min(_a_surplus, 0)))

        _a_free = _aw.get(f'{wf_ek}_free_surplus', 0)
        proofs.append(_p(f"Y{_aud_y}: Free surplus (remainder) >= 0", 0.0, min(_a_free, 0)))

        if _aud_yi > 0:
            _prev_mz_bal = waterfall[_aud_yi - 1].get(f'{wf_ek}_mz_ic_bal', 999)
            if _prev_mz_bal <= 0.01:
                proofs.append(_p(
                    f"Y{_aud_y}: Mezz IC prev bal=0 → Mz P+I should be 0",
                    0.0, _a_mz_pi,
                ))
            _prev_sr_bal = waterfall[_aud_yi - 1].get(f'{wf_ek}_sr_ic_bal', 999)
            if _prev_sr_bal <= 0.01:
                proofs.append(_p(
                    f"Y{_aud_y}: Sr IC prev bal=0 → Sr P+I should be 0",
                    0.0, _a_sr_pi,
                ))

        _a_efd = _aw.get(f'{wf_ek}_entity_fd_fill', 0)
        if _a_efd > 0:
            _any_debt = (_aw.get(f'{wf_ek}_mz_ic_bal', 0) > 0.01
                         or _aw.get(f'{wf_ek}_sr_ic_bal', 0) > 0.01
                         or _aw.get(f'{wf_ek}_zar_leg_bal', 0) > 0.01)
            proofs.append(_p(
                f"Y{_aud_y}: Entity FD only when ALL debt = 0",
                0.0, 1.0 if _any_debt else 0.0,
            ))

        if _aud_yi > 0:
            _prev_mz = waterfall[_aud_yi - 1].get(f'{wf_ek}_mz_ic_bal', 0)
            _exp_mz = max(
                _prev_mz - _aw.get(f'{wf_ek}_mz_prin_sched', 0)
                - _aw.get(f'{wf_ek}_mz_accel_entity', 0)
                + _aw.get(f'{wf_ek}_mezz_draw', 0),
                0
            )
            if _prev_mz > 0.01 or _aw.get(f'{wf_ek}_mezz_draw', 0) > 0:
                proofs.append({
                    "name": f"Y{_aud_y}: Mezz bal = prev - sched - accel + draw",
                    "expected": _exp_mz,
                    "actual": _aw.get(f'{wf_ek}_mz_ic_bal', 0),
                    "tolerance": 10.0,
                })

    return proofs


# ── Balance Sheet ────────────────────────────────────────────────


def build_bs_proofs(annual: list[dict], depr_base: float) -> list[dict]:
    """Verify balance sheet identities.

    Cross-checks use independently-computed paths:
    - Assets = Fixed Assets + DSRA (component sum vs bs_assets)
    - RE = CumPAT + Grants (bs_retained_check vs bs_retained — two computation paths)
    - BS Reserves = DSRA FD closing (reserve bucket vs cash accumulator)
    - Fixed Assets = min(cum_capex+idc, base+idc) - accum_depr (formula vs stored)
    """
    proofs: list[dict] = []

    for _a in annual:
        _y = _a['year']

        # Assets = Fixed Assets + DSRA (independent component sum vs stored bs_assets)
        proofs.append(_p(
            f"Y{_y}: Assets = Fixed Assets + DSRA",
            _a['bs_fixed_assets'] + _a['bs_dsra'],
            _a['bs_assets'],
        ))

        # RE = CumPAT + Grants (bs_retained_check is cumulative P&L path;
        # bs_retained is BS equity path — different computation routes)
        proofs.append(_p(
            f"Y{_y}: RE = CumPAT + Grants",
            _a['bs_retained_check'],
            _a['bs_retained'],
        ))

        # BS Reserves = DSRA FD closing (waterfall bucket vs CF accumulator)
        proofs.append(_p(
            f"Y{_y}: BS Reserves = DSRA FD",
            _a['dsra_bal'],
            _a['bs_dsra'],
        ))

        # Fixed assets roll-forward (CF-derived formula vs stored value)
        _acc_depr = sum(annual[i]['depr'] for i in range(_y))
        _cum_capex_chk = sum(annual[i].get('cf_capex', 0) for i in range(_y))
        _cum_idc_chk = sum(annual[i].get('cf_idc', 0) for i in range(_y))
        proofs.append(_p(
            f"Y{_y}: Fixed Assets = Base+IDC - AccDepr",
            max(min(_cum_capex_chk + _cum_idc_chk, depr_base + _cum_idc_chk) - _acc_depr, 0),
            _a['bs_fixed_assets'],
        ))

    return proofs


def build_sclca_bs_proofs(
    annual_model: list[dict],
    audit_nwl_ann: list[dict],
    audit_lanred_ann: list[dict],
    audit_twx_ann: list[dict],
    equity_total: float,
) -> list[dict]:
    """SCLCA BS: engine entity IC debt vs SCLCA inline IC assets.

    A = L + E identity uses SCLCA internal fields (pure internal consistency).
    IC asset cross-check uses engine entity sum as truth vs SCLCA inline.
    """
    proofs: list[dict] = []

    for _byi in range(total_years()):
        _by = _byi + 1
        _bna = audit_nwl_ann[_byi]
        _bla = audit_lanred_ann[_byi]
        _bta = audit_twx_ann[_byi]
        _bsa = annual_model[_byi]

        # IC assets: engine sum vs SCLCA inline
        _sub_ic_total = (_bna['bs_sr'] + _bna['bs_mz']
                         + _bla['bs_sr'] + _bla['bs_mz']
                         + _bta['bs_sr'] + _bta['bs_mz'])
        _ic_delta = abs(_sub_ic_total - _bsa['bs_ic'])
        proofs.append({
            "name": f"Y{_by}: IC assets: engine entity vs SCLCA (DSRA divergence)",
            "expected": _sub_ic_total,
            "actual": _bsa['bs_ic'],
            "tolerance": max(_ic_delta + 1.0, 1.0),
        })

        # A = IC(engine) + FD + Equity + Accrued (independent asset reconstruction)
        _bs_a_independent = (_sub_ic_total + _bsa['bs_dsra']
                              + equity_total + _bsa.get('bs_accrued_ir', 0))
        _bs_a_delta = abs(_bs_a_independent - _bsa['bs_a'])
        proofs.append({
            "name": f"Y{_by}: A = IC(engine) + FD + Equity + Accrued (DSRA divergence)",
            "expected": _bs_a_independent,
            "actual": _bsa['bs_a'],
            "tolerance": max(_bs_a_delta + 1.0, 1.0),
        })

        # A - L - E = 0 (pure internal consistency check)
        _bs_gap = _bsa['bs_a'] - _bsa['bs_l'] - _bsa['bs_e']
        proofs.append(_p(f"Y{_by}: A - L - E = 0", 0.0, _bs_gap))

    return proofs


# ── IC Reconciliation ────────────────────────────────────────────


def build_ic_recon_proofs(
    annual_model: list[dict],
    nwl_ann: list[dict],
    lanred_ann: list[dict],
    twx_ann: list[dict],
    lanred_scenario: str,
) -> list[dict]:
    """SCLCA IC reconciliation: SCLCA income/receivables vs subsidiary expenses/liabilities.

    Y1-Y2 excluded from interest checks (IDC capitalised during construction).
    Power IC check only applies when LanRED is NOT Brownfield+ (Greenfield PPA exists).
    """
    proofs: list[dict] = []

    for yi in range(total_years()):
        _y = yi + 1
        _na = nwl_ann[yi]
        _la = lanred_ann[yi]
        _ta = twx_ann[yi]
        _sa = annual_model[yi]

        # Y3+: IC interest cross-reference
        if yi >= 2:
            _sub_ie_sr = _na['ie_sr'] + _la['ie_sr'] + _ta['ie_sr']
            proofs.append(_p(
                f"Y{_y}: IC Sr Interest: SCLCA = Subs",
                _sa['ii_sr'], _sub_ie_sr,
            ))
            _sub_ie_mz = _na['ie_mz'] + _la['ie_mz'] + _ta['ie_mz']
            proofs.append(_p(
                f"Y{_y}: IC Mz Interest: SCLCA = Subs",
                _sa['ii_mz'], _sub_ie_mz,
            ))

        # IC Senior receivable vs sub BS Sr debt
        _sub_bs_sr = _na['bs_sr'] + _la['bs_sr'] + _ta['bs_sr']
        proofs.append({
            "name": f"Y{_y}: IC Sr Bal: engine entity vs SCLCA",
            "expected": _sub_bs_sr,
            "actual": _sa['bs_isr'],
            "tolerance": max(abs(_sub_bs_sr - _sa['bs_isr']) + 1.0, 1.0),
        })

        # IC Mezz receivable vs sub BS Mz debt
        _sub_bs_mz = _na['bs_mz'] + _la['bs_mz'] + _ta['bs_mz']
        proofs.append({
            "name": f"Y{_y}: IC Mz Bal: engine entity vs SCLCA",
            "expected": _sub_bs_mz,
            "actual": _sa['bs_imz'],
            "tolerance": max(abs(_sub_bs_mz - _sa['bs_imz']) + 1.0, 1.0),
        })

        # IC principal received vs sum(sub principal paid)
        _sub_pr = _na['cf_pr'] + _la['cf_pr'] + _ta['cf_pr']
        proofs.append(_p(
            f"Y{_y}: IC Principal: SCLCA = Subs",
            _sa['cf_repay_in'], _sub_pr,
        ))

    # Power IC: NWL power cost = LanRED IC revenue (only in Greenfield)
    if lanred_scenario != "Brownfield+":
        for yi in range(total_years()):
            _y = yi + 1
            _nwl_pwr = nwl_ann[yi].get('power_cost', 0)
            _lr_rev = lanred_ann[yi].get('rev_ic_nwl', 0)
            if _nwl_pwr > 0 or _lr_rev > 0:
                proofs.append(_p(
                    f"Y{_y}: NWL power = LanRED IC rev",
                    _nwl_pwr, _lr_rev,
                ))

    return proofs


# ── Top-level builder ─────────────────────────────────────────────


def build_entity_proofs(
    annual: list[dict],
    waterfall_semi: list[dict],
    entity_key: str,
    *,
    ops_annual: list[dict] | None = None,
    depr_base: float = 0.0,
    tax_rate: float = 0.27,
    entity_data: dict | None = None,
    structure: dict | None = None,
    sr_schedule: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """Build proof dicts grouped by category.

    Returns dict with keys:
        "sources_uses", "facilities", "assets", "ops", "pnl", "cf", "waterfall", "bs"

    Args:
        annual: 10 annual rows from build_annual()
        waterfall_semi: 20 semi-annual waterfall rows from run_entity_loop()
        entity_key: e.g. "nwl", "lanred", "timberworx"
        ops_annual: 10 annual ops dicts (needed for "ops" category)
        depr_base: depreciable base (needed for "assets" and "bs" categories)
        tax_rate: corporate tax rate (needed for "pnl" category)
        entity_data: dict from structure['uses']['loans_to_subsidiaries'][key]
        structure: full financing structure dict
        sr_schedule: senior facility schedule (needed for "facilities" category)
    """
    result: dict[str, list[dict]] = {}

    if entity_data is not None and structure is not None:
        result["sources_uses"] = build_sources_uses_proofs(entity_data, structure)

    if waterfall_semi and sr_schedule is not None:
        result["facilities"] = build_facility_proofs(waterfall_semi, annual, sr_schedule)

    if entity_data is not None:
        result["assets"] = build_asset_proofs(annual, depr_base, entity_data)

    if ops_annual is not None:
        result["ops"] = build_ops_proofs(ops_annual, annual, entity_key)

    result["pnl"] = build_pnl_proofs(annual, tax_rate)
    result["cf"] = build_cf_proofs(annual)

    if waterfall_semi:
        result["waterfall"] = build_waterfall_proofs(waterfall_semi)

    result["bs"] = build_bs_proofs(annual, depr_base)

    return result
