# PARTNER ANNEX SET — PHILIP

**Linked Agreement:** Master Partnership Agreement dated **[Effective Date]** between NexusNovus Capital B.V. and **[Philip's Legal Entity]**
**Partner Short Name:** Philip
**Document Date:** 2026-02-18

This document combines all partner-specific annexes for Philip into a single instrument. Each section corresponds to one Annex as referenced in the Agreement body.

**Numbering convention:** Designated Transaction schedules are numbered `Schedule B-1, B-2, ...` and Sub-Agent schedules are numbered `Schedule C-1, C-2, ...` to distinguish from Agreement clause numbers.

---

# ANNEX A — Work Scope Classification and Fee Variables

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## A.1 Scope Classification

Schedule B-1, B-2, etc. may override for a specific Designated Transaction.

| Code | Scope Item | Primary | Secondary |
|------|-----------|---------|-----------|
| S-01 | Project origination | | X |
| S-02 | Technology and Exporter Pre-Selection | X | |
| S-05 | ECA packaging and credit conversion | | X |
| S-06 | Non-recourse debt structuring | | X |
| S-07 | Credit-enhanced development debt (DFI) | | X |
| S-09 | Subsidy access (vendor-linked) | X | |

Only scope items where Philip holds a Primary or Secondary role are listed. Philip does not receive supplier commissions. Any supplier-side economics are disclosed and flow through NexusNovus governance.

## A.2 Fee Variables

Fee formulae are defined in the Agreement body (Clause 7.4). Only fee items linked to Philip's scope are shown.

### Segment 1: Repeat-Decay Items

**Formula (Clause 7.4):** `Fee_i_j = B_i x (A / sqrt(j))`

A is a fixed starting percentage. B_i is the project value per Designated Transaction. j is the instance number from the same source.

| Fee Item | Scope | A | B_i Definition |
|----------|-------|---|----------------|
| F-01: Project origination | S-01 | 2% | Project value |
| F-02: Technology / exporter pre-selection | S-02 | 1% | Project value |

Decay tracks per origination source (F-01) and per technology provider (F-02) independently.

**Example (F-02):** A = 1%, B_i = EUR 10,000,000:

| Instance j | A / sqrt(j) | Fee_i_j |
|------------|-------------|---------|
| 1 | 1.00% | 100,000 |
| 2 | 0.71% | 71,000 |
| 3 | 0.58% | 58,000 |
| 5 | 0.45% | 45,000 |
| 10 | 0.32% | 32,000 |

### Segment 2: Fixed-Rate Items

**Formula (Clause 7.4):** `Fee = R% x Base`

| Fee Item | Scope | R% | Base Definition |
|----------|-------|----|-----------------|
| F-05: Non-recourse debt | S-06 | 3% | Debt facility amount closed |
| F-06: Subsidy success fee | S-09 | 5% | Subsidy amount secured |

### Segment 3: Root-Curve Items (Frontier Funding Layers)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-10: ECA packaging | S-05 | B | `[__]` | ECA Covered Amount |
| F-13: Credit-enhanced development debt (DFI) | S-07 | C | `[__]` | DFI facility Covered Amount |

Renewal-decay and increase mechanics per Clause 7.6 of the Agreement apply to all Root-Curve items.

---

# ANNEX B — Designated Transaction Mandate Schedules

`[No Designated Transaction schedules activated at this time. Schedules will be added as Schedule B-1, B-2, etc.]`

---

# ANNEX R — Retainer Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## R.1 Activation

| Field | Value |
|-------|-------|
| Retainer activated | No |
| Activation date | N/A |
| Linked Designated Transaction(s) | N/A |

Retainer is not activated for Philip at this time. If activated in the future, the retainer terms in the Agreement body (Clause 17) and the base template mechanics apply. Activation requires a written amendment to this section.

---

# ANNEX E — Equity Conversion Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## E.1 Activation

| Field | Value |
|-------|-------|
| Equity conversion activated | Yes |
| Linked Designated Transaction(s) | All (subject to lease exclusion below) |

## E.2 Conversion Mechanics

| Field | Value |
|-------|-------|
| Eligible fees for conversion | All triggered fees |
| Maximum conversion amount | `[__]` per Designated Transaction |
| Conversion ratio / valuation basis | Fair market value at time of conversion, determined by mutual agreement or independent valuation |
| Conversion window | 60 days from fee trigger confirmation |

## E.3 Conversion Process

1. Partner must provide written notice of intent to convert within the conversion window.
2. NexusNovus shall confirm the conversion amount, equity instrument, and valuation within 15 Business Days of receiving notice.
3. Conversion is effective upon execution of the relevant equity subscription or transfer documentation.

## E.4 Equity Instrument

| Field | Value |
|-------|-------|
| Entity issuing equity | SPV or project vehicle of the relevant Designated Transaction |
| Instrument type | As agreed per conversion |
| Rights attached | As specified in the subscription documentation per conversion |
| Transfer restrictions | Lock-up period of `[__]` months; no transfer without NexusNovus consent |

## E.5 Anti-Dilution and Protective Rights

| Field | Value |
|-------|-------|
| Anti-dilution protection | No |
| Pre-emption rights | No |
| Tag-along / drag-along | Standard tag-along only |

## E.6 Conditions and Limitations

1. Conversion does not discharge any other obligation under the Agreement.
2. Fees converted to equity are no longer payable in cash and are not subject to retainer offset under Annex R.
3. **Lease Exclusion.** Fee-to-equity conversion is not available for lease-based Designated Transactions, per Clause 18.3 of the Agreement. This restriction cannot be overridden.
4. NexusNovus retains the right to refuse conversion if it would breach applicable law, governance requirements, or third-party obligations.

---

# ANNEX S — Specials / Project-Specific Structures

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## S.1 — Subsidy Conversion to TWX Minority Equity

**Linked Designated Transaction(s):** First Designated Transaction involving TWX only (one-time special)

### Special Terms

In lieu of the standard subsidy success fee (F-06) for the first Designated Transaction involving TWX, Philip may elect to convert the subsidy success fee into a minority equity stake in TWX.

| Field | Value |
|-------|-------|
| Conversion right | One-time election: subsidy success fee for the first TWX transaction may be converted to minority equity in TWX |
| Equity stake | Minority — percentage to be determined based on F-06 fee amount and TWX valuation at the time of conversion |
| Valuation basis | Independent valuation or mutual agreement |
| Replaces | This special replaces any right of first refusal (ROFR) that would otherwise apply under Contract B for the first TWX transaction |
| Subsequent transactions | Normal F-06 subsidy success fee applies (cash, per Annex A) — this conversion right is not repeatable |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| F-06 (Subsidy success fee) | One-time conversion to TWX minority equity instead of cash fee, for first TWX transaction only |
| Any ROFR under Contract B | Replaced by this equity conversion right for first TWX transaction |

## S.2 — Timber Trade Joint Venture (Finland)

**Linked Designated Transaction(s):** Designated Transactions involving Timber Trade operations in Finland

### Special Terms

Philip and NexusNovus intend to structure a joint venture for Timber Trade incorporation and operations in Finland.

| Field | Value |
|-------|-------|
| Structure | Finnish entity (Oy or equivalent) |
| Purpose | Local incorporation vehicle for Timber Trade operations, supplier structuring, and subsidy access in Finland/Nordic region |
| Philip's role | Operational lead — technology sourcing, supplier management, local regulatory and subsidy navigation |
| NexusNovus role | Capital structuring, governance, and Frontier Funding execution |
| Economic terms | To be agreed in a separate JV agreement |
| Timeline | JV agreement to be executed within `[__]` months of Agreement Effective Date |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| None | Additional structure; does not override Agreement provisions. Philip's fee entitlements for Timber Trade Designated Transactions are per Annex A unless the JV agreement states otherwise |

---

# ANNEX C — Sub-Agent Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## Framework Sub-Agent Authorization

Philip is authorized to engage Sub-Agents, subject to prior written NexusNovus approval per Clause 13. Individual Sub-Agent engagements are documented as numbered schedules (Schedule C-1, C-2, ...) below.

## Schedule C-1: Hannah (Sweden)

### Sub-Agent Identification

| Field | Value |
|-------|-------|
| Sub-Agent Name | Hannah `[Surname]` |
| Legal Form / Jurisdiction | `[__]` / Sweden |
| Registration Number | `[__]` |
| Contact Person | Hannah `[Surname]` |

### Scope of Sub-Agent Services

| # | Service Description | Linked Scope Code(s) | Notes |
|---|--------------------|-----------------------|-------|
| 1 | Technology and exporter sourcing — Nordic/Swedish market | S-02 | Swedish and Nordic supplier identification, qualification, and relationship management |
| 2 | Subsidy access — Swedish/EU subsidy pathways | S-09 | Swedish export subsidy and EU funding programme navigation |

### Reporting Line

| Field | Value |
|-------|-------|
| Reports to | Philip (primary), NexusNovus (copy) |
| Reporting cadence | Monthly or as required per Designated Transaction |
| Reporting format | NexusNovus standard template |

### Economics and Payment Flow

| Field | Value |
|-------|-------|
| Fee basis | `[__]` |
| Fee amount or rate | `[__]` |
| Payment source | Philip pays Hannah directly |
| Offset against Philip's fees | No — Sub-Agent costs are Philip's responsibility |

Payment-flow transparency: Philip shall disclose all Sub-Agent economics to NexusNovus. No undisclosed pass-through arrangements are permitted.

### Compliance

Hannah shall comply with the same compliance, confidentiality, and conduct obligations as Philip under the Agreement (Clauses 21 and 22). Philip is responsible for ensuring Sub-Agent compliance.

### Duration

| Field | Value |
|-------|-------|
| Start date | `[__]` |
| End date / trigger | Co-terminus with Agreement unless earlier terminated |
| Early termination conditions | Per Philip's discretion with NexusNovus notification; or NexusNovus directive per Clause 13 |

## Further Sub-Agent Schedules

Additional Sub-Agent engagements will be documented as Schedule C-2, C-3, etc., each referencing the relevant Schedule B-n where applicable.

---

# SIGNATURE BLOCK

For and on behalf of **NexusNovus Capital B.V.**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________

For and on behalf of **[Philip's Legal Entity]**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________
