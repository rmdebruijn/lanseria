# Financial Model — Sculpting Tab: Three-Task Enhancement Plan

## Context

The NWL Debt Sculpting tab in the Streamlit financial model needs three enhancements:

1. **Task 1** — Swap becomes permanent default; add a notional slider (EUR 2,171,764 min → EUR 3,996,392 max); unify the notional source between the UI and the SCLCA orchestration block (currently inconsistent). Fix the Section 4 bug where the entity cascade call omits the swap schedule.

2. **Task 2** — Replace the current one-time dividend display logic with a proper **Mezz Dividend Reserve** mechanism: a liability ledger (5.25% × opening Mezz balance, simple accumulation, no compounding) and a parallel Fixed Deposit funded from cascade surplus (after contractual P+I, before Ops Reserve). Applies to NWL and LanRED, not TWX. Payout happens when Mezz is fully repaid.

3. **Task 3** — Add a new **Section 7 Cash Waterfall** display: post-contractual-P+I surplus allocated down the priority stack as a stacked bar chart with detail table. Rate-ranked acceleration order: Mezz (14.75%) → Swap ZAR leg (9.69%) → Senior (5.20%).

**Key clarification:** The "5.25%" is the IRR gap rate (20% target − 14.75% contractual) already in `config/waterfall.json` as `cc_irr.gap`. No rate changes to IC or facility rates.

---

## Critical Files

- **Primary:** `11. Financial Model/model/app.py` (~20,000 lines)
- **Config (edit):** `11. Financial Model/model/config/waterfall.json`
- **Config (read-only ref):** `config/structure.json`, `config/financing.json`, `config/project.json`

---

## PART A — Config Changes

### A1. Add Local Content Ceiling to `waterfall.json`

**File:** `config/waterfall.json`

**Anchor — find:**
```json
  "nwl_swap": {
    "eur_leg": "bullet_m24",
```

**Replace the entire `nwl_swap` object with:**
```json
  "nwl_swap": {
    "eur_leg": "bullet_m24",
    "eur_leg_note": "Single bullet at M24 (same as FEC timing). IC stays vanilla.",
    "zar_leg_repayments": 12,
    "zar_leg_start_month": 36,
    "zar_rate": 0.0969,
    "note": "IC stays vanilla. EUR bullet to Investec. ZAR Rand leg 12 semi-annual M36-M102. Rate: Investec quoted 9.69% fixed (Oct 2025).",
    "local_content_ceiling_eur": 3996392,
    "nwl_civil_eur": 3746392,
    "wsp_eur": 250000
  },
```

---

## PART B — Engine Function Changes

### B1. Fix `_compute_entity_waterfall_inputs` — Add Mezz Dividend Reserve

**File:** `app.py`

**Anchor — find the state variable initialisation block inside the function (unique string):**
```python
    # New state variables
    ops_reserve_bal = 0.0
    opco_dsra_bal = 0.0
    entity_fd_bal = 0.0
    od_bal_entity = 0.0  # LanRED: OD received from NWL; NWL: OD lent to LanRED
```

**Replace with:**
```python
    # Load Mezz dividend gap rate from config
    _wf_cfg_inner = load_config("waterfall")
    mz_div_rate = _wf_cfg_inner.get("cc_irr", {}).get("gap", 0.0525)

    # New state variables
    ops_reserve_bal = 0.0
    opco_dsra_bal = 0.0
    entity_fd_bal = 0.0
    od_bal_entity = 0.0  # LanRED: OD received from NWL; NWL: OD lent to LanRED

    # Task 2: Mezz Dividend Reserve state (NWL and LanRED only)
    _mz_div_applies = entity_key in ('nwl', 'lanred')
    mz_div_liability_bal = 0.0   # Cumulative accrued liability (simple, no compounding)
    mz_div_fd_bal = 0.0          # FD cash funded to cover liability
    mz_div_payout_done = False   # Payout triggered flag
```

---

**Anchor — find the IC balance reduction step inside the `for yi in range(10)` loop (unique string):**
```python
        # Reduce IC balances by scheduled principal + prepayments
        mz_ic_bal = max(mz_ic_bal - mz_prin_sched, 0)
        sr_ic_bal = max(sr_ic_bal - sr_prin_sched - sr_prepay, 0)
```

