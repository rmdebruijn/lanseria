# PARTNER ANNEX SET — CARL / TERAYON

**Linked Agreement:** Master Partnership Agreement dated **[Effective Date]** between NexusNovus Capital B.V. and **Terayon (Pty) Ltd** (or relevant Carl entity)
**Partner Short Name:** Carl
**Document Date:** 2026-02-18

This document combines all partner-specific annexes for Carl into a single instrument. Each section corresponds to one Annex as referenced in the Agreement body.

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
| S-06 | First-loss / guarantee architecture | X | |
| S-04 | Equity / mezzanine structuring | X | |
| S-07 | Underwriting / swap credit conversion | X | |

Only scope items where Carl holds a Primary or Secondary role are listed.

## A.2 Fee Variables

Fee formulae are defined in the Agreement body (Clause 7.4). Variable values below are per the base template unless this Annex states otherwise. Only fee items linked to Carl's scope are shown.

### Segment 1: Repeat-Decay Items

**Formula (Clause 7.4):** `Fee_i_j = B_i x (A / sqrt(j))`

A is a fixed starting percentage. B_i is the project value per Designated Transaction. j is the instance number from the same source.

| Fee Item | Scope | A | B_i Definition |
|----------|-------|---|----------------|
| F-01: Project origination | S-01 | 2% | Project value |

Carl's origination (F-01) applies to Terayon-sourced opportunities outside the NexusNovus pipeline. Decay tracks per origination source.

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
| F-04a: Equity structuring | S-04 | 5% | Equity amount raised/closed |
| F-04b: Mezzanine structuring | S-04 | 4% | Mezzanine amount raised/closed |

### Segment 3: Root-Curve Items (Frontier Funding Layers)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-06a: Corporate guarantee | S-06 | A | 63 | Guarantee Covered Amount |
| F-06b: PE cash-backed guarantee | S-06 | A | 63 | Cash-backed Covered Amount |
| F-06c: Captive cell insurance | S-06 | A | 16 | Insurance Covered Amount |
| F-07b: Underwriting / insurance wrap | S-07 | B | `[__]` | Underwriting Covered Amount |
| F-07c: Currency swap | S-07 | B | `[__]` | Swap notional Covered Amount |

F-06c (captive cell) is set at A = 16 reflecting that Carl is compensated through the captive cell JV structure (see Annex S below). F-06a and F-06b are calibrated to ~2% effective at EUR 10M Covered Amount.

Renewal-decay and increase mechanics per Clause 7.6 of the Agreement apply to all Root-Curve items.

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

---

# ANNEX B — Designated Transaction Mandate Schedules

## Schedule B-1: NWL — Cross Currency Swap

| Field | Value |
|-------|-------|
| Transaction Index | B-1 |
| Project Name | NWL |
| Country / Region | `[__]` |
| Sector | Infrastructure / Utility |
| Estimated Project Value | `[__]` |

### Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-07 | Underwriting / swap credit conversion | P | Cross Currency Swap structuring |
| S-06 | First-loss / guarantee architecture | P | Veracity as guarantor |

### Credit Stack Routes

| Route | Applicable | Notes |
|-------|-----------|-------|
| Route 1: ECA cover | No | |
| Route 2: Underwriting / insurance wrap | No | |
| Route 3: Currency swap as credit instrument | Yes | Cross Currency Swap against books of Veracity as guarantor |

### Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | Carl / Terayon | CCS structuring + guarantor engagement |

### Fee References

| Fee Item | B_i (Covered Amount) | Notes |
|----------|--------------------|-------|
| F-07c: Currency swap | ~EUR 2,000,000 | CCS notional — current estimate |
| F-06a: Corporate guarantee | ~EUR 2,000,000 | Veracity guarantee on CCS — Covered Amount aligned with swap notional |

### Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | `[__]` |

### Special Conditions

None beyond standard terms.

---

## Schedule B-2: LanRED — Cross Currency Swap (Brownfield) OR Underwriting (Greenfield)

| Field | Value |
|-------|-------|
| Transaction Index | B-2 |
| Project Name | LanRED |
| Country / Region | `[__]` |
| Sector | Infrastructure / Utility |
| Estimated Project Value | `[__]` |

### Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-07 | Underwriting / swap credit conversion | P | CCS (brownfield scenario) or underwriting (greenfield scenario) |
| S-06 | First-loss / guarantee architecture | P | Supporting Layer A if required |

### Credit Stack Routes

Two alternative pathways depending on project configuration:

**Brownfield scenario:**

| Route | Applicable | Notes |
|-------|-----------|-------|
| Route 1: ECA cover | No | |
| Route 2: Underwriting / insurance wrap | No | |
| Route 3: Currency swap as credit instrument | Yes | CCS against PPA (power purchase agreement) as underlying |

**Greenfield scenario:**

| Route | Applicable | Notes |
|-------|-----------|-------|
| Route 1: ECA cover | No | |
| Route 2: Underwriting / insurance wrap | Yes | Underwriting wrap for greenfield structure |
| Route 3: Currency swap as credit instrument | No | |

