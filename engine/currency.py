"""Currency wrapper types — EUR, ZAR, and EurEquiv with mixed-arithmetic prevention.

EUR(100) + EUR(200) -> EUR(300)
EUR(100) + ZAR(200) -> TypeError
EUR(100) * 0.27     -> EUR(27)        (scalar)
EUR(100) / EUR(50)  -> 2.0            (ratio = dimensionless)
sum([EUR(1), EUR(2)])-> EUR(3)         (via __radd__ with 0-check)
max(EUR(1), EUR(2)) -> EUR(2)         (via __gt__)
float(EUR(100))     -> TypeError       (forces .value)
f"{EUR(1234.56):,.2f}" -> "1,234.56"  (via __format__)

EurEquiv: EUR-equivalent at a specific date/rate. Carries provenance
(original currency, original amount, fx rate used). Arithmetic works
like EUR for cascade calculations, but you can always recover the
original ZAR (or EUR) and the rate.
"""

from __future__ import annotations

from dataclasses import dataclass


class _CurrencyBase:
    __slots__ = ('_val',)

    def __init__(self, value: float | int | _CurrencyBase = 0.0):
        if isinstance(value, _CurrencyBase):
            self._val = value._val
        else:
            self._val = float(value)

    @property
    def value(self) -> float:
        return self._val

    # ── Same-type arithmetic ────────────────────────────────────

    def __add__(self, other):
        # sum() starts with int 0, so allow it
        if isinstance(other, (int, float)) and other == 0:
            return self
        if type(other) is not type(self):
            raise TypeError(
                f"Cannot add {type(self).__name__} and {type(other).__name__}"
            )
        return type(self)(self._val + other._val)

    def __radd__(self, other):
        # sum() calls 0 + EUR(...), so handle int/float 0
        if isinstance(other, (int, float)) and other == 0:
            return self
        if type(other) is not type(self):
            raise TypeError(
                f"Cannot add {type(other).__name__} and {type(self).__name__}"
            )
        return type(self)(other._val + self._val)

    def __sub__(self, other):
        if type(other) is not type(self):
            raise TypeError(
                f"Cannot subtract {type(other).__name__} from {type(self).__name__}"
            )
        return type(self)(self._val - other._val)

    def __rsub__(self, other):
        if isinstance(other, (int, float)) and other == 0:
            return type(self)(-self._val)
        if type(other) is not type(self):
            raise TypeError(
                f"Cannot subtract {type(self).__name__} from {type(other).__name__}"
            )
        return type(self)(other._val - self._val)

    # ── Scalar multiplication ───────────────────────────────────

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return type(self)(self._val * other)
        raise TypeError(
            f"Cannot multiply {type(self).__name__} by {type(other).__name__}"
        )

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return type(self)(self._val * other)
        raise TypeError(
            f"Cannot multiply {type(other).__name__} by {type(self).__name__}"
        )

    # ── Division ────────────────────────────────────────────────

    def __truediv__(self, other):
        # Same-type division -> dimensionless float (ratio)
        if type(other) is type(self):
            return self._val / other._val
        # Scalar division -> same type
        if isinstance(other, (int, float)):
            return type(self)(self._val / other)
        raise TypeError(
            f"Cannot divide {type(self).__name__} by {type(other).__name__}"
        )

    def __rtruediv__(self, other):
        # float / EUR is not meaningful; only EUR / EUR or EUR / scalar
        raise TypeError(
            f"Cannot divide {type(other).__name__} by {type(self).__name__}"
        )

    def __floordiv__(self, other):
        if type(other) is type(self):
            return self._val // other._val
        if isinstance(other, (int, float)):
            return type(self)(self._val // other)
        raise TypeError(
            f"Cannot floor-divide {type(self).__name__} by {type(other).__name__}"
        )

    # ── Comparisons (same-type only) ───────────────────────────

    def __eq__(self, other):
        if type(other) is type(self):
            return self._val == other._val
        # Allow comparison with 0 for convenience (e.g. `if amount == 0`)
        if isinstance(other, (int, float)) and other == 0:
            return self._val == 0.0
        return NotImplemented

    def __ne__(self, other):
        if type(other) is type(self):
            return self._val != other._val
        if isinstance(other, (int, float)) and other == 0:
            return self._val != 0.0
        return NotImplemented

    def __lt__(self, other):
        if type(other) is not type(self):
            raise TypeError(
                f"'<' not supported between {type(self).__name__} and {type(other).__name__}"
            )
        return self._val < other._val

    def __le__(self, other):
        if type(other) is not type(self):
            raise TypeError(
                f"'<=' not supported between {type(self).__name__} and {type(other).__name__}"
            )
        return self._val <= other._val

    def __gt__(self, other):
        if type(other) is not type(self):
            raise TypeError(
                f"'>' not supported between {type(self).__name__} and {type(other).__name__}"
            )
        return self._val > other._val

    def __ge__(self, other):
        if type(other) is not type(self):
            raise TypeError(
                f"'>=' not supported between {type(self).__name__} and {type(other).__name__}"
            )
        return self._val >= other._val

    # ── Unary / builtins ────────────────────────────────────────

    def __neg__(self):
        return type(self)(-self._val)

    def __pos__(self):
        return type(self)(self._val)

    def __abs__(self):
        return type(self)(abs(self._val))

    def __round__(self, n: int = 0):
        return type(self)(round(self._val, n))

    def __bool__(self):
        return self._val != 0.0

    def __float__(self):
        raise TypeError(
            f"Cannot implicitly convert {type(self).__name__} to float. "
            f"Use .value or .to_eur()/.to_zar() explicitly."
        )

    def __int__(self):
        raise TypeError(
            f"Cannot implicitly convert {type(self).__name__} to int. "
            f"Use .value explicitly."
        )

    # ── Display ─────────────────────────────────────────────────

    def __repr__(self):
        return f"{type(self).__name__}({self._val})"

    def __str__(self):
        return f"{type(self).__name__}({self._val:,.2f})"

    def __format__(self, spec):
        return format(self._val, spec)

    def __hash__(self):
        return hash((type(self).__name__, self._val))


class EUR(_CurrencyBase):
    """Euro amount."""

    def to_zar(self, rate: float) -> ZAR:
        """Convert to ZAR at the given EUR/ZAR rate."""
        return ZAR(self._val * rate)


class ZAR(_CurrencyBase):
    """South African Rand amount."""

    def to_eur(self, rate: float) -> EUR:
        """Convert to EUR at the given EUR/ZAR rate."""
        return EUR(self._val / rate)


@dataclass(frozen=True, slots=True)
class FxRate:
    """EUR/ZAR exchange rate (1 EUR = rate ZAR)."""
    rate: float

    def eur_to_zar(self, amount: EUR) -> ZAR:
        return ZAR(amount.value * self.rate)

    def zar_to_eur(self, amount: ZAR) -> EUR:
        return EUR(amount.value / self.rate)


# ── EUR-Equivalent at Date ──────────────────────────────────────


@dataclass(slots=True)
class EurEquiv:
    """EUR-equivalent of a foreign-currency amount at a specific rate.

    Tracks provenance: what the original amount was, in what currency,
    and what fx rate was used to derive the EUR value.

    Use cases:
    - Swap ZAR leg payments converted to EUR for the waterfall cascade
    - Mezz drawdown: EUR-equivalent fixed at drawdown date, underlying ZAR
    - Any mark-to-market restatement

    Arithmetic on .eur works like normal EUR. The original amount is
    preserved for audit, restatement, or re-conversion at a different rate.

    Examples:
        # ZAR swap payment -> EUR equiv at contract rate
        payment = EurEquiv.from_zar(ZAR(1_000_000), fx_rate=20.0)
        payment.eur          # EUR(50000.0)
        payment.original     # ZAR(1000000.0)
        payment.rate         # 20.0
        payment.value        # 50000.0 (float, for dict serialisation)

        # Restate at a different rate (e.g. spot)
        restated = payment.restate(fx_rate=22.0)
        restated.eur         # EUR(45454.545...)
        restated.original    # ZAR(1000000.0) — unchanged
        restated.rate        # 22.0

        # EUR amount that IS the original (no conversion)
        equity = EurEquiv.from_eur(EUR(50000))
        equity.original      # EUR(50000.0)
        equity.rate          # 1.0
    """
    eur: EUR
    original: EUR | ZAR
    rate: float  # fx rate used (1 EUR = rate ZAR); 1.0 if original is EUR

    @classmethod
    def from_zar(cls, amount: ZAR, fx_rate: float) -> EurEquiv:
        """Create EUR-equivalent from a ZAR amount at a given rate."""
        return cls(
            eur=EUR(amount.value / fx_rate),
            original=amount,
            rate=fx_rate,
        )

    @classmethod
    def from_eur(cls, amount: EUR) -> EurEquiv:
        """Wrap a native EUR amount (no conversion, rate=1.0)."""
        return cls(eur=amount, original=amount, rate=1.0)

    @property
    def value(self) -> float:
        """EUR float value for dict serialisation."""
        return self.eur.value

    @property
    def original_value(self) -> float:
        """Original currency float value."""
        return self.original.value

    @property
    def original_currency(self) -> str:
        """'EUR' or 'ZAR'."""
        return type(self.original).__name__

    def restate(self, fx_rate: float) -> EurEquiv:
        """Re-convert the original amount at a new fx rate.

        Only meaningful when original is ZAR. If original is EUR,
        returns self unchanged (rate stays 1.0).
        """
        if isinstance(self.original, ZAR):
            return EurEquiv(
                eur=EUR(self.original.value / fx_rate),
                original=self.original,
                rate=fx_rate,
            )
        return self  # EUR original: no restatement needed

    def __repr__(self) -> str:
        return (f"EurEquiv(eur={self.eur!r}, "
                f"original={self.original!r}, rate={self.rate})")

    def __format__(self, spec) -> str:
        return format(self.eur.value, spec)


# Sentinel zero values for use as defaults
ZERO_EUR = EUR(0.0)
ZERO_ZAR = ZAR(0.0)
ZERO_EQUIV = EurEquiv(eur=ZERO_EUR, original=ZERO_EUR, rate=1.0)
