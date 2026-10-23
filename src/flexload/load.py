"""The load: its type θ, value V, offer price c^σ, and three strategies.
B0 bids (δ, 0). R best-responds to the tariff under a belief.
B1 is the planner's optimum. Report §3, "Flexible load".

The load bids (d_bid, sigma_bid). Dispatch returns what it consumed and what
cleared, (d, sigma). A price-taker's belief 𝓜̃ is a ``Belief``: a ``Dispatch``
it takes λ, μ and each layer's cost from, and the row of report Table 2 it
holds. Its bill is then linear in the bid and the best response is a QP. The
exogenous price-taker's belief is the clearing at (δ, 0); the consistent one's
is the fixed point ``fixed_point`` closes. A price-setter's belief is the
market itself (bilevel, not built).
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from .system import Dispatch, Market, Scenario
from .tariff import Tariff


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

    psi: float  # the loss rate, $/MWh: cutting a fraction x of δ_t costs 2ψx per MWh cut
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
PSI = {"low": 50.0, "medium": 100.0, "high": 200.0}  # $/MWh; a price of 2βψ pushes the load to its band
BETA = {"low": 0.05, "medium": 0.2, "high": 0.5}
P = {"low": 0.02, "high": 0.2}
BUSINESS = {  # (ψ, β, A): what the load is, behind its designation
    "data_center_infer": (
        "high",
        "medium",
        "day",
    ),  # serves requests as they come; defers batch jobs within the day
    "data_center_train": (
        "medium",
        "medium",
        "window",
    ),  # checkpoints and resumes training jobs within the window
    "bitcoin_mine": (
        "low",
        "high",
        "elastic",
    ),  # curtailed hashing is lost, not shifted
}


def named_types(T: int, business: str = "data_center_train") -> dict[str, LoadType]:
    """θ₀…θ₄ of the report's type table, run as a ``business`` in ``BUSINESS``,
    which sets (ψ, β, A) for the rows that sweep them. The three businesses
    differ in A, the horizon over which consumption is conserved: a day for an
    inference data center, the window for a training one, none for a bitcoin
    mine. The emergency row is fixed at (ψ medium, β low, elastic, p high)."""
    psi, beta, a = BUSINESS[business]
    A = {"window": np.ones((1, T)), "elastic": np.zeros((0, T))}
    if T % 24 == 0:  # the day blocks need whole days
        A["day"] = np.kron(np.eye(T // 24), np.ones((1, 24)))
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
# V, c^σ, 𝒟_θ, S
# ----------------------------------------------------------------------------
def c_sigma(theta: LoadType, delta: np.ndarray) -> np.ndarray:
    """c^σ = 2 p ψ β, the cost of standing ready: the marginal loss at the
    band's edge, the largest shed the load tolerates, times the chance p it is
    called. A rate in $/MWh, the same in every hour."""
    return np.full(delta.shape, 2.0 * theta.p * theta.psi * theta.beta)


def V(theta: LoadType, delta: np.ndarray, d, sigma):
    """V(d, σ) = −Σ_t (ψ/δ_t)(d_t − δ_t)² − c^σᵀσ, on what the load consumes and
    what cleared. Value is per MW of load: with x_t = (δ_t − d_t)/δ_t the loss is
    ψ δ_t x_t², so a load twice the size loses twice as much from the same
    fractional cut, and the planner's cut λ_t/2ψ is a fraction of δ_t."""
    return -cp.sum(cp.multiply(theta.psi / delta, cp.square(d - delta))) - cp.sum(
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


def S(theta: LoadType, market: Market, scenario: Scenario, d, sigma, u, r, shed, y, Pi):
    """S = V(d, σ) − C_sys + c^σᵀσ, welfare on what the load consumed and what
    cleared. The offer cost sits in V and in C_sys, so it is added back once.
    On numbers or variables alike; read a number with ``.value``."""
    offer = c_sigma(theta, scenario.delta)
    C_sys = market.C_sys(scenario, u, r, sigma, offer, shed, y, Pi)
    return V(theta, scenario.delta, d, sigma) - C_sys + offer @ sigma


# ----------------------------------------------------------------------------
# R
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Belief:
    """𝓜̃, a price-taker's belief about dispatch (report Table 2): the
    ``dispatch`` it reads λ, μ, the layer costs, x̂ (``dispatch.d_bid``) and its
    expected curtailment from, and the row it holds. ``consistent`` False is
    the exogenous price-taker: ``dispatch`` is the clearing at (δ, 0), it pays
    the posted rate and consumes its bid. True is the consistent price-taker:
    ``dispatch`` is the clearing at its last bid, it knows its share and expects
    dᶠⁱʳᵐ where that clearing cut it."""

    dispatch: Dispatch
    consistent: bool


def payoff(
    theta: LoadType,
    tariff: Tariff,
    scenario: Scenario,
    belief: Belief,
    b0: Dispatch,
    d,
    sigma,
):
    """V(d, σ) − B(d, σ) under the belief, on the consumption and cleared
    reserve the load expects. The ex-ante pools Ĉᵏ come from ``b0``, the
    dispatch at (δ, 0). The charge is linearized at x̂, the bid the belief
    answered; the consistent price-taker knows its share there."""
    bill = tariff.bill(
        d,
        sigma,
        belief.dispatch,
        scenario.d_other,
        b0,
        d_hat=belief.dispatch.d_bid,
        knows_share=belief.consistent,
    )
    return V(theta, scenario.delta, d, sigma) - sum(bill.values())


def best_response(
    theta: LoadType,
    tariff: Tariff,
    scenario: Scenario,
    belief: Belief,
    b0: Dispatch,
    solver: str = "GUROBI",
) -> tuple[np.ndarray, np.ndarray]:
    """max payoff over 𝒟_θ: a QP. The load bids (d_bid, σ_bid) and expects
    (d̃, σ̃), report Table 2: σ̃ = σ_bid, offered only where the believed μ
    covers c^σ; d̃ = d_bid, except that the consistent curtailable load expects
    dᶠⁱʳᵐ where the believed dispatch cut it. Returns the bid."""
    T, delta = scenario.T, scenario.delta
    believed = belief.dispatch
    d_bid = cp.Variable(T)
    sigma_bid = cp.Variable(T) if theta.sells_reserve else np.zeros(T)
    cons = feasible(theta, delta, d_bid, sigma_bid)
    if theta.sells_reserve:
        clears = believed.mu >= c_sigma(theta, delta) - 1e-12
        if not clears.all():
            cons.append(sigma_bid[~clears] == 0.0)
    d_tilde = d_bid
    if belief.consistent and theta.curtailable:
        cut = (believed.d < believed.d_bid - 1e-9).astype(float)
        d_tilde = cp.multiply(1.0 - cut, d_bid) + cut * theta.d_firm(delta)
    objective = payoff(theta, tariff, scenario, belief, b0, d_tilde, sigma_bid)
    problem = cp.Problem(cp.Maximize(objective), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"best response failed: {problem.status}")
    if theta.sells_reserve:
        sigma_bid = np.asarray(sigma_bid.value)
    return np.asarray(d_bid.value), sigma_bid


def fixed_point(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    b0: Dispatch,
    tol: float = 1e-3,
    max_iter: int = 50,
    damping: float | None = 0.5,
) -> tuple[np.ndarray, np.ndarray, Dispatch, Dispatch, list[float]]:
    """The consistent price-taker. Respond to the belief, clear at the response,
    make that the belief, repeat until the bid stops moving. The belief each
    round is ``Belief(the last clearing, consistent=True)``, ``b0`` to start:
    the load knows its own share, so each round also moves the tangent of its
    charge to the last bid, and it expects curtailment where the last clearing
    cut it. ``b0`` is the dispatch at (δ, 0), as for ``best_response``.
    Each step moves a fraction ``damping`` toward the new response; ``None`` is
    the harmonic step 1/(k+1), which averages out the two-cycles a step merit
    order produces at scarcity hours. Returns (d_bid, sigma_bid, the dispatch
    at the response, the belief the final bid answered to, bid changes). If
    ``history[-1]`` is above ``tol`` the map did not settle: price-taking is the
    wrong model there (RQ3b)."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    belief, d_prev, sigma_prev, history = b0, delta.copy(), np.zeros(T), []
    for k in range(max_iter):
        d_bid, sigma_bid = best_response(
            theta, tariff, scenario, Belief(belief, consistent=True), b0
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
) -> tuple[np.ndarray, np.ndarray]:
    """B1: max S over (d_bid, σ_bid) ∈ 𝒟_θ, the load's and the operator's
    variables in one program. A curtailable type gives the planner the
    operator's instrument: headroom above dᶠⁱʳᵐ counts toward reserve. The planner
    consumes what it bids; curtailment below the bid is the operator's scarcity
    action, not a scheduling device. The planner consumes its bid, d = d_bid.
    Returns the bid (d_bid, σ_bid); S^B1 is read from its clearing, as for R."""
    T, J, delta = scenario.T, scenario.J, scenario.delta
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
    welfare = S(theta, market, scenario, d_bid, sigma, u, r, shed, y, Pi)
    problem = cp.Problem(cp.Maximize(welfare), cons)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"planner failed: {problem.status}")
    if theta.sells_reserve:
        sigma_bid = np.asarray(sigma_bid.value)
    return np.asarray(d_bid.value), sigma_bid
