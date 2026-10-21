"""The load: its type θ, value V, offer price c^σ, and three strategies.
B0 bids (δ, 0). R best-responds to the tariff under a belief.
B1 is the planner's optimum. Report §3, "Flexible load".

The load bids (d_bid, sigma_bid). Dispatch returns what it consumed and what
cleared, (d, sigma). A price-taker's belief about dispatch is a ``Dispatch``:
it takes λ, μ and each layer's cost as given. Its bill is then linear in the
bid and the best response is a QP. The exogenous price-taker's belief is the
clearing at (δ, 0); the consistent one's is the fixed point ``fixed_point``
closes. A price-setter's belief is the market itself (bilevel, not built).
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from .system import Dispatch, Market, Scenario
from .tariff import Tariff, total


# ----------------------------------------------------------------------------
# θ
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class LoadType:
    """θ = (ψ, β, A, p, sells reserve, curtailable). (ψ, β, A, p) are private:
    the weight on following δ, the tolerated deviation, the blocks of hours over
    which energy is conserved (``A`` is (M, T), one row per block), and the
    believed chance a sold MW is called. The two designations are public.
    ``sells_reserve``: offers σ at c^σ. ``curtailable``: declares a firm level
    before the window; the operator may curtail it to that level where serving it
    costs more than VOLL, unpaid, in exchange for its connection. A load sells
    reserve or is curtailable, never both: a MW is headroom or σ."""

    psi: float  # weight on following δ, $/MW²h
    beta: float  # tolerated deviation as a fraction of δ
    A: np.ndarray  # (M, T) energy-conservation blocks
    p: float  # believed probability that offered reserve is called
    sells_reserve: bool = False
    curtailable: bool = False
    name: str = ""

    def __post_init__(self):
        if self.sells_reserve and self.curtailable:
            raise ValueError("a load sells reserve or is curtailable, never both")

    def d_firm(self, delta: np.ndarray) -> np.ndarray | None:
        """The declared firm level, one MW amount over the window:
        dᶠⁱʳᵐ = (1 − β) min_t δ_t, the largest cut the type tolerates in its
        lowest hour. None unless the load is curtailable."""
        if not self.curtailable:
            return None
        return np.full(delta.shape, (1.0 - self.beta) * float(np.min(delta)))


# Placeholder parameter levels (docs/assumptions.md #16).
PSI = {"low": 0.5, "medium": 1.0, "high": 2.0}  # $/MW²h
BETA = {"low": 0.05, "medium": 0.2, "high": 0.5}
P = {"low": 0.02, "high": 0.2}
BUSINESS = {  # (ψ, β, A): what the load is, behind its designation
    "data_center": (
        "high",
        "medium",
        "window",
    ),  # shifts batch jobs, keeps the day's compute
    "bitcoin_mine": (
        "low",
        "high",
        "elastic",
    ),  # curtailed hashing is lost, not shifted
}


def named_types(T: int, business: str = "data_center") -> dict[str, LoadType]:
    """θ₀…θ₄ of the report's type table, run as a ``business``, ``"data_center"``
    or ``"bitcoin_mine"``, which sets (ψ, β, A) for the rows that sweep them.
    The emergency row is fixed at (ψ medium, β low, elastic, p high). A is one
    of the report's three: 1ᵀ conserves energy over the window, 0 is elastic,
    I is inflexible."""
    psi, beta, a = BUSINESS[business]
    A = {"window": np.ones((1, T)), "elastic": np.zeros((0, T))}
    return {
        "inflexible": LoadType(PSI[psi], 0.0, np.eye(T), 0.0, name="inflexible"),
        "mover": LoadType(PSI[psi], BETA[beta], A[a], 0.0, name="mover"),
        "controllable": LoadType(
            PSI[psi],
            BETA[beta],
            A[a],
            P["low"],
            sells_reserve=True,
            name="controllable",
        ),
        "emergency": LoadType(
            PSI["medium"],
            BETA["low"],
            A["elastic"],
            P["high"],
            sells_reserve=True,
            name="emergency",
        ),
        "curtailable": LoadType(
            PSI[psi], BETA[beta], A[a], 0.0, curtailable=True, name="curtailable"
        ),
    }


# ----------------------------------------------------------------------------
# V, c^σ, 𝒟_θ
# ----------------------------------------------------------------------------
def c_sigma(theta: LoadType, delta: np.ndarray) -> np.ndarray:
    """c^σ_t = 2 p ψ β δ_t, the cost of standing ready: the marginal loss at the
    largest shed the load tolerates, times the chance p it is called."""
    return 2.0 * theta.p * theta.psi * theta.beta * delta


def V(theta: LoadType, delta: np.ndarray, d, sigma):
    """V(d, σ) = −ψ‖d − δ‖² − c^σᵀσ, on what the load consumes and what cleared."""
    return -theta.psi * cp.sum_squares(d - delta) - cp.sum(
        cp.multiply(c_sigma(theta, delta), sigma)
    )


def feasible(theta: LoadType, delta: np.ndarray, d_bid, sigma_bid) -> list:
    """𝒟_θ as cvxpy constraints: tolerance |d − δ| ≤ βδ, energy conservation
    A d = A δ, and for a load that offers reserve d − σ ≥ (1 − β) δ."""
    cons = [
        d_bid >= 0.0,
        d_bid - delta <= theta.beta * delta,
        delta - d_bid <= theta.beta * delta,
    ]
    if theta.A.shape[0] > 0:
        cons.append(theta.A @ d_bid == theta.A @ delta)
    if theta.sells_reserve:
        cons += [sigma_bid >= 0.0, d_bid - sigma_bid >= (1.0 - theta.beta) * delta]
    return cons


# ----------------------------------------------------------------------------
# R
# ----------------------------------------------------------------------------
def payoff(
    theta: LoadType,
    tariff: Tariff,
    scenario: Scenario,
    belief: Dispatch,
    b0: Dispatch,
    d_bid,
    sigma_bid,
    d_hat: np.ndarray,
    anticipate: bool,
    voll: float,
    knows_share: bool,
):
    """V(d̃, σ̃) − B(d̃, σ̃) under the belief, where the tildes are the load's
    expectation of its own dispatch: σ̃ = σ_bid where μ̃ ≥ c^σ, else 0; and, if
    a curtailable load anticipates curtailment, d̃ = dᶠⁱʳᵐ where λ̃ = c^VOLL,
    else d_bid. The belief prices the bill; ``b0``, the dispatch at (δ, 0),
    holds the ex-ante pools Ĉᵏ, fixed under every belief."""
    delta = scenario.delta
    sigma_tilde = sigma_bid
    if theta.sells_reserve:
        clears = (belief.mu >= c_sigma(theta, delta) - 1e-12).astype(float)
        sigma_tilde = cp.multiply(clears, sigma_bid)
    d_tilde = d_bid
    if anticipate and theta.curtailable:
        cut = (belief.lam >= voll - 1e-6).astype(float)
        d_tilde = cp.multiply(1.0 - cut, d_bid) + cut * theta.d_firm(delta)
    bill = tariff.bill(
        d_tilde,
        sigma_tilde,
        belief,
        scenario.d_other,
        b0,
        d_hat=d_hat,
        own=True,
        knows_share=knows_share,
    )
    return V(theta, delta, d_tilde, sigma_tilde) - total(bill)


def best_response(
    theta: LoadType,
    tariff: Tariff,
    scenario: Scenario,
    belief: Dispatch,
    b0: Dispatch,
    d_hat: np.ndarray | None = None,
    anticipate: bool = False,
    voll: float = np.inf,
    knows_share: bool = False,
    solver: str = "GUROBI",
) -> tuple[np.ndarray, np.ndarray]:
    """max payoff over 𝒟_θ: a QP. ``b0`` is the dispatch at (δ, 0), the source
    of ex-ante pools. ``d_hat`` is the consumption the bill is linearized at; it
    defaults to the belief's. ``anticipate``: a curtailable load expects to be
    cut to dᶠⁱʳᵐ where the believed λ is at ``voll``, c^VOLL. ``knows_share``:
    the load knows its charge is its share of each pool (the consistent
    price-taker); otherwise it takes the posted average rate. In the hours
    where the believed μ is below c^σ the load offers zero. Returns the bid
    (d_bid, sigma_bid)."""
    T, delta = scenario.T, scenario.delta
    d_hat = belief.d if d_hat is None else d_hat
    d_bid = cp.Variable(T)
    sigma_bid = cp.Variable(T) if theta.sells_reserve else np.zeros(T)
    cons = feasible(theta, delta, d_bid, sigma_bid)
    if theta.sells_reserve:
        clears = belief.mu >= c_sigma(theta, delta) - 1e-12
        if not clears.all():
            cons.append(sigma_bid[~clears] == 0.0)
    objective = payoff(
        theta,
        tariff,
        scenario,
        belief,
        b0,
        d_bid,
        sigma_bid,
        d_hat,
        anticipate,
        voll,
        knows_share,
    )
    problem = cp.Problem(cp.Maximize(objective), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"best response failed: {problem.status}")
    if theta.sells_reserve:
        sigma_bid = np.maximum(np.asarray(sigma_bid.value), 0.0)
    return np.asarray(d_bid.value), sigma_bid


def fixed_point(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    anticipate: bool = False,
    tol: float = 1e-3,
    max_iter: int = 50,
    damping: float | None = 0.5,
) -> tuple[np.ndarray, np.ndarray, Dispatch, Dispatch, list[float]]:
    """The consistent price-taker. Respond to the belief, clear at the response,
    make that the belief, repeat until the bid stops moving. It knows its own
    share, so each round also moves the tangent of its charge to the last bid.
    Each step moves a fraction ``damping`` toward the new response; ``None`` is
    the harmonic step 1/(k+1), which averages out the two-cycles a step merit
    order produces at scarcity hours. Returns (d_bid, sigma_bid, the dispatch
    at the response, the belief the final bid answered to, bid changes). If
    ``history[-1]`` is above ``tol`` the map did not settle: price-taking is the
    wrong model there (RQ3b)."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    b0 = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    belief, d_prev, sigma_prev, history = b0, delta.copy(), np.zeros(T), []
    for k in range(max_iter):
        d_bid, sigma_bid = best_response(
            theta,
            tariff,
            scenario,
            belief,
            b0,
            d_hat=d_prev,
            anticipate=anticipate,
            voll=market.voll,
            knows_share=True,
        )
        step = damping if damping is not None else 1.0 / (k + 1)
        d_bid = step * d_bid + (1 - step) * d_prev
        sigma_bid = step * sigma_bid + (1 - step) * sigma_prev
        history.append(
            float(np.abs(d_bid - d_prev).max() + np.abs(sigma_bid - sigma_prev).max())
        )
        believed, belief = (
            belief,
            market.clear(scenario, d_bid, sigma_bid, offer, d_firm),
        )
        d_prev, sigma_prev = d_bid, sigma_bid
        if history[-1] < tol:
            break
    return d_prev, sigma_prev, belief, believed, history


