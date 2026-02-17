# Cross-Currency Swap Mechanics — NWL & LanRED

## 1. Context

SCLCA receives EUR-denominated debt (Senior from IIC at 4.70%, Mezzanine from CC at 14.75%) and deploys as IC loans to subsidiaries at +0.50% margin (Senior IC 5.20%, Mezz IC 15.25%). All subsidiary revenue is in ZAR. The FX mismatch between EUR debt obligations and ZAR revenue creates hedging risk.

Two hedging mechanisms exist:

| | **Option A: CC DSRA → FEC** | **Option B: Cross-Currency Swap** |
|---|---|---|
| Provider | Creation Capital (via DSRA) | Investec (direct swap) |
| Mechanism | CC 2nd Mezz draw by holding, pushed down to NWL as Mezz IC drawdown. NWL buys FEC (ZAR→EUR forward), provides EUR back to Holding via Senior IC prepayment, Holding prepays IIC. Effect: net zero to holding, NWL Senior IC ↓ but Mezz IC ↑ (higher rate: 15.25% replaces 5.20%) | IC draw → EUR into swap EUR leg → triggers ZAR drawdown |
| Cost basis | 14.75% (CC rate) + 5.25% (dividend accrual) = 20% effective, replacing Senior IC at 5.20% | 9.69% Investec fixed (Oct 2025 quote), replacing Senior IC at 5.20% |
| BS impact | None (FEC is pass-through, nets to zero) | EUR asset + ZAR liability on entity BS |
| Who bears FX risk | CC/IIC (FEC locks rate) | Entity (swap rate differential) |

---

## 2. Rate Architecture

```
                    Facility        IC Loan         Margin
                    ────────        ───────         ──────
Senior (IIC)        4.70%           5.20%           0.50%
Mezzanine (CC)      14.75%          15.25%          0.50%
Swap ZAR leg        —               9.69%           —
Swap EUR leg        4.70% (= IIC)   —               —
                                    ─────
                                    0.50% NEGATIVE CARRY
                                    (entity pays 5.20% IC,
                                     earns 4.70% on EUR leg)
```

The 0.50% negative carry is structural: the entity borrows from SCLCA at the IC rate (5.20%) and deposits EUR into the swap earning the IIC facility rate (4.70%). This margin leakage is the cost of intermediation.

---

## 3. NWL Swap — Detailed Mechanics

### 3.1 Toggle

```
┌─────────────────────────────────────────────────────┐
│  NWL Hedging Mechanism                              │
│  ○ CC DSRA → FEC  (default)                         │
│  ○ Cross-Currency Swap                              │
└─────────────────────────────────────────────────────┘
```

### 3.2 Sizing

The swap/FEC notional is sized at **FACILITY level** (IIC Senior, 4.70%), NOT at NWL IC level (5.20%). This is because the hedge covers the holding's obligation to IIC, not NWL's obligation to the holding.

```
IIC FACILITY (Senior Debt) balance at M24:

  Facility drawdown:              €13,597,304
  + IDC (rolled up, 4.70%):      +€1,077,634
  − Grant prepayments (M12):     −€3,236,004
  ─────────────────────────────────────────────
  ≈ Balance at M24:               ~€11,438,934

  P = Balance / 14 repayments =  ~€817,067
  I = Balance × 4.70% / 2 =      ~€268,815

  Swap notional = 2 × (P + I) =  ~€2,171,763  ← exact computed at runtime
                                                  from facility-level schedule
```

This is significantly larger than an NWL-only calculation because the facility carries the FULL project debt (all three entities), and the rate is the lower facility rate (4.70%) producing a larger balance relative to a higher-rate IC calculation.

### 3.3 The Cycle — Step by Step

