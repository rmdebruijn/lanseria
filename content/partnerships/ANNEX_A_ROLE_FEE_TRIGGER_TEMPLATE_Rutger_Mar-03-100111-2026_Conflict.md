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

**Tech and Project:**

| Code | Scope Item | Primary | Secondary |
|------|-----------|---------|-----------|
| S-01 | Project origination | `[__]` | `[__]` |
| S-02 | Technology and Exporter Pre-Selection | `[__]` | `[__]` |
| S-03 | Subsidy access (vendor-linked) | `[__]` | `[__]` |

**Equity and Senior Debt:**

| Code | Scope Item | Primary | Secondary |
|------|-----------|---------|-----------|
| S-04 | Equity / mezzanine structuring | `[__]` | `[__]` |
| S-05 | Non-recourse debt structuring | `[__]` | `[__]` |

**Layer Capital Structures:**

| Code | Scope Item | Primary | Secondary |
|------|-----------|---------|-----------|
| S-06 | First-loss / guarantee architecture (Layer A) | `[__]` | `[__]` |
| S-07 | Credit conversion (ECA / underwriting / swap) (Layer B) | `[__]` | `[__]` |
| S-08 | Credit-enhanced development debt / DFI (Layer C) | `[__]` | `[__]` |
| S-09 | Supplier credit working capital (Layer D) | `[__]` | `[__]` |

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

### Segment 2: Fixed-Rate Items (Subsidy, Equity, Mezzanine, Non-Recourse Debt)

**Formula (Clause 7.4):** `Fee = R% x Base`

| Fee Item | Scope | R% | Base Definition |
|----------|-------|----|-----------------|
| F-03: Subsidy success fee | S-03 | 5% | Subsidy amount secured |
| F-04a: Equity structuring | S-04 | 5% | Equity amount raised/closed |
| F-04b: Mezzanine structuring | S-04 | 4% | Mezzanine amount raised/closed |
| F-05: Non-recourse debt | S-05 | 3% | Debt facility amount closed |

### Segment 3: Frontier Funding Layers (Root-Curve Items)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-06a: Corporate guarantee | S-06 | A | 63 | Guarantee Covered Amount |
| F-06b: PE cash-backed guarantee | S-06 | A | 63 | Cash-backed Covered Amount |
| F-06c: Captive cell insurance | S-06 | A | 16 | Insurance Covered Amount |
| F-07a: ECA packaging | S-07 | B | `[__]` | ECA Covered Amount |
| F-07b: Underwriting / insurance wrap | S-07 | B | `[__]` | Underwriting Covered Amount |
| F-07c: Currency swap | S-07 | B | `[__]` | Swap notional Covered Amount |
| F-08: Credit-enhanced development debt (DFI) | S-08 | C | `[__]` | DFI facility Covered Amount |
| F-09: Supplier credit related supplier working capital | S-09 | D | `[__]` | Working Capital line for supplier |

**Example (F-06a/F-06b, A = 63):**

| B_i (Covered Amount) | sqrt(B_i) | Fee_i | Effective % |
|----------------------|-----------|-------|-------------|
| 1,000,000 | 1,000 | 63,000 | 6.30% |
| 5,000,000 | 2,236 | 140,900 | 2.82% |
| 10,000,000 | 3,162 | 199,200 | 1.99% |
| 20,000,000 | 4,472 | 281,700 | 1.41% |
| 50,000,000 | 7,071 | 445,500 | 0.89% |

**Example (F-06c, A = 16):**

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
