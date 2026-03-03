# Memo: Global Financial Engine Architecture

**Date:** 2026-02-27
**Author:** Rutger de Bruijn / Claude (Opus 4.6)
**Status:** Draft for discussion
**Scope:** Redesign of the SCLCA financial model into a reusable, auditable, unit-safe engine

---

## 1. Problem Statement

The current financial model is a monolithic Streamlit application (~20,000 lines) with calculations embedded in viewport code. While recent refactoring (Phases A-E) extracted core calculations into engine modules and established a canonical period index (0-19), the architecture remains project-specific and lacks:

- **Unit safety**: Numbers are bare floats. `25` could be ZAR, EUR, m3, or kWh.
- **Dimensional auditability**: No way to trace `Revenue = volume x tariff` back through units.
- **Intercompany integrity**: IC transactions are computed separately by each entity, then reconciled. Should be single-source.
- **Reusability**: The engine is tightly coupled to the CA/Lanseria project. Cannot plug in a different asset.
- **Pre-computed lookup**: Viewports still trigger calculations. Should be instant DataFrame lookups.

## 2. Proposed Architecture

### 2.1 Two-Tier Design

**Tier 1 — Global Financial Engine (project-agnostic library)**

Defines universal financial model rules, enforces constraints, provides the calculation framework. Any infrastructure project can use this engine.

Responsibilities:
- Canonical time spine management (periods, phases, milestones)
- Unit type system with dimensional analysis
- Standard P&L structure: Revenue - COGS = Gross Profit - OpEx = EBITDA - IE - Depr = PBT - Tax = PAT
- Standard CF derivation: EBITDA +/- adjustments - tax - debt service
- Standard BS: Assets = Liabilities + Equity (enforced, not checked)
- Facility schedule builder (construction IDC, repayment profiles)
- Waterfall allocator (priority cascade with convergence)
- Double-entry intercompany ledger
- DataFrame output with unit metadata per column

