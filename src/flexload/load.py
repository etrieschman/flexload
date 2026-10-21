"""The load: its type θ, value V, offer price c^σ, and three strategies.
B0 bids δ and offers nothing. R best-responds to a tariff under a belief.
B1 is the planner's optimum.

A price-taker's belief is a ``Dispatch``: it takes λ, μ and each layer's cost as given,
and the rate at its believed consumption ``d_hat``. Its bill is then linear in
(d, σ) and the best response is a QP. The exogenous price-taker's belief is the
clearing at (δ, 0); the consistent one's is the fixed point ``fixed_point``
closes. A price-setter's belief is the market itself (bilevel, not built).
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from .system import Dispatch, Market, Scenario
from .tariff import Menu, Tariff, total


# ----------------------------------------------------------------------------
# θ
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class LoadType:
    """θ = (ψ, β, A, p, sells reserve, curtailable). (ψ, β, A, p) are private:
    the weight on following δ, the tolerated deviation, the blocks of hours over
    which energy is conserved (``A`` is (M, T), one row per block), and the
    believed chance a sold MW is called. The designations are public.
    ``sells_reserve``: offers σ at c^σ. ``curtailable``: declares a firm level
    before the window; the operator may curtail it to that level where serving it
    costs more than VOLL, unpaid, in exchange for its connection. It offers no
    reserve, since the same MW cannot be both headroom and σ."""

    psi: float  # weight on following δ, $/MW²h
    beta: float  # tolerated deviation as a fraction of δ
    A: np.ndarray  # (M, T) energy-conservation windows
    p: float  # believed probability that offered reserve is called
    sells_reserve: bool = False
    curtailable: bool = False
    name: str = ""

    @property
    def offers(self) -> bool:
        return self.sells_reserve and not self.curtailable

    def d_firm(self, delta: np.ndarray) -> np.ndarray | None:
        """The declared firm level, a MW amount constant over the window:
        dᶠⁱʳᵐ = (1 − β) min_t δ_t, the largest cut the type tolerates in its
        lowest hour. None for a load that is not curtailable."""
        return np.full(delta.shape, (1.0 - self.beta) * float(np.min(delta))) if self.curtailable else None


def blocks(T: int, hours: int | None) -> np.ndarray:
    """A for blocks of ``hours`` each: T → one block (energy conserved over the
    window, A = 1ᵀ), 1 → every hour (inflexible, A = I), None → no block
    (elastic, A = 0)."""
    if hours is None:
        return np.zeros((0, T))
    starts = range(0, T, hours)
    return np.array([[1.0 if s <= t < s + hours else 0.0 for t in range(T)] for s in starts])


# Placeholder parameter values (docs/assumptions.md #16). Levels, not estimates.
PSI = {"low": 0.5, "medium": 1.0, "high": 2.0}  # $/MW²h
BETA = {"low": 0.05, "medium": 0.2, "high": 0.5}
P = {"low": 0.02, "high": 0.2}
BUSINESS = {  # (ψ, β, A): what the load is, behind its designation
    "data_center": ("high", "medium", "window"),  # shifts batch jobs, keeps the day's compute
    "bitcoin_mine": ("low", "high", "elastic"),  # curtailed hashing is lost, not shifted
}


def named_types(T: int, business: str = "data_center") -> dict[str, LoadType]:
    """θ₀…θ₄ of the report's type table, run as a ``business``: ``"data_center"``
    or ``"bitcoin_mine"`` sets (ψ, β, A) for the rows that sweep them. The
    emergency row is fixed at (medium, low, elastic, p high)."""
    psi, beta, a = BUSINESS[business]
    A = {"window": blocks(T, T), "elastic": blocks(T, None)}
    return {
        "inflexible": LoadType(PSI[psi], 0.0, blocks(T, 1), 0.0, name="inflexible"),
        "mover": LoadType(PSI[psi], BETA[beta], A[a], 0.0, name="mover"),
        "controllable": LoadType(PSI[psi], BETA[beta], A[a], P["low"], sells_reserve=True, name="controllable"),
        "emergency": LoadType(PSI["medium"], BETA["low"], A["elastic"], P["high"], sells_reserve=True, name="emergency"),
        "curtailable": LoadType(PSI[psi], BETA[beta], A[a], 0.0, curtailable=True, name="curtailable"),
    }


# ----------------------------------------------------------------------------
# V, cˢ, 𝒟_θ
# ----------------------------------------------------------------------------
def c_sigma(theta: LoadType, delta: np.ndarray) -> np.ndarray:
    """c^σ_t = 2 p ψ β δ_t, the cost of standing ready: the marginal loss at the
    largest shed the load tolerates, times the chance p it is called."""
    return 2.0 * theta.p * theta.psi * theta.beta * delta


def V(theta: LoadType, delta: np.ndarray, d, sigma):
    """V(d, σ) = −ψ‖d − δ‖² − c^σᵀσ, with σ the cleared reserve."""
    return -theta.psi * cp.sum_squares(d - delta) - cp.sum(cp.multiply(c_sigma(theta, delta), sigma))


def feasible(theta: LoadType, delta: np.ndarray, d, sigma) -> list:
    """𝒟_θ: tolerance, energy conservation, and the offer bound."""
    cons = [d >= 0.0, d - delta <= theta.beta * delta, delta - d <= theta.beta * delta]
    if theta.A.shape[0] > 0:
        cons.append(theta.A @ d == theta.A @ delta)
    if theta.offers:
        cons += [sigma >= 0.0, d - sigma >= (1.0 - theta.beta) * delta]
    return cons


# ----------------------------------------------------------------------------
# R
# ----------------------------------------------------------------------------
def payoff(theta: LoadType, tariff: Tariff, scenario: Scenario, belief: Dispatch, d, sigma, d_hat: np.ndarray, curtailed: np.ndarray | None = None):
    """V(d̃, σ̃) − B(d̃, σ̃) under the belief. The memo's tilde quantities for a
    price-taker: σ̃ = σ 𝟙[μ̄ ≥ c^σ], and d̃ = dᶠⁱʳᵐ in the hours ``curtailed`` where the
    load anticipates curtailment, the bid elsewhere."""
    delta = scenario.delta
    clears = (belief.mu >= c_sigma(theta, delta) - 1e-12).astype(float)
    sigma_t = cp.multiply(clears, sigma) if theta.offers else sigma
    d_t = d
    if curtailed is not None and theta.curtailable:
        m = np.asarray(curtailed, float)
        d_t = cp.multiply(1.0 - m, d) + m * theta.d_firm(delta)
    return V(theta, delta, d_t, sigma_t) - total(tariff.bill(d_t, sigma_t, belief, scenario.d_other, d_hat=d_hat))


def best_response(theta: LoadType, tariff: Tariff, scenario: Scenario, belief: Dispatch, d_hat: np.ndarray | None = None, curtailed: np.ndarray | None = None, solver: str = "GUROBI") -> tuple[np.ndarray, np.ndarray]:
    """max payoff over 𝒟_θ: a QP. ``d_hat`` defaults to the belief's consumption
    (δ for the exogenous price-taker). Where the offer is believed not to clear
    the load offers nothing (memo). Returns (d, σ)."""
    T, delta = scenario.T, scenario.delta
    d_hat = belief.d if d_hat is None else d_hat
    d = cp.Variable(T)
    sigma = cp.Variable(T) if theta.offers else np.zeros(T)
    cons = feasible(theta, delta, d, sigma)
    if theta.offers:
        clears = belief.mu >= c_sigma(theta, delta) - 1e-12
        if not clears.all():
            cons.append(sigma[~clears] == 0.0)
    problem = cp.Problem(cp.Maximize(payoff(theta, tariff, scenario, belief, d, sigma, d_hat, curtailed)), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"best response failed: {problem.status}")
    return np.asarray(d.value), np.maximum(np.asarray(sigma.value), 0.0) if theta.offers else sigma


def elect(theta: LoadType, menu: Menu, scenario: Scenario, belief: Dispatch, d_hat: np.ndarray | None = None, curtailed: np.ndarray | None = None) -> Tariff:
    """The option with the highest payoff at its own best response."""
    d_hat = belief.d if d_hat is None else d_hat
    best, best_value = None, -np.inf
    for option in menu.options:
        d, sigma = best_response(theta, option, scenario, belief, d_hat, curtailed)
        value = float(payoff(theta, option, scenario, belief, d, sigma, d_hat, curtailed).value)
        if value > best_value:
            best, best_value = option, value
    return best


def fixed_point(theta: LoadType, tariff: Tariff, market: Market, scenario: Scenario, anticipate: bool = False, tol: float = 1e-3, max_iter: int = 50, damping: float | None = 0.5) -> tuple[np.ndarray, np.ndarray, Dispatch, Dispatch, list[float]]:
    """The consistent price-taker: respond to the belief, clear at the response,
    make that the belief, repeat until the bid stops moving. Each step moves a
    fraction ``damping`` toward the new response; ``None`` is the harmonic step
    1/(k+1), which averages out the two-cycles a step merit order produces at
    scarcity hours. Returns (d, σ, dispatch at the response, the belief the
    final bid answered to, bid changes). If ``history[-1]`` is above ``tol`` the
    map did not settle: price-taking is the wrong model there (RQ3b)."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    belief = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    d_prev, sigma_prev, history = delta.copy(), np.zeros(T), []
    for k in range(max_iter):
        curtailed = (market.kappa(belief) >= market.voll) if anticipate else None
        d, sigma = best_response(theta, tariff, scenario, belief, d_prev, curtailed)
        step = damping if damping is not None else 1.0 / (k + 1)
        d, sigma = step * d + (1 - step) * d_prev, step * sigma + (1 - step) * sigma_prev
        history.append(float(np.abs(d - d_prev).max() + np.abs(sigma - sigma_prev).max()))
        believed, belief = belief, market.clear(scenario, d, sigma, offer, d_firm)
        d_prev, sigma_prev = d, sigma
        if history[-1] < tol:
            break
    return d_prev, sigma_prev, belief, believed, history


