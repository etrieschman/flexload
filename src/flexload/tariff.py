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
otherwise from the dispatch at the bid, ``dispatch``. Each layer's form sets it.
The reserve payment μᵀσ to a load that sells reserve is a credit layer of the
bill. ``exempt_curtailable`` frees a curtailable load from the reserve charge.

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

    hours: np.ndarray  # the price is always the one at the bid, so there is no ex_ante slot

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
        slope = self.marginal(x_hat, x_other, pool, price)  # Cᵏ x° / (x̂ + x°)²
        return np.sum(rate * x_hat) + cp.sum(cp.multiply(slope, x - x_hat))

    def marginal(self, x, x_other, pool, price):
        """∂Bᵏ/∂x at settlement (x̂ = x), holding Cᵏ fixed: Cᵏ x° / (x + x°)².
        Exact for an ex-ante pool. For an ex-post pool the term
        (∂Cᵏ/∂x)·x/(x + x°) is missing; it needs ∂μ/∂d, the price-setter's map."""
        return _divide(_divide(pool, x + x_other) * x_other, x + x_other)


@dataclass(frozen=True)
class TwoPart:
    """Bᵏ = φ x + T. The marginal rate is φ = phi · price per hour (on
    reserve price = μ; on investment price = 1, so φ = phi in $/MWh). The lump
    sum T is the load's share, by its believed base x̂, of what φ leaves of the
    pool, so the layer still collects Cᵏ; or ``T`` if given."""

    hours: np.ndarray
    ex_ante: bool = True
    phi: float = 0.0
    T: float | None = None

    def lump_sum(self, x_hat, x_other, pool, price) -> float:
        if self.T is not None:
            return self.T
        residual = float(np.sum(pool - self.phi * price * (x_hat + x_other)))
        return residual * float(np.sum(x_hat)) / float(np.sum(x_hat) + np.sum(x_other))

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        return cp.sum(cp.multiply(self.phi * price, x)) + self.lump_sum(
            x_hat, x_other, pool, price
        )

    def marginal(self, x, x_other, pool, price):
        return self.phi * price


# ----------------------------------------------------------------------------
# tariff
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Tariff:
    """One charge form per layer, the credit μᵀσ to a load that sells reserve,
    and one slot: ``exempt_curtailable`` frees a curtailable load from the
    reserve charge, since its headroom displaces procured reserve."""

    energy: Marginal | Share | TwoPart
    reserve: Marginal | Share | TwoPart
    investment: Marginal | Share | TwoPart
    exempt_curtailable: bool = False
    name: str = ""

    def _layers(self, dispatch: Dispatch, b0: Dispatch) -> list:
        """The billed layers as (name, form, pool, price). The pool is hourly
        and comes from ``b0`` if the form is ex ante, else from ``dispatch``;
        the price is always the one at the bid."""
        energy, reserve, investment = (
            b0 if getattr(form, "ex_ante", False) else dispatch for form in (self.energy, self.reserve, self.investment)
        )
        hours = self.investment.hours
        return [
            ("energy", self.energy, energy.C_energy, dispatch.lam),
            ("reserve", self.reserve, reserve.C_res, dispatch.mu),
            ("investment", self.investment, investment.C_inv * hours / hours.sum(), np.ones(hours.shape)),
        ]

    def bill(
        self,
        d,
        sigma,
        dispatch: Dispatch,
        d_other: np.ndarray,
        b0: Dispatch | None = None,
        d_hat=None,
        knows_share: bool = False,
    ) -> dict:
        """B = Σ_k Bᵏ, the reserve payment as a negative layer, as cvxpy expressions.
        ``dispatch`` is the dispatch at the bid and prices energy and the credit;
        ``b0`` is the dispatch at (δ, 0), the source of ex-ante pools, fixed under
        every belief. Inside a price-taker's objective ``dispatch`` is its belief,
        ``d_hat`` (x̂) is required, and ``knows_share`` says whether it knows its
        own share (``Share.charge``). The bill is the load's: everyone else's is
        the same call with d and d° swapped, σ = 0 (so no credit) and the tariff
        without the curtailable exemption, ``settle(own=False)``."""
        b0 = (
            dispatch if b0 is None else b0
        )  # one dispatch given: the load's belief plays both roles
        if d_hat is None:
            if isinstance(d, cp.Expression):
                raise ValueError(
                    "a price-taker's objective needs d_hat, the consumption its rate is set at"
                )
            d_hat = np.asarray(d, float)
        out = {k: cp.Constant(0.0) for k in LAYERS}
        for k, form, pool, price in self._layers(dispatch, b0):
            x, x_hat, x_other = (
                cp.multiply(form.hours, d),
                form.hours * d_hat,
                form.hours * d_other,
            )
            out[k] = form.charge(x, x_hat, x_other, pool, price, knows_share)
        if self.exempt_curtailable and dispatch.curtailable:
            out["reserve"] = cp.Constant(0.0)
        out["credit"] = -cp.sum(cp.multiply(dispatch.mu, sigma))
        return out

    def marginal(
        self,
        d: np.ndarray,
        dispatch: Dispatch,
        d_other: np.ndarray,
        b0: Dispatch | None = None,
    ) -> dict[str, np.ndarray]:
        """∂Bᵏ/∂d_t per layer at settlement, for the alignment metric."""
        b0 = dispatch if b0 is None else b0
        out = {k: np.zeros_like(d) for k in LAYERS}
        for k, form, pool, price in self._layers(dispatch, b0):
            out[k] = (
                form.marginal(form.hours * d, form.hours * d_other, pool, price)
                * form.hours
            )
        if self.exempt_curtailable and dispatch.curtailable:
            out["reserve"] = np.zeros_like(d)
        out["credit"] = np.zeros_like(d)
        return out


def _divide(a, b) -> np.ndarray:
    """a / b where b > 0, else 0: outside a layer's window the base and the cost are both zero."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.divide(a, b, out=np.zeros_like(b), where=b > 0)


# ----------------------------------------------------------------------------
# today's tariff τ₀
# ----------------------------------------------------------------------------
def named_tariffs(scenario: Scenario) -> dict[str, Tariff]:
    """τ₀, today's tariff, the same under every construct: energy at the
    margin, reserve split ex ante in every hour, and the investment layer split
    ex ante on the peak hour t*, as a capacity charge does. Where the fleet's
    rent pays its cost the investment pool is zero and the layer bills nothing:
    ERCOT at the calibrated reserve margin, as in an energy-only market."""
    every_hour, peak = np.ones(scenario.T), peak_hour(scenario.d_sys)
    return {
        "tau_0": Tariff(
            energy=Marginal(hours=every_hour),
            reserve=Share(hours=every_hour, ex_ante=True),
            investment=Share(hours=peak, ex_ante=True),
            exempt_curtailable=False,
            name="tau_0",
        )
    }