```
ARRANGEMENT (at or before M0):
══════════════════════════════════════════════════════════════════

 ┌──────────┐     IC Draw (EUR)      ┌─────────┐
 │  SCLCA   │ ──────────────────────→│   NWL   │
 │ Holding  │     (5.20% IC rate)    │         │
 └──────────┘                        └────┬────┘
                                          │
                                          │ Places EUR into swap
                                          ▼
                               ┌─────────────────────┐
                               │   Investec Swap      │
                               │   Counterparty       │
                               └──────────┬──────────┘
                                          │
                                          │ Triggers ZAR drawdown
                                          ▼
                               ┌─────────────────────┐
                               │   NWL receives ZAR   │
                               │   (EUR × FX20)       │
                               └─────────────────────┘

 NWL Balance Sheet immediately:
 ┌─────────────────────┐         ┌─────────────────────┐
 │ ASSETS              │         │ LIABILITIES         │
 │                     │         │                     │
 │ Swap: EUR Leg       │         │ Senior IC Loan      │
 │ (receivable)        │         │ Mezz IC Loan        │
 │ = 2×(P+I)           │         │ Swap: ZAR Leg       │
 │                     │         │ = EUR × FX20        │
 └─────────────────────┘         └─────────────────────┘
```

### 3.4 IDC Compounding (M0 → M24)

During the 24-month grace period, both legs accrue interest. No cash moves — interest capitalizes just like IDC on the IC loans.

```
EUR LEG (Asset)                      ZAR LEG (Liability)
══════════════════                   ══════════════════
Earns:  4.70% p.a. (IIC rate)       Accrues: 9.69% p.a. (Investec)
Compounds: semi-annual               Compounds: semi-annual
Direction: Balance GROWS ↑           Direction: Balance GROWS ↑
           ("Negative IDC")                     ("IDC on swap")

Timeline:
─────────────────────────────────────────────────────────────────
M0:   EUR = Notional                 ZAR = Notional × FX20
M6:   EUR + (EUR × 2.35%)           ZAR + (ZAR × 4.845%)
M12:  EUR + compounded               ZAR + compounded
M18:  EUR + compounded               ZAR + compounded
M24:  EUR = Notional × 1.047^2      ZAR = Notional × FX20 × 1.0969^2
      ≈ +9.6% growth                 ≈ +20.3% growth
─────────────────────────────────────────────────────────────────

NET COST OF CARRY = ZAR growth rate − EUR growth rate (FX-adjusted)
The ZAR leg grows FASTER than the EUR leg.
This differential is the price of the hedge.
```

### 3.5 M24: EUR Bullet Delivery

```
M24 EVENT:
══════════════════════════════════════════════════════════════════

  ┌─────────┐    EUR bullet     ┌──────────┐    EUR pass     ┌─────────┐
  │Investec │ ─────────────────→│   NWL    │ ──────────────→│  SCLCA  │
  │  Swap   │  (full notional   │          │  (IC Senior    │ Holding │
  └─────────┘   + accrued IDC)  └──────────┘   P1 + P2)     └────┬────┘
                                                                  │
                                                                  │ pays IIC
                                                                  ▼
                                                            ┌─────────┐
                                                            │   IIC   │
                                                            │(Senior) │
                                                            └─────────┘

  After M24:
  ┌─────────────────────┐         ┌─────────────────────┐
  │ ASSETS              │         │ LIABILITIES         │
  │                     │         │                     │
  │ Swap: EUR Leg = €0  │         │ Senior IC Loan      │
  │ (fully delivered)   │         │ Mezz IC Loan        │
  │                     │         │ Swap: ZAR Leg       │
  │                     │         │ (inflated by IDC,   │
  │                     │         │  starts repaying    │
  │                     │         │  at M36)            │
  └─────────────────────┘         └─────────────────────┘

  EUR leg → 0 (bullet, done)
  ZAR leg → still outstanding (now amortizes)
```

### 3.6 M36 → M102: ZAR Leg Amortization

