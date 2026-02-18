# ANNEX A
## Work Scope Classification and Fee Variables (Template)

**Linked Agreement:** Master Partnership Agreement dated **[Effective Date]** between NexusNovus Capital B.V. and **[Partner Legal Name]**
**Annex Version:** **[vX.Y]**
**Annex Effective Date:** **[Date]**

---

## 1. Annex Purpose

This Annex A provides:

1. Work Scope classification (Primary/Secondary) per Partner.
2. Variable values for the three fee formulae defined in the Agreement body (Clause 7.4).

Formulae are not restated here. Stacking rules are in the Agreement body (Clause 7.5). This Annex does not create payment entitlement by scope label alone.

---

## 2. Scope Classification

The relevant Schedule B-n may override for a specific Designated Transaction.

| Code | Scope Item | Primary | Secondary |
|------|-----------|---------|-----------|
| S-01 | Project origination | `[__]` | `[__]` |
| S-02 | Technology and Exporter Pre-Selection | `[__]` | `[__]` |
| S-03 | First-loss / guarantee architecture | `[__]` | `[__]` |
| S-04 | Equity / mezzanine structuring | `[__]` | `[__]` |
| S-05 | ECA packaging and credit conversion | `[__]` | `[__]` |
| S-06 | Non-recourse debt structuring | `[__]` | `[__]` |
| S-07 | Credit-enhanced development debt (DFI) | `[__]` | `[__]` |
| S-08 | Underwriting / swap credit conversion | `[__]` | `[__]` |
| S-09 | Subsidy access (vendor-linked) | `[__]` | `[__]` |
| S-10 | Supplier credit related supplier working capital | `[__]` | `[__]` |

---

## 3. Fee Variables

### Segment 1: Repeat-Decay Items (Origination, Technology)

**Formula (Clause 7.4):** `Fee_i_j = B_i x (A / sqrt(j))`

A is a fixed starting percentage. B_i is the project value per Designated Transaction. j is the instance number from the same source.

| Fee Item | Scope | A | B_i Definition |
|----------|-------|---|----------------|
| F-01: Project origination | S-01 | 2% | Project value |
| F-02: Technology / exporter pre-selection | S-02 | 1% | Project value |

Decay is tracked per origination source (F-01) and per technology provider (F-02) independently.

**Example (F-01):** A = 2%, B_i = EUR 10,000,000:

| Instance j | A / sqrt(j) | Fee_i_j |
|------------|-------------|---------|
| 1 | 2.00% | 200,000 |
| 2 | 1.41% | 141,000 |
| 3 | 1.15% | 115,000 |
| 5 | 0.89% | 89,000 |
| 10 | 0.63% | 63,000 |
| 20 | 0.45% | 45,000 |

### Segment 2: Fixed-Rate Items (Equity, Mezzanine, Non-Recourse Debt, Subsidy)

**Formula (Clause 7.4):** `Fee = R% x Base`

| Fee Item | Scope | R% | Base Definition |
|----------|-------|----|-----------------|
| F-03: Equity structuring | S-04 | 5% | Equity amount raised/closed |
| F-04: Mezzanine structuring | S-04 | 4% | Mezzanine amount raised/closed |
| F-05: Non-recourse debt | S-06 | 3% | Debt facility amount closed |
| F-06: Subsidy success fee | S-09 | 5% | Subsidy amount secured |

### Segment 3: Frontier Funding Layers (Root-Curve Items)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-07: Corporate guarantee | S-03 | A | 63 | Guarantee Covered Amount |
| F-08: PE cash-backed guarantee | S-03 | A | 63 | Cash-backed Covered Amount |
| F-09: Captive cell insurance | S-03 | A | 16 | Insurance Covered Amount |
| F-10: ECA packaging | S-05 | B | `[__]` | ECA Covered Amount |
| F-11: Underwriting / insurance wrap | S-08 | B | `[__]` | Underwriting Covered Amount |
| F-12: Currency swap | S-08 | B | `[__]` | Swap notional Covered Amount |
| F-13: Credit-enhanced development debt (DFI) | S-07 | C | `[__]` | DFI facility Covered Amount |
| F-14: Supplier credit related supplier working capital | S-10 | D | `[__]` | Working Capital line for supplier |

**Example (F-07/F-08, A = 63):**

| B_i (Covered Amount) | sqrt(B_i) | Fee_i | Effective % |
|----------------------|-----------|-------|-------------|
| 1,000,000 | 1,000 | 63,000 | 6.30% |
| 5,000,000 | 2,236 | 140,900 | 2.82% |
| 10,000,000 | 3,162 | 199,200 | 1.99% |
| 20,000,000 | 4,472 | 281,700 | 1.41% |
| 50,000,000 | 7,071 | 445,500 | 0.89% |

**Example (F-09, A = 16):**

| B_i (Covered Amount) | sqrt(B_i) | Fee_i | Effective % |
|----------------------|-----------|-------|-------------|
| 1,000,000 | 1,000 | 16,000 | 1.60% |
| 5,000,000 | 2,236 | 35,800 | 0.72% |
| 10,000,000 | 3,162 | 50,600 | 0.51% |
| 20,000,000 | 4,472 | 71,600 | 0.36% |
| 50,000,000 | 7,071 | 113,100 | 0.23% |

---

## 4. Signature Block

For and on behalf of **NexusNovus Capital B.V.**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________

For and on behalf of **[Partner Legal Name]**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________
