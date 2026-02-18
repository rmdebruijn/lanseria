# PARTNER ANNEX SET — ROBBERT

**Linked Agreement:** Master Partnership Agreement dated **[Effective Date]** between NexusNovus Capital B.V. and **[Robbert's Legal Entity]**
**Partner Short Name:** Robbert
**Document Date:** 2026-02-18

This document combines all partner-specific annexes for Robbert into a single instrument. Each section corresponds to one Annex as referenced in the Agreement body.

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
| S-02 | Technology and Exporter Pre-Selection | | X |
| S-05 | ECA packaging and credit conversion | X | |
| S-07 | Credit-enhanced development debt (DFI) | | X |
| S-09 | Subsidy access (vendor-linked) | | X |
| S-10 | Supplier credit related supplier working capital | | X |

Only scope items where Robbert holds a Primary or Secondary role are listed. Robbert's primary domain is ECA (S-05). All European ECAs fall within scope. Fee basis is at programme level, not per-application.

## A.2 Fee Variables

Fee formulae are defined in the Agreement body (Clause 7.4). Only fee items linked to Robbert's scope are shown.

### Segment 1: Repeat-Decay Items

**Formula (Clause 7.4):** `Fee_i_j = B_i x (A / sqrt(j))`

A is a fixed starting percentage. B_i is the project value per Designated Transaction. j is the instance number from the same source.

| Fee Item | Scope | A | B_i Definition |
|----------|-------|---|----------------|
| F-01: Project origination | S-01 | 2% | Project value |
| F-02: Technology / exporter pre-selection | S-02 | 1% | Project value |

**Example (F-01):** A = 2%, B_i = EUR 10,000,000:

| Instance j | A / sqrt(j) | Fee_i_j |
|------------|-------------|---------|
| 1 | 2.00% | 200,000 |
| 2 | 1.41% | 141,000 |
| 3 | 1.15% | 115,000 |
| 5 | 0.89% | 89,000 |
| 10 | 0.63% | 63,000 |

### Segment 2: Fixed-Rate Items

**Formula (Clause 7.4):** `Fee = R% x Base`

| Fee Item | Scope | R% | Base Definition |
|----------|-------|----|-----------------|
| F-06: Subsidy success fee | S-09 | 5% | Subsidy amount secured |

### Segment 3: Root-Curve Items (Frontier Funding Layers)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-10: ECA packaging | S-05 | B | `[__]` | ECA Covered Amount |
| F-13: Credit-enhanced development debt (DFI) | S-07 | C | `[__]` | DFI facility Covered Amount |
| F-14: Supplier credit related supplier working capital | S-10 | D | `[__]` | Working Capital line for supplier |

F-10 is Robbert's core fee item. The A value is subject to negotiation and will be set by written amendment to this Annex. F-13 and F-14 are similarly open pending negotiation.

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
| Retainer activated | Yes — conditional start |
| Activation date | Conditional: retainer starts on the date Robbert initiates the first subsidy application under Clause 8.3 |
| Linked Designated Transaction(s) | All |

## R.2 Retainer Amount and Cadence

| Field | Value |
|-------|-------|
| Monthly retainer amount | `[__]` |
| Payment cadence | Monthly |
| Currency | EUR |

## R.3 Conditions

| Field | Value |
|-------|-------|
| Performance conditions | Active participation in allocated Designated Transactions; maintenance of ECA submission tracker |
| Subsidy application initiation required (per Clause 8.3) | Yes — retainer activation is conditional on Robbert initiating a subsidy application |
| Minimum delivery obligations | Monthly ECA pipeline status update per active Designated Transaction |

## R.4 Offset and Reconciliation

Retainer amounts are creditable against future triggered fees per Clause 17.3 of the Agreement.

| Field | Value |
|-------|-------|
| Offset against success fees | Yes |
| Offset percentage | 100% of triggered fees until retainer is fully offset |
| Reconciliation period | Quarterly |

If total triggered fees in a reconciliation period exceed retainer paid, the excess is payable per Clause 16.

If total triggered fees are less than retainer paid, the difference is treated as: Non-refundable (retainer secures capacity, not outcomes).

## R.5 Suspension and Termination

NexusNovus may suspend retainer payments if:

- Partner fails to meet minimum delivery obligations;
- a Designated Transaction is suspended per Clause 25.4;
- a compliance concern arises per Clause 21;
- the conditional start trigger (subsidy application initiation) has not occurred within `[__]` months of Agreement Effective Date.

Retainer terminates automatically upon termination of the Agreement. Pro-rata treatment applies for partial periods.

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
| Eligible fees for conversion | All triggered fees except retainer amounts already offset |
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

## S.1 — Captive ECA Integrator

**Linked Designated Transaction(s):** All (framework-level special)

### Special Terms

Robbert shall develop and operate a captive integrator capability for repeatable ECA packaging across the NexusNovus portfolio. The integrator handles ECA applications on behalf of project vehicles, centralising method, quality, and country-specialist coordination under one platform.

| Field | Value |
|-------|-------|
| Structure | Company-captive or NexusNovus-controlled entity (Integrator per Agreement definition) |
| Robbert's role | Build, operate, and maintain the integrator platform; deploy country ECA specialists under central method |
| NexusNovus role | Governance, approval of specialist appointments, quality standards, and submission sign-off |
| Scope | All European ECAs; scope may extend to non-European ECAs by written amendment |
| Fee basis | Programme-level: Robbert's ECA fee (F-10) is earned at programme level, not per individual ECA application within a Designated Transaction |
| Specialist costs | Country ECA specialists are engaged as Sub-Agents under Annex C below; costs are Robbert's responsibility unless otherwise agreed |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 4.4(e) (ECA packaging) | Robbert operates through a captive integrator structure rather than ad-hoc ECA advisory |

## S.2 — Pan-European Banking Network Expansion

**Linked Designated Transaction(s):** All (framework-level special)

### Special Terms

Robbert shall leverage and expand his existing European banking network to support Layer C (Follow-On Liquidity) placement. This is a secondary scope activity (S-07) that complements the primary ECA packaging role.

| Field | Value |
|-------|-------|
| Purpose | Identify and engage EU commercial banks, DFIs, and local banks for debt placement on ECA-backed Designated Transactions |
| Scope | Pan-European; initial focus on `[__]` (specify priority countries/banks) |
| Deliverable | Banking network map with relationship status, appetite assessment, and conversion pipeline per Designated Transaction |
| Fee basis | Standard F-13 (DFI/Layer C) per Annex A — no special fee treatment |

### Scope of Override

No provision overridden. This is a description of Robbert's secondary scope execution approach for S-07.

---

# ANNEX C — Sub-Agent Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## Framework Sub-Agent Authorization

Robbert is authorized to engage country ECA specialists as Sub-Agents, subject to prior written NexusNovus approval per Clause 13. All specialists operate under the central ECA method established through the captive integrator (Annex S.1). Individual engagements are documented as numbered schedules (Schedule C-1, C-2, ...) below.

## Sub-Agent Economics (applies to all schedules)

| Field | Value |
|-------|-------|
| Fee basis | Per-assignment or retainer — to be agreed per specialist engagement |
| Payment source | Robbert pays Sub-Agents directly |
| Offset against Robbert's fees | No — Sub-Agent costs are Robbert's responsibility |

Payment-flow transparency: Robbert shall disclose all Sub-Agent economics to NexusNovus. No undisclosed pass-through arrangements are permitted.

## Compliance and Central Method (applies to all schedules)

Sub-Agents shall:

- comply with the same compliance, confidentiality, and conduct obligations as Robbert under the Agreement (Clauses 21 and 22);
- operate under the central ECA method and quality standards established by the integrator (Annex S.1);
- report through Robbert to NexusNovus on a cadence defined per Designated Transaction.

Robbert is responsible for ensuring Sub-Agent compliance and quality.

## Reporting (applies to all schedules)

| Field | Value |
|-------|-------|
| Reports to | Robbert (primary), NexusNovus (copy) |
| Reporting cadence | Per Designated Transaction milestone schedule |
| Reporting format | NexusNovus standard template + ECA submission tracker |

## Per-Country Sub-Agent Schedules

`[No Sub-Agent schedules activated at this time. Country ECA specialists will be added as Schedule C-1, C-2, etc., each identifying the specialist, country/ECA agency, scope, and fee arrangement.]`

---

# SIGNATURE BLOCK

For and on behalf of **NexusNovus Capital B.V.**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________

For and on behalf of **[Robbert's Legal Entity]**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________