**Tier 2 — Project Configuration (CA/Lanseria is instance #1)**

Fills in the global template with project-specific assumptions.

Responsibilities:
- Entity definitions (NWL, LanRED, TimberWorx)
- Revenue drivers (m3/day x ZAR/m3 for water, kWh x ZAR/kWh for solar)
- Cost drivers, escalation rates, capacity ramps
- Capital structure (senior/mezz split, rates, tenors)
- Intercompany loan terms
- Scenario inputs and sensitivity parameters

### 2.2 Unit Type System

Every numeric value in the model carries a unit. The engine enforces dimensional correctness at computation time.

**Base units:**
- Currency: EUR, ZAR
- Volume: m3 (cubic metres)
- Energy: kWh
- Time: period (semi-annual), year
- Dimensionless: ratio, percentage

**Compound units (derived):**
- ZAR/m3 (tariff)
- ZAR/kWh (PPA rate)
- EUR/period (revenue per period)
- m3/day (flow rate)

**Rules:**
- Multiplication: `m3 x ZAR/m3 = ZAR` (units cancel)
- Division: `ZAR / (ZAR/EUR) = EUR` (currency conversion)
- Addition: `ZAR + ZAR = ZAR` (same unit required)
- Addition: `ZAR + EUR = ERROR` (unit mismatch — must convert first)
- The unit of every DataFrame column is declared in schema metadata

**Example audit trail:**
```
NWL Revenue (period 4):
  = daily_volume[4] x tariff[4] x days_in_period[4]
  = 1,900 m3/day x 142.50 ZAR/m3 x 182 days
  = 49,257,000 ZAR
  = 49,257,000 ZAR / 21.57 ZAR/EUR
  = 2,283,727 EUR

  Units: (m3/day) x (ZAR/m3) x (days) = ZAR -> / (ZAR/EUR) = EUR  [check]
```

### 2.3 Pre-Computed DataFrame Hierarchy

The engine runs once (with convergence iterations), then freezes all results as pandas DataFrames indexed by canonical period. Viewports only read — never compute.

**Computation order (dependency graph):**

```
Layer 1: Time Spine
  periods_df: index(0-19), label, start_month, end_month, phase, year

Layer 2: Operating Model (per entity)
  ops_df: index(0-19), revenue, cogs, gross_profit, om_cost, power_cost, rent_cost, ebitda
  ops_annual_df: index(0-9), same fields aggregated

Layer 3: Facility Schedules (per entity, per facility type)
  facility_sr_df: index(0-17), opening, drawdown, interest, principal, acceleration, closing
  facility_mz_df: index(0-17), same structure

Layer 4: P&L (per entity)
  pnl_df: index(0-19), ebitda, ie_sr, ie_mz, depreciation, pbt, tax, pat

Layer 5: Waterfall (per entity)  [iterates with Layer 3 until converged]
  waterfall_df: index(0-19), ebitda, tax, sr_pi, mz_pi, cash_available, surplus,
                reserves, acceleration, dividends, balances...

Layer 6: Cash Flow (per entity)
  cf_df: index(0-9), ebitda, tax, capex, debt_service, dsra, net_cf

Layer 7: Balance Sheet (per entity)
  bs_df: index(0-9), fixed_assets, dsra, sr_closing, mz_closing, equity, retained, gap

Layer 8: Holding Company (SCLCA aggregate)
  holding_df: index(0-9), ic_interest_income, external_ie, net_interest, consolidated_bs
```

**Key property:** After computation, `waterfall_df.loc[4, 'ebitda']` is an instant lookup. No calculation triggered. The viewport does `st.dataframe(waterfall_df)` — done.

### 2.4 Double-Entry Intercompany Ledger

Intercompany transactions are defined once in a shared structure. Both counterparties read from the same source.

**IC Loan structure (example: SCLCA -> NWL Senior):**

```json
{
  "ic_loan_id": "sclca_nwl_senior",
  "lender": "sclca",
  "borrower": "nwl",
  "facility_type": "senior",
  "rate": 0.052,
  "schedule_df": "<reference to facility_sr_df for nwl>"
}
```

**Booking rules:**
| Period | SCLCA (lender) | NWL (borrower) |
|--------|----------------|----------------|
| Interest | +Interest Income (P&L) | -Interest Expense (P&L) |
| Principal | -IC Receivable (BS) | -IC Payable (BS) |
| Drawdown | +IC Receivable (BS) | +IC Payable (BS) |

Both sides reference `facility_sr_df` — same DataFrame, opposite signs. No reconciliation needed because there's only one truth.

**Integrity constraint:** `sum(lender_receivable) == sum(borrower_payable)` at every period, by construction.

### 2.5 Configuration Schema

**Global config (engine-level):**
```
global/
  units.json          — unit definitions and conversion rules
  pnl_template.json   — standard P&L line items and computation order
  cf_template.json    — standard CF derivation rules
  bs_template.json    — standard BS structure (A = L + E)
```

**Project config (instance-level):**
```
config/
  periods.json        — time spine (already exists)
  project.json        — FX, tax rate, global params
  structure.json      — capital stack, entity allocations
  financing.json      — facility terms, drawdowns, prepayments
  operations.json     — entity operating assumptions
  assets.json         — asset register, depreciation
  intercompany.json   — IC loan definitions (NEW)
```

## 3. Migration Path

### Phase 1: Unit Type System
- Extend `engine/currency.py` to a full `engine/units.py`
- Define base and compound units
- Enforce dimensional correctness in all engine calculations

### Phase 2: DataFrame Output Layer
- Convert entity module outputs from `list[dict]` to typed pandas DataFrames
- Add unit metadata to DataFrame columns
- Index all DataFrames by canonical period (0-19) or annual (0-9)

### Phase 3: Intercompany Ledger
- Create `config/intercompany.json` defining all IC relationships
- Refactor facility schedule generation to be shared (not per-entity)
- Enforce double-entry at the data layer

### Phase 4: Global Engine Extraction
- Separate engine into project-agnostic library vs project-specific config
- Define `pnl_template.json`, `cf_template.json`, `bs_template.json`
- Make entity modules fill in templates rather than hardcode P&L structure

### Phase 5: Viewport Rewrite
- Replace `_run_engine_model` monolith with single `run_model()` call
- Viewports become pure DataFrame formatters
- Every table = `st.dataframe(some_df.style.format(...))`

## 4. Benefits

1. **Auditability**: Every number traces back through units to source assumptions
2. **Integrity**: Double-entry IC eliminates reconciliation errors by construction
3. **Performance**: Pre-computed DataFrames = instant viewport rendering
4. **Reusability**: New project = new config folder, same engine
5. **Testability**: Each DataFrame can be snapshot-tested independently
6. **Queryability**: "What's NWL EBITDA in Y3?" = `ops_df.loc[4, 'ebitda']` — answered instantly

---

*This memo captures the architectural vision. Next step: research best practices for financial model engines, unit type systems, and DataFrame-based calculation frameworks, then produce an execution plan.*