```
ZAR LEG REPAYMENT SCHEDULE:
══════════════════════════════════════════════════════════════════

  Start:       M36 (12 months after EUR delivery)
  Frequency:   Semi-annual (every 6 months)
  Periods:     12 (M36, M42, M48, ..., M102)
  Rate:        9.69% p.a. fixed
  Profile:     P_constant (constant principal + declining interest)
  Opening:     Notional × FX20 × (1.0969)^2  ← inflated by 24mo IDC

  P (constant) = Opening / 12

  ┌────────┬──────────┬───────────┬───────────┬──────────┬───────────┐
  │ Period │  Month   │  Opening  │  Interest │ Princip. │  Closing  │
  ├────────┼──────────┼───────────┼───────────┼──────────┼───────────┤
  │   1    │   36     │ ZAR_IDC   │ HIGH      │    P     │    ↓      │
  │   2    │   42     │    ↓      │ declining │    P     │    ↓      │
  │  ...   │  ...     │    ↓      │ declining │    P     │    ↓      │
  │  12    │  102     │    P      │ small     │    P     │    0      │
  └────────┴──────────┴───────────┴───────────┴──────────┴───────────┘

  Each period: Payment = P (constant) + Interest (on declining balance)
  Interest = Opening × 9.69% / 2
  Total payment DECLINES over time (interest shrinks, principal constant)
  Deducted from NWL cash flow AFTER IC debt service
```

---

## 4. LanRED Swap — Detailed Mechanics

### 4.1 Toggle

```
┌─────────────────────────────────────────────────────┐
│  LanRED Energy Scenario                             │
│  ○ Greenfield   (default — no swap, no FX hedge)    │
│  ○ Brownfield+  (swap active — EUR acquisition)     │
└─────────────────────────────────────────────────────┘
```

LanRED Greenfield is a ZAR-only project (build at Lanseria, ZAR costs, ZAR revenue). No FX exposure, no hedge needed.

LanRED Brownfield+ acquires an existing portfolio (Northlands Energy) priced in EUR. The IC loan is in EUR but revenue is in ZAR → needs a swap.

### 4.2 Sizing

```
LanRED Senior IC:  €2,739,516  ← 100% allocated to EUR leg
                                  (entire Senior IC, not 2×P+I)
```

### 4.3 The Cycle

Identical mechanism to NWL, but different sizing and amortization:

```
ARRANGEMENT:
══════════════════════════════════════════════════════════════════

  SCLCA ──IC Draw (EUR)──→ LanRED ──Places EUR──→ Investec Swap
                                    ←Receives ZAR←

  EUR Leg = €2,739,516 (= LanRED Senior IC, full amount)
  ZAR Leg = €2,739,516 × 20 = R54,790,320
```

### 4.4 IDC Compounding (M0 → M24)

Same as NWL: EUR leg earns 4.70%, ZAR leg accrues 9.69%. Both capitalize. Same 0.50% negative carry on the IC margin.

### 4.5 Key Difference: EUR Leg Follows IC Senior

Unlike NWL (bullet), LanRED EUR leg **mirrors the IC Senior repayment schedule**:

```
NWL:     EUR ════════════════════●  (bullet at M24, one shot)
LanRED:  EUR ──●──●──●──●──●──●──●──●──●──●──●──●──●──●  (14 semi-annual)
              M24 M30 M36 M42 ......................... M102

  EUR delivered to IIC each period = same as IC Senior P+I
  EUR leg balance declines in lockstep with Senior IC balance
```

### 4.6 Key Difference: ZAR Leg Doubles Tenor

```
IC Senior:  14 semi-annual  (M24 → M102)  =  78 months  =  6.5 years
ZAR Leg:    28 semi-annual  (M24 → M186)  = 162 months  = 13.5 years

  The ZAR leg repays at HALF the speed of the EUR leg.
  This is deliberate: LanRED's ZAR revenue grows over time
  (PPA escalation), so stretching the ZAR leg matches
  the revenue curve better.

  ┌─────────────────────────────────────────────────────────────┐
  │ EUR leg:  ████████████████████████████████░░░░░░░░░░░░░░░░ │
  │           M24─────────────────────────M102                  │
  │                                                             │
  │ ZAR leg:  ████████████████████████████████████████████████ │
  │           M24───────────────────────────────────────M186    │
  └─────────────────────────────────────────────────────────────┘

  After M102: EUR leg = 0, ZAR leg still outstanding
  LanRED continues paying ZAR annuity from PPA revenue
  until M186 (no EUR exposure remaining)
```

