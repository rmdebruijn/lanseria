"""Reserve account assets — interest accrual, targets, and lifecycle schedules.

Reserves are financial assets held by the entity. Each reserve:
- Has an opening balance (carried from prior period's closing)
- Computes its own interest accrual (opening x rate)
- Knows its own target / fill requirement
- Reports the gap for the waterfall to allocate into

The waterfall ONLY allocates cash — it never computes interest or targets.

Reserve asset classes (for the One Big Loop):
    OpsReserve:     Working capital buffer (target = opex x coverage)
    OpcoDSRA:       Debt service reserve (target = next Sr P+I, capped at Sr balance)
    MezzDivFD:      Mezz dividend fixed deposit (accrues toward dividend payout)
    EntityFD:       Entity-level fixed deposit (post-debt surplus accumulator)
    ICOverdraft:    Intercompany overdraft (NWL lends to LanRED on deficit)

Schedule builder (for post-hoc verification):
    build_reserve_schedule():    Reconstructs lifecycle from waterfall output
    extract_reserve_vectors():   Extracts fill/release/interest/closing from waterfall
    verify_reserve_balance():    Cross-checks waterfall accumulators against schedule
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Reserve asset classes (for One Big Loop) ──────────────────────


@dataclass
class ReserveAccrual:
    """Output of a reserve's period-start accrual step."""
    opening: float
    interest: float
    balance_after_interest: float  # = opening + interest
    target: float
    gap: float                    # = max(target - balance_after_interest, 0)
    excess: float                 # = max(balance_after_interest - target, 0)


class OpsReserve:
    """Operating expense reserve — buffers next-period opex.

    Target = opex x coverage_pct (look-ahead to next period if current ~ 0).
    Interest accrues at fd_rate on opening balance each period.
    """

    def __init__(self, fd_rate_annual: float, coverage_pct: float = 1.0):
        self.fd_rate_semi = fd_rate_annual / 2.0
        self.coverage_pct = coverage_pct
        self.balance = 0.0

    def accrue(self, current_opex: float, next_opex: float = 0.0) -> ReserveAccrual:
        """Compute interest and target for current period.

        Args:
            current_opex: This period's opex (for target computation).
            next_opex: Next period's opex (used if current_opex ~ 0).
        """
        opening = self.balance
        interest = opening * self.fd_rate_semi
        self.balance += interest

        if current_opex < 0.01 and next_opex > 0:
            target = next_opex * self.coverage_pct
        else:
            target = current_opex * self.coverage_pct

        gap = max(target - self.balance, 0.0)
        excess = max(self.balance - target, 0.0) if self.balance > target else 0.0

        return ReserveAccrual(
            opening=opening,
            interest=interest,
            balance_after_interest=self.balance,
            target=target,
            gap=gap,
            excess=excess,
        )

    def fill(self, amount: float) -> float:
        """Deposit cash into reserve. Returns amount actually deposited."""
        deposited = max(amount, 0.0)
        self.balance += deposited
        return deposited


class OpcoDSRA:
    """Debt service reserve account — covers next senior P+I.

    Target = min(next_sr_pi, sr_balance). When sr_balance ~ 0, target = 0.
    Interest accrues at fd_rate on opening balance (DSRA is a EUR FD).
    """

    def __init__(self, fd_rate_annual: float = 0.035):
        self.fd_rate_semi = fd_rate_annual / 2.0
        self.balance = 0.0
        self.target = 0.0

    def accrue(self) -> ReserveAccrual:
        """Compute interest on opening balance and gap/excess against target."""
        opening = self.balance
        interest = opening * self.fd_rate_semi
        self.balance += interest
        gap = max(self.target - self.balance, 0.0)
        excess = max(self.balance - self.target, 0.0) if self.balance > self.target else 0.0

        return ReserveAccrual(
            opening=opening,
            interest=interest,
            balance_after_interest=self.balance,
            target=self.target,
            gap=gap,
            excess=excess,
        )

    def fill(self, amount: float) -> float:
        """Deposit cash into DSRA."""
        deposited = max(amount, 0.0)
        self.balance += deposited
        return deposited

    def release(self, amount: float) -> float:
        """Release excess from DSRA."""
        released = min(amount, self.balance)
        self.balance -= released
        return released

    def set_target(self, next_sr_pi: float, sr_balance: float):
        """Update target for next period (called after facility finalize)."""
        self.target = min(next_sr_pi, sr_balance) if sr_balance > 0.01 else 0.0

    @property
    def funded(self) -> bool:
        """Whether DSRA meets its target (within EUR 0.01 tolerance)."""
        return self.balance >= self.target - 0.01 or self.target < 0.01


