# PARTNER ANNEX SET — ZEN CUSTOMER FINANCE B.V.

**Linked Agreement:** Master Partnership Agreement dated **[Effective Date]** between NexusNovus Capital B.V. and Zen Customer Finance B.V.
**Partner Short Name:** ZCF
**Document Date:** **[Date]**

This document combines all partner-specific annexes for ZCF into a single instrument. Each section corresponds to one Annex as referenced in the Agreement body.

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
| S-07 | ECA packaging and credit conversion | X | |
| S-08 | Credit-enhanced development debt (DFI) | | X |
| S-03 | Subsidy access (vendor-linked) | | X |
| S-09 | Supplier credit related supplier working capital | | X |

Only scope items where ZCF holds a Primary or Secondary role are listed. ZCF's primary domain is ECA (S-07). All European ECAs fall within scope. Fee basis is at programme level, not per-application.

## A.2 Fee Variables

Fee formulae are defined in the Agreement body (Clause 7.4). Only fee items linked to ZCF's scope are shown.

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
| F-03: Subsidy success fee | S-03 | 5% | Subsidy amount secured |

### Segment 3: Root-Curve Items (Frontier Funding Layers)

**Formula (Clause 7.4):** `Fee_i = A x sqrt(B_i)`

A is a fixed constant set per instrument. B_i is the Covered Amount per Designated Transaction. Slab waterfall for stacking across Layers A/B/C/D is in the Agreement body (Clause 7.5).

| Fee Item | Scope | Layer | A | B_i Definition |
|----------|-------|-------|---|----------------|
| F-07a: ECA packaging | S-07 | B | `[__]` | ECA Covered Amount |
| F-08: Credit-enhanced development debt (DFI) | S-08 | C | `[__]` | DFI facility Covered Amount |
| F-09: Supplier credit related supplier working capital | S-09 | D | `[__]` | Working Capital line for supplier |

F-07a is ZCF's core fee item. The A value is subject to negotiation and will be set by written amendment to this Annex. F-08 and F-09 are similarly open pending negotiation.

Renewal-decay and increase mechanics per Clause 7.6 of the Agreement apply to all Root-Curve items.

---

# ANNEX B — Designated Transaction Mandate Schedules

## Schedule B-1: Catalytic Assets — NWL, LanRED Greenfield, TWX

**Schedule Number:** B-1
**Annex Effective Date:** **[Date]**

### 1. Project Identification

| Field | Value |
|-------|-------|
| Project Name | Catalytic Assets — NWL, LanRED Greenfield, TWX |
| Project Identifier | CA-BUNDLE-01 |
| Country / Region | South Africa — Lanseria (NWL, LanRED), National (TWX) |
| Sector | Water treatment (NWL), Renewable energy (LanRED), Timber / construction (TWX) |
| Estimated Project Value | EUR 13.5m (base IIC facility) — may grow to EUR 23.5m if LanRED brownfield is added |
| Note | TWX Phase 1 (acquisition of local company) is complete. TWX Phase 2 (initial expansion) is included in this bundle. TWX Phase 3 (next expansion, Finland/Finnvera) is a separate Designated Transaction under Schedule B-2. |

### Preamble — Deal Structure and Permutations

NexusNovus has been approved for a **EUR 13.5m Invest International (IIC) facility** covering NWL, LanRED greenfield (EUR 3m solar, BESS, and substation installation), and TWX as a bundled Designated Transaction under Catalytic Assets (Pty) Ltd.

The facility requires back-to-back corporate guarantees. The guarantors cannot carry the full EUR 13.5m exposure. The intended solution is a **cross-currency swap (CCS) with Investec Bank SA** absorbing approximately EUR 4m within the NWL envelope (Layer B, Route 3). This reduces guarantor exposure to approximately **EUR 9.5m**, which is feasible.

**Primary scenario (buyer credit / DFI):**
- EUR 9.5m: IIC facility via Atradius ECA cover, backed by guarantors
- EUR 4m: Investec CCS (NWL envelope, Layer B Route 3)
- Total IIC facility: EUR 13.5m