NexusNovus determines which scenario applies; the applicable route is confirmed in writing before mandate activation.

### Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | Carl / Terayon | CCS or underwriting structuring depending on scenario |

### Fee References

**Brownfield (CCS):**

| Fee Item | B_i (Covered Amount) | Notes |
|----------|--------------------|-------|
| F-07c: Currency swap | ~EUR 3,000,000 | CCS notional against PPA — current estimate |

**Greenfield (Underwriting):**

| Fee Item | B_i (Covered Amount) | Notes |
|----------|--------------------|-------|
| F-07b: Underwriting / insurance wrap | ~EUR 3,000,000 | Underwriting Covered Amount — current estimate |

### Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | `[__]` |

### Special Conditions

Scenario determination (brownfield CCS vs greenfield underwriting) is at NexusNovus discretion. Only one pathway activates per execution; fees are not payable on both.

---

# ANNEX R — Retainer Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## R.1 Activation

| Field | Value |
|-------|-------|
| Retainer activated | Yes |
| Activation date | `[__]` |
| Linked Designated Transaction(s) | All |

## R.2 Retainer Amount and Cadence

| Field | Value |
|-------|-------|
| Monthly retainer amount | ZAR 25,000 |
| Payment cadence | Monthly |
| Currency | ZAR |

## R.3 Conditions

| Field | Value |
|-------|-------|
| Performance conditions | Active participation in allocated Designated Transactions; maintenance of counterparty engagement tracker |
| Subsidy application initiation required (per Clause 8.3) | No |
| Minimum delivery obligations | Monthly status update per active Designated Transaction |

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
- a compliance concern arises per Clause 21.

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
| Conversion ratio / valuation basis | Fair market value at time of conversion, determined by mutual agreement or independent valuation if parties disagree within 15 Business Days |
| Conversion window | 60 days from fee trigger confirmation |

## E.3 Conversion Process

1. Either Party may provide written notice of intent to convert within the conversion window.
2. The receiving Party shall confirm the conversion amount, equity instrument, and valuation within 15 Business Days of receiving notice.
3. Conversion is effective upon execution of the relevant equity subscription or transfer documentation.

Note: This is a mutual conversion right — both NexusNovus and Carl may initiate.

## E.4 Equity Instrument

| Field | Value |
|-------|-------|
| Entity issuing equity | SPV or project vehicle of the relevant Designated Transaction |
| Instrument type | As agreed per conversion — ordinary shares, preference shares, or convertible note |
| Rights attached | As specified in the subscription documentation per conversion |
| Transfer restrictions | Lock-up period of `[__]` months from conversion; no transfer without counterparty consent |

## E.5 Anti-Dilution and Protective Rights

| Field | Value |
|-------|-------|
| Anti-dilution protection | Weighted-average broad-based |
| Pre-emption rights | Yes — pro-rata on subsequent equity rounds in the same vehicle |
| Tag-along / drag-along | Yes — standard tag-along; drag-along above `[__]`% threshold |

## E.6 Conditions and Limitations

1. Conversion does not discharge any other obligation under the Agreement.
2. Fees converted to equity are no longer payable in cash and are not subject to retainer offset under Annex R.
3. **Lease Exclusion.** Fee-to-equity conversion is not available for lease-based Designated Transactions, per Clause 18.3 of the Agreement. This restriction cannot be overridden.
4. NexusNovus retains the right to refuse conversion if it would breach applicable law, governance requirements, or third-party obligations.

---

# ANNEX S — Specials / Project-Specific Structures

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## S.1 — Captive Cell Insurance Joint Venture

**Linked Designated Transaction(s):** All (framework-level special)

### Special Terms

Carl and NexusNovus intend to establish a captive cell insurance structure for first-loss risk absorption across the Frontier Funding portfolio. Key terms:

| Field | Value |
|-------|-------|
| Structure | Protected cell company or equivalent segregated-portfolio vehicle |
| Governance | Joint — NexusNovus retains majority governance rights; Carl has operational involvement in cell structuring |
| Carl's economic participation | Equity interest in the cell and/or management fee — to be agreed in a separate JV agreement |
| Relationship to Annex A | F-06c (captive cell insurance) is set at A = 16, reflecting that Carl's primary compensation for captive cell work flows through the JV, not through the fee schedule |
| Timeline | JV agreement to be executed within `[__]` months of Agreement Effective Date |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| F-06c fee level in Annex A | Reduced A value (16 vs 63 for other Layer A instruments) to reflect JV compensation |

## S.2 — Tail Period

**Linked Designated Transaction(s):** All

### Special Terms

Upon termination of the Agreement for any reason, Carl retains tail rights on Designated Transactions in which Carl made a material, documented contribution prior to termination.

