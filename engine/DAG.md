# DAG — Directed Acyclic Graph in the Big Loop

## Why the DAG Matters

The entire financial model is a **DAG** — a directed acyclic graph. Every number
depends on other numbers, and those dependencies NEVER form a circle. This is
what makes the One Big Loop possible: single pass, zero iterations, zero
convergence.

If you introduce a cycle (A depends on B, B depends on A), the model breaks.
You'd need iterative convergence, and that's exactly the broken pattern we
replaced.

## Two Dimensions of the DAG

### 1. Cross-Period (Sequential, Time Axis)

Period N's **Closing balance** becomes Period N+1's **Opening balance**.
This is a forward-only chain:

```
P1.Closing → P2.Opening → P2.Closing → P3.Opening → ...
```

No period ever looks backward. Acceleration at P4 reduces P4's Closing, which
lowers P5's Opening, which lowers P5's Interest — but P4 is already final by
then. Single pass handles this naturally.

### 2. Intra-Period (Waterfall Cascade, Within a Single Period)

Within one period, the computation flows top-down:

```
Opening (fixed, from previous period)
  ↓
Interest = Opening × rate / 2        ← deterministic
Principal = Opening / N_remaining     ← deterministic
  ↓
EBITDA (from ops model, exogenous)
  ↓
Depreciation (from asset base, exogenous)
  ↓
PBT = EBITDA - Depr - Interest + FD_income
Tax = calc_tax(PBT, rate, loss_pool)
PAT = PBT - Tax
  ↓
Waterfall allocation:
  Cash available = EBITDA - Tax
  → Pay debt service (Interest + Principal)
  → Fill reserves (Ops reserve, DSRA)
  → Acceleration (surplus → reduce balance)
  → Entity FD (remainder)
  ↓
Closing = Opening - Principal - Acceleration   ← feeds next period
```

No step within the period depends on a later step. Pure DAG.

## Why This Eliminates Convergence

The old code ran 5 convergence iterations because it batch-built the facility
schedule first (guessing acceleration), then ran the waterfall (which computed
different acceleration), then rebuilt the facility (now with "correct"
acceleration), and repeated until the numbers stabilised.

The problem: the facility schedule and waterfall output were ALWAYS from
different iterations. They never agreed.

The One Big Loop computes everything for period N before moving to N+1:
1. Facility gives Interest and Principal (from current Opening)
2. P&L uses that Interest
3. Waterfall allocates cash and decides Acceleration
4. Facility finalizes: applies Acceleration, updates Closing

Within this single period, there is no circularity. Opening is fixed.
Everything flows forward.

## The Formula Roster and DAG Ordering

Each formula in the roster has **dependencies** — other formulas it reads.
The DAG determines execution order:

```json
{
  "revenue":    {"formula": "q * p",               "depends_on": ["volume", "price"]},
  "opex":       {"formula": "om + power + rent",   "depends_on": ["om_cost", "power_cost", "rent_cost"]},
  "ebitda":     {"formula": "revenue - opex",      "depends_on": ["revenue", "opex"]},
  "interest":   {"formula": "opening * rate / 2",  "depends_on": ["opening", "rate"]},
  "pbt":        {"formula": "ebit - ie + ii",      "depends_on": ["ebit", "interest", "fd_income"]}
}
```

A topological sort of this graph gives the execution order. If entity NWL
overrides `revenue` with a different formula that has different dependencies,
the DAG re-sorts automatically. The loop doesn't care WHAT the formula is —
it only cares that dependencies are resolved before the formula runs.

## Entity Overrides Don't Break the DAG

Global formula: `revenue = q * p`
NWL override:   `revenue = q * p * utilization * seasonal_factor`

The override adds dependencies (`utilization`, `seasonal_factor`) but does NOT
create a backward edge. The DAG grows wider (more inputs) but stays acyclic.

**The only rule**: an entity override CANNOT make formula A depend on formula B
if B already depends on A (directly or transitively). That would create a cycle.
The roster loader must validate this at load time.

## Inter-Company: The One Exception

Inter-company flows (NWL lends overdraft to LanRED) are technically a cycle:
- NWL surplus → OD lent → LanRED cash → LanRED waterfall
- LanRED deficit → needs OD → NWL must know how much to lend

We handle this with **IC correction passes** (Phase 5). The main entity loops
run independently (no IC). Then small, targeted IC patches fix the specific
cross-entity items. This is NOT a cycle in the DAG — it's a second forward
pass on a small subset of nodes.

## Practical Implications

1. **No cell can reference itself** — ever. Period.
2. **No formula can depend on its own output** — even indirectly.
3. **The formula roster must be validated** at load time: topological sort must
   succeed. If it fails, there's a cycle, and the config is rejected.
4. **UI click-to-trace** follows the DAG edges backward: from any number, walk
   the dependency chain to see exactly which inputs produced it.
5. **Parallel execution**: independent branches of the DAG can run in parallel.
   Revenue and Interest don't depend on each other — they can compute
   simultaneously. The DAG makes this explicit.