If the primary scenario holds, the LanRED brownfield expansion (EUR 10m, also via Investec CCS bank-to-bank) becomes possible within the B-1 envelope, growing total IIC exposure to EUR 23.5m.

**Fallback scenario (supplier credit):**
If the deal does not close as a DFI / buyer credit facility — for any reason (Investec withdrawal, IIC withdrawal, or otherwise) — and the transaction proceeds instead as a supplier credit structure, ZCF's compensation remains unchanged. The fee calculation that would have applied under F-08 (DFI) applies identically to the supplier credit amount. See Fee Treatment below.

### 2. Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-08 | Credit-enhanced development debt (DFI) | S | IIC facility — Layer C; target fee base |

ZCF's scope on B-1 is limited to the DFI work stream. ECA packaging (S-07) is performed as part of this work but is not separately scoped or compensated — it collapses into F-08. No other scope items allocated.

### 3. Credit Stack Routes

Credit stack routing for B-1 is managed at programme level by NexusNovus. ZCF's role is ECA packaging and DFI conversion support, not route selection. See Preamble for route structure.

### 4. Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | `[__]` | `[__]` |
| Supporting partner(s) | ZCF | ECA packaging (Atradius) + DFI conversion support |
| Sub-Agent(s) | Per Schedule C-n | Country ECA specialists as needed (Atradius / Netherlands) |

### 5. Deliverables and Milestones

| # | Deliverable | Milestone / Due Date | Acceptance Criteria | Fee Trigger (Y/N) |
|---|------------|---------------------|--------------------|--------------------|
| 1 | `[__]` | `[__]` | `[__]` | `[__]` |
| 2 | `[__]` | `[__]` | `[__]` | `[__]` |
| 3 | `[__]` | `[__]` | `[__]` | `[__]` |

### 6. Fee Treatment

**Anti-double-count rule applies.** ECA packaging work (S-07) and DFI conversion work (S-08) collapse into a single work stream for this Designated Transaction. ZCF is compensated on the **facility amount only**, not separately on both ECA and DFI layers.

| Scenario | Fee Item | B_i (Base / Covered Amount) | Notes |
|----------|----------|-----------------------------|-------|
| Primary (DFI / buyer credit) | F-08: DFI / Layer C | IIC facility amount (EUR 13.5m-23.5) | ECA work (F-07a) is not separately compensated; it collapses into F-08 |
| Fallback (supplier credit) | F-08 calculation applies | Supplier credit facility amount | Same compensation as primary scenario; F-08 formula applied to supplier credit base instead of DFI base |

No F-07a (ECA packaging) stacking applies to this Designated Transaction. No slab waterfall across Layers B and C for this transaction.

### 7. Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | Yes |
| Scope of exclusivity (if yes) | Yes |
| Duration of exclusivity (if yes) | 3 months |

### 8. Special Conditions

1. **Bundle scope.** This schedule covers three project vehicles under Catalytic Assets (Pty) Ltd: NWL (water treatment, Lanseria), LanRED greenfield (EUR 3m solar, BESS, substation — Lanseria), and Timberworx (timber/construction — Phase 1 acquisition complete, Phase 2 initial expansion included; TWX Phase 3 is separate under Schedule B-2). ECA packaging and fee triggers apply at programme level across the bundle per Annex S.1 (captive integrator).

2. **Investec conditionality.** The Investec CCS (EUR 4m, NWL envelope) is a prerequisite for the primary scenario. If Investec participates, guarantor exposure reduces to EUR 9.5m (feasible) and the LanRED brownfield expansion (EUR 10m, within this B-1 envelope) also becomes possible, growing the IIC facility to EUR 23.5m.

3. **Scenario-independent compensation.** Whether the transaction closes as buyer credit (DFI via IIC) or supplier credit, ZCF's fee is calculated identically using the F-08 formula on the relevant facility amount. The fee label may shift but the economics do not.

