# SCLCA Financial Model — Full Audit Report
**Date:** 2026-02-09
**Scope:** Cross-file consistency check of all config files and app.py display values

---

## PART A: Bugs Fixed

### A1. `mezz_reps = 8` hardcoded (should be 10)
- **File:** `app.py` line ~2005
- **Was:** `mezz_reps = 8` (hardcoded)
- **Now:** `mezz_reps = mezz.get('repayments', 10)` (reads from config)
- **Impact:** S&U tab was showing 8 mezzanine repayments instead of 10
- **Config:** `structure.json` → `mezzanine.repayments` = 10

### A2. LanRED tagline "1.2 MWp" → "2.4 MWp"
- **File:** `app.py` line ~1858
- **Was:** "1.2 MWp solar PV with battery storage..."
- **Now:** "2.4 MWp solar PV with battery storage..."
- **Derivation:** Solar budget EUR 2,036,166 / EUR 850 per kWp = 2,395 kWp ~ 2.4 MWp

### A3. Phoenix coverage used rounded R27.3M instead of exact R26.38M
- **Files:** `app.py` lines ~12120-12184 (Guarantors tab) and ~11147-11157 (SCLCA Security tab)
- **Was:** "Attributable (40%) = R27.3M", coverage 1.34x, 2yr cash R54.6M
- **Now:** "Attributable = R26.4M", coverage 1.30x, 2yr cash R52.8M
- **Root cause:** Chartwell Corner ownership is 20% (not 40%). The detail table already had the correct per-property data (R26,379,252 total attributable), but the hero metrics used a simplified "40% x R68.2M = R27.3M" calculation.
- **Exact:** Attributable EBITDA = R26,379,252; 2yr = R52,758,504; Coverage = 1.30x

### A4. CoE content_split wrong (40/30/30 → 60/30/10)
- **File:** `config/assets.json` — coe_001
- **Was:** `{"Finland": 0.40, "France": 0.30, "South Africa": 0.30}`
- **Now:** `{"Finland": 0.60, "France": 0.30, "South Africa": 0.10}`
- **Impact:** ECA content compliance calculations (Dutch content %, OECD local content test)

### A5. `senior_debt.json` stale after Panel Equipment addition
- **File:** `config/senior_debt.json`
- **Changes:**
  - `loan_amount.amount`: 13,442,928 → 13,612,928
  - `drawdown_total`: 13,442,928 → 13,612,928
  - `balance_for_repayment.amount`: 11,284,558 → 11,454,558
  - `principal_per_period`: 806,040 → 818,183
  - Waterfall steps updated accordingly
- **Note:** IDC (1,077,634) kept unchanged — model engine calculates dynamically. The 4th drawdown (EUR 170k at period -1) adds ~EUR 4k IDC, immaterial for this reference file.

### A6. `project.json` stale `total_capex`
- **File:** `config/project.json`
- **Was:** `total_capex`: 14,237,572
- **Now:** `total_capex`: 14,437,573
- **Derivation:** water 8,169,648 + coe 1,862,124 + solar 2,908,809 + esg 1,496,992 = 14,437,573

### A7. `mezz.json` stale `project_cost_eur`
- **File:** `config/mezz.json`
- **Was:** `project_cost_eur`: 15,694,388
- **Now:** `project_cost_eur`: 15,894,388
- **Note:** `initial_amount` (46,440,864 ZAR) differs from structure.json (47,059,088 ZAR). The mezz.json schedule is a standalone reference document — the model engine uses structure.json values. See B3 below.

### A8. `delivery.json` stale entity totals
- **File:** `config/delivery.json`
- **Changes:**
  - NWL: 10,655,819 → 10,655,818 (off by 1 EUR rounding)
  - LanRED: 3,206,197 → 3,205,999 (off by 198 EUR)
  - TWX: 1,832,372 → 2,032,571 (EUR 200k Panel Equipment was missing)
- **Source of truth:** `structure.json` entity totals

