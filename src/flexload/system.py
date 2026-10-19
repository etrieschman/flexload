"""The system: the exogenous state ω with the load's preferred profile δ
(``Scenario``), and the operator's clearing problem 𝓜_ω (``Market``).

One period of T hours at one node, cut from RTS-GMLC. Generators are offer
blocks, one column per step of a unit's cost curve, so costs are linear and the
merit order is a step function. ``unit[j]`` says which physical unit a column
belongs to; the largest-single-contingency reserve row is written per unit.

Formulas are cvxpy expressions whether their inputs are numbers or variables.
Read a number with ``.value``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import cvxpy as cp
import numpy as np
import polars as pl
import rts_gmlc as rts

HOURS_PER_YEAR = 8760

# Placeholder annualized capital cost by RTS-GMLC category, $/kW-year (RTS-GMLC
# has none). Replace with a cited table before a result depends on the
# investment layer. docs/assumptions.md #1.
INVESTMENT_COST_PER_KW_YEAR = {
    "Nuclear": 600.0, "Coal": 350.0, "Gas CC": 110.0, "Gas CT": 80.0, "Oil CT": 80.0,
    "Oil ST": 300.0, "Hydro": 300.0, "Wind": 140.0, "Solar PV": 90.0, "Solar RTPV": 90.0, "CSP": 500.0,
}
EXCLUDED = ("Storage", "Sync_Cond", "CSP")  # no single-period dispatch model
RENEWABLE_SERIES = ("pv", "rtpv", "wind", "hydro")  # availability from the time series


# ----------------------------------------------------------------------------
# ω and δ
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """One period. Shapes: T hours, J generator columns."""

    delta: np.ndarray  # (T,) the load's preferred consumption δ, MW
    d_other: np.ndarray  # (T,) all other load d°, MW
    cost_gen: np.ndarray  # (J,) energy cost cᵘ, $/MWh
    cost_res: np.ndarray  # (J,) reserve cost cʳ, $/MW-h
    cost_inv: np.ndarray  # (J,) investment cost cⁱⁿᵛ, $/MW per year
    capacity: np.ndarray  # (J, T) available capacity ū, MW
    nameplate: np.ndarray  # (J,) installed capacity, MW
    unit: np.ndarray  # (J,) int, physical unit of each column
    names: tuple[str, ...] = ()
    start: int = 0  # first hour of the period in the year

    @property
    def T(self) -> int:
        return self.delta.shape[0]

    @property
    def J(self) -> int:
        return self.cost_gen.shape[0]

    @property
    def d_sys(self) -> np.ndarray:
        """System load when the flexible load consumes δ: the B0 path."""
        return self.delta + self.d_other

    @property
    def peak(self) -> int:
        """Hour of the period's peak on the B0 path: the ex-ante peak hour."""
        return int(np.argmax(self.d_sys))

    @property
    def cost_inv_period(self) -> np.ndarray:
        """cⁱⁿᵛ prorated to the period, $/MW."""
        return self.cost_inv * self.T / HOURS_PER_YEAR

    @property
    def units(self) -> np.ndarray:
        """(U, J) membership: row u sums the columns of unit u."""
        ids = np.unique(self.unit)
        return (ids[:, None] == self.unit[None, :]).astype(float)

    @property
    def availability(self) -> np.ndarray:
        """(J, T) capacity as a fraction of nameplate; the long run's capacity shape."""
        return self.capacity / np.where(self.nameplate > 0, self.nameplate, 1.0)[:, None]