`[Awaiting further input on deliverables and milestones.]`

---

## Schedule B-2: Timberworx Phase 3

**Schedule Number:** B-2
**Annex Effective Date:** **[Date]**

### 1. Project Identification

| Field | Value |
|-------|-------|
| Project Name | Timberworx Phase 3 |
| Project Identifier | TWX-PH3 |
| Country / Region | South Africa (project) / Finland (exporter / ECA) |
| Sector | Timber / construction |
| Estimated Project Value | EUR 2.5m – 5m |
| Note | Phase 1 = acquisition of local company (complete). Phase 2 = initial expansion (part of B-1 CA bundle). Phase 3 = this schedule. |

### Preamble

Timberworx Phase 3 is the next expansion stage. Technology and equipment are most likely sourced from Finland, with Finnvera as the ECA. The expected financing route is supplier credit (Layer D). This is a straightforward single-ECA transaction.

### 2. Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-07 | ECA packaging and credit conversion | P | Finnvera (Finland); integrator-led, single-country ECA |
| S-09 | Supplier credit working capital | S | Layer D — Bills of Exchange bridge enabled by ECA |

### 3. Credit Stack Routes

| Route | Applicable (Yes/No) | Notes |
|-------|---------------------|-------|
| Route 1: ECA cover | Yes | Finnvera — primary and only credit conversion route |
| Route 2: Underwriting / insurance wrap | No | |
| Route 3: Currency swap as credit instrument | No | |

### 4. Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | `[__]` | `[__]` |
| Supporting partner(s) | ZCF | ECA packaging (Finnvera) |
| Sub-Agent(s) | Per Schedule C-n | Finland ECA specialist if needed |

### 5. Deliverables and Milestones

| # | Deliverable | Milestone / Due Date | Acceptance Criteria | Fee Trigger (Y/N) |
|---|------------|---------------------|--------------------|--------------------|
| 1 | `[__]` | `[__]` | `[__]` | `[__]` |
| 2 | `[__]` | `[__]` | `[__]` | `[__]` |

### 6. Fee Treatment

Single fee item. Supplier credit is the expected route; ECA packaging is the core deliverable.

| Fee Item | B_i (Base / Covered Amount) | Notes |
|----------|-----------------------------|-------|
| F-07a: ECA packaging | EUR 2.5m – 3m (ECA Covered Amount) | Layer B; Finnvera ECA |
| F-09: Supplier credit working capital | `[__]` (Working Capital line) | Layer D; slab +0.25% on Layer D Covered Amount |

No F-08 (DFI) applies.

### 7. Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | Yes |
| Scope of exclusivity (if yes) | Yes |
| Duration of exclusivity (if yes) | 6 months |

### 8. Special Conditions

Standalone Designated Transaction, separate from B-1 (CA bundle). Single-ECA, single-country deal with clear scope boundary. Finland specialist may be engaged under Annex C if required.

`[Awaiting further input on deliverables and milestones.]`

---

## Schedule B-3: Hermetics Health

**Schedule Number:** B-3
**Annex Effective Date:** **[Date]**

### 1. Project Identification

| Field | Value |
|-------|-------|
| Project Name | Hermetics Health |
| Project Identifier | HRM-HEALTH |
| Country / Region | `[__]` (project) / Netherlands (exporter / ECA — VDH) |
| Sector | Healthcare infrastructure + energy (biogas CHP included) |
| Estimated Project Value | EUR 7m – 10m |

### Preamble

Hermetics Health is a VDH supplier credit transaction of approximately EUR 7–10m. The current scope includes biogas CHP as part of the package. Financing route is supplier credit with ECA cover. Single-ECA, single fee line.

### 2. Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-07 | ECA packaging and credit conversion | P | VDH supplier credit; integrator-led |
| S-09 | Supplier credit working capital | S | Layer D — Bills of Exchange bridge enabled by ECA |

### 3. Credit Stack Routes

