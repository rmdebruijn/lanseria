"""IC facility schedule builder.

Builds a vanilla IC loan schedule with optional acceleration.
IDC capitalisation during construction -> P_constant repayment from M24.

FacilityState: period-by-period calculator for the One Big Loop.
build_schedule(): batch builder for standalone display / sensitivity analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.periods import (
    total_periods, repayment_start_month,
    n_construction, construction_period_labels,
    repayment_start_index, period_start_month,
)


# ── Period-by-period facility calculator ──────────────────────────


@dataclass
class FacilityPeriod:
    """Output of FacilityState.compute_period() — pre-finalization.

    Unified formula (all periods):
        Closing = Opening + DD + Interest + (-Interest_paid + IDC) - Principal - Acceleration

    Construction: IDC = Interest, Interest_paid = 0  → (-0 + Interest) = +Interest (capitalised)
    Repayment:    IDC = 0, Interest_paid = Interest  → (-Interest + 0) = -Interest (cash expense)
    """
    hi: int
    opening: float
    interest: float          # Opening × rate / 2 — always computed
    idc: float               # = interest during construction, 0 during repayment
    principal: float         # Scheduled P_constant (positive = repayment amount)
    pi: float                # interest + principal (cash debt service)
    draw_down: float
    pre_accel_closing: float # Closing BEFORE waterfall acceleration
    is_construction: bool
    is_repayment: bool


@dataclass
class FacilityState:
    """Period-by-period facility calculator.

    Replaces batch build_schedule() in the main loop.
    Construction is run as batch in init (no circularity).
    Repayment periods are computed one at a time:
        compute_period(hi) -> FacilityPeriod (pre-acceleration)
        finalize_period(hi, acceleration) -> updates balance, recalculates P_constant

    Args:
        principal: This entity's portion of the facility
        total_principal: Total facility across all entities (for pro-rata)
        repayments: Number of semi-annual repayment periods (e.g. 14 sr, 10 mz)
        rate: Annual IC rate (e.g. 0.052 for senior)
        drawdown_schedule: Facility-level drawdown amounts per construction period
        construction_periods: Period indices (e.g. [0, 1, 2, 3])
        grant_acceleration: {period_str: amount} — grant-funded acceleration
            during construction (e.g. {'2': 3236004.0} for DTIC at C3).
        dsra_amount: DSRA early repayment in repayment period 1
        dsra_drawdown: DSRA-funded drawdown in repayment period 1
    """
    principal: float
    total_principal: float
    repayments: int
    rate: float
    drawdown_schedule: list[float]
    construction_periods: list[int]
    grant_acceleration: dict[str, float] | None = None
    dsra_amount: float = 0.0
    dsra_drawdown: float = 0.0

    # Running state
    balance: float = field(init=False, default=0.0)
    _p_per: float = field(init=False, default=0.0)
    _p_per_after_dsra: float = field(init=False, default=0.0)
    _repayment_index: int = field(init=False, default=0)   # 1-based repayment counter
    _rep_start_idx: int = field(init=False, default=0)
    _pro_rata: float = field(init=False, default=0.0)

    # Output accumulator (same format as build_schedule)
    schedule: list[dict] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._pro_rata = (
            self.principal / self.total_principal
            if self.total_principal else 0.0
        )
        self._rep_start_idx = repayment_start_index()
        self._run_construction()
        self._init_repayment_profile()

    def _run_construction(self) -> None:
        """Run construction phase as batch (no circularity).

        Unified formula: Closing = Opening + DD + Interest + (-Interest_paid + IDC) - Principal - Accel
        Construction: Interest_paid=0, IDC=Interest → net = +Interest (capitalised)
        """
        for idx, period in enumerate(self.construction_periods):
            month = period_start_month(period)
            year = month / 12
            opening = self.balance
            interest = opening * self.rate / 2
            idc = interest  # Construction: IDC = Interest (capitalised)
            interest_paid = 0.0  # Construction: no cash interest payment
            dd = (
                self.drawdown_schedule[idx] * self._pro_rata
                if idx < len(self.drawdown_schedule) else 0.0
            )
            principal = 0.0
            accel = 0.0
            if self.grant_acceleration and str(period) in self.grant_acceleration:
                accel = self.grant_acceleration[str(period)]
            # Unified: Opening + DD + Interest + (-Interest_paid + IDC) - Principal - Accel
            # = Opening + DD + Interest + (0 + Interest) - 0 - Accel
            # = Opening + DD + 2*Interest - Accel ... NO
            # Wait: the formula is Closing = Opening + DD + IDC - Principal - Accel
            # Because: Interest + (-Interest_paid + IDC) = Interest - 0 + Interest = 2*Interest? No.
            # The columns: Interest is computed. -Interest_paid is cash out. +IDC is capitalised.
            # Net interest impact = -Interest_paid + IDC = -0 + Interest = +Interest
            # So: Closing = Opening + DD + (net interest impact) - Principal - Accel
            #            = Opening + DD + Interest - 0 - Accel
            movement = dd + idc - accel
            self.balance = opening + movement
            self.schedule.append({
                "Period": period, "Month": month, "Year": year,
                "Opening": opening, "Draw Down": dd, "Interest": interest,
                "IDC": idc,
                "Principle": 0,
                "Acceleration": -accel if accel > 0 else 0,
                "Movement": movement, "Closing": self.balance,
            })

    def _init_repayment_profile(self) -> None:
        """Set initial P_constant based on balance at end of construction."""
        if self.dsra_amount > 0:
            dsra_balance_after = self.balance - self.dsra_amount
            self._p_per_after_dsra = (
                dsra_balance_after / (self.repayments - 2)
                if self.repayments > 2 else 0.0
            )
            self._p_per = 0.0
        elif self.dsra_drawdown > 0:
            total_after_dsra = self.balance + self.dsra_drawdown
            self._p_per = (
                total_after_dsra / self.repayments
                if self.repayments > 0 else 0.0
            )
        else:
            self._p_per = (
                self.balance / self.repayments
                if self.repayments > 0 else 0.0
            )

    def compute_period(self, hi: int) -> FacilityPeriod:
        """Compute opening, interest, principal for this period.

        Does NOT finalize — waterfall decides acceleration first.
        Construction periods: interest computed but IDC=interest (capitalised, not cash).
        Repayment periods: interest is cash expense, IDC=0.
        """
        # Construction periods are already in self.schedule
        if hi < len(self.construction_periods):
            row = self.schedule[hi]
            return FacilityPeriod(
                hi=hi, opening=row["Opening"],
                interest=0.0, idc=row["IDC"],
                principal=0.0, pi=0.0,
                draw_down=row["Draw Down"],
                pre_accel_closing=row["Closing"],
                is_construction=True, is_repayment=False,
            )

        # Tail periods (after all repayments done)
        rep_i = hi - self._rep_start_idx + 1  # 1-based repayment number
        if rep_i > self.repayments or self.balance <= 0.01:
            return FacilityPeriod(
                hi=hi, opening=self.balance,
                interest=0.0, idc=0.0,
                principal=0.0, pi=0.0,
                draw_down=0.0,
                pre_accel_closing=self.balance,
                is_construction=False, is_repayment=False,
            )

        # Repayment period
        opening = self.balance
        interest = opening * self.rate / 2

        # Determine principal and draw_down
        if self.dsra_amount > 0:
            if rep_i == 1:
                draw_down, principal = 0.0, self.dsra_amount
            elif rep_i == 2:
                draw_down, principal = 0.0, 0.0
            else:
                draw_down, principal = 0.0, self._p_per_after_dsra
        elif self.dsra_drawdown > 0:
            draw_down = self.dsra_drawdown if rep_i == 1 else 0.0
            principal = self._p_per
        else:
            draw_down = 0.0
            principal = self._p_per

        # Ensure we don't overshoot zero balance
        if opening + draw_down - principal < -0.01:
            principal = opening + draw_down

        pre_accel_closing = opening + draw_down - principal

        return FacilityPeriod(
            hi=hi, opening=opening,
            interest=interest, idc=0.0,
            principal=principal,
            pi=interest + principal,
            draw_down=draw_down,
            pre_accel_closing=pre_accel_closing,
            is_construction=False, is_repayment=True,
        )

    def finalize_period(self, hi: int, acceleration: float = 0.0) -> None:
        """Apply acceleration, update balance, recalculate P_constant.

        Appends completed row to self.schedule.
        Must be called AFTER compute_period() and waterfall allocation.
        """
        # Construction periods are already finalized in __post_init__
        if hi < len(self.construction_periods):
            return

        fp = self.compute_period(hi)

        # Cap acceleration at available balance
        accel = min(acceleration, max(fp.pre_accel_closing, 0.0))

        closing = max(fp.pre_accel_closing - accel, 0.0)

        # Build schedule row (same format as build_schedule)
        month = period_start_month(hi)
        year = month / 12
        principle_signed = -fp.principal if fp.principal > 0 else 0.0

        self.schedule.append({
            "Period": hi, "Month": month, "Year": year,
            "Opening": fp.opening, "Draw Down": fp.draw_down,
            "Interest": fp.interest, "IDC": 0.0,
            "Principle": principle_signed,
            "Acceleration": -accel if accel > 0 else 0,
            "Movement": fp.draw_down + principle_signed - accel,
            "Closing": closing,
        })

        self.balance = closing

        # Recalculate P_constant for remaining periods after acceleration
        rep_i = hi - self._rep_start_idx + 1
        remaining = self.repayments - rep_i
        if accel > 0 and remaining > 0 and self.balance > 0.01:
            self._p_per = self.balance / remaining
            # Also update dsra variant if applicable
            if self.dsra_amount > 0 and rep_i >= 2:
                self._p_per_after_dsra = self.balance / remaining

    def next_pi_estimate(self) -> float:
        """Estimate next period's P+I based on current balance and P_constant.

        Used for DSRA target sizing (1x next Sr P+I).
        """
        if self.balance <= 0.01:
            return 0.0
        interest = self.balance * self.rate / 2
        p_const = self._p_per
        if self.dsra_amount > 0:
            # Use the after-dsra P_constant if in DSRA mode
            p_const = self._p_per_after_dsra
        return interest + p_const


def extract_facility_vectors(
    schedule: list[dict],
    num_periods: int | None = None,
) -> dict:
    """Pre-build per-half-period vectors for waterfall to READ (not recompute).

    Maps each semi-annual period (by start_month) to the corresponding facility
    schedule row, extracting Interest, Principle, Acceleration, and Closing balance.

    Construction-phase interest/principal = 0 (IDC is capitalised, not cash).

    Returns:
        dict with keys: interest, principal, acceleration, closing_bal
        Each is a list[float] of length num_periods.
    """
    if num_periods is None:
        num_periods = total_periods()

    rep_start = repayment_start_month()

    # Build lookup: month -> row
    by_month: dict[int, dict] = {}
    for r in schedule:
        by_month[r["Month"]] = r

    interest = []
    principal = []
    pi = []
    acceleration = []
    closing_bal = []

    for hi in range(num_periods):
        hm = period_start_month(hi)
        row = by_month.get(hm)

        if row is None:
            interest.append(0.0)
            principal.append(0.0)
            pi.append(0.0)
            acceleration.append(0.0)
            last_close = 0.0
            for r in schedule:
                if r["Month"] <= hm:
                    last_close = r["Closing"]
            closing_bal.append(last_close)
        elif hm < rep_start:
            # Construction phase: IDC is capitalised, not a cash interest expense
            interest.append(0.0)
            principal.append(0.0)
            pi.append(0.0)
            acceleration.append(0.0)
            closing_bal.append(row["Closing"])
        else:
            # Repayment phase: read interest, principal, acceleration
            _int = row["Interest"]
            _prin = abs(row["Principle"])
            interest.append(_int)
            principal.append(_prin)
            pi.append(_int + _prin)
            acceleration.append(abs(row.get("Acceleration", 0)))
            closing_bal.append(max(row["Closing"], 0.0))

    return {
        "interest": interest,
        "principal": principal,
        "pi": pi,
        "acceleration": acceleration,
        "closing_bal": closing_bal,
    }


def build_schedule(
    principal: float,
    total_principal: float,
    repayments: int,
    rate: float,
    drawdown_schedule: list[float],
    construction_periods: list[int],
    acceleration: dict[str, float] | None = None,
    dsra_amount: float = 0.0,
    dsra_drawdown: float = 0.0,
) -> list[dict]:
    """Build a vanilla IC loan schedule with optional acceleration.

    Args:
        principal: This entity's portion of the facility
        total_principal: Total facility across all entities (for pro-rata)
        repayments: Number of semi-annual repayment periods (e.g. 14 sr, 10 mz)
        rate: Annual IC rate (e.g. 0.052 for senior)
        drawdown_schedule: Facility-level drawdown amounts per construction period
        construction_periods: Period labels (e.g. [-4, -3, -2, -1])
        acceleration: {period_str: amount} — waterfall-driven acceleration
        dsra_amount: DSRA early repayment in period 1 (reduces balance, P2=IO, P3+ recalc)
        dsra_drawdown: DSRA-funded drawdown in period 1 (adds to balance)

    Returns:
        List of dicts with keys:
        Period, Month, Year, Opening, Draw Down, Interest,
        Principle, Acceleration, Movement, Closing
    """
    rows = []
    balance = 0.0
    pro_rata = principal / total_principal if total_principal else 0

    # Construction phase: drawdowns + IDC capitalisation
    for idx, period in enumerate(construction_periods):
        month = period_start_month(period)
        year = month / 12
        opening = balance
        idc = opening * rate / 2
        draw_down = drawdown_schedule[idx] * pro_rata if idx < len(drawdown_schedule) else 0
        accel = 0.0
        if acceleration and str(period) in acceleration:
            accel = acceleration[str(period)]
        movement = draw_down + idc - accel
        balance = opening + movement
        rows.append({
            "Period": period, "Month": month, "Year": year,
            "Opening": opening, "Draw Down": draw_down, "Interest": idc,
            "Principle": 0,
            "Acceleration": -accel if accel > 0 else 0,
            "Movement": movement, "Closing": balance,
        })

    # Repayment profile: vanilla P_constant, or DSRA-adjusted
    if dsra_amount > 0:
        dsra_balance_after = balance - dsra_amount
        p_per_after_dsra = dsra_balance_after / (repayments - 2) if repayments > 2 else 0
        p_per = 0
    elif dsra_drawdown > 0:
        total_after_dsra = balance + dsra_drawdown
        p_per = total_after_dsra / repayments if repayments > 0 else 0
    else:
        p_per = balance / repayments if repayments > 0 else 0

    for i in range(1, repayments + 1):
        period_idx = repayment_start_index() + (i - 1)
        month = period_start_month(period_idx)
        year = month / 12
        opening = balance
        interest = opening * rate / 2

        accel = 0.0
        if acceleration and str(period_idx) in acceleration:
            accel = min(acceleration[str(period_idx)], max(opening, 0))

        if dsra_amount > 0:
            if i == 1:
                draw_down, principle = 0, -dsra_amount
            elif i == 2:
                draw_down, principle = 0, 0
            else:
                draw_down, principle = 0, -p_per_after_dsra
        elif dsra_drawdown > 0:
            draw_down = dsra_drawdown if i == 1 else 0
            principle = -p_per
        else:
            draw_down = 0
            principle = -p_per

        # Ensure we don't overshoot zero balance
        if opening + draw_down + principle - accel < -0.01:
            principle = -(opening + draw_down - accel)

        movement = draw_down + principle - accel
        balance = opening + movement

        # Recalculate p_per for remaining periods after acceleration
        remaining = repayments - i
        if accel > 0 and remaining > 0 and balance > 0.01:
            p_per = balance / remaining

        rows.append({
            "Period": period_idx, "Month": month, "Year": year,
            "Opening": opening, "Draw Down": draw_down, "Interest": interest,
            "Principle": principle,
            "Acceleration": -accel if accel > 0 else 0,
            "Movement": movement, "Closing": max(balance, 0),
        })

    return rows


def apply_acceleration(
    schedule: list[dict],
    accel_map: dict[str, float],
    principal: float,
    total_principal: float,
    repayments: int,
    rate: float,
    drawdown_schedule: list[float],
    construction_periods: list[int],
) -> list[dict]:
    """Rebuild the schedule with waterfall-driven acceleration amounts.

    accel_map: {period_str: acceleration_amount} from waterfall pass.
    Returns a new schedule with acceleration = accel_map.
    """
    return build_schedule(
        principal, total_principal, repayments, rate,
        drawdown_schedule, construction_periods,
        acceleration=accel_map,
    )


def get_next_sr_pi(schedule: list[dict], after_month: int) -> float:
    """Look up the next Senior IC P+I payment after a given month.

    Used for OpCo DSRA sizing (1x next Sr IC P+I).
    """
    for r in schedule:
        if r["Month"] > after_month and r["Month"] >= repayment_start_month():
            return r["Interest"] + abs(r["Principle"])
    return 0.0


def extract_idc_table(schedule: list[dict]) -> list[dict]:
    """Extract IDC summary from construction rows of a facility schedule.

    Returns list of dicts with Period, Draw Down, IDC, plus a Total row.
    Reads directly from the schedule — no recalculation.
    """
    rows = []
    dd_total = 0.0
    idc_total = 0.0
    for r in schedule:
        if r["Principle"] != 0 or r["Period"] >= repayment_start_index():
            break
        dd = r["Draw Down"]
        idc = r["Interest"]
        dd_total += dd
        idc_total += idc
        rows.append({"Period": r["Period"], "Draw Down": dd, "IDC": idc})
    rows.append({"Period": "Total", "Draw Down": dd_total, "IDC": idc_total})
    return rows


def build_entity_schedule(
    entity_key: str,
    cfg,  # ModelConfig
    acceleration: dict[str, float] | None = None,
    debt_type: str = "senior",
) -> list[dict]:
    """Build an IC schedule for a specific entity and debt type.

    Convenience wrapper that reads entity loan amounts from ModelConfig.
    """
    entity_data = cfg.entity_loans()[entity_key]
    sr_detail = cfg.financing["loan_detail"]["senior"]
    drawdowns = sr_detail["drawdown_schedule"]
    construction_periods = construction_period_labels()

    if debt_type == "senior":
        return build_schedule(
            principal=entity_data["senior_portion"],
            total_principal=cfg.total_senior(),
            repayments=cfg.sr_repayments,
            rate=cfg.sr_ic_rate,
            drawdown_schedule=drawdowns,
            construction_periods=construction_periods,
            acceleration=acceleration,
        )
    else:
        mz_amount_eur = cfg.structure["sources"]["mezzanine"]["amount_eur"]
        mz_drawdowns = [mz_amount_eur, 0, 0, 0]
        return build_schedule(
            principal=entity_data["mezz_portion"],
            total_principal=cfg.total_mezz(),
            repayments=cfg.mz_repayments,
            rate=cfg.mz_ic_rate,
            drawdown_schedule=mz_drawdowns,
            construction_periods=construction_periods,
            acceleration=acceleration,
        )