| Field | Value |
|-------|-------|
| Tail period | 24 months from effective termination date |
| Tail scope | Fee Items for which Carl's contribution was accepted or in-progress at termination |
| Tail fee basis | Same formulae and variable values as at termination; no escalation |
| Evidence requirement | NexusNovus determines attributable contribution based on documented work product |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 26.2 (Tail) | Specifies 24-month tail with documented-contribution requirement |

## S.3 — Payment Terms

**Linked Designated Transaction(s):** All

### Special Terms

| Field | Value |
|-------|-------|
| Payment timing | 7 Business Days from NexusNovus receipt of the relevant project payment (not from invoice date) |
| Rationale | Cash-flow alignment: Carl is paid when NexusNovus is paid |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 16.2 (14 Business Day payment term) | Replaced with 7 Business Days from NexusNovus receipt |

## S.4 — Credit Insurance on NexusNovus

**Linked Designated Transaction(s):** All

### Special Terms

Carl may, at Carl's own cost, take out credit insurance on NexusNovus payment obligations under this Agreement. NexusNovus shall cooperate reasonably with any information requests from the insurer, provided no confidential project information is disclosed beyond what is necessary for the credit assessment.

### Scope of Override

No provision overridden. This is an additional right.

## S.5 — Break Fee

**Linked Designated Transaction(s):** All

### Special Terms

If NexusNovus abandons a Designated Transaction for reasons other than structural infeasibility, regulatory prohibition, or Partner breach, and Carl has delivered accepted work product for that transaction, Carl is entitled to a break fee.

| Field | Value |
|-------|-------|
| Break fee basis | Reasonable out-of-pocket costs incurred by Carl on that Designated Transaction, supported by documentation |
| Cap | `[__]` per Designated Transaction |
| Exclusions | No break fee if abandonment is due to structural infeasibility, regulatory prohibition, force majeure, or Carl's breach |
| Trigger | Written notice of abandonment from NexusNovus |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 9.3 (NexusNovus discretion to withdraw) | Break fee payable on non-structural abandonment where accepted work product exists |

## S.6 — Guarantee Renewal Exclusion

**Linked Designated Transaction(s):** All

### Special Terms

For avoidance of doubt: routine administrative guarantee renewals (extensions of the same instrument on the same terms for the same Designated Transaction) do not constitute a new Fee Trigger. Renewal-decay under Clause 7.6 applies only where the renewal involves a material restructuring, re-underwriting, or change in Covered Amount.

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 7.6 (Renewal-Decay) | Clarifies that administrative renewals are not fee-triggering events |

## S.7 — Dispute Resolution: Arbitration

**Linked Designated Transaction(s):** All

### Special Terms

Disputes between NexusNovus and Carl under this Agreement shall be resolved by arbitration. No personal guarantee of NexusNovus principals shall be required as a condition of this Agreement or any Designated Transaction.

| Field | Value |
|-------|-------|
| Arbitration rules | `[__]` (propose UNCITRAL or ICC) |
| Seat | `[__]` |
| Language | English |
| Personal guarantee requirement | None — expressly excluded |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 27.2 | Confirms arbitration and expressly excludes personal guarantee requirement |

---

# ANNEX C — Sub-Agent Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## Framework Sub-Agent Authorization

Carl is authorized to engage Sub-Agents for the following scope areas, subject to prior written NexusNovus approval per Clause 13:

| # | Service Area | Typical Sub-Agent Profile | Notes |
|---|-------------|--------------------------|-------|
| 1 | Guarantor sourcing | PE firms, family offices, corporate guarantee providers | Identifying and engaging potential first-loss counterparties |
| 2 | Underwriter sourcing | Insurance brokers, underwriting syndicates | Identifying and engaging potential Layer B underwriters |
| 3 | Captive cell specialists | Insurance structuring advisors, cell management companies | Supporting Annex S.1 captive cell JV development |

## Sub-Agent Economics

| Field | Value |
|-------|-------|
| Fee basis | To be agreed per Sub-Agent engagement |
| Payment source | Carl pays Sub-Agent directly |
| Offset against Carl's fees | No — Sub-Agent costs are Carl's responsibility |

Payment-flow transparency: Carl shall disclose all Sub-Agent economics to NexusNovus. No undisclosed pass-through arrangements are permitted.

## Compliance

Sub-Agents shall comply with the same compliance, confidentiality, and conduct obligations as Carl under the Agreement (Clauses 21 and 22). Carl is responsible for ensuring Sub-Agent compliance.

## Reporting

| Field | Value |
|-------|-------|
| Reports to | Both Carl and NexusNovus |
| Reporting cadence | As required per Designated Transaction |
| Reporting format | NexusNovus standard template |

## Per-Transaction Sub-Agent Schedules

Individual Sub-Agent engagements linked to specific Designated Transactions will be documented as numbered schedules (Schedule C-1, C-2, ...) each referencing the relevant Schedule B-n.

`[No Sub-Agent schedules activated at this time.]`

---

# SIGNATURE BLOCK

For and on behalf of **NexusNovus Capital B.V.**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________

For and on behalf of **Terayon (Pty) Ltd** (Carl)

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________
