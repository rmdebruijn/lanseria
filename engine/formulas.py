"""Generic financial formulas — stateless, no entity knowledge."""

from __future__ import annotations


def calc_interest(balance: float, annual_rate: float) -> float:
    """Semi-annual interest on a balance. Returns 0 if balance <= 0."""
    if balance <= 0.01:
        return 0.0
    return balance * annual_rate / 2.0


def calc_idc(opening: float, annual_rate: float) -> float:
    """Interest during construction (capitalised). Same formula as interest."""
    return calc_interest(opening, annual_rate)


def calc_flat_principal(balance: float, remaining_periods: int) -> float:
    """P_constant: equal principal repayment over remaining periods."""
    if remaining_periods <= 0 or balance <= 0.01:
        return 0.0
    return balance / remaining_periods


def calc_s12c_depreciation(depreciable_base: float, year_index: int) -> float:
    """Section 12C accelerated depreciation (40/20/20/20).

    year_index: 0-based annual index. Y0=40%, Y1=20%, Y2=20%, Y3=20%.
    Returns ANNUAL depreciation amount. Caller halves for semi-annual.
    """
    pcts = {0: 0.40, 1: 0.20, 2: 0.20, 3: 0.20}
    return depreciable_base * pcts.get(year_index, 0.0)


def calc_tax(pbt: float, rate: float, loss_pool: float) -> tuple[float, float]:
    """Corporate tax with loss carry-forward.

    Args:
        pbt: Profit before tax (this period)
        rate: Corporate tax rate (e.g. 0.27)
        loss_pool: Accumulated assessed loss (negative = losses available)

    Returns:
        (tax_amount, new_loss_pool)
    """
    taxable = pbt + loss_pool
    if taxable > 0:
        return taxable * rate, 0.0
    else:
        return 0.0, taxable


def calc_pbt(ebit: float, interest_expense: float, fd_income: float) -> float:
    """Profit before tax."""
    return ebit - interest_expense + fd_income


def calc_ebitda(revenue: float, opex: float) -> float:
    """Earnings before interest, tax, depreciation, amortisation."""
    return revenue - opex
