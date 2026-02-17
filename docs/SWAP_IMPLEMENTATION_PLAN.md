# Swap Implementation Plan

## Part 1: Human-Readable Plan

### Principle

The swap is an **alternative hedging path**. When selected, it replaces the CC DSRA→FEC mechanism. The core difference:

- **FEC path**: CC injects cash (2nd Mezz draw) → inflates NWL Mezz IC → NWL buys FEC → EUR to IIC
- **Swap path**: NWL places IC-drawn EUR into swap → gets ZAR → EUR delivered to IIC later → ZAR repaid to Investec

The **IC schedules never change** — they are always vanilla (14 Sr / 10 Mz). What changes is: (a) whether CC does a 2nd draw, (b) whether swap legs appear on entity BS/CF/P&L.

### What Pages/Tabs Are Affected

```
ARCHITECTURE PRINCIPLE:
══════════════════════════════════════════════════════════════════
  BUILDERS (compute):   Assets & Facilities tab, Operations tab
  LISTENERS (display):  P&L, BS, CF tabs — read from builders

  The swap is built in Assets & Facilities:
    - EUR leg = an ASSET (lives in Assets section)
    - ZAR leg = a FACILITY (lives in Facilities section, own schedule)
    - Mezz IC DSRA drawdown = SUPPRESSED to zero (not hidden —
      schedule still renders, the P1 drawdown number is 0)

  P&L, BS, CF never compute swap values. They read fields
  stamped by build_sub_annual_model() which itself reads
  from the swap schedules built in Assets & Facilities.
══════════════════════════════════════════════════════════════════

PAGE / TAB                    WHAT CHANGES
────────────────────────────  ──────────────────────────────────────────────

BUILDERS:

1. Swap Schedule Builders     Fix P_constant profile (not level annuity).
   (_build_nwl_swap_schedule)   Add IDC compounding phase. Both NWL & LanRED.
   (_build_lanred_swap_schedule)

2. IC Schedule Builder        When swap active: entity_dsra_mz = 0 for NWL.
   (build_simple_ic_schedule)   Mezz IC P1 drawdown becomes 0 (suppressed,
   (_build_all_entity_ic_      not hidden). Schedule still renders with all
    schedules)                  periods, just no inflation at P1.

3. Assets & Facilities tab    FACILITIES section:
   (render_subsidiary)          - Senior IC schedule: unchanged (always vanilla)
                                - Mezz IC schedule: P1 drawdown = 0 when swap
                                  (number suppressed, schedule always visible)
                                - Swap ZAR Leg: NEW full schedule table when
                                  swap active. Own heading, IDC phase +
                                  repayment phase, P_constant profile.
                                  This is a FACILITY (liability).

                                ASSETS section:
                                - Fixed assets: unchanged
                                - Swap EUR Leg: NEW asset entry when swap
                                  active. Shows notional, IDC growth,
                                  delivery schedule. This is an ASSET
                                  (receivable). Separate from facilities.

4. Entity Annual Model        Reads from swap schedules (built above).
   (build_sub_annual_model)     Stamps per-year fields on annual model:
                                swap_eur_bal, swap_zar_bal,
                                swap_eur_interest, swap_zar_interest,
                                swap_zar_p, swap_zar_i_cash.
                                Adjusts: ie, cf_ds, cf_net, bs_assets,
                                bs_debt, bs_retained.

5. SCLCA Holding Waterfall    Suppress CC 2nd draw (_draw_dsra = 0 at M24).
   (annual_model loop)          No DSRA pass-through when swap active.

LISTENERS (read from annual model, never compute):

6. P&L Tab                    New lines (when swap active):
   (render_subsidiary)          + Swap EUR Interest Income
                                − Swap ZAR Interest Expense
                                Reads swap_eur_interest, swap_zar_interest.

7. Cash Flow Tab              New section after Debt Service (when swap):
   (render_subsidiary)          Swap ZAR Interest, Principal, Total.
                                Reads cf_swap_zar_i, cf_swap_zar_p.

8. Balance Sheet Tab          EUR leg in Financial Assets (below DSRA FD).
   (render_subsidiary)          ZAR leg in Liabilities (after Mezz IC).
                                Reads swap_eur_bal, swap_zar_bal from
                                annual model. No on-the-fly computation.

9. SCLCA Holding BS           NO CHANGE. Holding sees IC loans + equity.

TOGGLE & SCULPTING:

10. NWL Debt Service Tab      Already has side-by-side FEC vs Swap.
    (Section 2: Hedging)        Toggle already works. No change needed.

11. LanRED — TWO decisions:   Greenfield vs Brownfield = operating model.
    (Brownfield+ scenario)      Brownfield vanilla vs Brownfield+ = swap.
                                The "+" IS the swap. Toggle ONLY appears
                                when Brownfield is selected (conditional).
                                Same builder/listener pattern as NWL.

12. Sculpting Tabs             NWL: toggle + explanation already there (OK).
    (Debt Sculpting)            LanRED: conditional swap toggle — only if
                                  Brownfield selected. May need improvement.
                                SCLCA: pass-through — shows NWL's hedge
                                  selection, shows LanRED's selection.
```