def scenario(start: int = 31 * 168, T: int = 168, alpha: float = 0.05, reserve_margin: float | None = None) -> Scenario:
    """Hours ``[start, start + T)`` of RTS-GMLC at one node. ``alpha`` is the
    flexible load's share of the period's energy, carved out of the RTS total
    with the system's shape, so δ + d° is the data. ``reserve_margin`` scales
    both loads so the tightest hour has that margin (``tighten``)."""
    lo, hi = start, start + T
    load = rts.timeseries("load", "day_ahead")[lo:hi]
    if len(load) != T:
        raise ValueError(f"hours {lo}:{hi} are not in the day-ahead series")
    total = sum(load[str(a)].to_numpy().astype(float) for a in (1, 2, 3))
    delta = alpha * total

    blocks = rts.offer_blocks().filter(pl.col("mw") > 0.0)
    series = {k: rts.timeseries(k, "day_ahead")[lo:hi] for k in RENEWABLE_SERIES}
    renewable = {c: s for s in series.values() for c in s.columns if c not in rts.TIME_COLS}
    cols = []  # (cost_gen, cost_res, cost_inv, capacity (T,), nameplate, unit, name)
    for u, g in enumerate(rts.gen().iter_rows(named=True)):
        uid, cat = g["gen_uid"], g["category"]
        if cat in EXCLUDED:
            continue
        inv = INVESTMENT_COST_PER_KW_YEAR[cat] * 1000.0
        if uid in renewable:
            avail = renewable[uid][uid].to_numpy().astype(float)
            cols.append((float(g["vom"] or 0.0), 0.0, inv, avail, float(g["pmax_mw"]), u, uid))
        else:
            for mw, cost in blocks.filter(pl.col("gen_uid") == uid).select("mw", "cost").iter_rows():
                cols.append((float(cost), 0.0, inv, mw * np.ones(T), float(mw), u, uid))
    s = Scenario(
        delta=delta,
        d_other=total - delta,
        cost_gen=np.array([c[0] for c in cols]),
        cost_res=np.array([c[1] for c in cols]),
        cost_inv=np.array([c[2] for c in cols]),
        capacity=np.array([c[3] for c in cols]),
        nameplate=np.array([c[4] for c in cols]),
        unit=np.array([c[5] for c in cols]),
        names=tuple(c[6] for c in cols),
        start=start,
    )
    return tighten([s], reserve_margin)[0]


def periods(T: int = 168, alpha: float = 0.05, reserve_margin: float | None = None) -> list[Scenario]:
    """The year cut into periods of T hours, under one tightness scale: the
    annual tightest hour has the margin and the other periods keep their
    seasonal slack."""
    starts = range(0, HOURS_PER_YEAR - HOURS_PER_YEAR % T, T)
    return tighten([scenario(s, T, alpha) for s in starts], reserve_margin)


def tighten(scenarios: list[Scenario], reserve_margin: float | None) -> list[Scenario]:
    """Scale δ and d° in every scenario by one factor so that the tightest hour
    across them has ``min_t Σ_j ū_jt / d_sys_t − 1 = reserve_margin``. Scaling
    load, not capacity, keeps unit sizes and the merit order intact. α is
    unchanged because both loads scale."""
    if reserve_margin is None:
        return scenarios
    s = min(margin(sc) for sc in scenarios) + 1.0
    s = s / (1.0 + reserve_margin)
    return [Scenario(sc.delta * s, sc.d_other * s, sc.cost_gen, sc.cost_res, sc.cost_inv, sc.capacity, sc.nameplate, sc.unit, sc.names, sc.start) for sc in scenarios]


def margin(scenario: Scenario) -> float:
    """The tightest hour's available capacity over system load, minus one."""
    return float((scenario.capacity.sum(axis=0) / scenario.d_sys).min() - 1.0)


# ----------------------------------------------------------------------------
# 𝓜_ω
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class DemandCurve:
    """ERCOT's operating reserve demand curve π: decreasing steps in reserve net
    of load-following, X_t = R_t − γ d_sys_t. ``widths`` in MW (last is ∞),
    ``prices`` in $/MW-h."""

    widths: np.ndarray
    prices: np.ndarray

    @classmethod
    def default(cls, voll: float, reference_mw: float) -> "DemandCurve":
        """Placeholder shaped like ERCOT's: steps at fractions of the largest
        unit, priced at fractions of VOLL. docs/assumptions.md #3."""
        return cls(reference_mw * np.array([0.25, 0.25, 0.5, 1.0, np.inf]), voll * np.array([1.0, 0.5, 0.2, 0.05, 0.0]))