**Replace with:**
```python
        # Save opening Mezz IC balance for dividend accrual (before this year's scheduled payment)
        _mz_opening_for_div_accrual = mz_ic_bal

        # Reduce IC balances by scheduled principal + prepayments
        mz_ic_bal = max(mz_ic_bal - mz_prin_sched, 0)
        sr_ic_bal = max(sr_ic_bal - sr_prin_sched - sr_prepay, 0)

        # Task 2: Mezz Dividend Reserve — accrual and payout trigger
        mz_div_accrual = 0.0
        mz_div_fd_fill = 0.0
        mz_div_payout = False
        mz_div_payout_amount = 0.0
        if _mz_div_applies and not mz_div_payout_done:
            # Accrue 5.25% on opening Mezz IC balance (simple, no compounding)
            if _mz_opening_for_div_accrual > 0.01:
                mz_div_accrual = _mz_opening_for_div_accrual * mz_div_rate
                mz_div_liability_bal += mz_div_accrual
            # Payout trigger: Mezz IC reaches zero this year
            if mz_ic_bal <= 0.01 and mz_div_liability_bal > 0.01:
                mz_div_payout = True
                mz_div_payout_done = True
```

---

**Anchor — find the Ops Reserve step header (unique string):**
```python
        # Step 1: Ops Reserve FD — fill to 100% of annual ops cost
```

**Insert immediately BEFORE that line:**
```python
        # Step 0.5: Mezz Dividend FD fill (soft fill — only from genuine surplus after P+I)
        # Funded before Ops Reserve but only if surplus exists. Starts once EBITDA > 0.
        if _mz_div_applies and not mz_div_payout and mz_div_accrual > 0 and remaining > 0:
            # Fill gap between FD balance and this year's target (cumulative liability so far)
            _fd_fill_gap = max(mz_div_liability_bal - mz_div_fd_bal, 0)
            mz_div_fd_fill = min(remaining, _fd_fill_gap)
            mz_div_fd_bal += mz_div_fd_fill
            remaining -= mz_div_fd_fill

        # Payout: FD balance paid as dividend slug when Mezz fully repaid
        if _mz_div_applies and mz_div_payout:
            mz_div_payout_amount = mz_div_fd_bal
            mz_div_fd_bal = 0.0       # FD cleared
            mz_div_liability_bal = 0.0  # Liability settled

        # Step 1: Ops Reserve FD — fill to 100% of annual ops cost
```

---

**Anchor — find the closing `rows.append({` block. The unique anchor is the last few fields before the closing `})`:**

Find the end of the existing `rows.append({...})` — specifically the last field before `})`  which is:
```python
            'free_surplus': free_surplus,
        })
```

**Replace with:**
```python
            'free_surplus': free_surplus,
            # Task 2: Mezz Dividend Reserve fields
            'mz_div_accrual': mz_div_accrual,
            'mz_div_liability_bal': mz_div_liability_bal,
            'mz_div_fd_fill': mz_div_fd_fill,
            'mz_div_fd_bal': mz_div_fd_bal,
            'mz_div_payout': mz_div_payout,
            'mz_div_payout_amount': mz_div_payout_amount,
        })
```

---

### B2. Update `_build_waterfall_model` — Propagate Mezz Dividend Fields + Fix Step 4

**File:** `app.py`

**Anchor — find inside the per-entity loop (unique string):**
```python
            wf[f'{ek}_entity_fd_fill'] = ewf.get('entity_fd_fill', 0)
            wf[f'{ek}_entity_fd_bal'] = ewf.get('entity_fd_bal', 0)
```

**Insert immediately AFTER those two lines:**
```python
            # Task 2: Mezz Dividend Reserve propagation (NWL and LanRED only; TWX yields zeros)
            wf[f'{ek}_mz_div_accrual']       = ewf.get('mz_div_accrual', 0)
            wf[f'{ek}_mz_div_liability_bal'] = ewf.get('mz_div_liability_bal', 0)
            wf[f'{ek}_mz_div_fd_fill']       = ewf.get('mz_div_fd_fill', 0)
            wf[f'{ek}_mz_div_fd_bal']        = ewf.get('mz_div_fd_bal', 0)
            wf[f'{ek}_mz_div_payout']        = ewf.get('mz_div_payout', False)
            wf[f'{ek}_mz_div_payout_amount'] = ewf.get('mz_div_payout_amount', 0)
```

---

**Anchor — find the Step 4 block (unique string):**
```python
        # Step 4: One-Time Dividend (when CC balance reaches 0)
        wf_slug_paid = 0.0
        if cc_bal <= 0.01 and not slug_settled and cc_slug_cumulative > 0:
            wf_slug_paid = min(remaining, cc_slug_cumulative)
            remaining -= wf_slug_paid
            slug_settled = True
        wf['wf_cc_slug_paid'] = wf_slug_paid
```

**Replace with:**
```python
        # Step 4: One-Time Dividend — authoritative source is entity-level FD payout
        # The FD is funded at entity level; payout flows up to SCLCA/holding, then to CC.
        # Does NOT reduce the holding 'remaining' pool (already funded from entity FD).
        wf_slug_paid = 0.0
        _entity_div_payout_total = (
            nwl_wf[yi].get('mz_div_payout_amount', 0) +
            lanred_wf[yi].get('mz_div_payout_amount', 0)
        )
        if _entity_div_payout_total > 0.01 and not slug_settled:
            wf_slug_paid = _entity_div_payout_total
            slug_settled = True
        # cc_slug_cumulative retained as IRR verification tracker (should ≈ wf_slug_paid)
        wf['wf_cc_slug_paid'] = wf_slug_paid
        wf['wf_cc_slug_verified'] = cc_slug_cumulative  # verification only
```

