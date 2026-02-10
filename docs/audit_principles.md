# Audit Principles — SCLCA Financial Model

## Purpose

Every page in the financial model includes a **per-page audit panel** that validates
internal consistency. The goal is to catch regressions automatically — if a future
code change breaks a financial identity, the audit panel surfaces it immediately.

## Architecture

### `run_page_audit(checks, page_name)`

A single reusable function renders an audit panel at the bottom of any tab.

- **Forced visibility**: If any check fails, `st.error()` is rendered *outside* the
  toggle so the user cannot miss it.
- **Toggle details**: All checks (pass and fail) are shown inside an `st.expander`
  labelled `"Audit — {page_name} (N checks, M failures)"`. The expander auto-opens
  when failures exist.
- **Tolerance**: Each check has a tolerance (default €1) to absorb floating-point drift.

### Check format

```python
{
    "name": "P&L: Rev - Costs = EBITDA",   # Human-readable identity
    "expected": 123456.78,                   # Left-hand side of the identity
    "actual":   123456.78,                   # Right-hand side
    "tolerance": 1.0,                        # Max acceptable abs(expected - actual)
}
```

## Per-Page Checks

### Sources & Uses
- Senior + Mezz = Total Loan (per entity)
- Fees allocated = sum of fee line items
- Sum of entity loans = facility total

### Facilities
- IC balance Y1 = drawdowns + IDC - prepayment
- IC balance Y10 = 0 (fully amortized)
- Sum(interest) = total interest expense from P&L
- Sum(principal) = opening balance

### Assets
- Depreciable base = total loan amount
- Y10 accumulated depreciation <= depreciable base
- Fee allocation matches config
- BS fixed assets Y1 = depreciable base - Y1 depreciation

### Operations
- Revenue components sum to rev_total
- EBITDA = rev_total - O&M - power - rent
- Operations rev_total = P&L rev_total per year (cross-tab)
- IC power: NWL power_cost = LanRED revenue (cross-entity)

### P&L
- Rev - OpEx = EBITDA
- EBITDA - Depr - IE = EBT (PBT)
- EBT x 27% = Tax (when EBT > 0)
- EBT - Tax = PAT

### Cash Flow
- DSRA: Opening + Deposit + Interest = Closing
- Comprehensive CF Net = sum of all components
- Sum(CF Net) = DSRA Y10 balance
- CF Ops = EBITDA + DSRA Interest - Tax

### Balance Sheet
- Assets = Debt + Equity
- Retained Earnings = Cumulative PAT + Grants
- BS debt = IC loan balances from schedule
- BS DSRA = CF DSRA closing balance
- BS fixed assets = depreciable base - accumulated depreciation

## Inter-Company Reconciliation (SCLCA)

Checks that SCLCA's income/receivables equal the sum of subsidiary expenses/liabilities:

- IC interest income (senior) = sum of subsidiary IE (senior)
- IC interest income (mezz) = sum of subsidiary IE (mezz)
- IC receivable (senior) = sum of subsidiary BS debt (senior)
- IC receivable (mezz) = sum of subsidiary BS debt (mezz)
- IC principal received = sum of subsidiary principal paid
- NWL power cost = LanRED power revenue
- NWL rent cost = TWX lease revenue

## Design Decisions

1. **Tolerance of €1**: Floating-point arithmetic produces sub-cent rounding.
   A €1 tolerance catches real bugs while ignoring noise.

2. **Forced errors outside toggle**: Users who never open the audit toggle still
   see a red banner when something breaks.

3. **Hidden operations table**: The Operations tab shows a narrative view. A
   toggled debug table exposes ALL computed keys from the operating model,
   ensuring that values computed but not displayed are still inspectable.

4. **Model return dict**: `build_sub_annual_model()` returns a dict with
   `annual`, `registry`, `sr_schedule`, `mz_schedule`, `depreciable_base`,
   and `entity_equity` — giving audit panels access to intermediate data
   without re-computing.