@dataclass(frozen=True)
class Dispatch:
    """What 𝓜_ω(d, σ) determined: quantities, prices, and the two pools the
    cost-share layers split. Shapes (T,) unless noted."""

    d: np.ndarray  # realized consumption dᶜᵘʳᵗ
    sigma: np.ndarray  # cleared reserve σᶜˡʳ
    u: np.ndarray  # (J, T) generation
    r: np.ndarray  # (J, T) generator reserve
    shed: np.ndarray  # other load not served, at VOLL
    lam: np.ndarray  # energy price λ
    mu: np.ndarray  # reserve price μ
    nu: np.ndarray  # (J, T) capacity rent ν
    eta: np.ndarray  # value of one more MW of the load's offer, η
    C_res: np.ndarray  # reserve pool Cʳᵉˢ_t = μ_t (Σ_j r_jt + σᶜˡʳ_t)
    C_inv: float  # investment pool Ĉⁱⁿᵛ for the period
    d_bid: np.ndarray  # the bid d
    sigma_bid: np.ndarray  # the offer σ
    d_firm: np.ndarray  # the firm level the operator may not curtail below
    c_s: np.ndarray  # the offer price cˢ
    y: np.ndarray  # (J,) capacity: nameplate in the short run, chosen in the long run
    reserve_value: float = 0.0  # Σ_t ∫π under the demand curve
    status: str = ""

    @property
    def R(self) -> np.ndarray:
        """Procured reserve Σ_j r_jt + σᶜˡʳ_t."""
        return self.r.sum(axis=0) + self.sigma

    @property
    def curtailable(self) -> bool:
        return bool(np.any(self.d_firm < self.d_bid - 1e-9))