---

### B3. Annual Model Overlay — Stamp Mezz Dividend Fields

**File:** `app.py`

**Anchor — find the waterfall overlay loop ending (unique string — last field stamped in the loop):**
```python
        _oa['wf_interest_saved'] = 0
```

**Insert immediately AFTER that line (still inside the overlay loop):**
```python
        # Task 2: Mezz Dividend Reserve overlay
        for _ek_mz in ['nwl', 'lanred']:
            _oa[f'wf_{_ek_mz}_mz_div_accrual']       = _ow.get(f'{_ek_mz}_mz_div_accrual', 0)
            _oa[f'wf_{_ek_mz}_mz_div_liability_bal'] = _ow.get(f'{_ek_mz}_mz_div_liability_bal', 0)
            _oa[f'wf_{_ek_mz}_mz_div_fd_fill']       = _ow.get(f'{_ek_mz}_mz_div_fd_fill', 0)
            _oa[f'wf_{_ek_mz}_mz_div_fd_bal']        = _ow.get(f'{_ek_mz}_mz_div_fd_bal', 0)
            _oa[f'wf_{_ek_mz}_mz_div_payout_amount'] = _ow.get(f'{_ek_mz}_mz_div_payout_amount', 0)
```

---

## PART C — Orchestration Changes

### C1. SCLCA Block — Read Swap Notional from Session State

**File:** `app.py`

**Anchor — find the entire swap-amount computation block (unique string):**
```python
    # NWL swap schedule (must be computed BEFORE entity waterfall inputs)
    nwl_swap_amount = 0
    _nwl_swap_eur_m24 = 0.0
    _nwl_swap_eur_m30 = 0.0
    _nwl_last_sr_month = 102
    if nwl_swap_enabled:
```

**Replace the entire block (from that comment down to and including `_swap_sched = ...`) with:**
```python
    # NWL swap schedule (must be computed BEFORE entity waterfall inputs)
    # Task 1: Notional driven by session_state["nwl_swap_notional"] (set by slider in Debt Sculpting).
    # Compute DSRA minimum locally for bounds enforcement.
    _sr_det_orch = financing['loan_detail']['senior']
    _sr_bal_orch = (
        _sr_det_orch['loan_drawdown_total']
        + _sr_det_orch['rolled_up_interest_idc']
        - _sr_det_orch['grant_proceeds_to_early_repayment']
        - _sr_det_orch['gepf_bulk_proceeds']
    )
    _sr_rate_orch = structure['sources']['senior_debt']['interest']['rate']
    _sr_num_orch  = structure['sources']['senior_debt']['repayments']
    _sr_p_orch    = _sr_bal_orch / _sr_num_orch
    _sr_i_m24_orch = _sr_bal_orch * _sr_rate_orch / 2
    _dsra_min_orch = 2 * (_sr_p_orch + _sr_i_m24_orch)
    _swap_notional_max_orch = load_config("waterfall")["nwl_swap"].get("local_content_ceiling_eur", 3996392)

    nwl_swap_amount = 0.0
    _nwl_last_sr_month = 102
    if nwl_swap_enabled:
        # Read from slider session state; fall back to DSRA minimum
        nwl_swap_amount = float(st.session_state.get("nwl_swap_notional", int(round(_dsra_min_orch))))
        # Clamp to valid bounds
        nwl_swap_amount = max(_dsra_min_orch, min(_swap_notional_max_orch, nwl_swap_amount))
        _nwl_last_sr_month = max(
            (r['Month'] for r in _entity_ic['nwl']['sr']
             if r['Month'] >= 24 and (abs(r.get('Principle', 0)) > 0 or abs(r.get('Repayment', 0)) > 0)),
            default=102
        )
    _swap_sched = (
        _build_nwl_swap_schedule(nwl_swap_amount, FX_RATE, last_sr_month=_nwl_last_sr_month)
        if nwl_swap_enabled else None
    )

    # Task 1: Compute and stamp excess notional (additional bullet to SCLCA IC)
    _nwl_swap_excess_notional = max(nwl_swap_amount - _dsra_min_orch, 0.0) if nwl_swap_enabled else 0.0
```

---

**Anchor — find the annual model overlay loop for excess bullet (add AFTER the overlay loop ends). Find:**
```python
    # --- END WATERFALL OVERLAY ---
```