class MezzDivFD:
    """Mezz dividend fixed deposit — accumulates toward dividend payout.

    Interest accrues at fd_rate on opening balance.
    Liability accrues at mz_div_rate on opening Mezz IC balance.
    When Mezz IC is fully repaid, payout = FD balance.
    """

    def __init__(self, fd_rate_annual: float, mz_div_rate_annual: float):
        self.fd_rate_semi = fd_rate_annual / 2.0
        self.mz_div_rate_semi = mz_div_rate_annual / 2.0
        self.balance = 0.0
        self.liability = 0.0
        self.payout_done = False
        self._last_accrual = 0.0

    def accrue(self, mz_ic_opening: float) -> ReserveAccrual:
        """Compute FD interest and dividend liability accrual.

        Args:
            mz_ic_opening: Mezz IC balance at start of period (for liability accrual).

        Returns:
            ReserveAccrual with target = liability (gap = liability - FD balance).
        """
        opening = self.balance
        interest = opening * self.fd_rate_semi
        self.balance += interest

        self._last_accrual = 0.0
        if not self.payout_done and mz_ic_opening > 0.01:
            self._last_accrual = mz_ic_opening * self.mz_div_rate_semi
            self.liability += self._last_accrual

        gap = max(self.liability - self.balance, 0.0)

        return ReserveAccrual(
            opening=opening,
            interest=interest,
            balance_after_interest=self.balance,
            target=self.liability,
            gap=gap,
            excess=0.0,
        )

    @property
    def div_accrual(self) -> float:
        """Last liability accrual amount (for output reporting)."""
        return self._last_accrual

    def should_payout(self, mz_ic_bal: float) -> bool:
        """Check if dividend payout is triggered (Mezz IC fully repaid)."""
        return (not self.payout_done
                and mz_ic_bal <= 0.01
                and self.liability > 0.01)

    def payout(self) -> float:
        """Execute payout: return FD balance, reset both FD and liability."""
        amount = self.balance
        self.balance = 0.0
        self.liability = 0.0
        self.payout_done = True
        return amount

    def fill(self, amount: float) -> float:
        """Deposit cash into mezz div FD."""
        deposited = max(amount, 0.0)
        self.balance += deposited
        return deposited


class EntityFD:
    """Entity-level fixed deposit — post-debt surplus accumulator.

    Only receives cash when ALL debt obligations = 0.
    Interest accrues at fd_rate on opening balance.
    """

    def __init__(self, fd_rate_annual: float):
        self.fd_rate_semi = fd_rate_annual / 2.0
        self.balance = 0.0

    def accrue(self) -> ReserveAccrual:
        """Compute interest on opening balance."""
        opening = self.balance
        interest = opening * self.fd_rate_semi
        self.balance += interest

        return ReserveAccrual(
            opening=opening,
            interest=interest,
            balance_after_interest=self.balance,
            target=0.0,
            gap=0.0,
            excess=0.0,
        )

    def fill(self, amount: float) -> float:
        """Deposit surplus cash into entity FD."""
        deposited = max(amount, 0.0)
        self.balance += deposited
        return deposited

    def withdraw(self, amount: float) -> float:
        """Withdraw from entity FD (e.g. dividends)."""
        withdrawn = min(amount, self.balance)
        self.balance -= withdrawn
        return withdrawn