@dataclass(frozen=True)
class Market:
    """The environment: ``reserve`` is ``"pjm"`` (hard requirement, the largest
    running unit plus γ d_sys) or ``"ercot"`` (demand curve on reserve net of
    load-following). ``missing_money`` is the annual Ĉⁱⁿᵛ from
    :func:`missing_money`; the short run needs it."""

    reserve: str = "ercot"
    gamma: float = 0.03
    voll: float = 5000.0
    long_run: bool = False
    ordc: DemandCurve | None = None  # ercot; None -> DemandCurve.default
    missing_money: float | None = None
    solver: str = "GUROBI"
    solver_options: dict = field(default_factory=dict)

    def curve(self, scenario: Scenario) -> DemandCurve:
        if self.ordc is not None:
            return self.ordc
        return DemandCurve.default(self.voll, float((scenario.units @ scenario.nameplate).max()))

    # --- objective and constraints, written once, used by clear, C_sys, planner --
    def system_cost(self, scenario: Scenario, u, r, sigma_clr, c_s, y, z, shed):
        """Σ_t [Σ_j (cᵘ u + cʳ r) + cˢ σᶜˡʳ + cⱽᴼᴸᴸ shed] + Σ_j cⁱⁿᵛ y (long run) − Σ_t ∫π (ercot)."""
        cost = cp.sum(cp.multiply(scenario.cost_gen[:, None], u)) + cp.sum(cp.multiply(scenario.cost_res[:, None], r))
        cost = cost + cp.sum(cp.multiply(c_s, sigma_clr)) + self.voll * cp.sum(shed)
        if self.long_run:
            cost = cost + scenario.cost_inv_period @ y
        if self.reserve == "ercot" and z is not None:
            cost = cost - cp.sum(cp.multiply(self.curve(scenario).prices[:, None], z))
        return cost

    def constraints(self, scenario: Scenario, sigma_bid, d_firm, u, r, sigma_clr, d_curt, y, z, shed) -> dict:
        """Balance (λ), capacity (ν), reserve (μ), offer (η), as named cvxpy
        constraints. Headroom dᶜᵘʳᵗ − dᶠⁱʳᵐ counts toward reserve."""
        T, J = scenario.T, scenario.J
        d_sys = d_curt + scenario.d_other
        cons = {"balance": cp.sum(u, axis=0) + shed == d_sys}
        if self.long_run:
            cons["capacity"] = u + r <= cp.multiply(scenario.availability, cp.reshape(y, (J, 1), order="C") @ np.ones((1, T)))
        else:
            cons["capacity"] = u + r <= scenario.capacity
        X = cp.Variable(T)  # reserve net of load-following, its own variable so the per-unit rows stay sparse
        cons["net_reserve"] = X == cp.sum(r, axis=0) + sigma_clr + (d_curt - d_firm) - self.gamma * d_sys
        M = scenario.units
        if self.reserve == "pjm":
            cons["reserve"] = np.ones((M.shape[0], 1)) @ cp.reshape(X, (1, T), order="C") >= M @ u + M @ r
        else:
            widths = self.curve(scenario).widths
            cons["reserve"] = cp.sum(z, axis=0) == X  # dual: π(X_t) = μ_t
            cons["segments"] = z[np.isfinite(widths), :] <= widths[np.isfinite(widths), None]
        if isinstance(sigma_clr, cp.Variable):
            cons["offer"] = sigma_clr <= sigma_bid
        return cons

    # --- clearing -----------------------------------------------------------------
    def clear(self, scenario: Scenario, d: np.ndarray, sigma: np.ndarray, c_s: np.ndarray, d_firm: np.ndarray | None = None) -> Dispatch:
        """𝓜_ω(d, σ): dispatch against the load's bid, offer and firm level, and
        read quantities, prices and pools. ``d_firm=None`` means the load is
        served in full. A curtailable load does not offer reserve."""
        T, J = scenario.T, scenario.J
        d, sigma = np.asarray(d, float), np.asarray(sigma, float)
        c_s = np.broadcast_to(np.asarray(c_s, float), (T,))
        d_firm = d.copy() if d_firm is None else np.minimum(np.asarray(d_firm, float), d)
        curtailable = bool(np.any(d_firm < d - 1e-9))
        if curtailable:
            sigma = np.zeros(T)
        sells = bool(np.any(sigma > 0.0))

        u = cp.Variable((J, T), nonneg=True)
        r = cp.Variable((J, T), nonneg=True)
        shed = cp.Variable(T, nonneg=True)
        sigma_clr = cp.Variable(T, nonneg=True) if sells else np.zeros(T)
        d_curt = cp.Variable(T) if curtailable else d
        y = cp.Variable(J, nonneg=True) if self.long_run else scenario.nameplate
        z = cp.Variable((self.curve(scenario).widths.size, T), nonneg=True) if self.reserve == "ercot" else None

        cost = self.system_cost(scenario, u, r, sigma_clr, c_s, y, z, shed)
        cons = self.constraints(scenario, sigma, d_firm, u, r, sigma_clr, d_curt, y, z, shed)
        if curtailable:  # the VOLL term stands in for the load's value, which the operator does not see
            cost = cost + self.voll * cp.sum(d - d_curt)
            cons["curtail"] = d_curt >= d_firm
            cons["serve"] = d_curt <= d
        problem = cp.Problem(cp.Minimize(cost), list(cons.values()))
        problem.solve(solver=self.solver, **self.solver_options)
        if problem.status not in ("optimal", "optimal_inaccurate"):
            raise RuntimeError(f"clearing failed: {problem.status}")

        # cvxpy reports an equality dual as −∂cost/∂rhs. Balance has load on the right, so λ = −dual.
        # The demand-curve row has reserve on the right and more reserve lowers cost, so μ = +dual.
        lam = -_dual(cons["balance"])
        mu = np.asarray(cons["reserve"].dual_value).sum(axis=0) if self.reserve == "pjm" else _dual(cons["reserve"])
        nu = np.asarray(cons["capacity"].dual_value)
        value = lambda v: np.asarray(v.value if isinstance(v, cp.Expression) else v)  # noqa: E731
        r_val, sigma_val = value(r), value(sigma_clr)
        C_res = mu * (r_val.sum(axis=0) + sigma_val)
        if self.long_run:
            C_inv = 0.0  # λ carries capacity cost through ν
        elif self.missing_money is None:
            raise ValueError("the short run needs Market.missing_money; see missing_money(market, periods(...))")
        else:
            C_inv = float(self.missing_money) * T / HOURS_PER_YEAR
        return Dispatch(
            d=value(d_curt), sigma=sigma_val, u=value(u), r=r_val, shed=value(shed),
            lam=lam, mu=np.asarray(mu), nu=nu, eta=_dual(cons["offer"]) if "offer" in cons else np.zeros(T),
            C_res=C_res, C_inv=C_inv, d_bid=d, sigma_bid=sigma, d_firm=d_firm, c_s=np.asarray(c_s), y=value(y),
            reserve_value=float(np.sum(self.curve(scenario).prices[:, None] * z.value)) if z is not None else 0.0,
            status=problem.status,
        )

    # --- read off a dispatch --------------------------------------------------------
    def C_sys(self, dispatch: Dispatch, scenario: Scenario) -> float:
        """The objective at the solution without the VOLL term on the load's own curtailment."""
        cost = self.system_cost(scenario, dispatch.u, dispatch.r, dispatch.sigma, dispatch.c_s, dispatch.y, None, dispatch.shed)
        return float(cost.value) - dispatch.reserve_value

    def kappa(self, dispatch: Dispatch) -> np.ndarray:
        """Marginal cost of serving the load: λ + γμ − 𝟙[dᶠⁱʳᵐ < d] μ."""
        return dispatch.lam + self.gamma * dispatch.mu - (dispatch.d_firm < dispatch.d_bid - 1e-9) * dispatch.mu

    def marginal_cost(self, dispatch: Dispatch) -> dict[str, np.ndarray]:
        """∂C_sys/∂d_t split the way the bill is: energy λ, reserve γμ less μ on
        curtailable headroom, investment 0 in the short run."""
        headroom = dispatch.d_firm < dispatch.d_bid - 1e-9
        return {"energy": dispatch.lam, "reserve": self.gamma * dispatch.mu - headroom * dispatch.mu, "investment": np.zeros(dispatch.lam.shape)}


