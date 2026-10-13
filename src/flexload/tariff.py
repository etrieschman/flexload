"""The operator's action τ: a function from what the load does and what clears
to money, one charge per layer.

The memo has three charge forms and every named tariff is three of them, one per
layer k ∈ {energy, reserve, investment}, plus a curtailment rule:

    marginal(w)                Φ = Σ_t λ_t x_t
    share(w, ex_ante)          Φ = C · x / (x̂ + x_other)
    two_part(w, ex_ante, phi)  Φ = φ x + T,  φ from μ, T set so the layer collects C

A **window** w is a vector of weights over hours: the base is x = diag(w) d for
a layer whose pool is hourly (reserve, C_t), and x = wᵀd for a layer whose pool
is one number (investment, C). The pool's shape decides. The operator fixes w
in advance (the ex-ante peak hour, all hours) or it is filled from the dispatch
ex post; the load's belief about an uncertain peak is a row of probabilities in
the same slot.

**ex_ante** says which dispatch the pool C is read from, the one at (δ, 0) or the
one at the bid. The tariff does not read dispatches itself: the caller computes
the pools with ``Market.pools`` from the dispatch each layer's flag names and
hands them in. Inside the load's objective the same arguments are its belief.

**x̂** (``d_hat``) is the consumption at which the average rate is set. A
price-taker takes the rate as given, so its objective uses the rate at its
believed consumption and every charge is linear in d. At settlement x̂ = x and the
share form is exact.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from ._expr import dot, is_expr, mul, sum_

LAYERS = ("energy", "reserve", "investment", "credit")


# ----------------------------------------------------------------------------
# windows
# ----------------------------------------------------------------------------
def hourly(T: int) -> np.ndarray:
    """Every hour, weight one: x_t = d_t."""
    return np.ones(T)


def all_hours(T: int) -> np.ndarray:
    """All hours summed: x = Σ_t d_t."""
    return np.ones(T)


def peak_hour(d_sys: np.ndarray) -> np.ndarray:
    """One-hot at the peak of ``d_sys``: the ex-ante peak when ``d_sys`` is the
    inflexible path, the realized peak when it is the dispatched one."""
    w = np.zeros(d_sys.shape[0])
    w[int(np.argmax(d_sys))] = 1.0
    return w


# ----------------------------------------------------------------------------
# charge forms
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Marginal:
    """Φ = Σ_t price_t x_t. The energy layer: price is λ."""

    w: np.ndarray | None = None

    def charge(self, x, x_hat, x_other, pool, price):
        return dot(price, x)

    def marginal(self, x, x_other, pool, price):
        return np.asarray(price, dtype=float)


@dataclass(frozen=True)
class Share:
    """Φ = C · x / (x̂ + x_other): the pool split in proportion to the base."""

    w: np.ndarray
    ex_ante: bool = True

    def charge(self, x, x_hat, x_other, pool, price):
        rate = _rate(pool, x_hat, x_other)
        return dot(rate, x) if np.ndim(pool) else rate * x

    def marginal(self, x, x_other, pool, price):
        """∂Φ/∂x = C · x_other / (x + x_other)², evaluated at x̂ = x."""
        total = np.asarray(x) + np.asarray(x_other)
        with np.errstate(divide="ignore", invalid="ignore"):
            out = np.where(total > 0, pool * np.asarray(x_other) / total**2, 0.0)
        return np.asarray(out, dtype=float)


@dataclass(frozen=True)
class TwoPart:
    """Φ = φ x + T. For an hourly pool φ_t = phi · μ_t (the memo's γμ_t on reserve);
    for a scalar pool φ = phi in $/MWh (the memo's 0 on investment). T is the
    load's share of what the marginal rate leaves of the pool, apportioned by
    its share of expected base, unless ``T`` is given."""

    w: np.ndarray
    ex_ante: bool = True
    phi: float = 0.0
    T: float | None = None

    def rate(self, pool, price):
        return self.phi * np.asarray(price) if np.ndim(pool) else self.phi

    def lump_sum(self, x_hat, x_other, pool, price) -> float:
        if self.T is not None:
            return self.T
        phi = self.rate(pool, price)
        residual = float(np.sum(pool - phi * (np.asarray(x_hat) + np.asarray(x_other))))
        own, total = float(np.sum(x_hat)), float(np.sum(x_hat) + np.sum(x_other))
        return residual * (own / total if total > 0 else 0.0)

    def charge(self, x, x_hat, x_other, pool, price):
        phi = self.rate(pool, price)
        linear = dot(phi, x) if np.ndim(pool) else phi * x
        return linear + self.lump_sum(x_hat, x_other, pool, price)

    def marginal(self, x, x_other, pool, price):
        phi = self.rate(pool, price)
        return np.broadcast_to(np.asarray(phi, dtype=float), np.shape(x)).copy()


def _rate(pool, x_hat, x_other):
    total = np.asarray(x_hat, dtype=float) + np.asarray(x_other, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(total > 0, np.asarray(pool, dtype=float) / total, 0.0)


def marginal(w: np.ndarray | None = None) -> Marginal:
    return Marginal(w)


def share(w: np.ndarray, ex_ante: bool = True) -> Share:
    return Share(np.asarray(w, dtype=float), ex_ante)


def two_part(w: np.ndarray, ex_ante: bool = True, phi: float = 0.0, T: float | None = None) -> TwoPart:
    return TwoPart(np.asarray(w, dtype=float), ex_ante, phi, T)


# ----------------------------------------------------------------------------
# curtailment
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Firm:
    """dᶠⁱʳᵐ_t = (1 − β_firm) δ_t in ``hours``, the bid elsewhere. With
    ``exempt_reserve`` the curtailable load pays no reserve charge (τ₆)."""

    beta_firm: float
    hours: np.ndarray  # (T,) bool
    exempt_reserve: bool = False


def firm(beta_firm: float, hours: np.ndarray, exempt_reserve: bool = False) -> Firm:
    return Firm(beta_firm, np.asarray(hours, dtype=bool), exempt_reserve)


# ----------------------------------------------------------------------------
# tariff
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Tariff:
    energy: Marginal
    reserve: Share | TwoPart
    investment: Share | TwoPart
    curtail: Firm | None = None
    name: str = ""

    # --- what the tariff tells the market ----------------------------------------
    def d_firm(self, delta: np.ndarray, d: np.ndarray) -> np.ndarray:
        if self.curtail is None:
            return np.asarray(d, dtype=float).copy()
        firm_level = (1.0 - self.curtail.beta_firm) * delta
        return np.where(self.curtail.hours, np.minimum(firm_level, d), d)

    # --- the bill ------------------------------------------------------------------
    def bill(self, d, sigma, lam, mu, C_res, C_inv, d_other, d_hat=None, own: bool = True) -> dict:
        """One charge per layer, the memo's Φᵏ(xᵏ(d); λ, μ; τ), plus the reserve
        payment as a credit. Works on numbers (settlement) or cvxpy expressions
        (the load's objective); in the latter ``d_hat`` is required. ``own=False``
        bills everyone else as one load (no credit, no exemption)."""
        if d_hat is None:
            if is_expr(d):
                raise ValueError("a price-taker's objective needs d_hat, the consumption its rate is set at")
            d_hat = d
        d_other = np.asarray(d_other, dtype=float)
        out = {}
        out["energy"] = self.energy.charge(d, d_hat, d_other, None, lam)
        w = self.reserve.w
        out["reserve"] = self.reserve.charge(mul(w, d), w * d_hat, w * d_other, np.asarray(C_res), mu)
        if own and self.curtail is not None and self.curtail.exempt_reserve:
            out["reserve"] = 0.0 * out["reserve"] if is_expr(out["reserve"]) else 0.0
        w = self.investment.w
        out["investment"] = self.investment.charge(dot(w, d), dot(w, d_hat), dot(w, d_other), float(C_inv), mu)
        out["credit"] = -dot(mu, sigma) if own else 0.0
        return out

    def marginal(self, d, sigma, lam, mu, C_res, C_inv, d_other) -> dict[str, np.ndarray]:
        """∂Φᵏ/∂d_t per layer at numbers, for the alignment metric."""
        d, d_other = np.asarray(d, dtype=float), np.asarray(d_other, dtype=float)
        out = {"energy": self.energy.marginal(d, d_other, None, lam)}
        w = self.reserve.w
        out["reserve"] = self.reserve.marginal(w * d, w * d_other, np.asarray(C_res), mu) * w
        if self.curtail is not None and self.curtail.exempt_reserve:
            out["reserve"] = np.zeros_like(d)
        w = self.investment.w
        out["investment"] = self.investment.marginal(float(w @ d), float(w @ d_other), float(C_inv), mu) * w
        out["credit"] = np.zeros_like(d)
        return out

    # --- variants ------------------------------------------------------------------
    def with_window(self, layer: str, w: np.ndarray) -> "Tariff":
        """The same tariff with one layer's window replaced: an ex-post peak at
        settlement, or the load's belief about the peak in its objective."""
        return replace(self, **{layer: replace(getattr(self, layer), w=np.asarray(w, dtype=float))})


@dataclass(frozen=True)
class Menu:
    """The load elects one option; its best response is the best over them."""

    options: tuple[Tariff, ...]
    name: str = ""


def total(bill: dict) -> float:
    return sum_(np.array([float(v) for v in bill.values()])) if not is_expr(*bill.values()) else sum(bill.values())


# ----------------------------------------------------------------------------
# named tariffs: one slot changed from τ₀ per row of the memo's table
# ----------------------------------------------------------------------------
def named_tariffs(scenario, beta_firm: float = 0.2, gamma: float = 0.03) -> dict[str, Tariff | Menu]:
    """τ₀…τ₆ for a scenario (windows need T and the ex-ante peak hour).
    ``gamma`` is the two-part marginal rate on reserve, the memo's φʳᵉˢ = γμ."""
    T = scenario.T
    peak = peak_hour(scenario.d_sys)
    tau_0 = Tariff(
        energy=marginal(),
        reserve=share(hourly(T), ex_ante=True),
        investment=share(peak, ex_ante=True),
        curtail=None,
        name="tau_0",
    )
    tau_1 = replace(tau_0, reserve=share(hourly(T), ex_ante=False), name="tau_1")
    tau_2 = replace(tau_0, reserve=two_part(hourly(T), ex_ante=True, phi=gamma), name="tau_2")
    tau_3 = replace(tau_0, investment=share(all_hours(T), ex_ante=True), name="tau_3")
    tau_4 = replace(tau_0, investment=two_part(peak, ex_ante=True, phi=0.0), name="tau_4")
    tau_5 = replace(tau_0, curtail=firm(beta_firm, peak.astype(bool)), name="tau_5")
    curtailable = replace(tau_0, curtail=firm(beta_firm, peak.astype(bool), exempt_reserve=True), name="tau_6b")
    tau_6 = Menu(options=(tau_0, curtailable), name="tau_6")
    return {t.name: t for t in (tau_0, tau_1, tau_2, tau_3, tau_4, tau_5, tau_6)}