class ICOverdraft:
    """Intercompany overdraft facility — NWL lends to LanRED on cash deficit.

    The IC overdraft is a single shared balance representing the outstanding
    amount that NWL has lent to LanRED. It is an ASSET from NWL's perspective
    (receivable) and a LIABILITY from LanRED's perspective (payable).

    Interest accrues at ic_rate on the opening balance each semi-annual period.
    Interest compounds (adds to the outstanding balance), increasing what
    LanRED owes and what NWL is owed.

    Lifecycle within a single waterfall period:
        1. accrue()  — compute interest on opening balance, add to balance
        2. lend()    — NWL lends new amount (increases balance)
           receive() — LanRED receives same amount (increases balance)
        3. repay()   — LanRED repays from surplus (decreases balance)

    The waterfall calls lend() on NWL's side and receive() on LanRED's side.
    Both increase the same underlying balance. In the One Big Loop, a single
    ICOverdraft instance is shared between the two entity waterfalls.
    """

    def __init__(self, ic_rate_annual: float = 0.10):
        self.ic_rate_semi = ic_rate_annual / 2.0
        self.balance = 0.0

    def accrue(self) -> ReserveAccrual:
        """Compute interest on opening OD balance and add to balance.

        Returns ReserveAccrual for consistency with other reserve classes.
        Target is set to 0 (the OD has no fill target — it is demand-driven).
        Gap and excess are 0 (no allocation target for the waterfall).
        """
        opening = self.balance
        interest = opening * self.ic_rate_semi
        self.balance += interest

        return ReserveAccrual(
            opening=opening,
            interest=interest,
            balance_after_interest=self.balance,
            target=0.0,
            gap=0.0,
            excess=0.0,
        )

    def lend(self, amount: float) -> float:
        """NWL lends to LanRED — increases outstanding OD balance.

        Called on NWL's waterfall when LanRED has a deficit and NWL has
        remaining cash. The lent amount reduces NWL's remaining cash and
        increases the OD receivable.

        Args:
            amount: Cash to lend (must be >= 0).

        Returns:
            Actual amount lent (same as input, clamped to >= 0).
        """
        lent = max(amount, 0.0)
        self.balance += lent
        return lent

    def receive(self, amount: float) -> float:
        """LanRED receives OD from NWL — increases outstanding OD balance.

        Called on LanRED's waterfall to inject the OD cash received from NWL.
        The received amount increases LanRED's remaining cash and increases
        the OD liability.

        Args:
            amount: Cash received (must be >= 0).

        Returns:
            Actual amount received (same as input, clamped to >= 0).
        """
        received = max(amount, 0.0)
        self.balance += received
        return received

    def repay(self, amount: float) -> float:
        """LanRED repays OD from surplus — decreases outstanding OD balance.

        Called on LanRED's waterfall after acceleration, when LanRED has
        remaining surplus cash. Repayment is capped at the current balance
        (cannot overpay).

        Args:
            amount: Cash available for repayment (must be >= 0).

        Returns:
            Actual amount repaid (min of amount and current balance).
        """
        repaid = min(max(amount, 0.0), self.balance)
        self.balance -= repaid
        return repaid

    @property
    def is_outstanding(self) -> bool:
        """Whether there is a material OD balance (> EUR 0.01)."""
        return self.balance > 0.01


def total_fd_income(
    ops_accrual: ReserveAccrual,
    entity_fd_accrual: ReserveAccrual,
    mz_div_accrual: ReserveAccrual | None = None,
    dsra_accrual: ReserveAccrual | None = None,
) -> float:
    """Sum of all FD interest income for P&L.

    This is the entity's interest income on its reserve balances.
    Used as fd_income input to compute_period_pnl().
    """
    total = ops_accrual.interest + entity_fd_accrual.interest
    if mz_div_accrual is not None:
        total += mz_div_accrual.interest
    if dsra_accrual is not None:
        total += dsra_accrual.interest
    return total


# ── Reserve schedule builder (post-hoc verification) ──────────────


