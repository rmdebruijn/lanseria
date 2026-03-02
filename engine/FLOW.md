# The Semi-Annual Loop

A universal project-finance engine. Each of the 20 canonical periods
(hi = 0..19) executes the same loop. The closing state of period N
becomes the opening state of period N+1.

Any upstream module (ops, revenue, cost, tariff, volume) simply feeds
into step 1. Any downstream consumer (reporting, ratios, dashboards)
reads from the completed period state. To model a new project, swap
the upstream modules — the loop stays the same.

```
 UPSTREAM MODULES (pluggable per project)
 =========================================

 +------------------+    +------------------+    +------------------+
 | Volume Model     |    | Tariff / Price   |    | Cost Model       |
 |                  |    |                  |    |                  |
 | capacity (m3/h)  |    | tariff (EUR/m3)  |    | fixed opex       |
 | utilisation %    |    | escalation %     |    | variable opex    |
 | seasonal curve   |    | contract terms   |    | O&M indexation   |
 | downtime         |    | take-or-pay      |    | insurance        |
 +--------+---------+    +--------+---------+    +--------+---------+
          |                       |                       |
          +----------+------------+-----------+-----------+
                     |                        |
                     v                        v
            Quantity x Price           Sum of cost lines
                     |                        |
                     +------------+-----------+
                                  |
                                  v
                             Revenue, Opex


 THE LOOP (one iteration per semi-annual period)
 =================================================

+==============================================================================+
|                    SEMI-ANNUAL PERIOD hi (0..19)                              |
|                                                                              |
|  State carried forward from period hi-1:                                     |
|    * Facility opening balances (Sr, Mz, Swap ZAR)                            |
|    * Financial asset balances (Swap EUR, OpCo DSRA, Ops Reserve, Entity FD,  |
|      Mezz Div FD, Overdraft)                                                 |
|    * Accumulated depreciation, cumulative capex                              |
|    * Tax loss pool                                                           |
|    * Cumulative PAT + grants (for RE check)                                  |
+==============================================================================+
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  | 1. OPERATING MODEL                                                    |   |
|  |                                                                       |   |
|  |    Revenue  = Quantity x Price     (from upstream modules)             |   |
|  |    Opex     = Sum of cost lines    (from upstream modules)             |   |
|  |    EBITDA   = Revenue - Opex                                          |   |
|  |                                                                       |   |
|  |    Note: during construction, Revenue = 0. But EBITDA can be non-zero |   |
|  |    if a grant is recognized as EBITDA (e.g. GEPF at C3).              |   |
|  +-------------------------------+--------------------------------------+   |
|                                  |                                           |
|                                  v                                           |
|  +----------------------------------------------------------------------+   |
|  | 2. FACILITY SCHEDULE (reads previous closing, calculates I & P)       |   |
|  |                                                                       |   |
|  |  For each facility (Sr IC, Mz IC, Swap ZAR):                         |   |
|  |                                                                       |   |
|  |    Opening = PREVIOUS period's Closing  (carried forward)             |   |
|  |                                                                       |   |
|  |    Construction (hi 0-3):                                             |   |
|  |      IDC = Opening x rate / 2     (capitalised, NOT cash)             |   |
|  |      Draw Down = per drawdown schedule                                |   |
|  |      Closing = Opening + Draw Down + IDC                              |   |
|  |      Cash Interest = 0  (IDC is not a cash / P&L item)               |   |
|  |      Principal = 0                                                    |   |
|  |                                                                       |   |
|  |    Repayment (hi 4-17):                                               |   |
|  |      Interest = Opening x rate / 2          (cash expense)            |   |
|  |      P_constant = Opening / N_remaining     (scheduled amount)        |   |
|  |      (these are CALCULATED amounts -- waterfall decides what's PAID)  |   |
|  |                                                                       |   |
|  |    Tail (hi 18-19):                                                   |   |
|  |      All facilities fully repaid, balances = 0                        |   |
|  +-------------------------------+--------------------------------------+   |
|                                  |                                           |
|            +---------------------+---------------------+                     |
|            v                                           v                     |
|  +---------------------------+   +---------------------------------------+   |
|  | 3a. P&L                   |   | 3b. CASH FLOW                         |   |
|  |                           |   |                                       |   |
|  |  Revenue                  |   |  Cash from Ops                        |   |
|  |  - Opex                   |   |    = EBITDA                           |   |
|  |  = EBITDA                 |   |    - Tax                              |   |
|  |  - Depreciation      [A]------+    + Grants (cash)                    |   |
|  |  = EBIT                   |   |    + FD income (from reserves)        |   |
|  |  - Interest Expense  [F]------+  - Debt Service                       |   |
|  |  + FD Income         [R]------+    = Sr P+I + Mz P+I + Swap ZAR      |   |
|  |  = PBT                   |   |  + Draw Downs                          |   |
|  |  - Tax               [T]------+    (facility draws during constr.)    |   |
|  |  = PAT                   |   |  - Capex                          [A]  |   |
|  |                           |   |  - Acceleration                  [F]  |   |
|  |  [A] = from Assets        |   |  +/- Reserve fills / releases    [R]  |   |
|  |  [F] = from Facilities    |   |  = Net Cash                           |   |
|  |  [R] = from Reserves      |   |                                       |   |
|  |  [T] = with loss pool     |   |  [A] = into/from Assets               |   |
|  +---------------------------+   |  [F] = into/from Facilities            |   |
|                                  |  [R] = into/from Reserves              |   |
|                                  +------------------+--------------------+   |
|                                                     |                        |
|                                                     v                        |
|  +----------------------------------------------------------------------+   |
|  | 4. WATERFALL (Allocator -- puts cash into buckets)                    |   |
|  |                                                                       |   |
|  |  Two pools enter the waterfall:                                       |   |
|  |                                                                       |   |
|  |    NORMAL pool  = EBITDA (all periods except C3)                      |   |
|  |    SPECIAL pool = DTIC grant + pre-rev hedge + EBITDA@C3 (GEPF)      |   |
|  |                                                                       |   |
|  |  Tax is split pro-rata across pools.                                  |   |
|  |  Specials skip debt service -- jump straight to Sr Acceleration.      |   |
|  |  Normal pool follows the full cascade:                                |   |
|  |                                                                       |   |
|  |  DEBT SERVICE CASCADE (normal pool only):                             |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |  |  1. Half Sr Interest          }                                 |  |   |
|  |  |  2. Half Mz Interest          } first pass: ensure minimum      |  |   |
|  |  |  3. Sr P + I (full)           } debt service is covered         |  |   |
|  |  |  4. Mz P + I (full)           }                                 |  |   |
|  |  |  5. Sr Scheduled Principal    }                                 |  |   |
|  |  |  6. Mz Scheduled Principal    }                                 |  |   |
|  |  |  7. Swap ZAR leg (scheduled)  }                                 |  |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |                                                                       |   |
|  |  = Debt Service Cash (subtotal)                                       |   |
|  |                                                                       |   |
|  |  + CASH INFLOWS (period-specific, see timing matrix below):           |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |  |  * DTIC Grant (cash)             --> special pool               |  |   |
|  |  |  * IIC / TA Grant                --> normal pool                |  |   |
|  |  |  * Pre-revenue hedge proceeds    --> special pool               |  |   |
|  |  |  * Mezz drawdown (if sculpted)   --> special pool               |  |   |
|  |  |  * EUR leg repayment (swap)      --> special pool               |  |   |
|  |  |  * DSRA Release                  --> normal pool                |  |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |                                                                       |   |
|  |  Surplus Available = (normal after DS) + (special after tax)          |   |
|  |                                                                       |   |
|  |  RESERVE & ACCELERATION CASCADE:                                      |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |  |   8. Ops Reserve fill ---------> Ops Reserve [R]                |  |   |
|  |  |   9. OpCo DSRA fill -----------> OpCo DSRA   [R]  (1x Sr P+I)  |  |   |
|  |  |  10. Overdraft repay / lend ---> Overdraft    [R]               |  |   |
|  |  |  11. Mezz Div Reserve ---------> Mezz Div FD  [R]               |  |   |
|  |  |  12. Sr Acceleration ----------> Sr Facility  [F]               |  |   |
|  |  |      (specials land here directly)                              |  |   |
|  |  |  13. Mz Acceleration ----------> Mz Facility  [F]  (after sr=0)|  |   |
|  |  |  14. Swap ZAR Acceleration ----> Swap ZAR     [F]               |  |   |
|  |  |  15. Entity FD fill -----------> Entity FD    [R]               |  |   |
|  |  |  16. Free Surplus                                               |  |   |
|  |  +-----------------------------------------------------------------+  |   |
|  |                                                                       |   |
|  |  Reserve RELEASES (when target drops or debt repaid):                 |   |
|  |    DSRA release when Sr repaid --> feeds back into surplus            |   |
|  |    Ops Reserve release if bal > target                                |   |
|  +-------------------------------+--------------------------------------+   |
|                                  |                                           |
|          +-----------------------+-----------------------+                   |
|          v                       v                       v                   |
|  +------------------+  +------------------+  +------------------------+     |
|  | 5a. FACILITY     |  | 5b. FINANCIAL    |  | 5c. PHYSICAL ASSETS    |     |
|  |     CLOSING      |  |     ASSETS       |  |                        |     |
|  |                  |  |     (Reserves)   |  |  Capex (construction)  |     |
|  | Sr IC:           |  |                  |  |  - Accum Depreciation  |     |
|  |  Opening         |  | Each reserve:    |  |  = Net Fixed Assets    |     |
|  |  + Draw Down     |  |  Opening         |  |                        |     |
|  |  + Interest      |  |  + Fill     [W]  |  |  Depreciation:         |     |
|  |  - Principal [W] |  |  + Interest      |  |  S12C accelerated      |     |
|  |  - Accel     [W] |  |  - Release  [W]  |  |  40/20/20/20 over      |     |
|  |  = Closing       |  |  = Closing       |  |  4 years from COD      |     |
|  |                  |  |                  |  |                        |     |
|  | Mz IC: (same)    |  | Reserves:        |  |  Swap EUR Leg (asset): |     |
|  | Swap ZAR: (same) |  |  * Ops Reserve   |  |  Bullet or amort       |     |
|  |                  |  |  * OpCo DSRA     |  |  delivery to IIC       |     |
|  | Movement =       |  |  * Entity FD     |  |                        |     |
|  |  DD + I - P - A  |  |  * Mezz Div FD   |  | [W] = from waterfall   |     |
|  | Closing =        |  |  * Overdraft     |  |                        |     |
|  |  Opening + Mvmt  |  |                  |  +------------------------+     |
|  |                  |  | [W] = from       |                                 |
|  | [W] = allocated  |  |   waterfall      |                                 |
|  |   by waterfall   |  +------------------+                                 |
|  +------------------+                                                       |
|                                                                              |
|          +--------------------------------------------------------------+    |
|          v                                                              |    |
|  +----------------------------------------------------------------------+   |
|  | 6. BALANCE SHEET (snapshot at period end)                              |   |
|  |                                                                       |   |
|  |  ASSETS                          |  LIABILITIES                       |   |
|  |  --------------------------------|----------------------------------  |   |
|  |  Fixed Assets             [5c]   |  Sr IC Closing            [5a]    |   |
|  |    Capex - Accum Depr            |  Mz IC Closing            [5a]    |   |
|  |                                  |  Swap ZAR Liability       [5a]    |   |
|  |  Financial Assets                |  --------------------------------  |   |
|  |    Swap EUR Leg           [5c]   |  Total Debt                       |   |
|  |    Ops Reserve            [5b]   |                                    |   |
|  |    OpCo DSRA              [5b]   |  EQUITY                            |   |
|  |    Mezz Div FD            [5b]   |  --------------------------------  |   |
|  |    Entity FD              [5b]   |  Share Capital (injected)          |   |
|  |  --------------------------------|  Retained Earnings                 |   |
|  |  Total Assets                    |    = Cumulative PAT + Grants       |   |
|  |                                  |  --------------------------------  |   |
|  |                                  |  Total Equity                      |   |
|  |                                  |                                    |   |
|  |  CHECK: Total Assets = Total Debt + Total Equity                      |   |
|  |  CHECK: Retained Earnings = Cumulative PAT + Cumulative Grants        |   |
|  |         (BS Gap = 0)                                                  |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  | 7. RATIOS & COVENANTS (read-only, never feed back)                    |   |
|  |                                                                       |   |
|  |    DSCR = Cash from Ops / Debt Service                                |   |
|  |    LLCR = NPV(future CFADS) / Outstanding Debt                        |   |
|  |    PLCR = NPV(future CFADS over project life) / Outstanding Debt      |   |
|  |    Gearing = Total Debt / Total Assets                                |   |
|  |    Interest Cover = EBITDA / Interest Expense                         |   |
|  |    Debt/Equity = Total Debt / Total Equity                            |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+==============================================================================+
|                                                                              |
|  ---> Carry forward to period hi+1:                                          |
|         Facility closings, reserve balances, accum depreciation,             |
|         tax loss pool, cumulative PAT + grants                               |
|                                                                              |
+==============================================================================+


 CONVERGENCE (ELIMINATED)
 ========================

  The old code ran up to 5 convergence iterations because it batch-built
  the facility schedule first, then ran the waterfall, then rebuilt the
  facility with new acceleration amounts, and repeated until stable.

  The One Big Loop eliminates this entirely. Within a single period:

    1. Opening balance is FIXED (carried from previous period's Closing)
    2. Interest = Opening × rate / 2  ← deterministic, no iteration
    3. Principal = Opening / N_remaining  ← deterministic
    4. P&L uses that Interest
    5. Waterfall allocates cash → decides Acceleration
    6. Closing = Opening - Principal - Acceleration

  There is no circularity within a period. Opening is known. Everything
  flows forward. Acceleration at period N reduces Closing(N), which
  becomes Opening(N+1) — but N is already final by then.

  Single pass. Zero iterations. Zero convergence tolerance.

  See engine/DAG.md for the full proof of why this works.


 FACILITY CLOSING — THE ONLY FORMULA
 =====================================

  There is no "prepayment". There is only:

    CONSTRUCTION:
      Closing = Opening + Draw Down + IDC

    REPAYMENT:
      Closing = Opening
              + Draw Down        (rare: only if DSRA drawdown sculpted)
              + Interest         (Opening x rate / 2)
              - Principal        (scheduled: P_constant)
              - Acceleration     (waterfall-allocated surplus)
              = Opening + Movement

  "Acceleration" is the ONLY mechanism for paying down faster than
  scheduled. Grants, specials, surplus cash — everything that accelerates
  repayment flows through the waterfall and comes out as acceleration.

  The facility doesn't know or care where the cash came from. It just
  sees: "waterfall says pay EUR X extra this period". That's acceleration.

  After acceleration, P_constant is recalculated:
    P_constant(next) = Closing / N_remaining

  In the old batch approach, this chain (lower balance → lower interest
  → more cash → more acceleration) required convergence iterations. In the
  One Big Loop, this chain resolves naturally: acceleration at period N
  reduces Closing(N), and the effect propagates forward to period N+1's
  Opening — no re-run needed.


 TIMELINE & PERIOD-BY-PERIOD MATRIX (NWL example)
 ==================================================

  hi:   0     1     2     3    |  4     5     6     ...   17    | 18    19
        C1    C2    C3    C4   |  R1    R2    R3    ...   R14   | T1    T2
  mo:   0     6     12    18   |  24    30    36    ...   108   | 114   120

  The waterfall table starts at C2 (first period with any cash to allocate).
  C1 has no cash flow -- only facility drawdowns and IDC.

               C1     C2      C3      C4     R1     R2 ... R14    T1    T2
            +------+-------+-------+-------+------+------+------+------+------+
  EBITDA    |   0  | 2,239 | 2,589 | 2,474 | ...  | ...  | ...  | ...  | 3,037|
            +------+-------+-------+-------+------+------+------+------+------+
  DTIC      |      | 1,159 |       |       |      |      |      |      |      |
  IIC/TA    |      |    50 |       |       |      |      |      |      |      |
  Pre-Rev   |      |       |       | 2,172 |      |      |      |      |      |
  Hedge     |      |       |       |       |      |      |      |      |      |
  DSRA Rel  |      |       |       |  18   |  18  |  18  | ...  |  55  |      |
            +------+-------+-------+-------+------+------+------+------+------+
  Tax       |      |  (30) | (226) | (353) | (343)| (360)| ...  | ...  | (820)|
            +------+-------+-------+-------+------+------+------+------+------+
  CASH AVAIL|   0  | 3,418 | 4,535 | 2,121 | 2,043| 2,043| ...  | 2,049| 2,217|
            +------+-------+-------+-------+------+------+------+------+------+
  Sr P+I    |      |       |       | (954) | (936)| (918)| ...  |      |      |
  Swap ZAR  |      |       |       |       | (380)| (369)| ...  |      |      |
  Mz P+I    |      |       |       | (329) | (315)| (301)| ...  |      |      |
            +------+-------+-------+-------+------+------+------+------+------+
  SURPLUS   |   0  | 3,418 |   519 | 3,253 |  871 |  445 | ...  | 2,049| 2,217|
  AVAILABLE |      |       |       |       |      |      |      |      |      |
            +------+-------+-------+-------+------+------+------+------+------+
  Ops Res   |      |  (50) | (253) |  (25) |  (65)|   (4)|      |   (5)|   (5)|
  DSRA Fill |      |       | (265) | (670) |      |      |      |      |      |
  OD lend   |      |       |       |       |      |      |      |      |      |
  Mz Div FD |      |       | (184) |  (37) |  (31)|  (25)| ...  |      |      |
  Mz Accel  |      |       |(1,259)| (787) | (429)| (477)| ...  |      |      |
  ZAR Accel |      |       |       |       |      |      | ...  |      |      |
  Sr Accel  |      |(3,368)|(1,115)|       |      |      |      | (969)| (699)|
  Entity FD |      |       |       |       |      |      |      | (418)|(1,853)|
            +------+-------+-------+-------+------+------+------+------+------+

  Reading the matrix:
  - C1: nothing happens in waterfall. Facility drawdown + IDC only.
  - C2: DTIC (1,159) + IIC (50) + EBITDA (2,239) = 3,418 cash available.
         Both grants are SPECIAL at C2 -> jump to Sr Acceleration (3,368).
         Note: EBITDA at C2 is NORMAL cash, but no P+I due yet.
  - C3: EBITDA (2,589) tagged as SPECIAL (GEPF recognised).
         Entire EBITDA jumps to acceleration. Mz Accel gets 1,259.
  - C4: Pre-rev hedge (2,172) enters as SPECIAL.
         First period with Sr P+I (954) and Mz P+I (329).
  - R1+: Normal operations. EBITDA is NORMAL, pays DS first,
         surplus cascades through reserves then acceleration.
  - T1/T2: All debt repaid. Surplus fills Entity FD.

  The SPECIAL vs NORMAL tagging rule:
    * DTIC grant           --> always SPECIAL
    * Pre-revenue hedge    --> always SPECIAL
    * Mezz drawdown        --> always SPECIAL
    * EUR leg repayment    --> always SPECIAL
    * EBITDA at C3 (M12)   --> SPECIAL (GEPF grant recognised as EBITDA)
    * EBITDA all other      --> NORMAL
    * IIC / TA grant       --> NORMAL
    * DSRA release         --> NORMAL


 ASSET LIFECYCLE
 ================

  PHYSICAL ASSETS (Fixed Assets)

  +-------+----------+---------+----------+---------+----------+-----
  | Capex | Capex    | Capex   | COD      |         |          |
  | draw  | draw     | draw    | Depr Y1  | Depr Y2 | Depr Y3  | ...
  | C1    | C2       | C3      | 40%      | 20%     | 20%      | 20%
  +-------+----------+---------+----------+---------+----------+-----
  |<--- accumulate capex  --->|<--- S12C depreciation begins ---->|
        (construction)               (operations, from COD)

  S12C = Section 12C of SA Income Tax Act (accelerated depreciation).
  Depreciable base = total capex (excluding land, pre-development).
  Year 1 from COD: 40%. Years 2-4: 20% each. Fully depreciated by Y4.
  Semi-annual depreciation = annual rate / 2.

  FINANCIAL ASSETS (Reserves -- waterfall fills & depletes)

  These sit on the Balance Sheet as assets. They are CASH POOLS
  controlled by the waterfall. Each has an opening, fill, interest,
  release, and closing -- just like a facility but on the asset side.

  Ops Reserve:     Working capital buffer.
                   Target = f(opex, config).
                   Fills from waterfall step 8.
                   Releases if balance > target (e.g. opex drops).
                   Earns FD interest --> P&L.

  OpCo DSRA:       Debt Service Reserve Account.
                   Target = 1x next Sr P+I.
                   Fills from waterfall step 9.
                   As Sr debt amortises, target DROPS --> excess released.
                   When Sr fully repaid: target = 0, entire balance released.
                   Released cash re-enters waterfall for acceleration.
                   Earns FD interest --> P&L.

  Entity FD:       Fixed Deposit / surplus accumulator.
                   No target -- absorbs whatever is left after step 14.
                   Earns FD interest --> P&L.
                   Available for dividends or future distributions.

  Mezz Div FD:     Mezz Dividend Reserve.
                   Accrues dividend obligation while mezz outstanding.
                   Fills from waterfall step 11.
                   Pays out when: mezz repaid AND conditions met.
                   Earns FD interest --> P&L.

  Swap EUR Leg:    Financial asset (not a reserve -- separate lifecycle).
                   EUR placed into swap at inception.
                   Compounds at IIC rate during construction (IDC).
                   NWL: bullet delivery at M24 (entire balance to IIC).
                   LanRED: amortises with Sr IC (14 semi-annual from M24).
                   After delivery: asset = 0.

  Overdraft:       Inter-entity lending facility.
                   Lent when one entity has surplus, another deficit.
                   Repaid from waterfall step 10.
                   Accrues interest (inter-company rate).


 PLUGGABLE UPSTREAM MODULES
 ============================

  The loop doesn't care WHERE revenue or cost comes from.
  Any project can plug in by implementing:

  +------------------+     Revenue = f(volume, price, escalation, ...)
  | Revenue Module   |     Could be: water tariff, power PPA, toll road,
  |                  |     rental income, commodity sales, ...
  +------------------+
         |
         v
  +------------------+     EBITDA = Revenue - Opex
  | Cost Module      |     Could be: O&M contract, staffing, chemicals,
  |                  |     energy, maintenance CapEx, ...
  +------------------+
         |
         v
  +------------------+     The loop takes EBITDA as input
  | THE LOOP         |     Everything downstream is generic project finance
  +------------------+

  Example: NWL desalination
    Volume  = capacity_m3h x utilisation x hours_per_period
    Revenue = volume x tariff_eur_m3 x (1 + escalation)^year
    Opex    = O&M_monthly x 6 x (1 + indexation)^year + insurance + ...

  Example: future solar project
    Volume  = capacity_kw x irradiance x degradation^year
    Revenue = volume x ppa_price_kwh x (1 + escalation)^year
    Opex    = O&M_per_kw x capacity + insurance + grid_fees

  Example: toll road
    Volume  = traffic_base x (1 + growth)^year x seasonal_factor
    Revenue = volume x toll_rate x (1 + escalation)^year
    Opex    = maintenance_km x length + admin + insurance
```

