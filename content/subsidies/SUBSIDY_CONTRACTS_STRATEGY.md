# Contract A + B — Mechanics and Separation Logic

## How The Two Contracts Work and Why They Are Independent

---

### Overview

NexusNovus uses two vendor-facing contracts for subsidy-linked project development. They are **legally and financially independent** — this is deliberate architecture, not a technicality.

| | Contract A | Contract B |
|---|---|---|
| **Title** | Subsidy Execution & Certification | Project Development, Sub-Scope & ROFR |
| **Audience** | Public — visible to subsidy authorities | Private — not shown to authorities |
| **Parties** | Vendor + Subsidy Agent + NexusNovus | Vendor + Promoter + NexusNovus |
| **Purpose** | Govern the subsidy application process | Vendor invests BD budget for ROFR |
| **Money flow** | Subsidy → Vendor (minus 10% fees) | Vendor → NexusNovus (BD allocation) |
| **NexusNovus role** | Project coordinator (does not apply for or receive subsidy) | Scope designer, budget controller |

---

### Contract A — Subsidy Execution & Certification Agreement

**What happens:**
1. The vendor is the formal applicant and recipient of the subsidy
2. A Subsidy Agent (appointed by NexusNovus) prepares, submits, and administers the application
3. The subsidy authority awards the grant — money lands in the vendor's account
4. 10% is deducted: Subsidy Agent commission + NexusNovus admin/success fee
5. The **Net Available Amount** stays with the vendor
6. An **Award Certificate** confirms amounts; an **Adjustment Certificate** handles downward revisions

**What Contract A does NOT do:**
- It does not direct subsidy money to NexusNovus (beyond the 10% fee)
- It does not fund the Development Fund
- It does not create any obligation for the vendor to spend subsidy proceeds in any particular way
- The vendor receives subsidy money. Contract A is complete.

**The Subsidy Agent Fee has priority** — paid first from each tranche, before any other distribution.

---

### Contract B — Project Development, Sub-Scope & Right of First Refusal

**What happens:**
1. The vendor — as an independent commercial decision — allocates a **business development budget** to NexusNovus
2. In exchange, the vendor receives a **Right of First Refusal** within their Technology Class
3. NexusNovus designs the scope and controls the allocation:
   - **Promoter retainer** — binds the local promoter/specialist to the project
   - **Specialists** — feasibility studies, engineering, environmental, legal
   - **Assets** — equipment or IP acquired for the project (e.g. cloud hardware, panel equipment)
   - **Buffer** — flexible reserve for NexusNovus to deploy as needed
   - **Vendor scope** — work allocated back to the vendor themselves (Sub-Scope deliverables)
4. The budget is **non-refundable** once scope commences (irrevocability clause)
5. ROFR is conditional, valid for 3 years, permits matching competing offers

**What Contract B does NOT do:**
- It does not reference the subsidy or Contract A
- It does not claim any portion of subsidy proceeds
- The vendor's BD budget is their own money — a commercial investment in project positioning

---

### Why They Are Separate

**For subsidy authorities:** Contract A is a clean subsidy execution agreement. Vendor applies, vendor receives. 10% administration is standard market practice. There are no visible side-arrangements, no commercial quid pro quos, no ROFR mechanics. Authorities see exactly what they should see.

**For the vendor:** Two things happen in sequence but independently. They receive a subsidy (Contract A) — this puts cash in their hands. They then make a commercial decision to invest BD budget into project development (Contract B) — this positions them for technology selection. Both are rational. Neither depends on the other.

**For NexusNovus:** The separation means NexusNovus never touches subsidy money. The vendor receives the subsidy and keeps it. The vendor then — separately — commits their own BD budget. That the subsidy made the vendor liquid is a consequence of good positioning, not a contractual linkage.

---

### The Activation Event — Timing Protection, Not Financial Link

Contract A contains a **standstill mechanism**: until the subsidy is formally awarded (the "Business Development Activation Event"), execution of BD budget obligations under Contract B is frozen. Once the authority awards, the standstill lifts automatically.

This is a **timing protection** for the vendor:
- Not asked to commit BD budget before knowing if subsidies land
- Once confirmed, the commitment is irrevocable — no withdrawal citing compliance, subsidies, or other reasons
- NexusNovus gets certainty of execution; the vendor gets downside protection

The standstill is the only thread connecting A and B. It does not create a flow of funds from A to B.

---

### Special Cases

**Timberworx (Philip):** Philip is technically the exporter in the subsidy structure but will not supply equipment himself. His ROFR under Contract B converts into equity in Timberworx at pre-defined minority stake levels — a cross-equity arrangement in lieu of supply rights.

**Asset acquisition:** Where a subsidy relates to infrastructure NexusNovus intends to control (e.g. LeafCloud servers for Cradle Cloud), the Contract B BD budget may fund asset acquisition. The asset sits within the project SPV or NexusNovus-controlled entity.

---

### Contract Status

These contracts are **v.2, vetted by ASA Law**. Currently under review — content may change.

Remaining work per vendor engagement:
- **Schedule 1** (Contract A) — Target Subsidy Amount per programme
- **Annex A** (Contract B) — Development Budget Note: scope, allocation, payment mechanics
- **Annex 1** (Contract A) — Award/Adjustment Certificate: populated post-award