def build_reserve_schedule(
    num_periods: int,
    fills: list[float],
    releases: list[float],
    interest_amounts: list[float],
    initial_balance: float = 0.0,
) -> dict[str, list[float]]:
    """Build a reserve schedule from waterfall allocation decisions.

    This function takes the waterfall's per-period fill, release, and
    interest amounts (which the waterfall already computed) and produces
    the canonical Opening/Fill/Interest/Release/Closing lifecycle.

    The interest_amounts are pre-computed by the waterfall (Opening x rate / 2)
    because the waterfall needs to know the opening balance to compute interest.
    We take these as given rather than recomputing, since the waterfall is the
    single source of truth for the allocation sequence.

    Args:
        num_periods: Number of semi-annual periods (typically 20).
        fills: Per-period fill amounts from waterfall (positive = inflow).
        releases: Per-period release amounts from waterfall (positive = outflow).
        interest_amounts: Per-period interest earned (positive = inflow).
        initial_balance: Balance at the start of period 0.

    Returns:
        dict with keys: opening, fill, interest, release, closing
        Each is a list[float] of length num_periods.
    """
    opening: list[float] = []
    fill_out: list[float] = []
    interest_out: list[float] = []
    release_out: list[float] = []
    closing: list[float] = []

    balance = initial_balance

    for hi in range(num_periods):
        op = balance
        f = fills[hi] if hi < len(fills) else 0.0
        r = releases[hi] if hi < len(releases) else 0.0
        i = interest_amounts[hi] if hi < len(interest_amounts) else 0.0

        cl = op + f + i - r

        opening.append(op)
        fill_out.append(f)
        interest_out.append(i)
        release_out.append(r)
        closing.append(cl)

        balance = cl

    return {
        "opening": opening,
        "fill": fill_out,
        "interest": interest_out,
        "release": release_out,
        "closing": closing,
    }


def extract_reserve_vectors(
    wf_semi: list[dict],
    reserve_name: str,
) -> dict[str, list[float]]:
    """Extract fill/release/interest/closing vectors for a named reserve
    from the waterfall semi-annual output.

    Supported reserve_name values:
        ops_reserve  -- Ops Reserve FD
        opco_dsra    -- OpCo DSRA
        entity_fd    -- Entity FD
        mz_div_fd    -- Mezz Dividend FD
        od           -- Overdraft (NWL->LanRED)

    Returns dict with keys: fill, release, interest, closing
    Each is a list[float] of length len(wf_semi).
    """
    key_map = {
        "ops_reserve": {
            "fill": "ops_reserve_fill",
            "release": lambda _r: 0.0,  # ops reserve releases are embedded in fill (negative)
            "interest": "ops_reserve_interest",
            "closing": "ops_reserve_bal",
        },
        "opco_dsra": {
            "fill": "opco_dsra_fill",
            "release": "opco_dsra_release",
            "interest": "opco_dsra_interest",
            "closing": "opco_dsra_bal",
        },
        "entity_fd": {
            "fill": "entity_fd_fill",
            "release": lambda _r: 0.0,
            "interest": "entity_fd_interest",
            "closing": "entity_fd_bal",
        },
        "mz_div_fd": {
            "fill": "mz_div_fd_fill",
            "release": "mz_div_payout_amount",  # payout IS the release event
            "interest": "mz_div_fd_interest",
            "closing": "mz_div_fd_bal",
        },
        "od": {
            "fill": "od_lent",
            "release": "od_repaid",
            "interest": "od_interest",
            "closing": "od_bal",
        },
    }

    if reserve_name not in key_map:
        raise ValueError(f"Unknown reserve: {reserve_name}. "
                         f"Supported: {list(key_map.keys())}")

    km = key_map[reserve_name]
    n = len(wf_semi)

    def _get(row: dict, key_or_fn) -> float:
        if callable(key_or_fn):
            return key_or_fn(row)
        return row.get(key_or_fn, 0.0)

    return {
        "fill": [_get(wf_semi[hi], km["fill"]) for hi in range(n)],
        "release": [_get(wf_semi[hi], km["release"]) for hi in range(n)],
        "interest": [_get(wf_semi[hi], km["interest"]) for hi in range(n)],
        "closing": [_get(wf_semi[hi], km["closing"]) for hi in range(n)],
    }


def verify_reserve_balance(
    wf_semi: list[dict],
    reserve_name: str,
    tolerance: float = 0.01,
) -> tuple[bool, float]:
    """Verify that a reserve's closing balance in the waterfall output
    matches what build_reserve_schedule would produce.

    Returns (passed, max_difference).
    """
    vectors = extract_reserve_vectors(wf_semi, reserve_name)
    n = len(wf_semi)

    schedule = build_reserve_schedule(
        num_periods=n,
        fills=vectors["fill"],
        releases=vectors["release"],
        interest_amounts=vectors["interest"],
        initial_balance=0.0,
    )

    max_diff = 0.0
    for hi in range(n):
        diff = abs(schedule["closing"][hi] - vectors["closing"][hi])
        max_diff = max(max_diff, diff)

    return max_diff <= tolerance, max_diff
