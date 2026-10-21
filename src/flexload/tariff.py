"""The operator's action τ: how the load's charge Bᵏ recovers each layer's cost
Cᵏ. The bill is B = Σₖ Bᵏ. Report §3, "Tariff".

Each layer k ∈ {energy, reserve, investment} has a charge form on a base: the
load's consumption in the hours 𝒲ᵏ, written as a weight vector w. Energy and
reserve have an hourly cost Cᵏ_t, so their base is w ∘ d; investment has one
cost for the window, so its base is wᵀd.

    Marginal(w)                 Bᵏ = Σ_t price_t x_t            the layer's price on each MWh
    Share(w, ex_ante)           Bᵏ = Σ_t Cᵏ_t x_t / (x̂_t + x°_t)  the load's share of the cost
    TwoPart(w, ex_ante, phi, T) Bᵏ = φ x + T                     a marginal rate plus a lump sum

x̂ is the load's believed consumption, where its charge is linearized so that
its best response is a QP. A load that takes the posted rate pays the average
rate Cᵏ/(x̂ + x°) on each MWh (the exogenous price-taker). A load that knows its
share pays along the tangent of the exact charge at x̂, slope Cᵏ x°/(x̂ + x°)²
(the consistent price-taker, ``knows_share``). At settlement x̂ = x and the
split pool is exact either way.

Slots: ``ex_ante`` reads Cᵏ from the dispatch at the load's preferred profile
(δ, 0), as ERCOT procures reserve against a forecast; otherwise from the
dispatch at the bid. ``credit`` pays a load that sells reserve μᵀσ.
``exempt_curtailable`` frees a curtailable load from the reserve charge (τ₅).

Formulas are cvxpy expressions on numbers or variables alike; read ``.value``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cvxpy as cp
import numpy as np

from .system import Dispatch, Scenario

LAYERS = ("energy", "reserve", "investment")


def peak_hour(d_sys: np.ndarray) -> np.ndarray:
    """w one-hot at the peak of ``d_sys``: the ex-ante peak hour t* when d_sys is the B0 path."""
    w = np.zeros(d_sys.shape[0])
    w[int(np.argmax(d_sys))] = 1.0
    return w


# ----------------------------------------------------------------------------
# charge forms: charge(x, x_hat, x_other, pool, price) and its derivative in x
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Marginal:
    """Bᵏ = Σ_t price_t x_t: the layer's price on each MWh. Energy under τ₀, price λ."""

    w: np.ndarray
    ex_ante: bool = False  # the price is the realized one; kept so every form has the slot

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        return cp.sum(cp.multiply(price, x))

    def marginal(self, x, x_other, pool, price) -> np.ndarray:
        return np.broadcast_to(np.asarray(price, float), np.shape(x)).astype(float)


@dataclass(frozen=True)
class Share:
    """Split pool: Bᵏ = Cᵏ · x / (x̂ + x°), the load's share of the layer's cost by
    its share of consumption. Hourly for energy and reserve, one number for investment."""

    w: np.ndarray
    ex_ante: bool = True

    def charge(self, x, x_hat, x_other, pool, price, knows_share: bool = False):
        """Linear in x around x̂. Posted rate: the average rate at x̂ times x.
        Knows its share: the tangent of Cᵏ x/(x + x°) at x̂, slope Cᵏ x°/(x̂ + x°)².
        Both equal the exact charge when x = x̂, as at settlement."""
        total = x_hat + x_other
        if not knows_share:
            return cp.sum(cp.multiply(pool / total, x))
        at_hat = np.sum(pool * x_hat / total)
        return at_hat + cp.sum(cp.multiply(pool * x_other / total**2, x - x_hat))

    def marginal(self, x, x_other, pool, price) -> np.ndarray:
        """∂Bᵏ/∂x at settlement (x̂ = x), holding Cᵏ fixed: Cᵏ x° / (x + x°)².
        Exact for an ex-ante pool. For an ex-post pool the term
        (∂Cᵏ/∂x)·x/(x + x°) is missing; it needs ∂μ/∂d, the price-setter's map."""
        return pool * x_other / (x + x_other) ** 2


@dataclass(frozen=True)
class TwoPart:
    """Bᵏ = φ x + T. The marginal rate is φ = phi · price per hour (γμ_t on
    reserve, price = μ; on investment price = 1 so φ = phi in $/MWh). The lump
    sum T is the load's share, by its believed base x̂, of what φ leaves of the
    pool, so the layer still collects Cᵏ; or ``T`` if given."""

    w: np.ndarray
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
        return cp.sum(cp.multiply(self.rate(price), x)) + self.lump_sum(x_hat, x_other, pool, price)

    def marginal(self, x, x_other, pool, price) -> np.ndarray:
        return np.broadcast_to(self.rate(price), np.shape(x)).astype(float)