If that exact string doesn't exist, find the line immediately after the last `_oa['wf_interest_saved'] = 0` assignment (which is the end of the overlay loop body). After the loop closes, add:

```python
    # Task 1: Stamp excess swap notional as Year 2 bullet to SCLCA IC
    for _yi_ex, _oa_ex in enumerate(annual_model):
        _oa_ex['nwl_swap_excess_bullet'] = (
            _nwl_swap_excess_notional if (nwl_swap_enabled and _yi_ex == 1) else 0.0
        )
```

### C2. Fix Section 4 Bug — Pass Swap Schedule in Entity Cascade Call

**File:** `app.py`

**Anchor — find this exact call inside NWL Debt Sculpting Section 4 (unique string):**
```python
                # Compute entity waterfall
                _ent_wf = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _sub_sr_schedule, _sub_mz_schedule)
```

**Replace with:**
```python
                # Compute entity waterfall (Task 1 fix: pass swap schedule when swap active)
                _ent_wf = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _sub_sr_schedule if not _ds_swap_active else _nwl_sr_no_dsra,
                    _sub_mz_schedule if not _ds_swap_active else _nwl_mz_no_dsra,
                    nwl_swap_schedule=_ds_swap_sched if _ds_swap_active else None)
```

Note: `_nwl_sr_no_dsra`, `_nwl_mz_no_dsra`, and `_ds_swap_sched` are computed earlier in Section 2 and are in scope.

---

## PART D — Display / UI Changes

### D1. Add Notional Slider in NWL Debt Sculpting Section 2

**File:** `app.py`

**Anchor — find the swap amount assignment in Section 2 (unique string):**
```python
                # Compute swap schedule (needed by both panels for sizing)
                # Swap notional = same as DSRA = 2×(P+I) at M24
                _ds_swap_amt = _ds_dsra_amount
                _ds_last_sr_m = max(
```

**Replace from that anchor down to (and including) `_ds_swap_sched = _build_nwl_swap_schedule(...)` with:**
```python
                # Task 1: Swap notional slider (swap scenario only)
                if _ds_swap_active:
                    _nwl_swap_cfg_ui = load_config("waterfall")["nwl_swap"]
                    _slider_min = int(round(_ds_dsra_amount))
                    _slider_max = int(_nwl_swap_cfg_ui.get("local_content_ceiling_eur", 3996392))

                    # Initialise session state if not yet set
                    if "nwl_swap_notional" not in st.session_state:
                        st.session_state["nwl_swap_notional"] = _slider_min

                    with st.container(border=True):
                        st.markdown("**Swap Notional** — Adjust between DSRA minimum and Local Content ceiling")
                        _nc1, _nc2, _nc3 = st.columns([3, 1, 1])
                        with _nc1:
                            _selected_notional = st.slider(
                                "Swap Notional (EUR)",
                                min_value=_slider_min,
                                max_value=_slider_max,
                                step=1000,
                                value=int(st.session_state["nwl_swap_notional"]),
                                key="_ds_nwl_swap_notional_slider",
                                help=(
                                    f"Min = DSRA notional (€{_slider_min:,.0f} = 2×P+I at M24). "
                                    f"Max = Local content ceiling: "
                                    f"NWL Civil €{_nwl_swap_cfg_ui.get('nwl_civil_eur', 3746392):,.0f} "
                                    f"+ WSP €{_nwl_swap_cfg_ui.get('wsp_eur', 250000):,.0f} "
                                    f"= €{_slider_max:,.0f}."
                                ),
                            )
                            st.session_state["nwl_swap_notional"] = _selected_notional
                        _excess_notional = _selected_notional - _slider_min
                        with _nc2:
                            st.metric("DSRA Min", f"€{_slider_min:,.0f}")
                        with _nc3:
                            st.metric(
                                "Excess → Bullet",
                                f"€{_excess_notional:,.0f}",
                                delta="Additional repayment to SCLCA IC" if _excess_notional > 0 else None,
                            )
                        if _excess_notional > 0:
                            st.info(
                                f"€{_excess_notional:,.0f} above DSRA minimum paid as additional "
                                f"bullet to SCLCA IC at M24, reducing holding IC balance. "
                                f"ZAR repayment leg scales to full notional of "
                                f"€{_selected_notional:,.0f}."
                            )
                    _ds_swap_amt = float(st.session_state["nwl_swap_notional"])
                else:
                    _ds_swap_amt = _ds_dsra_amount

                _ds_last_sr_m = max(
                    (r['Month'] for r in _nwl_sr_no_dsra
                     if r['Month'] >= 24 and abs(r.get('Principle', 0)) > 0),
                    default=102)
                _ds_swap_sched = _build_nwl_swap_schedule(_ds_swap_amt, FX_RATE, last_sr_month=_ds_last_sr_m)
```

---

### D2. Update Section 3 — One-Time Dividend Chart + Table