### A9. `financing.json` stale `balance_to_repay`
- **File:** `config/financing.json`
- **Was:** `balance_to_repay`: 11,284,558; `principal_per_period`: 806,040
- **Now:** `balance_to_repay`: 11,454,558; `principal_per_period`: 818,183
- **Calc:** 13,612,928 - 1,159,313 - 2,076,691 + 1,077,634 = 11,454,558; / 14 = 818,183

### A10. Wrong fallback defaults in `app.py`
- **File:** `app.py`
- CoE rent escalation fallback: 7.0 → 5.0 (matches `operations.json`)
- TWX `price_per_unit_zar` fallback: 85,000 → 340,000 (R340k/house, not R85k)
- TWX `training_start_month` fallback: 30 → 18 (matches `operations.json`)

### A11. MEMORY.md — CoE rent escalation 7% → 5%
- **File:** `MEMORY.md` (auto-memory)
- **Was:** "7% annual escalation"
- **Now:** "5% annual escalation" (matches `operations.json`)

### A12. `project.json` FX note stale amounts
- **File:** `config/project.json`
- **Was:** "Mezz EUR 2,251,460 / ZAR 46,440,864 = 20.627"
- **Now:** "Mezz EUR 2,281,460 / ZAR 47,059,088 = 20.627"

---

## PART B: Observations (No Code Change)

### B1. Dual FX rates (20.0 vs ~21.57)
ZAR→EUR conversions for grants/DSRA use implied FX ~21.57 (e.g., R25M DTIC = EUR 1,159,313 → implied FX 21.57), not the model FX of 20.0. This appears intentional — actual transaction rates vs model display rate. All files are internally consistent within their respective FX contexts.

### B2. GEPF R800k unaccounted component
R40M GEPF + R4M third party = R44M, but financing.json says total = R44.8M. User confirmed R44.8M is correct — likely includes an additional component not broken out in the current config.

### B3. `mezz.json` internal inconsistency
- `initial_drawdown_zar` in financing.json: 47,059,088 (updated to match structure.json)
- `initial_amount` in mezz.json: 46,440,864 (old value)
- `rolled_up_interest_zar`: 13,809,805 and `balance_after_rollup_zar`: 55,750,669 are derived from the old 46,440,864 base
- **Impact:** None on model output — mezz.json is a reference schedule document. The model engine reads from structure.json/financing.json. However, the internal inconsistency should be noted for any future mezz.json consumers.

### B4. `country_allocation.json` totals don't sum
Country amounts sum to EUR 15,848,074 but stated total is EUR 16,512,924 (includes IDC). This file appears to be a standalone reference document not consumed by the model engine.

### B5. Hardcoded guarantor financial data
Veracity and Phoenix financial data appears inline in app.py in 3+ locations each (Security tab summary + dedicated Guarantors tab). These should ideally be centralized in a `config/guarantors.json` file. **Recommended future refactor.**

### B6. Display-layer config duplication
Several display/graph sections (Revenue Mix ~L5874, Operations ~L3150) hardcode arrays that also exist in `operations.json`. These currently match but create drift risk. **Recommended future refactor.**

### B7. Pro-rata percentages sum to 1.012
Due to 3-decimal rounding in structure.json (NWL 0.679 + LanRED 0.204 + TWX 0.129 = 1.012). Cosmetic only — actual allocations use exact values.

### B8. TWX coe_lease.start_month (18) vs NWL coe_rent.start_month (24)
These are NOT mirror transactions — TWX leases to third-party tenants from M18, NWL rents from TWX from M24 (after loan holiday). Different start months are correct by design.

---

## Files Modified

| File | Changes |
|------|---------|
| `app.py` | A1 (mezz_reps), A2 (LanRED MWp), A3 (Phoenix coverage ×3 locations), A10 (fallback defaults ×3) |
| `config/assets.json` | A4 (CoE content_split + note) |
| `config/senior_debt.json` | A5 (loan_amount, drawdown_total, balance, principal, waterfall) |
| `config/project.json` | A6 (total_capex), A12 (FX note) |
| `config/mezz.json` | A7 (project_cost_eur) |
| `config/delivery.json` | A8 (NWL/LanRED/TWX totals) |
| `config/financing.json` | A9 (balance_to_repay, principal_per_period) |
| `MEMORY.md` | A11 (rent escalation 7%→5%) |