# ----------------------------------------------------------------------------
# B1
# ----------------------------------------------------------------------------
def planner(theta: LoadType, market: Market, scenario: Scenario, solver: str = "GUROBI") -> tuple[np.ndarray, np.ndarray, float]:
    """max_{(d, σ) ∈ 𝒟_θ} V(d, σᶜˡʳ) − C_sys, the load's and the operator's
    variables in one program. A curtailable type gives the planner the same
    instrument the operator has: its headroom d − (1 − β) δ counts toward
    reserve. The planner consumes what it bids; curtailment below the bid is the
    operator's scarcity action, not a scheduling device. The offer cost sits in
    V and in C_sys, so it is added back once. Returns (d, σ, S*)."""
    T, J, delta = scenario.T, scenario.J, scenario.delta
    offer = c_sigma(theta, delta)
    d = cp.Variable(T)
    sigma = cp.Variable(T) if theta.offers else np.zeros(T)
    sigma_clr = cp.Variable(T, nonneg=True) if theta.offers else np.zeros(T)
    u, r, shed = cp.Variable((J, T), nonneg=True), cp.Variable((J, T), nonneg=True), cp.Variable(T, nonneg=True)
    y = cp.Variable(J, nonneg=True) if market.long_run else scenario.nameplate
    z = cp.Variable((market.curve(scenario).widths.size, T), nonneg=True) if market.reserve == "ercot" else None
    d_firm = theta.d_firm(delta) if theta.curtailable else d
    cons = feasible(theta, delta, d, sigma) + list(market.constraints(scenario, sigma, d_firm, u, r, sigma_clr, d, y, z, shed).values())
    cost = market.system_cost(scenario, u, r, sigma_clr, offer, y, z, shed)
    welfare = V(theta, delta, d, sigma_clr) - cost + offer @ sigma_clr
    problem = cp.Problem(cp.Maximize(welfare), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"planner failed: {problem.status}")
    return np.asarray(d.value), np.maximum(np.asarray(sigma.value), 0.0) if theta.offers else sigma, float(problem.value)
