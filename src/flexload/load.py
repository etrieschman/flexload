"""The load: its type θ, its value V, its offer price cˢ, and its three
strategies, B0 (inflexible: bid δ, offer nothing), R (best response under a
belief), and B1 (the planner's optimum).

The price-taker's best response is a QP: every tilde quantity in the memo is a
constant or the bid itself, so the bill is linear in (d, σ) and V is a concave
quadratic. The exogenous and consistent price-takers differ only in where the
constants come from: the clearing at (δ, 0), or the fixed point
:func:`fixed_point` closes. The price-setter is a different, bilevel problem and
is not built yet (see CLAUDE.md, next steps).
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from ._expr import dot, mul, sum_squares, where
from .market import Dispatch, Market
from .scenario import Scenario
from .tariff import Menu, Tariff, total


# ----------------------------------------------------------------------------
# type
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class LoadType:
    """θ = (ψ, β, A, p) plus whether it sells reserve. ``A`` is (M, T) with
    A_mt = 1[t ∈ window m]: rows are disjoint commitment windows over which
    consumption is conserved (zero rows: elastic; one row of ones: weekly;
    identity: inflexible)."""

    psi: float  # weight on following δ, $/MW²h
    beta: float  # tolerated deviation as a fraction of δ
    A: np.ndarray  # (M, T) energy-conservation windows
    p: float  # believed probability that offered reserve is called
    sells_reserve: bool = False
    name: str = ""


def windows_elastic(T: int) -> np.ndarray:
    return np.zeros((0, T))


def windows_weekly(T: int) -> np.ndarray:
    return np.ones((1, T))


def windows_daily(T: int, hours_per_day: int = 24) -> np.ndarray:
    days = T // hours_per_day
    A = np.zeros((days, T))
    for m in range(days):
        A[m, m * hours_per_day : (m + 1) * hours_per_day] = 1.0
    return A


def windows_inflexible(T: int) -> np.ndarray:
    return np.eye(T)


def named_types(T: int, psi: float = 1.0) -> dict[str, LoadType]:
    """Named points in the type space, from the large-load catalog. Parameter
    values are placeholders recorded in docs/assumptions.md."""
    return {
        "inflexible": LoadType(psi, 0.0, windows_inflexible(T), 0.0, False, "inflexible"),
        "mover": LoadType(psi, 0.2, windows_weekly(T), 0.0, False, "mover"),
        "clr": LoadType(psi, 0.2, windows_weekly(T), 0.02, True, "clr"),
        "ers": LoadType(psi, 0.05, windows_weekly(T), 0.2, True, "ers"),
    }


# ----------------------------------------------------------------------------
# value and offer price
# ----------------------------------------------------------------------------
def c_s(theta: LoadType, delta: np.ndarray) -> np.ndarray:
    """The cost of standing ready, cˢ_t = 2 p ψ β δ_t: the marginal loss at the
    largest shed the load tolerates, times the chance it is called."""
    return 2.0 * theta.p * theta.psi * theta.beta * np.asarray(delta, dtype=float)


def V(theta: LoadType, delta: np.ndarray, d, sigma):
    """V(d, σ) = −ψ‖d − δ‖² − cˢᵀσ, with σ the *cleared* reserve. Numbers or cvxpy."""
    return -theta.psi * sum_squares(d - delta) - dot(c_s(theta, delta), sigma)


def feasible(theta: LoadType, delta: np.ndarray, d, sigma) -> list:
    """𝒟_θ: tolerance, energy conservation, and the reserve bound, as cvxpy constraints."""
    cons = [d >= 0.0, d - delta <= theta.beta * delta, delta - d <= theta.beta * delta]
    if theta.A.shape[0] > 0:
        cons.append(theta.A @ d == theta.A @ delta)
    if theta.sells_reserve:
        cons += [sigma >= 0.0, d - sigma >= (1.0 - theta.beta) * delta]
    return cons


# ----------------------------------------------------------------------------
# R: best response of a price-taker
# ----------------------------------------------------------------------------
def best_response(
    theta: LoadType,
    tariff: Tariff | Menu,
    delta: np.ndarray,
    lam: np.ndarray,
    mu: np.ndarray,
    C_res: np.ndarray,
    C_inv: float,
    d_other: np.ndarray,
    d_hat: np.ndarray | None = None,
    curtailed: np.ndarray | None = None,
    solver: str = "CLARABEL",
) -> tuple[np.ndarray, np.ndarray]:
    """max V(d̃, σ̃) − B(d̃, σ̃; λ̄, μ̄; τ) over 𝒟_θ, taking prices, pools and the
    rate at ``d_hat`` as given (``d_hat`` defaults to δ, the exogenous
    price-taker). The offer clears where μ̄ ≥ cˢ. ``curtailed`` is the hours the
    load believes it will be curtailed to dᶠⁱʳᵐ (``None``: it ignores
    curtailment). Under a ``Menu`` the load elects the option with the highest
    payoff. Returns (d, σ)."""
    if isinstance(tariff, Menu):
        best = None
        for option in tariff.options:
            d, sigma = best_response(theta, option, delta, lam, mu, C_res, C_inv, d_other, d_hat, curtailed, solver)
            payoff = _payoff(theta, option, delta, d, sigma, lam, mu, C_res, C_inv, d_other, d_hat, curtailed)
            if best is None or payoff > best[0]:
                best = (payoff, d, sigma)
        return best[1], best[2]

    T = delta.shape[0]
    d_hat = delta if d_hat is None else np.asarray(d_hat, dtype=float)
    d = cp.Variable(T)
    # a curtailable load does not offer reserve: the same MW cannot be both σ and headroom (memo)
    sells = theta.sells_reserve and tariff.curtail is None
    sigma = cp.Variable(T) if sells else np.zeros(T)
    d_tilde, sigma_tilde = _tilde(theta, tariff, delta, d, sigma, mu, curtailed)
    objective = V(theta, delta, d_tilde, sigma_tilde) - total(
        tariff.bill(d_tilde, sigma_tilde, lam, mu, C_res, C_inv, d_other, d_hat=d_hat)
    )
    constraints = feasible(theta, delta, d, sigma) if sells else feasible(
        LoadType(theta.psi, theta.beta, theta.A, theta.p, False, theta.name), delta, d, sigma
    )
    if sells:
        # offer nothing where the offer is believed not to clear (memo, Section 2.3)
        clears = np.asarray(mu) >= c_s(theta, delta) - 1e-12
        if not clears.all():
            constraints.append(sigma[~clears] == 0.0)
    problem = cp.Problem(cp.Maximize(objective), constraints)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"best response failed: {problem.status}")
    sigma_value = np.asarray(sigma.value) if sells else sigma
    return np.asarray(d.value), np.maximum(sigma_value, 0.0)


def _tilde(theta, tariff, delta, d, sigma, mu, curtailed):
    """The memo's tilde quantities for a price-taker: σ̃ᶜˡʳ = σ 1[μ̄ ≥ cˢ],
    d̃ = dᶠⁱʳᵐ where curtailment is anticipated, the bid elsewhere."""
    clears = (np.asarray(mu) >= c_s(theta, delta) - 1e-12).astype(float)
    sigma_tilde = mul(clears, sigma) if (theta.sells_reserve and tariff.curtail is None) else sigma
    if curtailed is None or tariff.curtail is None:
        return d, sigma_tilde
    d_firm = (1.0 - tariff.curtail.beta_firm) * delta
    mask = np.asarray(curtailed, dtype=bool) & tariff.curtail.hours
    return where(mask, d_firm, d), sigma_tilde


def _payoff(theta, tariff, delta, d, sigma, lam, mu, C_res, C_inv, d_other, d_hat, curtailed) -> float:
    d_tilde, sigma_tilde = _tilde(theta, tariff, delta, d, sigma, mu, curtailed)
    return float(
        V(theta, delta, d_tilde, sigma_tilde)
        - total(tariff.bill(d_tilde, sigma_tilde, lam, mu, C_res, C_inv, d_other, d_hat=d_hat))
    )


# ----------------------------------------------------------------------------
# the consistent price-taker: a fixed point on prices, pools and the rate base
# ----------------------------------------------------------------------------
def fixed_point(
    theta: LoadType,
    tariff: Tariff | Menu,
    market: Market,
    scenario: Scenario,
    anticipate_curtailment: bool = False,
    tol: float = 1e-3,
    max_iter: int = 50,
    damping: float | None = 0.5,
) -> tuple[np.ndarray, np.ndarray, Dispatch, list[float]]:
    """Solve the price-taker's QP at the current constants, clear at the
    response, update the constants, repeat until the bid stops moving. Returns
    (d, σ, the dispatch at the response, the history of bid changes).

    Each step moves a fraction ``damping`` of the way to the new response.
    ``damping=None`` uses the harmonic step 1/(k+1), which averages out the
    two-cycles a step-function merit order produces (the load leaves a scarcity
    hour, the scarcity vanishes, the load returns) at the cost of slow
    convergence on well-behaved maps. If ``history[-1]`` is above ``tol`` the map
    did not settle; under scarcity that is a finding about price-taking."""
    delta, T = scenario.delta, scenario.T
    offer = c_s(theta, delta)
    dispatch = market.clear(scenario, tariff, delta, np.zeros(T), offer)
    d_hat = delta.copy()
    lam, mu = dispatch.lam, dispatch.mu
    C_res, C_inv = market.pools(dispatch, scenario)
    history: list[float] = []
    d_prev, sigma_prev = delta.copy(), np.zeros(T)
    for k in range(max_iter):
        curtailed = (market.kappa(dispatch) >= market.voll) if anticipate_curtailment else None
        d, sigma = best_response(theta, tariff, delta, lam, mu, C_res, C_inv, scenario.d_other, d_hat, curtailed)
        step = damping if damping is not None else 1.0 / (k + 1)
        d = step * d + (1.0 - step) * d_prev
        sigma = step * sigma + (1.0 - step) * sigma_prev
        change = float(np.max(np.abs(d - d_prev)) + np.max(np.abs(sigma - sigma_prev)))
        history.append(change)
        dispatch = market.clear(scenario, tariff, d, sigma, offer)
        lam, mu = dispatch.lam, dispatch.mu
        C_res, C_inv = market.pools(dispatch, scenario)
        d_hat, d_prev, sigma_prev = d, d, sigma
        if change < tol:
            break
    return d_prev, sigma_prev, dispatch, history


# ----------------------------------------------------------------------------
# B1: the planner
# ----------------------------------------------------------------------------
def planner(theta: LoadType, market: Market, scenario: Scenario, tariff: Tariff | None = None, solver: str = "CLARABEL") -> tuple[np.ndarray, np.ndarray, float]:
    """max_{(d, σ) ∈ 𝒟_θ} V(dᶜᵘʳᵗ, σ) − C_sys over the load's and the operator's
    variables in one program. With a curtailment ``tariff`` the planner has the
    same instrument the operator has under it: it may serve dᶜᵘʳᵗ between the
    tariff's firm level and the bid in the curtailable hours, and the headroom
    counts toward reserve. Without one, dᶠⁱʳᵐ = d. The load's offer cost is in
    both V and the LP objective (it offers at cost), so it is added back once.
    Returns (d, σ, S*)."""
    T, J = scenario.T, scenario.J
    delta = scenario.delta
    offer = c_s(theta, delta)
    curtail = tariff.curtail if tariff is not None else None
    sells = theta.sells_reserve and curtail is None
    d = cp.Variable(T)
    sigma = cp.Variable(T) if sells else np.zeros(T)
    u = cp.Variable((J, T), nonneg=True)
    r = cp.Variable((J, T), nonneg=True)
    sigma_clr = cp.Variable(T, nonneg=True) if sells else np.zeros(T)
    y = cp.Variable(J, nonneg=True) if market.long_run else scenario.nameplate
    z = cp.Variable((market.curve(scenario).widths.size, T), nonneg=True) if market.reserve == "ercot" else None
    shed = cp.Variable(T, nonneg=True)

    extra = []
    if curtail is not None:
        h = curtail.hours
        firm_level = (1.0 - curtail.beta_firm) * delta
        d_curt_var = cp.Variable(T)
        d_curt = where(h, d_curt_var, d)
        d_firm = where(h, firm_level, d)
        extra = [d_curt_var[h] >= firm_level[h], d_curt_var[h] <= d[h]]
    else:
        d_curt, d_firm = d, d

    cost = market.system_cost(scenario, u, r, sigma_clr, offer, y, z, shed)
    welfare = V(theta, delta, d_curt, sigma_clr) - cost + dot(offer, sigma_clr)
    cons = market.constraints(scenario, sigma, d_firm, u, r, sigma_clr, d_curt, y, z, shed)
    load_type = theta if sells else LoadType(theta.psi, theta.beta, theta.A, theta.p, False, theta.name)
    problem = cp.Problem(cp.Maximize(welfare), list(cons.values()) + feasible(load_type, delta, d, sigma) + extra)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"planner failed: {problem.status}")
    sigma_value = np.maximum(np.asarray(sigma.value), 0.0) if sells else sigma
    return np.asarray(d.value), sigma_value, float(problem.value)
