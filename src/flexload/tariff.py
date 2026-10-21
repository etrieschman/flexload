"""The operator's action τ: how the load's charge Bᵏ recovers each layer's cost
Cᵏ. The bill is B = Σₖ Bᵏ. Report §3, "Tariff".

Each layer k ∈ {energy, reserve, investment} has a charge form on a base x, the
load's consumption in the layer's hours 𝒲ᵏ (``hours``, a 0/1 vector over t):
x = hours ∘ d. Every layer is hourly. Energy and reserve have an hourly cost
Cᵏ_t from dispatch; investment has one cost for the window, which the tariff
spreads over its hours, Cⁱⁿᵛ_t = Cⁱⁿᵛ hours_t / Σ hours, all of it on t* under τ₀.

    Marginal(hours)                 Bᵏ = Σ_{t∈𝒲ᵏ} price_t d_t                 the layer's price on each MWh
    Share(hours, ex_ante)           Bᵏ = Σ_{t∈𝒲ᵏ} Cᵏ_t d_t / (d̂_t + d°_t)       the load's share of the cost
    TwoPart(hours, ex_ante, phi, T) Bᵏ = Σ_{t∈𝒲ᵏ} φ_t d_t + T                 a marginal rate plus a lump sum

x̂ is the load's believed consumption, where its charge is linearized so that
its best response is a QP. A load that takes the posted rate pays the average
rate Cᵏ/(x̂ + x°) on each MWh (the exogenous price-taker). A load that knows its
share pays along the tangent of the exact charge at x̂, slope Cᵏ x°/(x̂ + x°)²
(the consistent price-taker, ``knows_share``). At settlement x̂ = x and the
split pool is exact either way.

Slots: ``ex_ante`` reads Cᵏ from the dispatch at the load's preferred profile
(δ, 0), the B0 dispatch ``b0``, as ERCOT procures reserve against a forecast;
otherwise from the dispatch at the bid, ``realized``. Each layer's form sets it. ``credit`` pays a load that sells reserve μᵀσ.
``exempt_curtailable`` frees a curtailable load from the reserve charge (τ₅).

Formulas are cvxpy expressions on numbers or variables alike; read ``.value``.
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from .system import Dispatch, Scenario

LAYERS = ("energy", "reserve", "investment")


def peak_hour(d_sys: np.ndarray) -> np.ndarray:
    """Hours one-hot at the peak of ``d_sys``: the ex-ante peak hour t* when d_sys is the B0 path."""
    hours = np.zeros(d_sys.shape[0])
    hours[int(np.argmax(d_sys))] = 1.0
    return hours


# ----------------------------------------------------------------------------
# charge forms: charge(x, x_hat, x_other, pool, price) and its derivative in x
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Marginal:
    """Bᵏ = Σ_t price_t x_t: the layer's price on each MWh. Energy under τ₀, price λ."""

    hours: np.ndarray
    ex_ante: bool = (
        False  # the price is the realized one; kept so every form has the slot
    )

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        return cp.sum(cp.multiply(price, x))

    def marginal(self, x, x_other, pool, price):
        return price


@dataclass(frozen=True)
class Share:
    """Split pool: Bᵏ = Σ_t Cᵏ_t x_t / (x̂_t + x°_t), the load's share of the layer's cost by its share of consumption, hour by hour."""

    hours: np.ndarray
    ex_ante: bool = True

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        """Linear in x around x̂. Posted rate: the average rate at x̂ times x.
        Knows its share: the tangent of Cᵏ x/(x + x°) at x̂, slope Cᵏ x°/(x̂ + x°)².
        Both equal the exact charge when x = x̂, as at settlement."""
        rate = _divide(
            pool, x_hat + x_other
        )  # the average rate at x̂; zero outside the layer's hours
        if not knows_share:
            return cp.sum(cp.multiply(rate, x))
        slope = _divide(rate * x_other, x_hat + x_other)  # Cᵏ x° / (x̂ + x°)²
        return np.sum(rate * x_hat) + cp.sum(cp.multiply(slope, x - x_hat))

    def marginal(self, x, x_other, pool, price):
        """∂Bᵏ/∂x at settlement (x̂ = x), holding Cᵏ fixed: Cᵏ x° / (x + x°)².
        Exact for an ex-ante pool. For an ex-post pool the term
        (∂Cᵏ/∂x)·x/(x + x°) is missing; it needs ∂μ/∂d, the price-setter's map."""
        return _divide(_divide(pool, x + x_other) * x_other, x + x_other)


@dataclass(frozen=True)
class TwoPart:
    """Bᵏ = φ x + T. The marginal rate is φ = phi · price per hour (γμ_t on
    reserve, price = μ; on investment price = 1 so φ = phi in $/MWh). The lump
    sum T is the load's share, by its believed base x̂, of what φ leaves of the
    pool, so the layer still collects Cᵏ; or ``T`` if given."""

    hours: np.ndarray
    ex_ante: bool = True
    phi: float = 0.0
    T: float | None = None

    def rate(self, price):
        return self.phi * np.asarray(price, float)

    def lump_sum(self, x_hat, x_other, pool, price) -> float:
        if self.T is not None:
            return self.T
        residual = float(np.sum(pool - self.rate(price) * (x_hat + x_other)))
        return residual * float(np.sum(x_hat)) / float(np.sum(x_hat) + np.sum(x_other))

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        return cp.sum(cp.multiply(self.rate(price), x)) + self.lump_sum(
            x_hat, x_other, pool, price
        )

    def marginal(self, x, x_other, pool, price):
        return self.rate(price)