**File:** `app.py`

**Anchor — find the data extraction loop in Section 3 (unique string):**
```python
                _div_mz_closing = []
                _div_accrual = []
                _div_cum = []
                _div_slug_yr = None
                _cum = 0.0
                _slug_paid = False
                _mz_prev_close = _div_mz_opening
                for _yi_d in range(10):
                    _mz_close = _ent_wf_div[_yi_d].get('mz_ic_bal', 0)
                    _div_mz_closing.append(_mz_close)
                    if _slug_paid:
                        _div_accrual.append(0.0)
                        _div_cum.append(0.0)
                    else:
                        _acc = _mz_prev_close * _ds_cc_gap if _mz_prev_close > 0.01 else 0.0
                        _div_accrual.append(_acc)
                        _cum += _acc
                        _div_cum.append(_cum)
                        if _mz_close <= 0.01:
                            _div_slug_yr = _yi_d
                            _slug_paid = True
                    _mz_prev_close = _mz_close
```

**Replace with:**
```python
                _div_mz_closing = []
                _div_accrual = []
                _div_cum = []       # Liability cumulative (from engine)
                _div_fd_bals = []   # FD balance (from engine)
                _div_slug_yr = None
                _cum = 0.0
                _slug_paid = False
                _mz_prev_close = _div_mz_opening
                for _yi_d in range(10):
                    _mz_close = _ent_wf_div[_yi_d].get('mz_ic_bal', 0)
                    _div_mz_closing.append(_mz_close)
                    _div_fd_bals.append(_ent_wf_div[_yi_d].get('mz_div_fd_bal', 0))
                    if _slug_paid:
                        _div_accrual.append(0.0)
                        _div_cum.append(0.0)
                    else:
                        # Use engine-computed accrual if available (Task 2), else compute directly
                        _acc = _ent_wf_div[_yi_d].get(
                            'mz_div_accrual',
                            _mz_prev_close * _ds_cc_gap if _mz_prev_close > 0.01 else 0.0
                        )
                        _div_accrual.append(_acc)
                        _cum = _ent_wf_div[_yi_d].get('mz_div_liability_bal', _cum + _acc)
                        _div_cum.append(_cum)
                        if _mz_close <= 0.01:
                            _div_slug_yr = _yi_d
                            _slug_paid = True
                    _mz_prev_close = _mz_close
```

---

**Anchor — find the FD balance trace insertion point. Find the cumulative dividend trace:**
```python
                _fig_div.add_trace(go.Scatter(
                    x=_div_years, y=_div_cum,
                    mode='lines+markers', name='Cumulative Dividend',
                    line=dict(color='#EF4444', width=2, dash='dot'),
                    yaxis='y',
                ))
```

**Insert immediately AFTER that trace:**
```python
                _fig_div.add_trace(go.Scatter(
                    x=_div_years, y=_div_fd_bals,
                    mode='lines+markers', name='Mezz Div FD Balance',
                    line=dict(color='#059669', width=2, dash='dash'),
                    yaxis='y',
                ))
```

---

**Anchor — find the chart title in Section 3:**
```python
                    title='One-Time Dividend — NWL Contribution',
```

**Replace with:**
```python
                    title='Mezz Dividend Reserve — Liability vs FD Balance (NWL)',
```

---

**Anchor — find the `st.plotly_chart(_fig_div, ...)` line in Section 3. Insert the detail table IMMEDIATELY AFTER it:**

```python
                # Task 2: Mezz Dividend Reserve detail table
                with st.expander("Mezz Dividend Reserve Detail", expanded=False):
                    _mz_div_openings = [_div_mz_opening] + _div_mz_closing[:-1]
                    _mz_div_table = {
                        'Mz IC Opening':   [f"€{v:,.0f}" if v > 0.5 else '—' for v in _mz_div_openings],
                        'Accrual (5.25%)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _div_accrual],
                        'Liability (cum)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _div_cum],
                        'FD Fill':         [f"€{_ent_wf_div[yi].get('mz_div_fd_fill', 0):,.0f}"
                                            if _ent_wf_div[yi].get('mz_div_fd_fill', 0) > 0.5 else '—'
                                            for yi in range(10)],
                        'FD Balance':      [f"€{v:,.0f}" if v > 0.5 else '—' for v in _div_fd_bals],
                        'Gap (Liab−FD)':   [f"€{max(_div_cum[yi] - _div_fd_bals[yi], 0):,.0f}"
                                            if max(_div_cum[yi] - _div_fd_bals[yi], 0) > 0.5 else '—'
                                            for yi in range(10)],
                    }
                    _div_years_tbl = [f"Y{yi+1}" for yi in range(10)]
                    st.dataframe(
                        pd.DataFrame(_mz_div_table, index=_div_years_tbl).T,
                        use_container_width=True
                    )
                    if _div_slug_yr is not None:
                        _payout_amt = _ent_wf_div[_div_slug_yr].get(
                            'mz_div_payout_amount', _div_cum[_div_slug_yr]
                        )
                        st.success(
                            f"Payout in Y{_div_slug_yr+1}: "
                            f"**€{_payout_amt:,.0f}** paid from FD to SCLCA/CC."
                        )
```