### The 6 Changes

#### Change 1: Suppress CC 2nd Draw When Swap Active

**Where**: `_build_all_entity_ic_schedules()` (line ~1016) and SCLCA holding waterfall (line ~10935)

**What**: When `sclca_nwl_hedge == "Cross-Currency Swap"`:
- Set `entity_dsra_mz = 0` for NWL (no DSRA drawdown into Mezz IC)
- Set `entity_dsra_sr = 0` for NWL (no DSRA principal into Senior IC at P1; Senior follows normal P_constant schedule)
- At holding level: `_draw_dsra = 0` at M24

**Effect**: NWL Mezz IC schedule shows original balance (no P1 inflation). NWL Senior IC P1 reverts to normal P_constant (no special DSRA sizing). Holding CF shows no CC 2nd draw.

**Also in**: `build_sub_annual_model()` (line ~2683) — same suppression for entity-level schedule builder.

#### Change 2: Fix Swap Schedule Builders — P_constant

**Where**: `_build_nwl_swap_schedule()` (line ~1402) and `_build_lanred_swap_schedule()` (line ~1446)

**What**: Replace level annuity formula with P_constant:
```
BEFORE: annuity = bal × r / (1 - (1+r)^-n)     ← wrong
AFTER:  principal = bal / n                      ← constant P
        payment = principal + interest            ← declining total
```

**Effect**: ZAR leg payments decline over time (constant principal, declining interest). Matches Senior debt profile.

#### Change 3: Add IDC Compounding to Swap Legs

**Where**: `build_sub_annual_model()` (line ~2700+) — inside the annual model builder

**What**: When swap active, compute per-year:
- **EUR leg**: Opening × (1 + 4.70%/2)^periods_in_year. Grows during grace (M0→M24). After M24: NWL=0 (bullet delivered), LanRED=amortizes with IC Senior.
- **ZAR leg**: Opening × (1 + 9.69%/2)^periods_in_year. Grows during grace (M0→M24). After repayment start: amortizes per P_constant schedule.

Stamp on annual model: `swap_eur_bal`, `swap_zar_bal`, `swap_eur_interest`, `swap_zar_interest`, `swap_zar_repayment`.

#### Change 4: Wire Swap Into Entity P&L

**Where**: `build_sub_annual_model()` — finance costs section, and `render_subsidiary()` P&L tab

**Model fields**:
- `swap_eur_interest_income`: EUR leg × 4.70% / 2 (positive, income)
- `swap_zar_interest_expense`: ZAR leg × 9.69% / 2 (negative, expense)
- During grace (M0→M24): capitalize (IDC), do NOT flow through P&L
- Post grace: cash interest, flows through P&L

**P&L rendering** (after Mezz IC interest):
```
+ Swap EUR Interest Income     (only when swap active)
− Swap ZAR Interest Expense    (only when swap active)
```

Adjust `ie` (total interest expense) to include net swap interest.

#### Change 5: Wire Swap Into Entity Cash Flow

**Where**: `build_sub_annual_model()` — CF section, and `render_subsidiary()` CF tab

**Model fields**:
- `cf_swap_zar_p`: ZAR leg principal repayment (P_constant, from schedule)
- `cf_swap_zar_i`: ZAR leg interest payment (cash, from schedule)
- `cf_swap_eur_received`: EUR received from swap (NWL: bullet M24, LanRED: per IC period)

**CF rendering** (new section after DEBT SERVICE):
```
SWAP HEDGE
  Swap ZAR Interest        (cf_swap_zar_i)
  Swap ZAR Principal       (cf_swap_zar_p)
  Total Swap Payment       (cf_swap_zar_total)
```

Adjust `cf_after_debt_service` and `cf_net` to include swap ZAR payments.

#### Change 6: Wire Swap Into Entity Balance Sheet

**Where**: `render_subsidiary()` BS tab (line ~7568+) — already partially implemented but broken

