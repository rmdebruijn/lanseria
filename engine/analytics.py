"""Post-loop analytics — computed on COMPLETED loop output.

These functions are READ-ONLY on the loop result. They never feed back
into the loop (no DAG cycle). They're computed in a post-loop pass and
attached to the result for views to consume.

All functions operate on lists/dicts from EntityResult or LoopResult.
No pandas dependency (views can wrap results in DataFrames themselves).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ── DSCR (Debt Service Coverage Ratio) ──────────────────────────


def dscr_series(annual: list[dict]) -> list[float | None]:
    """DSCR per year: cf_ops / cf_ds.

    Returns None for years with zero debt service.
    """
    return [
        a["cf_ops"] / a["cf_ds"] if a.get("cf_ds", 0) > 0 else None
        for a in annual
    ]


def dscr_min(annual: list[dict]) -> float:
    """Minimum DSCR across all years with positive debt service."""
    vals = [v for v in dscr_series(annual) if v is not None]
    return min(vals) if vals else 0.0


def dscr_avg(annual: list[dict]) -> float:
    """Average DSCR across all years with positive debt service."""
    vals = [v for v in dscr_series(annual) if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


# ── IRR (Internal Rate of Return) ───────────────────────────────


def _npv(rate: float, cashflows: list[float]) -> float:
    """Net present value of a cash flow series at a given rate."""
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))


def _irr(cashflows: list[float], guess: float = 0.10, tol: float = 1e-8, max_iter: int = 100) -> float | None:
    """IRR via Newton-Raphson.

    Returns None if no convergence (e.g., all-positive or all-negative flows).
    """
    # Quick check: need at least one sign change
    signs = set(1 if cf > 0 else -1 if cf < 0 else 0 for cf in cashflows)
    if len(signs - {0}) < 2:
        return None

    rate = guess
    for _ in range(max_iter):
        npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))
        # Derivative: d(NPV)/d(rate) = sum(-i * cf / (1+rate)^(i+1))
        dnpv = sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(cashflows))
        if abs(dnpv) < 1e-15:
            return None
        rate_new = rate - npv / dnpv
        if abs(rate_new - rate) < tol:
            return rate_new
        rate = rate_new

    return None  # Did not converge


def project_irr(annual: list[dict]) -> float | None:
    """Project IRR from annual cash flows.

    CF = [-capex, ..., cf_ops, ..., terminal_value_if_any]
    Uses cf_capex (negative) and cf_ops (positive) from build_annual().
    """
    cashflows = []
    for a in annual:
        capex = -a.get("cf_capex", 0)  # capex is positive in build_annual
        ops_cf = a.get("cf_ops", 0)
        # Year 0 (construction) typically has large capex, no ops
        cf = ops_cf + capex if capex < 0 else ops_cf
        cashflows.append(cf)
    return _irr(cashflows)


def equity_irr(annual: list[dict]) -> float | None:
    """Equity IRR — cash flows to equity holders.

    CF = equity_invested + (cf_after_debt_service - reserve_movements)
    """
    cashflows = []
    for a in annual:
        equity_in = -a.get("cf_equity", 0)  # equity is a cash outflow
        after_ds = a.get("cf_after_debt_service", 0)
        grants_in = a.get("cf_grants", 0)
        cf = equity_in + after_ds + grants_in
        cashflows.append(cf)
    return _irr(cashflows)


# ── LLCR (Loan Life Coverage Ratio) ─────────────────────────────


def llcr_series(
    annual: list[dict],
    discount_rate: float,
) -> list[float | None]:
    """LLCR per year: NPV(remaining CFADS) / outstanding debt.

    discount_rate: annual discount rate (e.g. 0.052 for senior IC rate).
    Returns None for years with zero debt.
    """
    n = len(annual)
    cfads = [a.get("cf_ops", 0) for a in annual]
    debt = [a.get("bs_debt", 0) for a in annual]

    result: list[float | None] = []
    for yi in range(n):
        if debt[yi] <= 0.01:
            result.append(None)
            continue
        # NPV of remaining CFADS from yi+1 to end
        remaining_cfads = cfads[yi:]
        npv = sum(
            cf / (1 + discount_rate) ** (i + 1)
            for i, cf in enumerate(remaining_cfads)
        )
        result.append(npv / debt[yi] if debt[yi] > 0 else None)

    return result


# ── PLCR (Project Life Coverage Ratio) ──────────────────────────


def plcr_series(
    annual: list[dict],
    discount_rate: float,
) -> list[float | None]:
    """PLCR per year: NPV(CFADS to project end) / outstanding debt.

    Similar to LLCR but always discounts to project end (not loan life end).
    """
    # For this model, PLCR = LLCR (single loan tenor = project life)
    return llcr_series(annual, discount_rate)


# ── Summary Metrics ─────────────────────────────────────────────


@dataclass
class EntityMetrics:
    """Key metrics extracted from a completed entity run.

    Used by sensitivity sweeps — each sweep run extracts these metrics
    and stores them as a row in a DataFrame.
    """
    entity_key: str
    total_revenue: float
    total_ebitda: float
    total_pat: float
    ebitda_margin: float
    net_margin: float
    dscr_min: float
    dscr_avg: float
    project_irr: float | None
    equity_irr: float | None
    llcr_min: float | None

    def to_dict(self) -> dict:
        return {
            "entity": self.entity_key,
            "total_revenue": self.total_revenue,
            "total_ebitda": self.total_ebitda,
            "total_pat": self.total_pat,
            "ebitda_margin": self.ebitda_margin,
            "net_margin": self.net_margin,
            "dscr_min": self.dscr_min,
            "dscr_avg": self.dscr_avg,
            "project_irr": self.project_irr,
            "equity_irr": self.equity_irr,
            "llcr_min": self.llcr_min,
        }


def extract_metrics(
    entity_key: str,
    annual: list[dict],
    discount_rate: float = 0.052,
) -> EntityMetrics:
    """Extract all key metrics from a completed entity's annual rows."""
    total_rev = sum(a.get("rev_total", 0) for a in annual)
    total_ebitda = sum(a.get("ebitda", 0) for a in annual)
    total_pat_val = sum(a.get("pat", 0) for a in annual)

    llcr_vals = [v for v in llcr_series(annual, discount_rate) if v is not None]

    return EntityMetrics(
        entity_key=entity_key,
        total_revenue=total_rev,
        total_ebitda=total_ebitda,
        total_pat=total_pat_val,
        ebitda_margin=(total_ebitda / total_rev * 100) if total_rev else 0.0,
        net_margin=(total_pat_val / total_rev * 100) if total_rev else 0.0,
        dscr_min=dscr_min(annual),
        dscr_avg=dscr_avg(annual),
        project_irr=project_irr(annual),
        equity_irr=equity_irr(annual),
        llcr_min=min(llcr_vals) if llcr_vals else None,
    )