## Key Principles

1. **The loop is the universal chassis.** Swap upstream modules to model
   any project. The financial engine (facility, waterfall, P&L, CF, BS)
   stays identical.

2. **Facility = calculator.** Computes Interest and P_constant on the
   PREVIOUS period's closing balance. The schedule is vanilla -- no DSRA,
   no hedge, no acceleration baked in on first pass.

3. **There is only acceleration, no prepayment.** Every mechanism for paying
   down a facility faster than scheduled P_constant flows through the
   waterfall and emerges as "acceleration". Grants, specials, surplus cash —
   all become acceleration. The facility doesn't know the source.

4. **Waterfall = allocator.** Takes cash available, puts it in buckets.
   Does NOT calculate interest or principal -- reads from facility vectors.
   Fills reserves (financial assets), accelerates facilities (liabilities).

5. **No convergence needed.** The One Big Loop processes period-by-period:
   Opening is fixed, Interest/Principal are deterministic, Waterfall decides
   Acceleration, Closing = Opening - Principal - Acceleration. Single pass.
   See DAG.md for the full proof.

6. **Two pools: NORMAL and SPECIAL.** EBITDA is normally NORMAL cash and
   follows the full cascade. But at C3 (month 12), EBITDA is SPECIAL
   (GEPF grant recognised). Grants and hedge proceeds are always SPECIAL.
   Specials skip debt service and jump to Sr Acceleration.

7. **Cash inflows have specific timing.** DTIC + IIC land at C2 (month 6).
   Pre-revenue hedge at C4 (month 18). DSRA releases start at C4 and
   continue as Sr debt amortises. This is NOT uniform across periods.

8. **Balance Sheet = snapshot.** Reads closing positions from facilities
   (liabilities), reserves (financial assets), and depreciation schedule
   (fixed assets). Two audit checks: Assets = Debt + Equity, and
   Retained Earnings = Cumulative PAT + Grants (BS Gap = 0).

9. **Reserves are two-way.** Waterfall fills them (step 8-11, 15).
   When no longer needed (e.g. DSRA after Sr repaid), they release back
   into cash available. The DSRA target DROPS as Sr amortises, so
   releases happen gradually, not just at final repayment.

10. **Ratios never feed back.** DSCR, LLCR, gearing are read-only outputs.

11. **app.py = display only.** All computation lives in `engine/` and
    `entities/`. The app reads from `EntityResult` and renders.
