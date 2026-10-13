"""The operator's clearing problem 𝓜_ω and everything read off its solution.

``Market`` is the environment the game is played in: which reserve construct
(PJM's hard requirement or ERCOT's demand curve), the load-following share γ,
the value of lost load, and whether capacity is sunk (short run) or chosen
(long run). It is never the operator's choice.

The LP objective is assembled by :meth:`Market.system_cost` once and used three
times: minimized in :meth:`Market.clear`, evaluated on a solution in
:meth:`Market.C_sys`, and maximized against in the planner's problem
(``load.planner``). The constraints are assembled by :meth:`Market.constraints`
and shared the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cvxpy as cp
import numpy as np

from ._expr import is_expr, mul, sum_
from .scenario import Scenario


@dataclass(frozen=True)
class DemandCurve:
    """ERCOT's operating reserve demand curve π: a decreasing step function of
    reserve net of load-following, X_t = R_t − γ d_sys_t. ``widths`` are the
    segment lengths in MW (the last is unbounded), ``prices`` their $/MW-h."""

    widths: np.ndarray
    prices: np.ndarray

    def __post_init__(self):
        assert self.widths.shape == self.prices.shape
        assert np.all(np.diff(self.prices) <= 0.0), "ORDC prices must decrease"

    @classmethod
    def default(cls, voll: float, reference_mw: float) -> "DemandCurve":
        """A placeholder shaped like ERCOT's: steps at fractions of a reference
        reserve quantity (the largest unit) with prices as fractions of VOLL.
        Replace with a curve built from LOLP before results depend on it."""
        return cls(
            widths=reference_mw * np.array([0.25, 0.25, 0.5, 1.0, np.inf]),
            prices=voll * np.array([1.0, 0.5, 0.2, 0.05, 0.0]),
        )

    def value(self, X: np.ndarray) -> np.ndarray:
        """∫₀ˣ π(z) dz for each X_t ≥ 0."""
        X = np.asarray(X, dtype=float)
        out = np.zeros_like(X)
        lower = 0.0
        for w, p in zip(self.widths, self.prices):
            out += p * np.clip(X - lower, 0.0, w)
            lower += w
        return out


@dataclass(frozen=True)
class Dispatch:
    """The solution of 𝓜_ω(d, σ): what the market determined. Load quantities
    first, then generators, then prices. Shapes: (T,) unless noted."""

    d: np.ndarray  # realized consumption dᶜᵘʳᵗ
    sigma: np.ndarray  # cleared reserve σᶜˡʳ
    u: np.ndarray  # (J, T) generation
    r: np.ndarray  # (J, T) generator reserve
    lam: np.ndarray  # energy price λ
    mu: np.ndarray  # reserve price μ
    nu: np.ndarray  # (J, T) capacity rent ν
    eta: np.ndarray  # value of one more MW of load reserve offer η
    d_bid: np.ndarray  # the bid d the load submitted
    sigma_bid: np.ndarray  # the reserve σ the load offered
    d_firm: np.ndarray  # the firm level the tariff set
    c_s: np.ndarray  # the offer price the load submitted
    y: np.ndarray  # (J,) capacity: nameplate in the short run, chosen in the long run
    reserve_value: float = 0.0  # Σ_t ∫ π under the demand curve; 0 under a hard requirement
    status: str = ""

    @property
    def curtailed(self) -> np.ndarray:
        return self.d < self.d_bid - 1e-6

    @property
    def R(self) -> np.ndarray:
        """Procured reserve Σ_j r_jt + σᶜˡʳ_t."""
        return self.r.sum(axis=0) + self.sigma


@dataclass(frozen=True)
class Market:
    """``reserve`` is ``"pjm"`` (hard requirement: the largest running unit plus
    γ d_sys, written once per unit) or ``"ercot"`` (demand curve on reserve net
    of load-following; load-following itself is hard)."""

    reserve: str = "ercot"
    gamma: float = 0.03
    voll: float = 5000.0
    long_run: bool = False
    ordc: DemandCurve | None = None  # ercot only; None -> DemandCurve.default at clear time
    solver: str = "HIGHS"
    solver_options: dict = field(default_factory=dict)

    def __post_init__(self):
        assert self.reserve in ("pjm", "ercot"), self.reserve

    # --- the curve actually used ----------------------------------------------
    def curve(self, scenario: Scenario) -> DemandCurve:
        if self.ordc is not None:
            return self.ordc
        largest = scenario.units @ scenario.nameplate
        return DemandCurve.default(self.voll, float(largest.max()))

    # --- objective, written once ----------------------------------------------
    def system_cost(self, scenario: Scenario, u, r, sigma_clr, c_s, y=None, z=None):
        """Σ_t [Σ_j (cᵘ u + cʳ r) + cˢ σᶜˡʳ] + Σ_j cⁱⁿᵛ y (long run) − Σ_t ∫π (ercot).
        Without the VOLL term: that is added in ``clear`` only, because it stands
        in for the load's value the operator does not observe."""
        cost = sum_(mul(scenario.cost_gen[:, None], u)) + sum_(mul(scenario.cost_res[:, None], r))
        cost = cost + sum_(mul(c_s, sigma_clr))
        if self.long_run:
            cost = cost + sum_(mul(scenario.cost_inv, y))
        if self.reserve == "ercot" and z is not None:
            cost = cost - sum_(mul(self.curve(scenario).prices[:, None], z))
        return cost

    # --- constraints, written once --------------------------------------------
    def constraints(self, scenario: Scenario, d_bid, sigma_bid, d_firm, u, r, sigma_clr, d_curt, y, z):
        """The memo's dispatch constraints as a dict of named cvxpy constraints,
        so ``clear`` can read duals by name and the planner can reuse them with
        ``d_curt`` as its own variable."""
        T, J = scenario.T, scenario.J
        M = scenario.units
        d_sys = d_curt + scenario.d_other
        cons = {}
        cons["balance"] = cp.sum(u, axis=0) == d_sys
        if self.long_run:
            cons["capacity"] = u + r <= cp.multiply(scenario.availability, cp.reshape(y, (J, 1), order="C") @ np.ones((1, T)))
        else:
            cons["capacity"] = u + r <= scenario.capacity
        headroom = d_curt - d_firm
        # X_t = Σ_j r_jt + σᶜˡʳ_t + headroom_t − γ d_sys_t, reserve net of load-following,
        # as its own variable so the per-unit rows below stay sparse.
        X = cp.Variable(T)
        cons["net_reserve"] = X == cp.sum(r, axis=0) + sigma_clr + headroom - self.gamma * d_sys
        if self.reserve == "pjm":
            # one row per unit: everyone else's reserve covers the unit's output
            ones = np.ones((M.shape[0], 1))
            cons["reserve"] = ones @ cp.reshape(X, (1, T), order="C") >= M @ u + M @ r
        else:
            widths = self.curve(scenario).widths
            cons["reserve"] = cp.sum(z, axis=0) == X  # dual = π(X_t) = μ_t
            cons["segments"] = z[np.isfinite(widths), :] <= widths[np.isfinite(widths), None]
        if sigma_clr is not None and not isinstance(sigma_clr, np.ndarray):
            cons["offer"] = sigma_clr <= sigma_bid
        if not isinstance(d_curt, np.ndarray) and d_firm is not d_curt:
            cons["curtail_lo"] = d_curt >= d_firm
            cons["curtail_hi"] = d_curt <= d_bid
        return cons

    # --- clearing ----------------------------------------------------------------
    def clear(self, scenario: Scenario, tariff, d: np.ndarray, sigma: np.ndarray, c_s: np.ndarray) -> Dispatch:
        """𝓜_ω(d, σ): take the load's bid and offer price as given, dispatch, and
        return quantities and duals. ``tariff`` enters only through dᶠⁱʳᵐ."""
        T, J = scenario.T, scenario.J
        d = np.asarray(d, dtype=float)
        sigma = np.asarray(sigma, dtype=float)
        c_s = np.broadcast_to(np.asarray(c_s, dtype=float), (T,))
        d_firm = tariff.d_firm(scenario.delta, d) if tariff is not None else d.copy()
        curtailable = bool(np.any(d_firm < d - 1e-9))
        if curtailable:
            sigma = np.zeros(T)  # a curtailable load does not offer reserve (memo)
        sells = bool(np.any(sigma > 0.0))

        u = cp.Variable((J, T), nonneg=True)
        r = cp.Variable((J, T), nonneg=True)
        sigma_clr = cp.Variable(T, nonneg=True) if sells else np.zeros(T)
        d_curt = cp.Variable(T) if curtailable else d
        y = cp.Variable(J, nonneg=True) if self.long_run else scenario.nameplate
        z = None
        if self.reserve == "ercot":
            z = cp.Variable((self.curve(scenario).widths.size, T), nonneg=True)

        cost = self.system_cost(scenario, u, r, sigma_clr, c_s, y, z)
        if curtailable:
            cost = cost + self.voll * cp.sum(d - d_curt)
        cons = self.constraints(scenario, d, sigma, d_firm, u, r, sigma_clr, d_curt, y, z)
        problem = cp.Problem(cp.Minimize(cost), list(cons.values()))
        problem.solve(solver=self.solver, **self.solver_options)
        if problem.status not in ("optimal", "optimal_inaccurate"):
            raise RuntimeError(
                f"clearing failed: {problem.status}. Other load cannot be shed, so the "
                f"scenario's reserve margin must cover gamma={self.gamma} plus, under PJM, "
                f"the largest unit's share of load (see scenario.reserve_margin)."
            )

        # cvxpy reports an equality dual as -∂cost/∂rhs. Balance has load on the
        # right, so λ = -dual; the demand-curve row has reserve on the right and
        # more reserve lowers cost, so μ = +dual. Checked numerically (tests).
        lam = -_dual(cons["balance"])
        if self.reserve == "pjm":
            mu = np.asarray(cons["reserve"].dual_value).sum(axis=0)  # only the largest unit binds
        else:
            mu = _dual(cons["reserve"])
        nu = np.asarray(cons["capacity"].dual_value)
        eta = np.asarray(cons["offer"].dual_value) if "offer" in cons else np.zeros(T)
        reserve_value = 0.0
        if z is not None:
            reserve_value = float(np.sum(self.curve(scenario).prices[:, None] * z.value))
        return Dispatch(
            d=np.asarray(d_curt.value if curtailable else d_curt),
            sigma=np.asarray(sigma_clr.value if sells else sigma_clr),
            u=u.value,
            r=r.value,
            lam=lam,
            mu=np.asarray(mu),
            nu=nu,
            eta=eta,
            d_bid=d,
            sigma_bid=sigma,
            d_firm=d_firm,
            c_s=np.asarray(c_s),
            y=np.asarray(y.value if self.long_run else y),
            reserve_value=reserve_value,
            status=problem.status,
        )

    # --- read off a dispatch --------------------------------------------------------
    def C_sys(self, dispatch: Dispatch, scenario: Scenario) -> float:
        """The objective at the solution without the VOLL term (the memo's C_sys)."""
        cost = self.system_cost(scenario, dispatch.u, dispatch.r, dispatch.sigma, dispatch.c_s, dispatch.y)
        return float(cost - dispatch.reserve_value)

    def pools(self, dispatch: Dispatch, scenario: Scenario) -> tuple[np.ndarray, float]:
        """(Cʳᵉˢ_t, Cⁱⁿᵛ): the reserve pool μ_t(Σ_j r_jt + σᶜˡʳ_t) hour by hour, and
        the missing money Σ_j (cⁱⁿᵛ_j − Σ_t ν_jt) ū_j, zero in the long run."""
        C_res = dispatch.mu * dispatch.R
        if self.long_run:
            C_inv = 0.0
        else:
            C_inv = float(np.sum((scenario.cost_inv - dispatch.nu.sum(axis=1)) * scenario.nameplate))
        return C_res, C_inv

    def kappa(self, dispatch: Dispatch) -> np.ndarray:
        """Marginal cost of serving the load: λ + γμ − 𝟙[dᶠⁱʳᵐ < d] μ."""
        curtailable = dispatch.d_firm < dispatch.d_bid - 1e-9
        return dispatch.lam + self.gamma * dispatch.mu - curtailable * dispatch.mu

    def marginal_cost_by_layer(self, dispatch: Dispatch) -> dict[str, np.ndarray]:
        """∂C_sys/∂d_t split the way the bill is: energy λ, reserve γμ less μ on
        curtailable headroom, investment 0 in the short run."""
        curtailable = dispatch.d_firm < dispatch.d_bid - 1e-9
        return {
            "energy": dispatch.lam,
            "reserve": self.gamma * dispatch.mu - curtailable * dispatch.mu,
            "investment": np.zeros_like(dispatch.lam),
        }


def _dual(constraint) -> np.ndarray:
    v = constraint.dual_value
    return np.asarray(v, dtype=float).reshape(-1)