# ----------------------------------------------------------------------------
# B1
# ----------------------------------------------------------------------------
def planner(
    theta: LoadType, market: Market, scenario: Scenario, solver: str = "GUROBI"
) -> tuple[np.ndarray, np.ndarray, float]:
    """B1: max over (d_bid, σ_bid) ∈ 𝒟_θ of V(d, σᶜˡʳ) − C_sys, the load's and the
    operator's variables in one program. A curtailable type gives the planner the
    operator's instrument: headroom above dᶠⁱʳᵐ counts toward reserve. The planner
    consumes what it bids; curtailment below the bid is the operator's scarcity
    action, not a scheduling device. The offer cost sits in V and in C_sys, so it
    is added back once. The planner consumes its bid, d = d_bid. Returns
    (d_bid, σ_bid, S^B1)."""
    T, J, delta = scenario.T, scenario.J, scenario.delta
    offer = c_sigma(theta, delta)
    d_bid = cp.Variable(T)
    sigma_bid = cp.Variable(T) if theta.sells_reserve else np.zeros(T)
    sigma = (
        cp.Variable(T, nonneg=True) if theta.sells_reserve else np.zeros(T)
    )  # what clears
    u, r, shed = (
        cp.Variable((J, T), nonneg=True),
        cp.Variable((J, T), nonneg=True),
        cp.Variable(T, nonneg=True),
    )
    y = cp.Variable(J, nonneg=True) if market.long_run else scenario.nameplate
    d_firm = theta.d_firm(delta) if theta.curtailable else d_bid
    if market.reserve == "ercot":
        z = cp.Variable((market.ordc_for(scenario).widths.size, T), nonneg=True)
        Pi = market.ordc_for(scenario).prices @ z
    else:
        z, Pi = None, np.zeros(T)
    cons = feasible(theta, delta, d_bid, sigma_bid) + list(
        market.constraints(
            scenario, sigma_bid, d_firm, u, r, sigma, d_bid, y, z, shed
        ).values()
    )
    welfare = (
        V(theta, delta, d_bid, sigma)
        - market.C_sys(scenario, u, r, sigma, offer, shed, y, Pi)
        + offer @ sigma
    )
    problem = cp.Problem(cp.Maximize(welfare), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"planner failed: {problem.status}")
    if theta.sells_reserve:
        sigma_bid = np.maximum(np.asarray(sigma_bid.value), 0.0)
    return np.asarray(d_bid.value), sigma_bid, float(problem.value)