---

### D3. Mezz Dividend Reserve Display for LanRED

**File:** `app.py`

**Anchor — find inside the LanRED sculpting section (unique string):**
```python
                # ════════════════════════════════════════════════════
                # Section 2: LanRED Swap Details (only when swap active)
                # ════════════════════════════════════════════════════
                if _lr_ds_swap_active and _sub_swap_sched:
```

**Insert immediately BEFORE that anchor:**
```python
                st.divider()
                # ════════════════════════════════════════════════════
                # Section 1b: LanRED Mezz Dividend Reserve
                # ════════════════════════════════════════════════════
                st.subheader("Mezz Dividend Reserve (LanRED)")
                _lr_cc_gap = load_config("waterfall").get("cc_irr", {}).get("gap", 0.0525)
                st.caption(
                    f"LanRED Mezz IC accrues {_lr_cc_gap:.2%}/yr on opening balance "
                    f"as deferred dividend obligation to Creation Capital. "
                    f"FD funded from surplus (after P+I, before Ops Reserve). "
                    f"Paid as slug at Mezz repayment."
                )

                _lr_mz_div_accruals = [_ent_wf[yi].get('mz_div_accrual', 0) for yi in range(10)]
                _lr_mz_div_liab     = [_ent_wf[yi].get('mz_div_liability_bal', 0) for yi in range(10)]
                _lr_mz_div_fd       = [_ent_wf[yi].get('mz_div_fd_bal', 0) for yi in range(10)]
                _lr_mz_closing      = [_ent_wf[yi].get('mz_ic_bal', 0) for yi in range(10)]
                _lr_div_years       = [f"Y{yi+1}" for yi in range(10)]

                _lr_fig_div = go.Figure()
                _lr_fig_div.add_trace(go.Scatter(
                    x=_lr_div_years, y=_lr_mz_closing,
                    mode='lines+markers', name='Mezz IC Balance',
                    line=dict(color='#7C3AED', width=2)))
                _lr_fig_div.add_trace(go.Bar(
                    x=_lr_div_years, y=_lr_mz_div_accruals,
                    name=f'Dividend Accrual ({_lr_cc_gap:.2%})',
                    marker_color='#F59E0B', opacity=0.7))
                _lr_fig_div.add_trace(go.Scatter(
                    x=_lr_div_years, y=_lr_mz_div_liab,
                    mode='lines+markers', name='Liability (cum)',
                    line=dict(color='#EF4444', width=2, dash='dot')))
                _lr_fig_div.add_trace(go.Scatter(
                    x=_lr_div_years, y=_lr_mz_div_fd,
                    mode='lines+markers', name='FD Balance',
                    line=dict(color='#059669', width=2, dash='dash')))
                _lr_fig_div.update_layout(
                    height=320, barmode='overlay',
                    title='Mezz Dividend Reserve — LanRED',
                    yaxis=dict(title='EUR', showgrid=True, gridcolor='#E2E8F0'),
                    xaxis=dict(showgrid=False),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
                st.plotly_chart(_lr_fig_div, use_container_width=True, key='lr_mz_div_graph')

                with st.expander("LanRED Mezz Dividend Reserve Detail", expanded=False):
                    _lr_mz_openings = [_lr_mz_closing[yi-1] if yi > 0 else
                                       next((r.get('Opening', 0) for r in _sub_mz_schedule
                                             if r['Month'] >= 24), 0)
                                       for yi in range(10)]
                    _lr_div_table = {
                        'Mz Opening':      [f"€{v:,.0f}" if v > 0.5 else '—' for v in _lr_mz_openings],
                        'Accrual':         [f"€{v:,.0f}" if v > 0.5 else '—' for v in _lr_mz_div_accruals],
                        'Liability (cum)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _lr_mz_div_liab],
                        'FD Fill':         [f"€{_ent_wf[yi].get('mz_div_fd_fill', 0):,.0f}"
                                            if _ent_wf[yi].get('mz_div_fd_fill', 0) > 0.5 else '—'
                                            for yi in range(10)],
                        'FD Balance':      [f"€{v:,.0f}" if v > 0.5 else '—' for v in _lr_mz_div_fd],
                        'Gap':             [f"€{max(_lr_mz_div_liab[yi] - _lr_mz_div_fd[yi], 0):,.0f}"
                                            if max(_lr_mz_div_liab[yi] - _lr_mz_div_fd[yi], 0) > 0.5 else '—'
                                            for yi in range(10)],
                    }
                    st.dataframe(
                        pd.DataFrame(_lr_div_table, index=_lr_div_years).T,
                        use_container_width=True
                    )
```