def missing_money(market: Market, periods: list[Scenario], cache: bool = True) -> float:
    """Ĉⁱⁿᵛ := Σ_j (cⁱⁿᵛ_j − Σ_t ν_jt) ū_j over a year on the B0 path (δ, 0):
    annual investment cost less the rents capacity earns in the market, in $.
    Cached under ``~/.cache/flexload`` by market fields and the year's data."""
    key = _cache_key(market, periods) if cache else None
    if key is not None and key.exists():
        return float(json.loads(key.read_text())["annual"])
    m = Market(market.reserve, market.gamma, market.voll, False, market.ordc, 0.0, market.solver, market.solver_options)
    by_period = []
    for s in periods:
        b0 = m.clear(s, s.delta, np.zeros(s.T), np.zeros(s.T))
        by_period.append(float(np.sum((s.cost_inv_period - b0.nu.sum(axis=1)) * s.nameplate)))
    annual = float(np.sum(by_period))
    if key is not None:
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text(json.dumps({"annual": annual, "by_period": by_period, "starts": [s.start for s in periods]}))
    return annual


def _cache_key(market: Market, periods: list[Scenario]) -> Path:
    h = hashlib.sha1(repr((market.reserve, market.gamma, market.voll)).encode())
    if market.ordc is not None:
        h.update(market.ordc.widths.tobytes() + market.ordc.prices.tobytes())
    for s in periods:
        for a in (s.d_sys, s.capacity, s.cost_inv, s.cost_gen):
            h.update(np.ascontiguousarray(a).tobytes())
    return Path.home() / ".cache" / "flexload" / "missing_money" / f"{h.hexdigest()}.json"


def _dual(constraint) -> np.ndarray:
    return np.asarray(constraint.dual_value, dtype=float).reshape(-1)
