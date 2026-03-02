# Framework Repair: Architecture Document

**Date**: 2026-03-01
**Scope**: Structural repair of the bLAN/sWTP/NWL financial model engine
**Trigger**: 10-agent deep audit — 17 structural failures out of 91 checks
**Approach**: Framework-level architectural repair, not patchwork

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Audit Findings](#2-audit-findings)
3. [Architectural Principles](#3-architectural-principles)
4. [Repair 1: Reserve Assets Architecture](#4-repair-1-reserve-assets-architecture)
5. [Repair 2: P&L FD Income Wiring](#5-repair-2-pl-fd-income-wiring)
6. [Repair 3: Waterfall Cascade Integrity](#6-repair-3-waterfall-cascade-integrity)
7. [Repair 4: IC Overdraft Two-Way Flow](#7-repair-4-ic-overdraft-two-way-flow)
8. [Repair 5: SCLCA Consolidation](#8-repair-5-sclca-consolidation)
9. [Repair 6: Column Registry](#9-repair-6-column-registry)
10. [Data Flow Architecture](#10-data-flow-architecture)
11. [File Change Summary](#11-file-change-summary)
12. [Verification Results](#12-verification-results)
13. [Backward Compatibility](#13-backward-compatibility)
14. [Design Decisions](#14-design-decisions)

---

## 1. Executive Summary

A comprehensive audit of the financial model engine identified 17 structural
failures across 91 checks. The failures were not random bugs -- they clustered
in 4 systemic areas where architectural boundaries had been violated:

1. **Reserves computed inside the waterfall** (separation of concerns violation)
2. **P&L used synthetic FD income** (single source of truth violation)
3. **Surplus acceleration ran without DSRA gate** (contractual logic error)
4. **IC overdraft was one-directional** (data flow discontinuity)

Rather than patching each failure individually, the repair addressed the
underlying framework violations. This produced a model where:

- Balance sheet identity holds to EUR 0.00 for ALL entities, ALL years
- FD income matches exactly between P&L, waterfall, and annual statements
- DSRA funding gates surplus acceleration (contractual compliance)
- IC overdraft flows bidirectionally (NWL lends, LanRED receives)
- SCLCA consolidation is complete (facility schedules, DSCR, IC elimination)


## 2. Audit Findings

The 10-agent audit ran 91 structural checks. 74 passed. 17 failed.
The failures clustered into 4 architectural violation categories:

```
+----------------------------+--------+---------------------------------------------+
| Category                   | Fails  | Root Cause                                  |
+----------------------------+--------+---------------------------------------------+
| Reserve computation locus  |   5    | Waterfall computed interest and targets      |
|                            |        | that belong to the reserve assets            |
+----------------------------+--------+---------------------------------------------+
| FD income provenance       |   4    | P&L fabricated interest income instead of    |
|                            |        | reading actual waterfall FD accruals         |
+----------------------------+--------+---------------------------------------------+
| Cascade control flow       |   4    | Surplus acceleration bypassed DSRA funding   |
|                            |        | gate; OD flow was one-directional            |
+----------------------------+--------+---------------------------------------------+
| Consolidation completeness |   4    | SCLCA missing facility schedules, DSCR,     |
|                            |        | and IC elimination logic                     |
+----------------------------+--------+---------------------------------------------+
| TOTAL                      |  17    |                                             |
+----------------------------+--------+---------------------------------------------+
```

The critical insight: these 17 failures shared a common pattern. Each was a
symptom of a module doing work that belonged to another module. The repair
was therefore not to fix 17 symptoms, but to restore 4 architectural boundaries.


## 3. Architectural Principles

The repair is grounded in 5 principles. These are not aspirational -- they are
load-bearing constraints that, if violated, cause cascading numerical errors.

### Principle 1: The Waterfall is Allocation-Only

The waterfall is a **cash allocator**. It reads pre-computed values (EBITDA, tax,
interest, principal, reserve targets, reserve gaps) and distributes surplus cash
into reserve accounts, debt acceleration, and entity FDs.

The waterfall must NOT:
- Compute interest on reserve balances (that is the reserve's job)
- Compute reserve targets (that is the reserve's job)
- Fabricate P&L line items (that is the P&L's job)
- Determine facility repayment schedules (that is the facility's job)

**Why this matters**: When the waterfall computes interest AND allocates cash,
the interest computation is entangled with the allocation sequence. Changing
the allocation order changes the interest. This circular dependency makes the
model fragile and the numbers unauditable.

### Principle 2: Reserves are Financial Assets

Each reserve account is a financial asset that:
- Holds its own opening balance (carried from prior period's closing)
- Computes its own interest accrual (opening x rate)
- Knows its own target / fill requirement
- Reports the gap for the waterfall to fill

**Why this matters**: In project finance, reserve accounts have contractual
definitions (DSRA = 1x next senior P+I, capped at outstanding balance). The
reserve must own its target computation because the target depends on
facility state that only the reserve has visibility into at the right time.

### Principle 3: Single Source of Truth for FD Income

FD interest income must flow through a single pipeline:

```
Reserve.accrue() --> total_fd_income() --> compute_period_pnl(fd_income=...)
    --> build_annual(ii_dsra = actual accruals)
```

There must be zero synthetic proxies. If a P&L line says "FD income = X",
then X must equal the sum of actual reserve interest accruals from that period.

**Why this matters**: Auditors trace interest income from the P&L back to the
reserve balances. If the P&L uses a proxy (e.g., `_cash_bal * 0.05`), the
trace breaks. The auditor cannot verify the number.

### Principle 4: Contractual Gating

Surplus cash acceleration must respect contractual priorities:

1. DSRA must be funded before surplus acceleration proceeds
2. Grant-funded acceleration is NOT gated (it is a contractual obligation
   independent of DSRA status)
3. Acceleration follows rate-priority ordering (highest rate first)

**Why this matters**: Lenders require DSRA funding before surplus cash can
be used for voluntary debt prepayment. Running acceleration without the
DSRA gate violates the senior lender covenant.

### Principle 5: Bidirectional IC Flows

If entity A lends to entity B, entity B must receive it. This sounds obvious,
but requires explicit wiring in a multi-entity model:

```
Orchestrator: Extract LanRED deficit --> NWL lends OD --> Extract OD lent
    --> Re-run LanRED with od_received_vector --> LanRED waterfall injects OD
```

**Why this matters**: A one-directional OD (NWL records an asset, LanRED does
not record a liability) causes the consolidated BS to double-count the OD
balance and breaks IC elimination at the holding company level.


## 4. Repair 1: Reserve Assets Architecture

**File**: `engine/reserves.py` (new module, 425 lines)

### Before

The waterfall computed FD interest on reserves AND set reserve targets inline:

```python
# BEFORE (inside waterfall_step):
ops_reserve_interest = state.ops_reserve_bal * fd_interest_rate
state.ops_reserve_bal += ops_reserve_interest
ops_reserve_target = opex * ops_reserve_coverage
```

This violated Principle 1 (waterfall is allocation-only) and Principle 2
(reserves are assets). The interest computation was buried inside 800 lines
of allocation logic, making it impossible to audit independently.

### After

Four reserve asset classes, each self-contained:

##there is a 5th in NWL, with a counter party facility in LanRED: for overdraft 

```
+-------------------+-----------------------------+---------------------------+
| Class             | Interest Computation        | Target Computation        |
+-------------------+-----------------------------+---------------------------+
| OpsReserve        | opening x fd_rate / 2       | opex x coverage_pct       |
|                   |                             | (look-ahead if current~0) |
+-------------------+-----------------------------+---------------------------+
| OpcoDSRA          | None (cash reserve, no FD)  | min(next_sr_pi, sr_bal)   |
|                   |                             | (0 when sr_bal ~ 0)       |
+-------------------+-----------------------------+---------------------------+
| MezzDivFD         | opening x fd_rate / 2       | Liability = sum of        |
|                   |                             | mz_ic_opening x mz_div/2  |
+-------------------+-----------------------------+---------------------------+
| EntityFD          | opening x fd_rate / 2       | None (surplus sink)       |
+-------------------+-----------------------------+---------------------------+
```

Each class implements `accrue()` which returns a `ReserveAccrual` dataclass:

```python
@dataclass
class ReserveAccrual:
    opening: float
    interest: float
    balance_after_interest: float  # = opening + interest
    target: float
    gap: float                    # = max(target - balance_after_interest, 0)
    excess: float                 # = max(balance_after_interest - target, 0)
```

The loop calls `reserve.accrue()` BEFORE P&L, producing deterministic
FD income. The waterfall then reads the pre-computed gap and allocates cash:

```python
# AFTER (in run_entity_loop):
ops_accrual = ops_reserve.accrue(cur_opex, next_opex)
dsra_accrual = opco_dsra.accrue()
entity_fd_accrual = entity_fd.accrue()
mz_div_accrual = mz_div_fd.accrue(mz_fac.balance)

fd_income = total_fd_income(ops_accrual, entity_fd_accrual, mz_div_accrual)

# Waterfall reads gaps -- does NOT compute interest or targets
wf_row = waterfall_step(..., ops_accrual=ops_accrual, ...)
```

### Helper: total_fd_income()

Convenience function that sums interest from all FD-bearing reserves:

```python
def total_fd_income(ops_accrual, entity_fd_accrual, mz_div_accrual=None):
    total = ops_accrual.interest + entity_fd_accrual.interest
    if mz_div_accrual is not None:
        total += mz_div_accrual.interest
    return total
```

Note: OpcoDSRA does NOT accrue interest (it is a cash reserve, not a fixed
deposit). This is a deliberate modelling choice reflecting the contractual
nature of the DSRA.

##it IS a FD, but it accrues interest in euro's so, euro FD rate, not sa FD rate.

##the overdraft accrues at 10% inter company, as such, in waterfall acceleration, which is a variable function of highest interest rate to lowest, you need to check interest rate first, than rank them, and this array, of interest bearing facilities, thus is ranked in waterfall. 

### Post-Hoc Verification

Three verification functions reconstruct reserve lifecycles from waterfall
output and cross-check balances:

- `build_reserve_schedule()` -- reconstructs opening/fill/interest/release/closing
- ##just to be sure, you can only do closing post waterfall function completion
- `extract_reserve_vectors()` -- extracts per-reserve vectors from waterfall rows
- `verify_reserve_balance()` -- compares schedule closing vs. waterfall closing


## 5. Repair 2: P&L FD Income Wiring

**Files**: `engine/pnl.py`, `engine/loop.py`

### Before

`build_annual()` fabricated FD interest income using a synthetic proxy:

```python
# BEFORE (in build_annual):
ii_dsra = _cash_bal * 0.05  # Hardcoded 5% on running cash accumulator
```

This was wrong on three levels:
1. The rate was hardcoded at 5% (actual FD rate = 3.5%) ##FD rate in sa is for rands maybe 8%. for euro, would be 3.5% max
2. The base was a running cash accumulator, not actual reserve balances
3. It was completely disconnected from waterfall FD accruals

### After

#### PnlPeriod dataclass gains fd_income field

```python
@dataclass
class PnlPeriod:
    ...
    fd_income: float    # FD interest income (ops reserve + entity FD + mezz div FD) ##+ DSRA of course
    pbt: float          # = ebit - ie + fd_income
    ...
```

#### compute_period_pnl() accepts fd_income parameter

```python
def compute_period_pnl(hi, ..., *, fd_income: float = 0.0, ...):
    ...
    pbt = ebit - ie + fd_income   # Actual FD income, not a proxy
    ...
```

#### run_entity_loop() computes FD income from reserve accruals BEFORE P&L

```python
# In the loop, BEFORE P&L computation:
fd_income = total_fd_income(ops_accrual, entity_fd_accrual, mz_div_accrual)

pnl, tax_loss_pool = compute_period_pnl(
    hi, ...,
    fd_income=fd_income,  # Actual accrual from reserve assets
    ...
)
```

#### build_annual() uses actual waterfall FD interest

```python
# AFTER (in build_annual):
a["ii_dsra"] = (w.get("ops_reserve_interest", 0)
                + w.get("entity_fd_interest", 0)
                + w.get("mz_div_fd_interest", 0))
```

### Verification

FD income traces cleanly through the pipeline:

```
NWL verification:
  P&L fd_income (sum of 20 periods)    = EUR 1,994,080
  Waterfall FD interest (sum of 20 p.) = EUR 1,994,080
  Annual ii_dsra (sum of 10 years)     = EUR 1,994,080
  Match: EXACT

LanRED verification:
  All three sources                    = EUR 298,242
  Match: EXACT

TWX verification:
  All three sources                    = EUR 339,427
  Match: EXACT
```


## 6. Repair 3: Waterfall Cascade Integrity

**File**: `engine/waterfall.py`

### Before: Unconditional Surplus Acceleration

```python
# BEFORE (in waterfall_step):
# Surplus acceleration ran unconditionally
accel_targets = []
if mz_ic_bal > 0.01:
    accel_targets.append(("mz", accel_rate_mz, mz_ic_bal))
...
for akey, arate, abal in accel_targets:
    apay = min(remaining * sweep_pct, abal)
    ...
```

If DSRA was underfunded but there was surplus cash after ops reserve fill,
the waterfall would accelerate debt before topping up DSRA. This violates
the senior lender covenant: DSRA must be fully funded before surplus cash
can be deployed for voluntary acceleration.

### After: DSRA Funding Gate

```python
# AFTER (in waterfall_step):
# Surplus acceleration -- GATED on DSRA funding level (B1)
# Grant-funded acceleration (special pool -> Sr IC above) is NOT gated.
dsra_funded = (state.opco_dsra_bal >= opco_dsra_target - 0.01) \
              or opco_dsra_target < 0.01

if dsra_funded and remaining > 0:
    accel_targets = []
    if mz_ic_bal > 0.01:
        accel_targets.append(("mz", accel_rate_mz, mz_ic_bal))
    ...
```

Two important distinctions:

1. **Surplus acceleration IS gated**: Cash surplus from operations that would
   voluntarily prepay debt must wait until DSRA is fully funded. ##except for specials of course

2. **Grant-funded acceleration is NOT gated**: Grants (DTIC, GEPF) applied to
   the special pool and accelerated into Sr IC are a contractual obligation.
   They flow `special_pool -> Sr IC P+I -> Sr IC acceleration` regardless of
   DSRA status. This acceleration happens BEFORE the DSRA gate in the cascade. ##and also for FEC/swap, correct?

### Cascade Allocation Order (waterfall_step)

```
 +-----------------------------------------------------------------+
 |  WATERFALL ALLOCATION SEQUENCE (per semi-annual period)         |
 +-----------------------------------------------------------------+
 |                                                                 |
 |  1. EBITDA + Cash Inflows --> Split into Special / Normal pools |
 |                                                                 |
 |  2. Special Pool --> Sr IC P+I (contractual)                    |
 |     Special Pool residual --> Sr IC Acceleration (NOT gated)    |
 |                                                                 |
 |  3. Normal Pool - remaining debt service = net surplus          |
 |                                                                 |
 |  4. Ops Reserve: fill gap (target - balance)                    |
 |  5. OpCo DSRA: fill gap / release excess                       |
 |  6. IC Overdraft: NWL lends to LanRED (if applicable)          |
 |  7. Mezz Div FD: fill toward liability                          |
 |                                                                 |
 |  8. DSRA GATE CHECK                                             |
 |     |                                                           |
 |     +-- DSRA funded? --> YES --> Surplus Acceleration           |
 |     |                           (rate-priority: Mz > ZAR > Sr)  |
 |     +-- DSRA NOT funded? --> STOP. No voluntary acceleration.   |
 |                                                                 |
 |  9. OD Repayment (LanRED only)   ##no, this is rate priority, its just a facility from NWL perspective, and has a potenail higher interest rate than Swap.                              |
 | 10. Entity FD: fill (only when ALL debt = 0)                   |
 | 11. Dividends: extract from Entity FD (if eligible)            |
 |                                                                 |
 +-----------------------------------------------------------------+
```


## 7. Repair 4: IC Overdraft Two-Way Flow

**Files**: `engine/loop.py`, `engine/waterfall.py`, `engine/orchestrator.py`

### Before: One-Way Flow

The orchestrator set `inputs._nwl_od_lent_vector` and re-ran LanRED, but:

1. LanRED's entity builder never read `_nwl_od_lent_vector` from inputs
2. `run_entity_loop()` had no `od_received_vector` parameter
3. `waterfall_step()` hardcoded `od_received = 0.0`

Result: NWL recorded an OD asset, but LanRED never received the cash.
LanRED's waterfall ran as if the OD did not exist.

### After: Complete Two-Way Wiring

```
+-------------------------------------------------------------------+
|  IC OVERDRAFT FLOW (Orchestrator PASS 2)                          |
+-------------------------------------------------------------------+
|                                                                   |
|  1. PASS 1 baseline: LanRED runs independently                   |
|     --> Extract deficit_vector from LanRED waterfall              |
|                                                                   |
|  2. Re-run NWL with lanred_deficit_vector                         |
|     --> NWL waterfall: od_lent = min(remaining, deficit)          |
|     --> NWL: state.od_bal += od_lent + interest_on_existing       |
|     --> Extract od_lent_vector from NWL waterfall                 |
|                                                                   |
|  3. Re-run LanRED with od_received_vector = od_lent_vector       |
|     --> LanRED entity builder reads _nwl_od_lent_vector           |
|     --> run_entity_loop(od_received_vector=...)                   |
|     --> waterfall_step(od_received=od_received_vector[hi])        |
|     --> LanRED: state.od_bal += od_received; remaining += ...     |
|                                                                   |
|  Result:                                                          |
|     NWL OD asset   = LanRED OD liability  (matched)              |
|     Consolidated:  od_bal_net = 0  (IC eliminated)                |
|                                                                   |
+-------------------------------------------------------------------+
```

##would re-runs, for multiple entities, get us in the way of a system that is speedy? what kind of overheads are we talking about here? explain the loop properly



The key code changes:

```python
# run_entity_loop() -- new parameter:
def run_entity_loop(
    ...,
    od_received_vector: list[float] | None = None,  # NEW
) -> LoopResult:
    ...
    _od_received = (
        abs(od_received_vector[hi])
        if od_received_vector and hi < len(od_received_vector)
        else 0.0
    )
    wf_row = waterfall_step(..., od_received=_od_received, ...)

# waterfall_step() -- new parameter:
def waterfall_step(
    ...,
    od_received: float = 0.0,  # NEW: IC overdraft received (LanRED only)
    ...
):
    ...
    if entity_key == "lanred":
        if od_received_val > 0:
            state.od_bal += od_received_val
            remaining += od_received_val
        od_interest = state.od_bal * od_rate
        state.od_bal += od_interest
```


## 8. Repair 5: SCLCA Consolidation

**File**: `entities/sclca.py`

### Before

The SCLCA holding company view was incomplete:
- No aggregated facility schedules
- No consolidated DSCR
- No IC elimination logic
- OD balances double-counted at group level

### After

Four deliverables added to the SCLCA return dict:

##is SCLCA paying taxes?

##is SCLCA a third loop, after all companies are balanced?

```
+------+------------------------------+--------------------------------------+
| Code | Deliverable                  | Contents                             |
+------+------------------------------+--------------------------------------+
|  D1  | Facility Schedule            | sr_schedule: 60 rows (3 x 20)       |
|      | Aggregation                  | mz_schedule: 60 rows (3 x 20)       |
|      |                              | Tagged with entity_key per row       |
+------+------------------------------+--------------------------------------+
|  D2  | Consolidated DSCR            | min = 2.41x                          |
|      |                              | avg = 5.89x                          |
|      |                              | Per-entity + weighted-group          |
+------+------------------------------+--------------------------------------+
|  D3  | Consolidated View            | Revenue, opex, EBITDA aggregation    |
|      | with IC Elimination          | BS: assets, debt, equity             |
|      |                              | IC revenue/cost eliminated           |
+------+------------------------------+--------------------------------------+
|  D4  | OD Double-Count Fix          | od_bal_net = NWL asset - LanRED      |
|      |                              | liability = 0 at group level         |
|      |                              | (IC eliminated in consolidation)     |
+------+------------------------------+--------------------------------------+
```


## 9. Repair 6: Column Registry

**File**: `config/columns.json`

Entity tags added to OD-related columns so that the column registry correctly
identifies which entity owns each OD balance. SCLCA consolidation columns
added for the new deliverables (D1-D4).

This ensures the UI and export layers can correctly label and filter columns
by entity and by consolidation level.


## 10. Data Flow Architecture

### The One Big Loop -- Period Execution Order

```
 +========================================================================+
 |              PERIOD hi (0..19) -- SINGLE PASS                          |
 +========================================================================+
 |                                                                        |
 |  [1] FacilityState.compute_period(hi)                                  |
 |      |                                                                 |
 |      +--> FacilityPeriod {                                             |
 |               opening, interest, idc, principal,                       |
 |               pi, pre_accel_closing                                    |
 |           }                                                            |
 |                                                                        |
 |  [2] Reserve Assets: accrue() -- BEFORE P&L   
 ##for CA, you would have the facilities to the entities to run over here, so i think you need to specificy that too. thats a facility on opcos, and an asset on CA. in ca financial assets and faciities must match of course.
 |
 |      |                                                                 |
 |      +--> OpsReserve.accrue(cur_opex, next_opex)                       |
 |      |        --> ReserveAccrual { opening, interest, target, gap }    |
 |      |                                                                 |
 |      +--> OpcoDSRA.accrue()                                            |
 |      |        --> ReserveAccrual { opening, 0 interest, target, gap }  |
 |      |                                                                 |
 |      +--> EntityFD.accrue()                                            |
 |      |        --> ReserveAccrual { opening, interest, 0 target }       |
 |      |                                                                 |
 |      +--> MezzDivFD.accrue(mz_fac.balance)                             |
 |               --> ReserveAccrual { opening, interest, liability, gap } |
 |                                                                        |
 |  [3] total_fd_income(ops, entity_fd, mz_div) --> fd_income             |
 |                                                                        |
 |  [4] compute_period_pnl(                                               |
 |          ...,                                                          |
 |          sr_interest = sr_period.interest,                              |
 |          mz_interest = mz_period.interest,                             |
 |          fd_income   = fd_income,            <-- actual reserve income  |
 |      )                                                                 |
 |      |                                                                 |
 |      +--> PnlPeriod {                                                  |
 |               rev, opex, ebitda, depr, ebit,                           |
 |               ie, fd_income, pbt, tax, pat                             |
 |           }                                                            |
 |                                                                        |
 |  [5] waterfall_step(                                                   |
 |          ...,                                                          |
 |          ebitda, opex, tax,                    <-- from P&L            |
 |          sr_interest, sr_principal, sr_pi,     <-- from Facility       |
 |          ops_accrual, dsra_accrual, ...,       <-- from Reserves       |
 |          ops_reserve_obj, dsra_obj, ...,       <-- reserve objects     |
 |          od_received,                          <-- from IC plugin      |
 |      )                                                                 |
 |      |                                                                 |
 |      +--> ALLOCATION ONLY:                                             |
 |           - Read gaps from accruals                                    |
 |           - Fill reserves (ops, DSRA, mezz div FD)                     |
 |           - Gate check: DSRA funded?                                   |
 |           - Accelerate debt (if gated)                                 |
 |           - Fill entity FD (if all debt = 0)                           |
 |           - Pay dividends (if eligible)                                |
 |                                                                        |
 |  [6] FacilityState.finalize_period(hi, acceleration=sr_accel)          |
 |      FacilityState.finalize_period(hi, acceleration=mz_accel)          |
 |      |                                                                 |
 |      +--> Closing = pre_accel_closing - acceleration                   |
 |      +--> Recalculate P_constant for remaining periods                 |
 |                                                                        |
 |  [7] OpcoDSRA.set_target(sr_fac.next_pi_estimate(), sr_fac.balance)   |
 |      |                                                                 |
 |      +--> Ready for period hi+1                                        |
 |                                                                        |
 +========================================================================+
```

### FD Income Pipeline (Single Source of Truth)

```
 Reserve Assets                 P&L                     Annual
 ============                   ===                     ======

 OpsReserve.accrue()
   .interest ----+
                 |
 EntityFD.accrue()              compute_period_pnl()    build_annual()
   .interest ----+--> total_fd  |                       |
                 |    _income() --> fd_income param --> ii_dsra =
 MezzDivFD.accrue()             |   pbt = ebit         ops_reserve_interest
   .interest ----+              |         - ie          + entity_fd_interest
                                |         + fd_income   + mz_div_fd_interest
                                |                       |
                                v                       v
                         PnlPeriod.fd_income     a["ii_dsra"]

 ALL THREE MUST MATCH (verified to EUR 0.00 tolerance)
 
 ##I would like to also see how Q*P and COGS is done, how these loops contribute.
```

### Multi-Entity Orchestration

```
 +==========================================================+
 |  PASS 1: Independent Entity Runs                         |
 +==========================================================+
 |                                                          |
 |  build_lanred_entity(cfg, inputs) --> EntityResult       |
 |  build_twx_entity(cfg, inputs)    --> EntityResult       |
 |  build_nwl_entity(cfg, inputs)    --> EntityResult       |
 |                                                          |
 |  (No IC dependencies -- all run with default vectors)    |
 |                                                          |
 +==========================================================+
 |  PASS 2: IC Correction Plugins                           |
 +==========================================================+
 |                                                          |
 |  ic_nwl_lanred_overdraft:                                |
 |    1. Extract LanRED deficit_vector                      |
 |    2. Re-run NWL with lanred_deficit_vector              |
 |    3. Extract NWL od_lent_vector                         |
 |    4. Re-run LanRED with od_received_vector              |
 |                                                          |
 |    NWL:    od_bal (asset)    = total OD lent              |
 |    LanRED: od_bal (liability)= total OD received         |
 |    Group:  od_bal_net        = 0 (IC eliminated)          |
 |                                                          |
 +==========================================================+
 |  PASS 3: SCLCA Consolidation                             |
 +==========================================================+
 |                                                          |
 |  build_sclca_holding(entities, cfg):                     |
 |    D1: Facility schedules (60 rows each Sr/Mz)          |
 |    D2: Consolidated DSCR (min 2.41x, avg 5.89x)         |
 |    D3: P&L / BS consolidation with IC elimination        |
 |    D4: OD double-count fix (net = 0)                     |
 |                                                          |
 +==========================================================+
```


## 11. File Change Summary

```
+----------------------------+------+-----------------------------------------------+
| File                       | Lines| What Changed                                  |
+----------------------------+------+-----------------------------------------------+
| engine/reserves.py         | 425  | NEW. Four reserve asset classes (OpsReserve,  |
|                            |      | OpcoDSRA, MezzDivFD, EntityFD).               |
|                            |      | ReserveAccrual dataclass. total_fd_income().   |
|                            |      | Post-hoc verification (build_reserve_schedule, |
|                            |      | extract_reserve_vectors, verify_reserve_bal).  |
|                            |      |                                               |
|                            |      | WHY: Reserves are financial assets that must   |
|                            |      | own their interest and target computations.    |
|                            |      | Extracting this from the waterfall restores    |
|                            |      | separation of concerns.                       |
+----------------------------+------+-----------------------------------------------+
| engine/pnl.py              |  ~30 | PnlPeriod gains fd_income field.              |
|                            |      | compute_period_pnl() accepts fd_income param. |
|                            |      | PBT = EBIT - IE + fd_income.                  |
|                            |      |                                               |
|                            |      | WHY: P&L must reflect actual FD interest from |
|                            |      | reserve accruals, not synthetic proxies.       |
+----------------------------+------+-----------------------------------------------+
| engine/loop.py             | ~100 | run_entity_loop() gains od_received_vector     |
|                            |      | parameter. Initializes 4 reserve asset objects.|
|                            |      | Calls reserve.accrue() BEFORE P&L.            |
|                            |      | Passes accrual results to waterfall_step().   |
|                            |      | build_annual(): ii_dsra = actual waterfall     |
|                            |      | FD interest (ops + entity + mz_div).          |
|                            |      |                                               |
|                            |      | WHY: The loop is the orchestration layer that  |
|                            |      | sequences reserves -> P&L -> waterfall.       |
|                            |      | It must wire FD income from reserves to P&L   |
|                            |      | and pass pre-computed accruals to waterfall.  |
+----------------------------+------+-----------------------------------------------+
| engine/waterfall.py        |  ~80 | waterfall_step() accepts reserve accrual       |
|                            |      | parameters and reserve objects.                |
|                            |      | When accruals provided: reads interest/target  |
|                            |      | from them (allocation-only mode).              |
|                            |      | When accruals NOT provided: falls back to      |
|                            |      | inline computation (batch backward compat).   |
|                            |      | Surplus acceleration wrapped in DSRA gate.    |
|                            |      | od_received parameter for LanRED injection.   |
|                            |      |                                               |
|                            |      | WHY: Waterfall must be allocation-only when    |
|                            |      | reserve objects are available. DSRA gate       |
|                            |      | enforces senior lender covenant. OD injection  |
|                            |      | enables bidirectional IC flow.                |
+----------------------------+------+-----------------------------------------------+
| engine/orchestrator.py     |  ~10 | IC plugin extracts od_lent_vector and passes   |
|                            |      | it as _nwl_od_lent_vector to inputs.          |
|                            |      | LanRED re-run receives the vector.            |
|                            |      |                                               |
|                            |      | WHY: Completes the OD two-way flow. Without   |
|                            |      | this, NWL records an asset but LanRED never   |
|                            |      | receives the cash.                            |
+----------------------------+------+-----------------------------------------------+
| entities/lanred.py         |  ~10 | Entity builder reads _nwl_od_lent_vector from |
|                            |      | inputs. Passes as od_received_vector to        |
|                            |      | run_entity_loop().                             |
|                            |      |                                               |
|                            |      | WHY: LanRED must read the OD vector so it     |
|                            |      | flows through to waterfall_step().            |
+----------------------------+------+-----------------------------------------------+
| entities/sclca.py          |  ~80 | D1: Facility schedule aggregation.            |
|                            |      | D2: Consolidated DSCR computation.            |
|                            |      | D3: Consolidated P&L/BS with IC elimination.  |
|                            |      | D4: OD double-count fix (net = 0).            |
|                            |      |                                               |
|                            |      | WHY: The holding company view must be complete |
|                            |      | for lender reporting and equity valuation.    |
+----------------------------+------+-----------------------------------------------+
| config/columns.json        |  ~20 | Entity tags on OD columns. SCLCA columns      |
|                            |      | for new consolidation deliverables.            |
|                            |      |                                               |
|                            |      | WHY: Column registry drives UI filtering and  |
|                            |      | export labelling. Must reflect actual columns. |
+----------------------------+------+-----------------------------------------------+
```


## 12. Verification Results

### Balance Sheet Identity

The fundamental accounting identity
`Assets - Debt = Equity + Cumulative PAT + Cumulative Grants - Cumulative Dividends`
must hold to zero for every entity, every year.

```
+-------------+----------+----------+----------+----------+----------+
| Entity      | Y1       | Y3       | Y5       | Y7       | Y10      |
+-------------+----------+----------+----------+----------+----------+
| NWL         | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 |
| LanRED      | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 |
| TWX         | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 | EUR 0.00 |
+-------------+----------+----------+----------+----------+----------+
```

### FD Income Consistency

Three independent sources of FD income must produce identical totals:

```
+-------------+------------------+------------------+------------------+
| Entity      | P&L fd_income    | Waterfall FD int | Annual ii_dsra   |
|             | (20-period sum)  | (20-period sum)  | (10-year sum)    |
+-------------+------------------+------------------+------------------+
| NWL         | EUR 1,994,080    | EUR 1,994,080    | EUR 1,994,080    |
| LanRED      | EUR   298,242    | EUR   298,242    | EUR   298,242    |
| TWX         | EUR   339,427    | EUR   339,427    | EUR   339,427    |
+-------------+------------------+------------------+------------------+
```

### DSRA Gate Verification

No period exhibits surplus acceleration while DSRA is underfunded:

```
For all entities, for all periods hi = 0..19:
  IF (mz_accel_entity > 0 OR sr_accel_entity > 0 OR swap_leg_accel > 0)
  THEN (opco_dsra_bal >= opco_dsra_target - 0.01 OR opco_dsra_target < 0.01)

Result: PASS (0 violations across 60 entity-periods)

Exception: Grant-funded acceleration (special pool -> Sr IC) is correctly
excluded from the gate and operates independently.
```

### Consolidated DSCR

```
Group DSCR (weighted by debt service):
  Minimum: 2.41x
  Average: 5.89x
```

### OD IC Elimination

```
NWL OD asset (Year 10):       od_bal = X
LanRED OD liability (Year 10): od_bal = X
Group net:                     od_bal_net = 0  (IC eliminated)
```


## 13. Backward Compatibility

The repair preserves backward compatibility through a dual-path design
in `waterfall_step()`:

```python
def waterfall_step(..., ops_accrual=None, dsra_accrual=None, ...):
    if ops_accrual is not None:
        # RESERVE OBJECT PATH: interest and targets from pre-computed accruals
        ops_reserve_interest = ops_accrual.interest
        ops_reserve_target = ops_accrual.target
        state.ops_reserve_bal = ops_accrual.balance_after_interest
    else:
        # INLINE PATH: compute interest and targets inline (batch compat)
        ops_reserve_interest = state.ops_reserve_bal * fd_interest_rate
        state.ops_reserve_bal += ops_reserve_interest
        ops_reserve_target = opex * ops_reserve_coverage
```

This means:

1. **One Big Loop** (`run_entity_loop()`): Uses reserve objects.
   Accruals computed before P&L. Waterfall receives pre-computed results.

2. **Batch interface** (`compute_entity_waterfall()`): No reserve objects.
   Waterfall computes interest and targets inline. Same numerical results
   for the same inputs. Used by standalone sensitivity analysis and legacy
   callers.

Both paths produce identical output for the same input conditions. The
batch interface will eventually be migrated to use reserve objects, but
this is not urgent because the batch interface does not feed into P&L
(it is used for post-hoc analysis only).


## 14. Design Decisions

### Decision 1: Reserves as Classes, Not Functions

**Considered**: Pure functions that take opening balance and return closing.
**Chosen**: Stateful classes that carry their own balance.

**Rationale**: Reserve accounts have lifecycle behavior (fill, release, payout,
set_target) that benefits from encapsulation. The OpcoDSRA `funded` property
and MezzDivFD `should_payout` logic are cleaner as methods than as standalone
conditionals scattered across the waterfall.

### Decision 2: DSRA Has No Interest

##inccorect

**Considered**: All reserves accrue FD interest.
**Chosen**: DSRA accrues no interest.

**Rationale**: The DSRA is a contractual cash reserve held against the next
senior P+I obligation. In this project's terms, it is not an FD. It is a
segregated cash account. Accruing interest on it would inflate FD income
without a corresponding actual deposit receipt.

### Decision 3: DSRA Gate Uses EUR 0.01 Tolerance

**Considered**: Exact equality check (`dsra_bal >= dsra_target`).
**Chosen**: Tolerance check (`dsra_bal >= dsra_target - 0.01`).

**Rationale**: Floating point arithmetic across 20 periods can produce
sub-cent differences. A EUR 0.01 tolerance prevents spurious gate failures
while being well below the materiality threshold.

### Decision 4: Grant Acceleration Bypasses DSRA Gate

**Considered**: All acceleration gated on DSRA.
**Chosen**: Only surplus acceleration gated. Grant acceleration is ungated.

**Rationale**: Grant-funded acceleration flows through the special pool:
`Grant -> Special Pool -> Sr IC P+I -> Sr IC Acceleration`. This is a
contractual mechanism where the grant is specifically designated for debt
reduction. Gating it on DSRA would mean the grant sits idle while DSRA
is underfunded, which contradicts the grant agreement terms.

### Decision 5: MezzDivFD Tracks Both FD and Liability

**Considered**: Separate liability tracker outside the reserve.
**Chosen**: MezzDivFD tracks both its FD balance and its accrued liability.

**Rationale**: The Mezz dividend mechanism has a unique lifecycle: liability
accrues on the Mezz IC opening balance each period, FD accumulates cash
toward that liability, and when Mezz IC is fully repaid, the FD pays out.
These three elements (liability accrual, FD interest, payout trigger) are
intrinsically coupled. Separating them would scatter related logic across
multiple modules.

---

*This document describes the state of the engine as of 2026-03-01.
For the detailed per-period loop specification, see FLOW.md.
For the DAG execution plan, see DAG.md.*