| Route | Applicable (Yes/No) | Notes |
|-------|---------------------|-------|
| Route 1: ECA cover | Yes | ECA on VDH supplier credit — `[ECA agency TBD]` |
| Route 2: Underwriting / insurance wrap | No | |
| Route 3: Currency swap as credit instrument | No | |

### 4. Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | `[__]` | `[__]` |
| Supporting partner(s) | ZCF | ECA packaging |
| Sub-Agent(s) | Per Schedule C-n | Country ECA specialist if needed |

### 5. Deliverables and Milestones

| # | Deliverable | Milestone / Due Date | Acceptance Criteria | Fee Trigger (Y/N) |
|---|------------|---------------------|--------------------|--------------------|
| 1 | `[__]` | `[__]` | `[__]` | `[__]` |
| 2 | `[__]` | `[__]` | `[__]` | `[__]` |

### 6. Fee Treatment

Single fee item. Supplier credit is the financing route; ECA packaging is the core deliverable.

| Fee Item | B_i (Base / Covered Amount) | Notes |
|----------|-----------------------------|-------|
| F-07a: ECA packaging | EUR 7m – 10m (ECA Covered Amount) | Layer B; ECA on VDH supplier credit |
| F-09: Supplier credit working capital | `[__]` (Working Capital line) | Layer D; slab +0.25% on Layer D Covered Amount |

No F-08 (DFI) applies.

### 7. Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | yes |
| Scope of exclusivity (if yes) | yes |
| Duration of exclusivity (if yes) | 3 months |

### 8. Special Conditions

1. **Biogas CHP included.** Biogas CHP is included in the current VDH project scope. A separate modular biogas plant (Finland/Finnvera, lease buy-back via LanRED) is covered under Schedule B-4. The two biogas components are independently scoped and compensated.

2. **Equity conversion excluded.** Fee-to-equity conversion under Annex E is not available for Hermetics Health Designated Transactions. This applies to both B-3 and B-4.

`[Awaiting further input on ECA agency, country, deliverables, and milestones.]`

---

## Schedule B-4: Hermetics Health — Modular Biogas Plant

**Schedule Number:** B-4
**Annex Effective Date:** **[Date]**

### 1. Project Identification

| Field | Value |
|-------|-------|
| Project Name | Hermetics Health — Modular Biogas Plant |
| Project Identifier | HRM-BG |
| Country / Region | `[__]` (project) / Finland (exporter / ECA) |
| Sector | Energy / biogas |
| Estimated Project Value | 5m euro |

### Preamble

Modular biogas plant for the Hermetics Health site, with a lease buy-back option from LanRED. Equipment most likely sourced from Finland with Finnvera as ECA. This is a separate Designated Transaction from Schedule B-3 (Hermetics Health main facility), which includes biogas CHP as part of its VDH scope. The modular biogas plant here is a distinct asset with its own financing route and lease structure.

**Lease buy-back note:** Per Clause 18.3 of the Agreement, fee-to-equity conversion (Annex E) is not available for lease-based Designated Transactions. This restriction applies to this schedule.

### 2. Scope Statement

| Code | Scope Item | Class (P/S/—) | Notes |
|------|-----------|---------------|-------|
| S-07 | ECA packaging and credit conversion | P | Finnvera (Finland); integrator-led |
| S-09 | Supplier credit working capital | S | Layer D — Bills of Exchange bridge enabled by ECA |

### 3. Credit Stack Routes

| Route | Applicable (Yes/No) | Notes |
|-------|---------------------|-------|
| Route 1: ECA cover | Yes | Finnvera — primary and only credit conversion route |
| Route 2: Underwriting / insurance wrap | No | |
| Route 3: Currency swap as credit instrument | No | |

### 4. Role Assignment

| Role | Assigned To | Notes |
|------|------------|-------|
| Lead structuring partner | `[__]` | `[__]` |
| Supporting partner(s) | ZCF | ECA packaging (Finnvera) |
| Sub-Agent(s) | Per Schedule C-n | Finland ECA specialist if needed (same as B-2) |