**Fix the existing code**:
- EUR leg: Y1-Y2 = growing (IDC compounds). Y2 end (NWL) = 0 after bullet. LanRED = amortizes.
- ZAR leg: Y1-Y2 = growing (IDC compounds). After repayment start = declining.
- Both legs: read from `swap_eur_bal` and `swap_zar_bal` stamped on annual model (Change 3).
- Position: EUR leg below DSRA FD in assets. ZAR leg after Mezz IC in liabilities.
- Total Assets / Total Debt / Retained Earnings / Total Equity: include swap legs.

### What Does NOT Change

- IC schedule structure (always 14 Sr / 10 Mz)
- IC interest rates (5.20% Sr, 15.25% Mz)
- SCLCA Holding BS (no swap at holding level)
- Waterfall cascade logic (Sr P+I → Mz P+I → DSRA → Dividend)
- TWX (no swap, never has FX exposure)
- NWL Debt Service tab Section 2 (already has FEC vs Swap comparison — keep as-is)
- Toggle default (FEC is default, swap is opt-in)

### Execution Order

```
Step 1:  Fix swap schedule builders (P_constant)     ← foundation
Step 2:  Suppress CC 2nd draw when swap active        ← IC schedules + holding
Step 3:  Add swap fields to annual model              ← IDC, interest, balances
Step 4:  Wire P&L (new interest lines)                ← render
Step 5:  Wire CF (new swap section)                   ← render
Step 6:  Fix BS (swap legs from annual model)         ← render
Step 7:  Verify A=D+E check still passes              ← integrity
```

---

## Part 2: Coding Instructions

### Step 1: Fix `_build_nwl_swap_schedule` and `_build_lanred_swap_schedule`

**File**: `app.py` lines 1386-1473

Replace level annuity with P_constant in both functions:

```python
# BEFORE (both functions):
if semi_rate > 0:
    annuity = zar_amount * semi_rate / (1 - (1 + semi_rate) ** -tenor)
else:
    annuity = zar_amount / tenor
# ...
principal = annuity - interest

# AFTER (both functions):
p_constant = zar_amount / tenor  # Fixed principal per period
# ...
interest = opening * semi_rate
principal = p_constant
payment = principal + interest  # Declining total
```

Also add IDC compounding phase to both schedules. Before repayment start, append IDC rows:
```python
# IDC phase: M0 to start_month, every 6 months
bal = zar_amount
for i in range(start_month // 6):
    month = i * 6
    opening = bal
    interest = opening * semi_rate
    bal = opening + interest  # Capitalize
    schedule.append({'period': -(start_month//6 - i), 'month': month,
                     'opening': opening, 'interest': interest,
                     'principal': 0, 'payment': 0,
                     'closing': bal, 'phase': 'idc'})

# Then recalculate p_constant on the IDC-inflated balance:
p_constant = bal / tenor
```

Return dict gains: `'zar_amount_idc': bal` (the IDC-inflated opening for repayment phase).

Do the same for the EUR leg: add `eur_amount_idc` = `swap_amount_eur * (1 + eur_rate/2)^(grace_periods)`.

### Step 2: Suppress CC 2nd Draw

**File**: `app.py`

**Location 1**: `_build_all_entity_ic_schedules()` (line ~1012-1016)

```python
# Current:
entity_dsra_sr = _ic_dsra_p1 * dsra_alloc.get(ek, 0.0)
entity_dsra_mz = pre_revenue_hedge_total * dsra_alloc.get(ek, 0.0)

# Change to:
if ek == 'nwl' and nwl_swap_enabled:
    entity_dsra_sr = 0.0  # No DSRA sizing on Senior P1
    entity_dsra_mz = 0.0  # No CC 2nd draw into Mezz
else:
    entity_dsra_sr = _ic_dsra_p1 * dsra_alloc.get(ek, 0.0)
    entity_dsra_mz = pre_revenue_hedge_total * dsra_alloc.get(ek, 0.0)
```

**Location 2**: `build_sub_annual_model()` (line ~2678-2683) — same pattern.

**Location 3**: SCLCA holding waterfall (line ~10934-10935):
```python
# Current:
if _m == 24:
    _draw_dsra = pre_revenue_hedge

# Change to:
if _m == 24:
    _draw_dsra = 0 if nwl_swap_enabled else pre_revenue_hedge
```

### Step 3: Add Swap Fields to Annual Model

**File**: `app.py`, inside `build_sub_annual_model()` (after line ~2860)

For each year, when swap active:

```python
# Swap leg balances and interest (stamped on annual model)
if _swap_active:
    # EUR leg balance (IDC pre-M24, then delivery/amortization)
    a['swap_eur_bal'] = ...  # from schedule
    a['swap_zar_bal'] = ...  # from schedule

    # Interest (capitalized during grace, cash after grace)
    a['swap_eur_interest'] = ...  # 4.70% on EUR bal
    a['swap_zar_interest'] = ...  # 9.69% on ZAR bal

    # ZAR repayment (P+I from schedule, only after repayment start)
    a['swap_zar_p'] = ...
    a['swap_zar_i_cash'] = ...
    a['swap_zar_total'] = a['swap_zar_p'] + a['swap_zar_i_cash']
else:
    a['swap_eur_bal'] = 0
    a['swap_zar_bal'] = 0
    a['swap_eur_interest'] = 0
    a['swap_zar_interest'] = 0
    a['swap_zar_p'] = 0
    a['swap_zar_i_cash'] = 0
    a['swap_zar_total'] = 0
```

Adjust existing fields:
```python
# P&L: add swap interest to finance costs
a['ie'] = a['ie_sr'] + a['ie_mz'] - a['swap_eur_interest'] + a['swap_zar_interest']

# CF: deduct swap ZAR from free CF
a['cf_swap_zar'] = a['swap_zar_total'] / FX_RATE  # Convert to EUR for CF
a['cf_after_debt_service'] = a['cf_ops'] - a['cf_ds'] - a['cf_swap_zar']
a['cf_net'] = ... - a['cf_swap_zar']  # Include in comprehensive net

# BS: add swap legs
a['bs_assets'] = a['bs_fixed_assets'] + a['bs_dsra'] + a['swap_eur_bal']
a['bs_debt'] = a['bs_sr'] + a['bs_mz'] + (a['swap_zar_bal'] / FX_RATE)
```

### Step 4: Wire P&L Rendering

**File**: `app.py`, `render_subsidiary()` P&L section (line ~6200+)

After Mezz IC interest lines, add:
```python
if _entity_swap_active:
    _pl_line('Swap EUR Interest Income', 'swap_eur_interest', sign=1.0)  # positive
    _pl_line('Swap ZAR Interest Expense', 'swap_zar_interest', sign=-1.0)  # negative
```

### Step 5: Wire CF Rendering

**File**: `app.py`, `render_subsidiary()` CF section (line ~6698+)

After Total Debt Service, before NET CASH FLOW:
```python
if _entity_swap_active:
    _cf_section('SWAP HEDGE')
    _cf_line('Swap ZAR Interest', 'cf_swap_zar_i', -1.0)
    _cf_line('Swap ZAR Principal', 'cf_swap_zar_p', -1.0)
    _cf_line('Total Swap Payment', 'cf_swap_zar', -1.0, row_type='total')
    _cf_spacer()
```

### Step 6: Fix BS Rendering (LISTENER — reads only, never computes)

**File**: `app.py`, `render_subsidiary()` BS section (line ~7568+)

**DELETE** the entire on-the-fly computation block (lines 7568-7608):
- Remove `_entity_swap_sched` computation
- Remove `_swap_eur_vals` / `_swap_zar_vals` loop computation
- Remove `_entity_swap_active` flag derived from session state

**REPLACE** with simple reads from annual model:
```python
# BS is a LISTENER — reads pre-computed values from annual model
_entity_swap_active = any(a.get('swap_eur_bal', 0) != 0 or a.get('swap_zar_bal', 0) != 0
                          for a in _sub_annual)
_swap_eur_vals = [a.get('swap_eur_bal', 0) for a in _sub_annual]
_swap_zar_vals = [a.get('swap_zar_bal', 0) / FX_RATE for a in _sub_annual]  # EUR equiv
```

The rendering code (lines 7610-7667) stays mostly the same — EUR below DSRA FD, ZAR after Mezz IC. But it now reads from the annual model instead of computing.

### Step 7: Verify Integrity

After all changes:
- A=D+E check must still pass (bs_gap = 0)
- DSCR must reflect swap payments (cf_ops / (cf_ds + cf_swap_zar))
- RE must match cumulative PAT (including swap interest in PAT)
- Holding CF must show no DSRA drawdown when swap active
- NWL Mezz IC schedule must NOT have P1 drawdown when swap active

### Files Modified

```
app.py only — all changes in one file:
  - _build_nwl_swap_schedule()       ~line 1386
  - _build_lanred_swap_schedule()    ~line 1433
  - _build_all_entity_ic_schedules() ~line 955
  - build_sub_annual_model()         ~line 2600
  - render_subsidiary() BS section   ~line 7568
  - render_subsidiary() CF section   ~line 6690
  - render_subsidiary() P&L section  ~line 6200
  - SCLCA holding waterfall          ~line 10934
```

No config changes needed — `waterfall.json` already has correct swap config.