# ----------------------------------------------------------------------------
# tariff
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Tariff:
    """One charge form per layer, plus two slots: ``credit`` pays a load that
    sells reserve μᵀσ; ``exempt_curtailable`` frees a curtailable load from the
    reserve charge, since its headroom displaces procured reserve."""

    energy: Marginal | Share | TwoPart
    reserve: Marginal | Share | TwoPart
    investment: Marginal | Share | TwoPart
    credit: bool = True
    exempt_curtailable: bool = False
    name: str = ""

    def _layers(self, realized: Dispatch, b0: Dispatch) -> list:
        """The three layers as (name, form, pool, price). The pool is hourly and
        comes from ``b0`` if the form is ex ante, else from ``realized``; the
        price is always the realized one."""
        energy = b0 if self.energy.ex_ante else realized
        reserve = b0 if self.reserve.ex_ante else realized
        investment = b0 if self.investment.ex_ante else realized
        hours = self.investment.hours
        return [
            ("energy", self.energy, energy.C_energy, realized.lam),
            ("reserve", self.reserve, reserve.C_res, realized.mu),
            (
                "investment",
                self.investment,
                investment.C_inv * hours / hours.sum(),
                np.ones(hours.shape),
            ),
        ]

    def bill(
        self,
        d,
        sigma,
        realized: Dispatch,
        d_other: np.ndarray,
        b0: Dispatch | None = None,
        d_hat=None,
        own: bool = True,
        knows_share: bool = False,
    ) -> dict:
        """B = Σ_k Bᵏ, the reserve payment as a negative layer, as cvxpy expressions.
        ``realized`` is the dispatch at the bid and prices energy and the credit;
        ``b0`` is the dispatch at (δ, 0), the source of ex-ante pools. Inside a
        price-taker's objective both are its belief, ``d_hat`` (x̂) is required, and
        ``knows_share`` says whether it knows its own share (``Share.charge``).
        ``own=False`` bills everyone else as one load: no credit, no exemption."""
        b0 = (
            realized if b0 is None else b0
        )  # one dispatch given: the load's belief plays both roles
        if d_hat is None:
            if isinstance(d, cp.Expression):
                raise ValueError(
                    "a price-taker's objective needs d_hat, the consumption its rate is set at"
                )
            d_hat = np.asarray(d, float)
        out = {}
        for k, form, pool, price in self._layers(realized, b0):
            x, x_hat, x_other = (
                _base(form.hours, d),
                form.hours * d_hat,
                form.hours * d_other,
            )
            out[k] = form.charge(x, x_hat, x_other, pool, price, knows_share)
        if own and self.exempt_curtailable and realized.curtailable:
            out["reserve"] = cp.Constant(0.0)
        out["credit"] = (
            -cp.sum(cp.multiply(realized.mu, sigma))
            if (own and self.credit)
            else cp.Constant(0.0)
        )
        return out

    def marginal(
        self,
        d: np.ndarray,
        realized: Dispatch,
        d_other: np.ndarray,
        b0: Dispatch | None = None,
    ) -> dict[str, np.ndarray]:
        """∂Bᵏ/∂d_t per layer at settlement, for the alignment metric."""
        b0 = realized if b0 is None else b0
        out = {}
        for k, form, pool, price in self._layers(realized, b0):
            out[k] = (
                form.marginal(form.hours * d, form.hours * d_other, pool, price)
                * form.hours
            )
        if self.exempt_curtailable and realized.curtailable:
            out["reserve"] = np.zeros_like(d)
        out["credit"] = np.zeros_like(d)
        return out


def _divide(a, b) -> np.ndarray:
    """a / b where b > 0, else 0: the hours outside a layer's window have no base and no cost."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.divide(a, b, out=np.zeros_like(b), where=b > 0)


def _base(hours: np.ndarray, d):
    """The consumption in the layer's hours, hours ∘ d: a number for a number, an expression for a variable."""
    return cp.multiply(hours, d) if isinstance(d, cp.Expression) else hours * d


def total(bill: dict):
    return sum(bill.values())


# ----------------------------------------------------------------------------
# today's tariff τ₀
# ----------------------------------------------------------------------------
def named_tariffs(scenario: Scenario) -> dict[str, Tariff]:
    """τ₀: energy at the margin, reserve and investment split ex ante, investment on the peak hour t*."""
    every_hour, peak = np.ones(scenario.T), peak_hour(scenario.d_sys)
    tau_0 = Tariff(  # ERCOT and PJM today
        energy=Marginal(hours=every_hour, ex_ante=False),
        reserve=Share(hours=every_hour, ex_ante=True),
        investment=Share(hours=peak, ex_ante=True),
        credit=True,
        exempt_curtailable=False,
        name="tau_0",
    )
    return {t.name: t for t in (tau_0,)}