# ----------------------------------------------------------------------------
# tariff
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Tariff:
    """One charge form per layer, plus two slots: ``credit`` pays a load that
    sells reserve μᵀσ; ``exempt_curtailable`` frees a curtailable load from the
    reserve charge (τ₅), since its headroom displaces procured reserve."""

    energy: Marginal | Share | TwoPart
    reserve: Marginal | Share | TwoPart
    investment: Marginal | Share | TwoPart
    credit: bool = True
    exempt_curtailable: bool = False
    name: str = ""

    def _layers(self, realized: Dispatch, ex_ante: Dispatch):
        """(name, form, base, pool, price) per layer, where base(d) is the
        consumption in the layer's hours. Energy and reserve are hourly: base
        w ∘ d, pool Cᵏ_t. Investment is one number: base wᵀd, pool Cⁱⁿᵛ. The
        base is a number for a number and an expression for a variable."""
        for k, price in (("energy", realized.lam), ("reserve", realized.mu)):
            form = getattr(self, k)
            src = ex_ante if form.ex_ante else realized
            yield k, form, (lambda d, w=form.w: cp.multiply(w, d) if isinstance(d, cp.Expression) else w * d), getattr(src, "C_energy" if k == "energy" else "C_res"), price
        form = self.investment
        src = ex_ante if form.ex_ante else realized
        yield "investment", form, (lambda d, w=form.w: w @ d), src.C_inv, 1.0

    def bill(self, d, sigma, realized: Dispatch, d_other: np.ndarray, ex_ante: Dispatch | None = None, d_hat=None, own: bool = True, knows_share: bool = False) -> dict:
        """B = Σ_k Bᵏ, the reserve payment as a negative layer, as cvxpy expressions.
        ``realized`` prices energy and the credit; each layer's cost comes from
        ``ex_ante`` or ``realized`` as the form's flag says. Inside a price-taker's
        objective both are its belief, ``d_hat`` (x̂) is required, and
        ``knows_share`` says whether it knows its own share (``Share.charge``).
        ``own=False`` bills everyone else as one load: no credit, no exemption."""
        ex_ante = realized if ex_ante is None else ex_ante
        if d_hat is None:
            if isinstance(d, cp.Expression):
                raise ValueError("a price-taker's objective needs d_hat, the consumption its rate is set at")
            d_hat = np.asarray(d, float)
        out = {}
        for k, form, base, pool, price in self._layers(realized, ex_ante):
            out[k] = form.charge(base(d), base(d_hat), base(d_other), pool, price, knows_share)
        if own and self.exempt_curtailable and realized.curtailable:
            out["reserve"] = cp.Constant(0.0)
        out["credit"] = -cp.sum(cp.multiply(realized.mu, sigma)) if (own and self.credit) else cp.Constant(0.0)
        return out

    def marginal(self, d: np.ndarray, realized: Dispatch, d_other: np.ndarray, ex_ante: Dispatch | None = None) -> dict[str, np.ndarray]:
        """∂Bᵏ/∂d_t per layer at settlement, for the alignment metric."""
        ex_ante = realized if ex_ante is None else ex_ante
        out = {}
        for k, form, base, pool, price in self._layers(realized, ex_ante):
            out[k] = form.marginal(base(d), base(d_other), pool, price) * form.w
        if self.exempt_curtailable and realized.curtailable:
            out["reserve"] = np.zeros_like(d)
        out["credit"] = np.zeros_like(d)
        return out


@dataclass(frozen=True)
class Menu:
    """The load elects one option (``load.elect``)."""

    options: tuple[Tariff, ...]
    name: str = ""


def total(bill: dict):
    return sum(bill.values())


# ----------------------------------------------------------------------------
# named tariffs: τ₀ today; τ₁…τ₅ one slot changed each (the report's table)
# ----------------------------------------------------------------------------
def named_tariffs(scenario: Scenario, gamma: float = 0.03) -> dict[str, Tariff | Menu]:
    T, every_hour, peak = scenario.T, np.ones(scenario.T), peak_hour(scenario.d_sys)
    tau_0 = Tariff(energy=Marginal(every_hour), reserve=Share(every_hour), investment=Share(peak), name="tau_0")  # ERCOT and PJM today
    tau_1 = replace(tau_0, reserve=Share(every_hour, ex_ante=False), name="tau_1")  # ex-post reserve cost
    tau_2 = replace(tau_0, reserve=TwoPart(every_hour, phi=gamma), name="tau_2")  # two-part reserve: γμ_t + T
    tau_3 = replace(tau_0, investment=Share(every_hour), name="tau_3")  # investment on all hours (PUCT 58484)
    tau_4 = replace(tau_0, investment=TwoPart(peak, phi=0.0), name="tau_4")  # two-part investment: lump sum only
    tau_5 = Menu((tau_0, replace(tau_0, exempt_curtailable=True, name="tau_5_curtailable")), name="tau_5")  # PJM Non-Firm CD
    return {t.name: t for t in (tau_0, tau_1, tau_2, tau_3, tau_4, tau_5)}