---

## 5. Comparison: FEC vs Swap

### 5.1 NWL — What Changes

```
                        CC DSRA → FEC               Cross-Currency Swap
                        ═════════════               ═══════════════════
CC 2nd Mezz draw        YES (€2.17M at M24)         NO (CC does not inject)
Mezz IC DSRA drawdown   YES (inflates Mezz bal)      NO (Mezz stays original)
Mezz IC repayments      HIGHER (on inflated bal)     LOWER (on original bal)
FEC on BS               NO (pass-through, nets 0)    N/A
EUR Leg on BS           NO                           YES (asset, earns 4.70%)
ZAR Leg on BS           NO                           YES (liability, 9.69%)
IDC on swap legs        N/A                          YES (both compound M0→M24)
Swap ZAR annuity in CF  NO                           YES (new CF line, M36+)
Effective cost          ~20% (CC rate + dividend)     9.69% (Investec fixed)
Tenor of hedge cost     One-shot                     12 semi-annual (6 years)
```

### 5.2 LanRED — What Changes

```
                        Greenfield                  Brownfield+ (Swap)
                        ══════════                  ══════════════════
FX exposure             NONE (ZAR-only project)     YES (EUR acquisition)
Swap active             NO                          YES
EUR Leg                 —                           100% of Senior IC
ZAR Leg                 —                           28 semi-annual
EUR leg amortization    —                           Follows IC Senior (14)
ZAR leg amortization    —                           Double tenor (28)
IDC on swap legs        —                           YES (M0→M24 compound)
Operating model         Greenfield (build)          Brownfield (acquire)
Day-1 revenue           NO (construction)           YES (existing PPAs)
ECA/Atradius            YES                         NO (self-funded)
Overdraft facility      YES (early shortfalls)      NO (Day-1 revenue)
```

---

## 6. Balance Sheet Impact — Full Lifecycle

### 6.1 NWL (Swap Selected)

```
YEAR:        Y1        Y2        Y3        Y4        Y5  ...  Y9
             M0-M12    M13-M24   M25-M36   M37-M48   M49-M60

ASSETS:
Fixed        ████████  ████████  ███████   ██████    █████     ██
DSRA FD      ░░░░░░░░  ░░░░░░░░  ░░░░░░░  ░░░░░░   ░░░░░     ░░
EUR Leg      ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓▓  0         0         0        0
             (growing   (bullet                (EUR fully delivered
              w/ IDC)    at M24)                 at M24)

LIABILITIES:
Senior IC    ████████  ████████  ███████   ██████    █████     █
Mezz IC      ████████  ████████  ███████   ██████    █████     0
             (NO DSRA   (NO DSRA
              inflate)   inflate)
ZAR Leg      ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓   ▓▓▓▓▓    ▓▓▓      0
             (growing   (growing   (amortizing from M36,
              w/ IDC)    w/ IDC)    12 semi-annual)
```

### 6.2 LanRED (Brownfield+ with Swap)

```
YEAR:        Y1        Y2        Y3        Y4  ...  Y9   ...  Y14
             M0-M12    M13-M24   M25-M36   M37       M97       M186

ASSETS:
Fixed        ████████  ████████  ███████   ██████    ██        ██
EUR Leg      ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓   ▓▓▓▓▓    ▓         0
             (growing   (growing   (amortizing with IC Senior,
              w/ IDC)    w/ IDC)    14 semi-annual M24→M102)

LIABILITIES:
Senior IC    ████████  ████████  ███████   ██████    █         0
Mezz IC      ████████  ████████  ███████   ██████    ██        0
ZAR Leg      ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓▓  ▓▓▓▓▓▓▓  ▓▓▓▓▓▓   ▓▓▓▓      ▓
             (growing   (growing   (amortizing 28 semi-annual M24→M186,
              w/ IDC)    w/ IDC)    OUTLIVES IC Senior by 7 years)
```

---

## 7. Cash Flow Impact