### 5. Deliverables and Milestones

| # | Deliverable | Milestone / Due Date | Acceptance Criteria | Fee Trigger (Y/N) |
|---|------------|---------------------|--------------------|--------------------|
| 1 | `[__]` | `[__]` | `[__]` | `[__]` |
| 2 | `[__]` | `[__]` | `[__]` | `[__]` |

### 6. Fee Treatment

Single fee item. ECA packaging is the core deliverable.

| Fee Item | B_i (Base / Covered Amount) | Notes |
|----------|-----------------------------|-------|
| F-07a: ECA packaging | EUR 5m (ECA Covered Amount) | Layer B; Finnvera ECA |
| F-09: Supplier credit working capital | `[__]` (Working Capital line) | Layer D; slab +0.25% on Layer D Covered Amount |

No F-08 (DFI) applies.

### 7. Exclusivity

| Field | Value |
|-------|-------|
| Transaction-level exclusivity granted | yes |
| Scope of exclusivity (if yes) | `yes` |
| Duration of exclusivity (if yes) | 6 months |

### 8. Special Conditions

1. **Lease structure.** LanRED lease buy-back option applies. Equity conversion under Annex E is excluded per Clause 18.3 (lease-based Designated Transactions).

2. **Relationship to B-3.** B-3 (Hermetics Health, VDH) includes biogas CHP in its current scope. This B-4 covers a separate modular biogas plant with distinct sourcing (Finland/Finnvera) and financing (lease buy-back). The two are complementary but independently scoped and compensated.

3. **Finland specialist.** Finnvera specialist engagement may overlap with Schedule B-2 (TWX Phase 3). Single Sub-Agent appointment under Annex C may cover both.

`[Awaiting further input on project value, deliverables, and milestones.]`

---

# ANNEX R — Retainer Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## R.1 Activation

| Field | Value |
|-------|-------|
| Retainer activated | Yes — conditional start |
| Activation date | Conditional: The retainer shall commence only upon receipt of the first tranche of approved subsidy funds pursuant to Clause 8.3. |
| Linked Designated Transaction(s) | All |

## R.2 Retainer Amount and Cadence

| Field | Value |
|-------|-------|
| Monthly retainer amount | EUR 2,000 |
| Payment cadence | Monthly (conditional) |
| Currency | EUR |

## R.3 Conditions

| Field | Value |
|-------|-------|
| Performance conditions | Active participation in allocated Designated Transactions; maintenance of ECA submission tracker |
| Initial Subsidy fund received (per Clause 8.3) | Yes — retainer activation is conditional on first subsidy application payout |
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
- the conditional start trigger (subsidy application initiation) has not occurred within `6` months of Agreement Effective Date.

Retainer terminates automatically upon termination of the Agreement. Pro-rata treatment applies for partial periods.

---

# ANNEX E — Equity Conversion Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## E.1 Activation

| Field | Value |
|-------|-------|
| Equity conversion activated | Yes |
| Linked Designated Transaction(s) | B-1 (Catalytic Assets) and B-2 (TWX Phase 3) only |
| Excluded Designated Transaction(s) | B-3 (Hermetics Health) — equity conversion not available; B-4 (Hermetics Biogas) — lease-based, excluded per Clause 18.3 |

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
| Tag-along / drag-along | Standard |

## E.6 Conditions and Limitations

1. Conversion does not discharge any other obligation under the Agreement.
2. Fees converted to equity are no longer payable in cash and are not subject to retainer offset under Annex R.
3. **Lease Exclusion.** Fee-to-equity conversion is not available for lease-based Designated Transactions, per Clause 18.3 of the Agreement. This restriction cannot be overridden.
4. NexusNovus retains the right to refuse conversion if it would breach applicable law, governance requirements, or third-party obligations.
5. **Hermetics Health exclusion.** Fee-to-equity conversion is not available for any Hermetics Health Designated Transaction (B-3 and B-4). B-4 is additionally excluded as a lease-based transaction per Clause 18.3.

