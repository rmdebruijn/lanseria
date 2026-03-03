# Memo: Living UI — Template-Driven, Zero-Literal Presentation Layer

**Date:** 2026-02-27
**Author:** Rutger de Bruijn / Claude (Opus 4.6)
**Status:** Draft
**Companion:** `memo_global_engine.md` (engine architecture)

---

## 1. Problem

The current UI is a 20,000-line monolith that mixes computation with presentation. Numbers, names, dates, and definitions are hardcoded throughout — in Python code, markdown text, SVG diagrams, and metric cards. This creates:

- **Data drift**: a name changes in one config but stays stale in three templates
- **Audit failure**: "where does this EUR 13.6m come from?" has no traceable answer
- **Security leakage**: hiding a tab doesn't prevent data from being computed and loaded
- **Duplication**: every new project requires copying and editing UI code
- **Literal creep**: developers embed numbers in text because there's no enforcement mechanism

## 2. Design Principles

### 2.1 Zero Literals in Presentation

No number, name, date, or defined term appears as a hardcoded value in any template, markdown file, SVG, or metric card. Every displayable value is a **reference** resolved at render time from one of two sources:

1. **Engine DataFrames** — computed, frozen, indexed by canonical period
2. **Registries** — static lookup tables for names, definitions, labels, milestones

If it's a number, it comes from a DataFrame. If it's a name, it comes from a registry. If it's a date, it comes from the time spine or a milestone registry. No exceptions.

### 2.2 Templates, Not Pages

Every tab in the UI is a **template** that receives data and renders it. Templates exist at three levels:

| Level | Example | Reuse |
|-------|---------|-------|
| Global | P&L, Cash Flow, Balance Sheet, Task List | Every project, every entity |
| Domain | LCOW analysis (water), PPA analysis (solar) | Every project of that asset class |
| Project | Custom overrides or extensions | One project only (rare) |

A domain template is just a global template that was extended once and proved reusable. The template hierarchy grows organically: write it once for one project, promote it when a second project needs it.

### 2.3 Authorization Gates Loading, Not Display

When a user logs in with access to projects 5, 6, 7:

- The engine computes **only** projects 5, 6, 7
- DataFrames for projects 1-4 are **never in memory**
- The sidebar shows **only** projects 5, 6, 7
- Templates render **only** from DataFrames in scope

There is no client-side hiding. The data doesn't exist in the session. You cannot leak what was never loaded.

Within a project, entity-level access works the same way. If a user can see NWL but not LanRED, LanRED's DataFrames never reach the template layer.

### 2.4 Registries as Source of Truth

Static reference data lives in registries — JSON files with stable IDs:

```
registries/
  entities.json       — id, display_name, legal_name, short_name, reg_number
  parties.json        — id, display_name, role, jurisdiction
  milestones.json     — id, label, period_index, month
  fee_types.json      — id, label, category
  unit_labels.json    — id, symbol, display_name, plural
```

Templates reference by ID:

```
"The {entities.nwl.display_name} facility of {facility_sr_df.amount:eur}
 is provided by {parties.invest_int.display_name}"
```

renders to:

```
"The NWL facility of EUR 13,597,304 is provided by Invest International"
```

Change a name in the registry, every template updates. Zero drift.

### 2.5 Cross-Project Views

Users with multi-project access get portfolio-level views using the **same templates** with wider scope:

- **Combined tasks**: pulls from multiple project databases, one table, sortable/filterable
- **Portfolio dashboard**: headline metrics from each project's frozen DataFrames, side by side
- **Cross-project conditions**: all unsatisfied CPs across the portfolio

The template doesn't change. It renders whatever's in scope. Authorization defines the scope.

### 2.6 Lint Enforcement

A static analysis pass (pre-commit hook or CI) scans all presentation code for violations:

| Check | Violation | Fix |
|-------|-----------|-----|
| Number in text | `"14 repayment periods"` | `"{facility.repayments} repayment periods"` |
| Name in text | `"Smart City Lanseria"` | `"{entities.sclca.display_name}"` |
| Number in SVG | `<text>EUR 8.5M</text>` | `<text>{exposure.final:eur_m}</text>` |
| Date in markdown | `"COD: Month 18"` | `"COD: {milestones.cod.display}"` |
| Currency without unit | `revenue = 2_500_000` | `revenue = Q(2_500_000, "ZAR")` |

No hardcoded literals pass through to production.

## 3. Adding a New Project

1. Create `config/project_new/` — periods, financing, operations, structure
2. Register in `projects.json`
3. Assign user access
4. Done

No code changes. The engine computes, templates render, authorization gates. The same P&L tab, CF tab, waterfall tab, task list — all work. If the project needs a domain-specific tab that doesn't exist yet, write one template, register it. It's available for all future projects of that type.

## 4. Architecture Summary

```
Engine (computes, freezes DataFrames)          ← no UI knowledge
  │
Registries (names, labels, definitions)        ← no computation
  │
Authorization (user → projects → entities)     ← gates what gets loaded
  │
Templates (global → domain → project)          ← reads DataFrames + registries
  │
Lint (enforces zero literals)                  ← catches violations before deploy
  │
UI (renders templates)                         ← thin wrapper, zero logic
```

Each layer has one job. No layer reaches into another's responsibility.

## 5. What This Enables

- **New project**: config folder + access grant. Minutes, not weeks.
- **New asset class**: one domain template, reusable forever.
- **Audit query**: every displayed value traces to a DataFrame cell or registry entry.
- **Name change**: one registry edit, zero code changes.
- **Security review**: no data in session that the user shouldn't see, by construction.
- **AI integration**: an agent can query any DataFrame directly — same data the UI shows, instant.

---

*Next step: research best practices for template-driven financial UIs, registry patterns, and zero-literal enforcement in data-heavy applications.*