### 7.1 NWL Cash Flow — FEC vs Swap

```
FEC (default):
Revenue → EBITDA → Senior IC (P+I) → Mezz IC (P+I, HIGHER) → Free CF
                                      ↑ inflated by DSRA draw

Swap:
Revenue → EBITDA → Senior IC (P+I) → Mezz IC (P+I, LOWER) → Swap ZAR → Free CF
                                      ↑ original balance      ↑ NEW LINE
                                                               9.69% annuity
                                                               M36→M102
```

### 7.2 LanRED Cash Flow — Greenfield vs Brownfield+

```
Greenfield:
Revenue → EBITDA → Senior IC (P+I) → Mezz IC (P+I) → Free CF

Brownfield+:
Revenue → EBITDA → Senior IC (P+I) → Mezz IC (P+I) → Swap ZAR → Free CF
                                                       ↑ NEW LINE
                                                       9.69% annuity
                                                       M24→M186
                                                       (28 semi-annual)
```

---

## 8. P&L Impact

When swap is active, two new interest lines appear:

```
P&L:
  Revenue
  − COGS / O&M
  ─────────────
  EBITDA
  − Depreciation
  ─────────────
  EBIT
  − Senior IC Interest
  − Mezz IC Interest
  + Swap EUR Interest Income     ← NEW (4.70% on EUR leg balance)
  − Swap ZAR Interest Expense    ← NEW (9.69% on ZAR leg balance)
  ─────────────
  EBT
  − Tax
  ─────────────
  PAT

Net swap interest = EUR income (4.70%) − ZAR expense (9.69%) = NEGATIVE
                    (this is the cost of the hedge)
```

During grace period (M0→M24): Both capitalize (IDC), no P&L impact.
Post-M24: Cash interest flows through P&L.

---

## 9. SCLCA Holding — What DOES and DOES NOT Change

```
HOLDING LEVEL:
══════════════════════════════════════════════════════════════════

DOES NOT CHANGE:
  − IC loan schedules (always vanilla — 14 Sr / 10 Mz)
  − IC interest rates (5.20% Sr, 15.25% Mz)
  − Holding BS (sees IC loans + equity stakes only)
  − Waterfall cascade structure (Sr P+I → Mz P+I → DSRA → etc.)
  − Facility repayment schedules (Senior, Mezz)

CHANGES (NWL swap):
  − CC 2nd Mezz draw: SUPPRESSED (no injection at M24)
  − DSRA pass-through: SUPPRESSED (no DSRA→FEC flow)
  − Facility Mezz balance: LOWER (no DSRA inflation)
  − Holding CF: No DSRA drawdown line at M24

CHANGES (LanRED Brownfield+):
  − Operating model switches to Brownfield
  − ECA Atradius cover: DISABLED
  − No separate holding-level swap tracking
    (swap lives entirely at LanRED entity BS)
```

---

## 10. Summary: The Swap "Cycle"

```
┌───────────────────────────────────────────────────────────────────┐
│                    THE SWAP CYCLE                                 │
│                                                                   │
│  1. SCLCA draws IC loan → passes EUR to entity                   │
│  2. Entity places EUR into swap → EUR Leg (asset, earns 4.70%)   │
│  3. Swap triggers ZAR drawdown → ZAR Leg (liability, 9.69%)     │
│  4. Both legs compound during grace (IDC / "negative IDC")       │
│  5. EUR delivered to IIC (NWL: bullet M24, LanRED: follows IC)  │
│  6. ZAR repaid to Investec (NWL: 12×M36+, LanRED: 28×M24+)     │
│  7. 0.50% negative carry = cost of IC intermediation             │
│  8. Net hedge cost = 9.69% − 4.70% = 4.99% spread (pre-FX)     │
│                                                                   │
│  KEY INSIGHT: Swap replaces CC's 20% effective cost with         │
│  Investec's 9.69% — saving ~10% p.a. on the hedge amount.       │
│  Trade-off: BS complexity (EUR asset + ZAR liability visible).   │
└───────────────────────────────────────────────────────────────────┘
```