---

### D4. New Section 7 — Cash Waterfall Priority Cascade (NWL)

**File:** `app.py`

**Anchor — find the end of Section 6 in NWL Debt Sculpting (unique string, the last `st.divider()` after Section 6 content). The Section 6 block ends with its final content. Find the `st.subheader("6.` line and locate the end of that section's content, then find:**

The safest anchor is the next entity/tab guard after NWL's sculpting block. Find the comment block that separates NWL sculpting from LanRED sculpting:
```python
            elif entity_key == 'lanred':
```

**Insert immediately BEFORE that `elif` (still inside the NWL `if entity_key == 'nwl':` block, after Section 6 ends):**

```python
                st.divider()

                # ════════════════════════════════════════════════════
                # Section 7: Cash Waterfall — Priority Cascade Display
                # ════════════════════════════════════════════════════
                st.subheader("7. Cash Waterfall — Priority Cascade")
                st.caption(
                    "Surplus after contractual Senior P+I and Mezz P+I, "
                    "allocated by priority. Stacked bars = bucket allocations; "
                    "dotted line = total available pool. "
                    "Acceleration ranked by rate: Mezz (14.75%) → Swap ZAR (9.69%) → Senior (5.20%)."
                )

                # Recompute entity waterfall with correct swap setting for Section 7
                _wfall_s7 = _compute_entity_waterfall_inputs(
                    entity_key, _sub_ops_annual,
                    _sub_sr_schedule if not _ds_swap_active else _nwl_sr_no_dsra,
                    _sub_mz_schedule if not _ds_swap_active else _nwl_mz_no_dsra,
                    nwl_swap_schedule=_ds_swap_sched if _ds_swap_active else None
                )

                _s7_years    = [f"Y{yi+1}" for yi in range(10)]
                _s7_free_cash = [
                    max(_wfall_s7[yi]['ebitda'] - _wfall_s7[yi]['tax']
                        - _wfall_s7[yi]['sr_pi'] - _wfall_s7[yi]['mz_pi'], 0)
                    for yi in range(10)
                ]
                _s7_mz_div   = [_wfall_s7[yi].get('mz_div_fd_fill', 0) for yi in range(10)]
                _s7_ops_res  = [_wfall_s7[yi].get('ops_reserve_fill', 0) for yi in range(10)]
                _s7_dsra     = [_wfall_s7[yi].get('opco_dsra_fill', 0) for yi in range(10)]
                _s7_od       = [_wfall_s7[yi].get('od_lent', 0) for yi in range(10)]
                _s7_mz_accel = [_wfall_s7[yi].get('mz_accel_entity', 0) for yi in range(10)]
                _s7_zar      = [_wfall_s7[yi].get('zar_leg_payment', 0) for yi in range(10)]
                _s7_sr_accel = [_wfall_s7[yi].get('sr_accel_entity', 0) for yi in range(10)]
                _s7_ent_fd   = [_wfall_s7[yi].get('entity_fd_fill', 0) for yi in range(10)]

                _s7_buckets = [
                    ('Mezz Div FD (5.25%)', _s7_mz_div,   '#DC2626'),
                    ('Ops Reserve',          _s7_ops_res,  '#0D9488'),
                    ('OpCo DSRA',            _s7_dsra,     '#2563EB'),
                    ('LanRED OD Lending',    _s7_od,       '#F59E0B'),
                    ('Mezz Accel (14.75%)',  _s7_mz_accel, '#7C3AED'),
                    ('ZAR Rand Leg (9.69%)', _s7_zar,      '#D97706'),
                    ('Sr Accel (5.20%)',     _s7_sr_accel, '#1E3A5F'),
                    ('Entity FD (residual)', _s7_ent_fd,   '#059669'),
                ]

                fig_s7 = go.Figure()
                for _lbl, _vals, _clr in _s7_buckets:
                    if any(v > 0 for v in _vals):
                        fig_s7.add_trace(go.Bar(
                            x=_s7_years, y=_vals,
                            name=_lbl, marker_color=_clr,
                        ))
                fig_s7.add_trace(go.Scatter(
                    x=_s7_years, y=_s7_free_cash,
                    mode='lines+markers', name='Free Cash (after P+I)',
                    line=dict(color='#111827', width=2.5, dash='dot'),
                    marker=dict(size=7),
                ))
                fig_s7.update_layout(
                    barmode='stack',
                    title=f'{name} — Surplus Cascade (post-contractual P+I)',
                    yaxis_title='EUR',
                    height=440,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(showgrid=True, gridcolor='#E2E8F0'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
                st.plotly_chart(fig_s7, use_container_width=True, key='nwl_cash_waterfall_s7')

                with st.expander("Cascade Detail Table (Y1–Y10)", expanded=False):
                    _s7_tbl = {
                        'Free Cash (after P+I)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_free_cash],
                        '1. Mezz Div FD':         [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_mz_div],
                        '2. Ops Reserve':          [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_ops_res],
                        '3. OpCo DSRA':            [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_dsra],
                        '4. LanRED OD Lending':    [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_od],
                        '5. Mezz Accel (14.75%)':  [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_mz_accel],
                        '6. ZAR Rand Leg (9.69%)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_zar],
                        '7. Sr Accel (5.20%)':     [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_sr_accel],
                        '8. Entity FD (residual)': [f"€{v:,.0f}" if v > 0.5 else '—' for v in _s7_ent_fd],
                    }
                    st.dataframe(pd.DataFrame(_s7_tbl, index=_s7_years).T, use_container_width=True)
                    # Audit: cascade sum should equal free cash (within rounding)
                    _s7_audit = []
                    for _yi_ck in range(10):
                        _alloc = sum([
                            _s7_mz_div[_yi_ck], _s7_ops_res[_yi_ck], _s7_dsra[_yi_ck],
                            _s7_od[_yi_ck], _s7_mz_accel[_yi_ck], _s7_zar[_yi_ck],
                            _s7_sr_accel[_yi_ck], _s7_ent_fd[_yi_ck],
                        ])
                        _gap = _s7_free_cash[_yi_ck] - _alloc
                        _s7_audit.append(f"Y{_yi_ck+1}: {'OK' if abs(_gap) < 2 else f'€{_gap:,.0f}'}")
                    st.caption("Unallocated residual (should be OK): " + " | ".join(_s7_audit))
```

