"""The operator's action τ: what the load pays, one charge Φᵏ per layer.

Energy settles at λ. Reserve and investment are cost-share layers: a pool Cᵏ,
read off a dispatch, is split by a charge form on a base xᵏ = w ∘ d (reserve,
hour by hour) or xᵏ = wᵀd (investment, one number over a window w):

    share(w, ex_ante)          Φ = C · x / (x̂ + x°)
    two_part(w, ex_ante, phi)  Φ = φ x + T,  T set so the layer still collects C

``ex_ante`` names the dispatch the pool comes from: the one at (δ, 0) or the one
at the bid. x̂ is the consumption the average rate is set at; a price-taker takes
the rate at x̂ as given, so its bill is linear in d (the rate-taker reading). At
settlement x̂ = x and the share form is exact.

Formulas are cvxpy expressions on numbers or variables alike; read ``.value``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cvxpy as cp
import numpy as np

from .system import Dispatch, Scenario

LAYERS = ("energy", "reserve", "investment", "credit")


# ----------------------------------------------------------------------------
# windows
# ----------------------------------------------------------------------------
def all_hours(T: int) -> np.ndarray:
    return np.ones(T)


def peak_hour(d_sys: np.ndarray) -> np.ndarray:
    """One-hot at the peak of ``d_sys``."""
    w = np.zeros(d_sys.shape[0])
    w[int(np.argmax(d_sys))] = 1.0
    return w


# ----------------------------------------------------------------------------
# charge forms
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Share:
    """Φ = C · x / (x̂ + x°)."""

    w: np.ndarray
    ex_ante: bool = True

    def charge(self, x, x_hat, x_other, pool, price):
        rate = pool / (x_hat + x_other)
        return cp.sum(cp.multiply(rate, x))

    def marginal(self, x, x_other, pool, price) -> np.ndarray:
        """∂Φ/∂x at x̂ = x."""
        return pool * x_other / (x + x_other) ** 2


@dataclass(frozen=True)
class TwoPart:
    """Φ = φ x + T. φ = phi · price per hour (the memo's γμ_t on reserve, price = μ;
    on investment price = 1 so φ = phi in $/MWh). T is the load's share, by
    expected base, of what φ leaves of the pool, unless ``T`` is given."""

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

    def charge(self, x, x_hat, x_other, pool, price):
        return cp.sum(cp.multiply(self.rate(price), x)) + self.lump_sum(x_hat, x_other, pool, price)

    def marginal(self, x, x_other, pool, price) -> np.ndarray:
        return np.broadcast_to(self.rate(price), np.shape(x)).astype(float)


def share(w, ex_ante: bool = True) -> Share:
    return Share(np.asarray(w, float), ex_ante)


def two_part(w, ex_ante: bool = True, phi: float = 0.0, T: float | None = None) -> TwoPart:
    return TwoPart(np.asarray(w, float), ex_ante, phi, T)


# ----------------------------------------------------------------------------
# tariff
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Tariff:
    """One charge form per cost-share layer. ``exempt_curtailable``: a load the
    operator may curtail pays no reserve charge (τ₆), since its headroom
    displaces procured reserve."""

    reserve: Share | TwoPart
    investment: Share | TwoPart
    exempt_curtailable: bool = False
    name: str = ""

    def bill(self, d, sigma, realized: Dispatch, d_other: np.ndarray, ex_ante: Dispatch | None = None, d_hat=None, own: bool = True) -> dict:
        """B = Σ_k Φᵏ plus the reserve payment as a credit, as cvxpy expressions.
        ``realized`` prices energy and the credit; each cost-share pool comes from
        ``ex_ante`` or ``realized`` as the layer's flag says. Inside a
        price-taker's objective both are its belief and ``d_hat`` is required.
        ``own=False`` bills everyone else as one load: no credit, no exemption."""
        ex_ante = realized if ex_ante is None else ex_ante
        if d_hat is None:
            if isinstance(d, cp.Expression):
                raise ValueError("a price-taker's objective needs d_hat, the consumption its rate is set at")
            d_hat = np.asarray(d, float)
        out = {"energy": cp.sum(cp.multiply(realized.lam, d))}
        w, src = self.reserve.w, ex_ante if self.reserve.ex_ante else realized
        out["reserve"] = self.reserve.charge(cp.multiply(w, d), w * d_hat, w * d_other, src.C_res, realized.mu)
        if own and self.exempt_curtailable and realized.curtailable:
            out["reserve"] = cp.Constant(0.0)
        w, src = self.investment.w, ex_ante if self.investment.ex_ante else realized
        out["investment"] = self.investment.charge(w @ d, w @ d_hat, w @ d_other, src.C_inv, 1.0)
        out["credit"] = -cp.sum(cp.multiply(realized.mu, sigma)) if own else cp.Constant(0.0)
        return out

    def marginal(self, d: np.ndarray, realized: Dispatch, d_other: np.ndarray, ex_ante: Dispatch | None = None) -> dict[str, np.ndarray]:
        """∂Φᵏ/∂d_t per layer, for the alignment metric."""
        ex_ante = realized if ex_ante is None else ex_ante
        out = {"energy": realized.lam}
        w, src = self.reserve.w, ex_ante if self.reserve.ex_ante else realized
        out["reserve"] = self.reserve.marginal(w * d, w * d_other, src.C_res, realized.mu) * w
        if self.exempt_curtailable and realized.curtailable:
            out["reserve"] = np.zeros_like(d)
        w, src = self.investment.w, ex_ante if self.investment.ex_ante else realized
        out["investment"] = self.investment.marginal(w @ d, w @ d_other, src.C_inv, 1.0) * w
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
# named tariffs: one slot changed from τ₀ per row of the memo's table
# ----------------------------------------------------------------------------
def named_tariffs(scenario: Scenario, gamma: float = 0.03) -> dict[str, Tariff | Menu]:
    """τ₀…τ₆ for a scenario. The memo's τ₅ (a firm level) is now the curtailable
    load type, so it is not a tariff; τ₆ keeps its number."""
    T, peak = scenario.T, peak_hour(scenario.d_sys)
    tau_0 = Tariff(reserve=share(all_hours(T)), investment=share(peak), name="tau_0")
    tau_1 = replace(tau_0, reserve=share(all_hours(T), ex_ante=False), name="tau_1")  # live reserve pool
    tau_2 = replace(tau_0, reserve=two_part(all_hours(T), phi=gamma), name="tau_2")  # γμ_t + T
    tau_3 = replace(tau_0, investment=share(all_hours(T)), name="tau_3")  # all hours, not the peak
    tau_4 = replace(tau_0, investment=two_part(peak, phi=0.0), name="tau_4")  # lump sum only
    tau_6 = Menu((tau_0, replace(tau_0, exempt_curtailable=True, name="tau_6_curtailable")), name="tau_6")
    return {t.name: t for t in (tau_0, tau_1, tau_2, tau_3, tau_4, tau_6)}