---

# ANNEX S — Specials / Project-Specific Structures

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## S.1 — Captive ECA Integrator

**Linked Designated Transaction(s):** All (framework-level special)

### Special Terms

ZCF shall develop and operate a captive integrator capability for repeatable ECA packaging across the NexusNovus portfolio. The integrator handles ECA applications on behalf of project vehicles, centralising method, quality, and country-specialist coordination under one platform.

| Field | Value |
|-------|-------|
| Structure | Company-captive or NexusNovus-controlled entity (Integrator per Agreement definition) |
| ZCF's role | Build, operate, and maintain the integrator platform; deploy country ECA specialists under central method |
| NexusNovus role | Governance, approval of specialist appointments, quality standards, and submission sign-off |
| Scope | All European ECAs; scope may extend to non-European ECAs by written amendment |
| Programme-level | ZCF's ECA fee (F-07a) is earned at programme level, not per individual ECA application within a Designated Transaction |
| Specialist costs | Country ECA specialists are engaged as Sub-Agents under Annex C below; costs are ZCF's responsibility unless otherwise agreed |

### Scope of Override

| Provision Overridden | Nature of Override |
|---------------------|-------------------|
| Clause 4.4(g) (ECA packaging) | ZCF operates through a captive integrator structure rather than ad-hoc ECA advisory |

## S.2 — Pan-European Banking Network Expansion

**Linked Designated Transaction(s):** All (framework-level special)

### Special Terms

ZCF shall leverage and expand his existing European banking network to support Layer C (Follow-On Liquidity) placement. This is a secondary scope activity (S-08) that complements the primary ECA packaging role.

| Field | Value |
|-------|-------|
| Purpose | Identify and engage EU commercial banks, DFIs, and local banks for debt placement on ECA-backed Designated Transactions |
| Scope | Pan-European; initial focus on `[__]` (specify priority countries/banks) |
| Deliverable | Banking network map with relationship status, appetite assessment, and conversion pipeline per Designated Transaction |
| Fee basis | Standard F-08 (DFI/Layer C) per Annex A — no special fee treatment |

### Scope of Override

No provision overridden. This is a description of ZCF's secondary scope execution approach for S-08.

---

# ANNEX C — Sub-Agent Terms

**Annex Version:** v1.0
**Annex Effective Date:** **[Date]**

## Framework Sub-Agent Authorization

ZCF is authorized to engage country ECA specialists as Sub-Agents, subject to prior written NexusNovus approval per Clause 13. All specialists operate under the central ECA method established through the captive integrator (Annex S.1). Individual engagements are documented as numbered schedules (Schedule C-1, C-2, ...) below.

## Sub-Agent Economics (applies to all schedules)

| Field | Value |
|-------|-------|
| Fee basis | Per-assignment or retainer — to be agreed per specialist engagement |
| Payment source | ZCF pays Sub-Agents directly |
| Offset against ZCF's fees | No — Sub-Agent costs are ZCF's responsibility |

Payment-flow transparency: ZCF shall disclose all Sub-Agent economics to NexusNovus. No undisclosed pass-through arrangements are permitted.

## Compliance and Central Method (applies to all schedules)

Sub-Agents shall:

- comply with the same compliance, confidentiality, and conduct obligations as ZCF under the Agreement (Clauses 21 and 22);
- operate under the central ECA method and quality standards established by the integrator (Annex S.1);
- report through ZCF to NexusNovus on a cadence defined per Designated Transaction.

ZCF is responsible for ensuring Sub-Agent compliance and quality.

## Reporting (applies to all schedules)

| Field | Value |
|-------|-------|
| Reports to | ZCF (primary), NexusNovus (copy) |
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

For and on behalf of **Zen Customer Finance B.V.**

Name: ____________________
Title: ____________________
Date: _____________________
Signature: ________________