---

## PART E — Implementation Sequence & Dependencies

```
A1 (waterfall.json: add ceiling constants)
  └─► C1 (orchestration: read notional from session state)   [depends on A1 for ceiling value]
  └─► D1 (slider UI in Section 2)                            [depends on A1 for ceiling value]

B1 (_compute_entity_waterfall_inputs: Mezz Div Reserve)      [standalone]
  └─► B2 (_build_waterfall_model: propagate fields + fix Step 4)
  └─► B3 (annual model overlay)
  └─► D2 (Section 3 chart update)
  └─► D3 (LanRED Mezz Div Reserve display)
  └─► D4 (Section 7 — reads mz_div_fd_fill from engine)

C2 (Section 4 bug fix: swap schedule in call)               [standalone, independent]

D4 depends on: B1 (for mz_div_fd_fill field) + D1 (for _ds_swap_sched scope)
```

**Recommended order:**
1. A1 — config (2 min)
2. C2 — bug fix (2 min, independent)
3. B1 — engine extension (main logic, 30–45 min)
4. B2 + B3 — waterfall propagation (10 min)
5. C1 — orchestration notional (10 min)
6. D1 — slider UI (15 min)
7. D2 — Section 3 chart + table (15 min)
8. D3 — LanRED display (10 min)
9. D4 — Section 7 (20 min)

---

## PART F — Verification

### Task 1
- Slider default = `_ds_dsra_amount` ≈ €2,171,764 on first load
- Slider max = €3,996,392 (from config)
- Set slider to €3,000,000 → `_ds_swap_sched['eur_amount']` = 3,000,000
- `nwl_swap_amount` in orchestration equals slider value (not old IC-schedule sum)
- `annual_model[1]['nwl_swap_excess_bullet']` = slider − DSRA min when slider > min
- Section 4: with swap on, `_ent_wf[yi]['zar_leg_payment'] > 0` for years 3–9

### Task 2
- Y1 accrual = Mezz IC M24 opening × 5.25% (verify manually from `_sub_mz_schedule`)
- `mz_div_liability_bal` = simple running sum of annual accruals (no compounding)
- `mz_div_fd_bal <= mz_div_liability_bal` at all years
- `mz_div_fd_fill = 0` in any year where `net < 0` (deficit year)
- `mz_div_payout = True` in the first year `mz_ic_bal <= 0.01`
- Section 3 chart: Liability (cum) and FD Balance lines converge at payout year
- TWX: all `mz_div_*` fields = 0 (guarded by `_mz_div_applies`)
- `wf['wf_cc_slug_paid']` ≈ `cc_slug_cumulative` at payout year (within rounding)

### Task 3
- Section 7 stacked bars sum ≤ free cash line at all years
- Audit row in expander shows "OK" for each year (gap < €2)
- ZAR Rand Leg bars: non-zero only when swap active
- Mezz Div FD (red) bar: appears in years where `mz_div_fd_fill > 0`
- Toggle swap off → ZAR Rand Leg disappears, Mezz Div FD may change
