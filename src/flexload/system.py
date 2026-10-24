"""The system: the exogenous state ω with the load's preferred profile δ
(``Scenario``), and the operator's dispatch 𝓜_ω (``Market``). Report §3,
"Timing and information" and "Market".

One operating window 𝒯 of T hours at one node, cut from RTS-GMLC. Generators
are offer blocks, one column per step of a unit's cost curve, so costs are
linear and the merit order is a step function. ``unit[j]`` says which physical
unit a column belongs to; the reserve row is written per unit.

Formulas are cvxpy expressions whether their inputs are numbers or variables.
Read a number with ``.value``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
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
    "Nuclear": 600.0,
    "Coal": 350.0,
    "Gas CC": 110.0,
    "Gas CT": 80.0,
    "Oil CT": 80.0,
    "Oil ST": 300.0,
    "Hydro": 300.0,
    "Wind": 140.0,
    "Solar PV": 90.0,
    "Solar RTPV": 90.0,
    "CSP": 500.0,
}
EXCLUDED = ("Storage", "Sync_Cond", "CSP")  # no single-period dispatch model
RENEWABLE = ("pv", "rtpv", "wind", "hydro")  # availability from the time series


# ----------------------------------------------------------------------------
# ω and δ
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """One operating window. Shapes: T hours, J generator columns."""

    delta: np.ndarray  # (T,) the load's preferred consumption δ, MW
    d_other: np.ndarray  # (T,) all other load d°, MW
    cost_gen: np.ndarray  # (J,) energy cost cᵘ, $/MWh
    cost_res: np.ndarray  # (J,) reserve cost cʳ, $/MW-h
    cost_inv: np.ndarray  # (J,) investment cost cⁱⁿᵛ, $/MW per year
    capacity: np.ndarray  # (J, T) available capacity ū, MW
    nameplate: np.ndarray  # (J,) installed capacity, MW
    unit: np.ndarray  # (J,) int, physical unit of each column
    names: tuple[str, ...] = ()
    start: int = 0  # first hour of the window in the year
    epsilon_std: float = 0.0  # σ of the normal fit to the hourly net-load forecast error ε, MW; one value for the year

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
        """Hour of the window's peak on the B0 path: the ex-ante peak hour t*."""
        return int(np.argmax(self.d_sys))

    @property
    def units(self) -> np.ndarray:
        """(U, J) membership: row u sums the columns of unit u."""
        ids = np.unique(self.unit)
        return (ids[:, None] == self.unit[None, :]).astype(float)

    @property
    def availability(self) -> np.ndarray:
        """(J, T) capacity as a fraction of nameplate; the long run's capacity shape."""
        return (
            self.capacity / np.where(self.nameplate > 0, self.nameplate, 1.0)[:, None]
        )


def scenario(
    start: int = 31 * 168,
    T: int = 168,
    alpha: float = 0.05,
    reserve_margin: float | None = 0.15,
    reserve_offer: float = 0.1,
) -> Scenario:
    """Hours ``[start, start + T)`` of RTS-GMLC's day-ahead series at one node.
    ``alpha`` sets the load's size: δ is that share of system load, hour by
    hour, carved out of the RTS total so δ + d° is the data. ``reserve_margin``
    scales both loads so the tightest hour has that margin (``tighten``). The
    default 0.15 is the margin at which ERCOT's prices pay the fleet's annual
    investment cost (``C_inv`` ≈ 0 over the year). ``reserve_offer`` sets the
    reserve offer cʳⱼ = reserve_offer × cᵘⱼ on thermal blocks (RTS-GMLC has
    none; docs/assumptions.md #5); renewables and hydro offer none."""
    lo, hi = start, start + T
    load = rts.timeseries("load", "day_ahead")[lo:hi]
    if len(load) != T:
        raise ValueError(f"hours {lo}:{hi} are not in the day-ahead series")
    total = sum(load[str(a)].to_numpy().astype(float) for a in (1, 2, 3))
    delta = alpha * total

    blocks = rts.offer_blocks().filter(pl.col("mw") > 0.0)
    series = {k: rts.timeseries(k, "day_ahead")[lo:hi] for k in RENEWABLE}
    renewable = {
        c: s for s in series.values() for c in s.columns if c not in rts.TIME_COLS
    }
    cols = []  # (cost_gen, cost_res, cost_inv, capacity (T,), nameplate, unit, name)
    for u, g in enumerate(rts.gen().iter_rows(named=True)):
        uid, cat = g["gen_uid"], g["category"]
        if cat in EXCLUDED:
            continue
        inv = INVESTMENT_COST_PER_KW_YEAR[cat] * 1000.0
        if uid in renewable:
            avail = renewable[uid][uid].to_numpy().astype(float)
            cols.append(
                (float(g["vom"] or 0.0), 0.0, inv, avail, float(g["pmax_mw"]), u, uid)  # no offer: nothing idle to hold
            )
        else:
            for mw, cost in (
                blocks.filter(pl.col("gen_uid") == uid).select("mw", "cost").iter_rows()
            ):
                cols.append(
                    (float(cost), reserve_offer * float(cost), inv, mw * np.ones(T), float(mw), u, uid)
                )
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
        epsilon_std=_epsilon_std(),
    )
    return tighten([s], reserve_margin)[0]


@lru_cache(maxsize=None)
def _epsilon_std() -> float:
    """σ of the normal fit to the hourly net-load forecast error ε over the year.
    Net load is load less wind and solar. ε_t is its real-time value, averaged
    from five minutes to the hour, minus its day-ahead forecast."""

    def net_load(market: str) -> np.ndarray:
        total = 0.0
        for kind, sign in (("load", 1.0), ("wind", -1.0), ("pv", -1.0), ("rtpv", -1.0)):
            series = rts.timeseries(kind, market)
            total = (
                total
                + sign
                * series.select(
                    pl.sum_horizontal(
                        [c for c in series.columns if c not in rts.TIME_COLS]
                    )
                )
                .to_numpy()
                .ravel()
            )
        return total

    day_ahead = net_load("day_ahead")  # hourly
    real_time = (
        net_load("real_time").reshape(-1, 12).mean(axis=1)
    )  # twelve five-minute values per hour
    return float(np.std(real_time - day_ahead))


def windows(
    T: int = 168,
    alpha: float = 0.05,
    reserve_margin: float | None = 0.15,
    reserve_offer: float = 0.1,
) -> list[Scenario]:
    """The year cut into operating windows of T hours, under one tightness
    scale: the annual tightest hour has the margin and the other windows keep
    their seasonal slack. At the default 0.15, ERCOT's energy-only prices pay
    the fleet's annual investment cost and PJM is short about 1.06 B$."""
    hours = rts.timeseries("load", "day_ahead").height
    return tighten(
        [
            scenario(s, T, alpha, reserve_margin=None, reserve_offer=reserve_offer)
            for s in range(0, hours - hours % T, T)
        ],
        reserve_margin,
    )


def tighten(scenarios: list[Scenario], reserve_margin: float | None) -> list[Scenario]:
    """Scale δ and d° in every scenario by one factor so that the tightest hour
    across them has ``margin == reserve_margin``. Scaling load, not capacity,
    keeps unit sizes and the merit order intact; α is unchanged."""
    if reserve_margin is None:
        return scenarios
    s = (min(margin(sc) for sc in scenarios) + 1.0) / (1.0 + reserve_margin)
    return [
        Scenario(
            sc.delta * s,
            sc.d_other * s,
            sc.cost_gen,
            sc.cost_res,
            sc.cost_inv,
            sc.capacity,
            sc.nameplate,
            sc.unit,
            sc.names,
            sc.start,
            sc.epsilon_std,
        )
        for sc in scenarios
    ]


def margin(scenario: Scenario) -> float:
    """The tightest hour's available capacity over system load, minus one."""
    return float((scenario.capacity.sum(axis=0) / scenario.d_sys).min() - 1.0)


# ----------------------------------------------------------------------------
# 𝓜_ω
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class ORDC:
    """ERCOT's operating reserve demand curve π as steps: ``widths`` w_s in MW
    (the last is ∞) and ``prices`` π_s in $/MW-h, decreasing. Reserve above
    load-following fills the steps in order; the step in use sets μ_t."""

    widths: np.ndarray
    prices: np.ndarray

    @classmethod
    def from_lolp(
        cls, voll: float, min_contingency: float, epsilon_std: float, steps: int = 10
    ) -> "ORDC":
        """π(z) = VOLL · Pr[ε > z − R̲] with ε ~ N(0, epsilon_std²), as steps
        spaced evenly in price: heights at fractions (steps−1)/steps, …, 1/steps
        of VOLL, widths from the normal quantiles where the curve crosses each
        height, then a step of zero price and infinite width. Narrow near R̲,
        wide in the tail."""
        from scipy.stats import norm

        fractions = np.arange(steps - 1, 0, -1) / steps
        edges = np.concatenate(
            [
                [0.0],
                np.maximum(
                    min_contingency + epsilon_std * norm.ppf(1.0 - fractions), 0.0
                ),
            ]
        )
        prices = voll * np.concatenate(
            [[1.0], fractions[:-1]]
        )  # each step's height is the curve at its left edge
        return cls(
            np.concatenate([np.diff(edges), [np.inf]]), np.concatenate([prices, [0.0]])
        )


@dataclass(frozen=True)
class Dispatch:
    """What 𝓜_ω(d, σ) determined: the load's consumption d (the report's dᶜᵘʳᵗ)
    and cleared reserve σ (σᶜˡʳ), generation, prices (λ, μ, ν), the reserve
    value Π_t, and the cost of each layer Cᵏ. The bid it answered is kept as
    ``d_bid``, ``sigma_bid``. Shapes (T,) unless noted."""

    d: np.ndarray  # consumption served
    sigma: np.ndarray  # reserve cleared from the load's offer
    u: np.ndarray  # (J, T) generation
    r: np.ndarray  # (J, T) generator reserve
    shed: np.ndarray  # other load not served, at VOLL
    lam: np.ndarray  # energy price λ
    mu: np.ndarray  # reserve price μ
    nu: np.ndarray  # (J, T) capacity rent ν
    eta: np.ndarray  # value of one more MW of the load's offer, η
    Pi: np.ndarray  # value of reserve held, ∫π (ERCOT); zero under PJM
    C_energy: np.ndarray  # cost of the energy layer, λ_t d_sys_t
    C_res: np.ndarray  # cost of the reserve layer, μ_t (Σ_j r_jt + σ_t)
    C_inv: float  # cost of the investment layer for the window: annual Cⁱⁿᵛ × T/8760
    d_bid: np.ndarray  # the load's bid
    sigma_bid: np.ndarray  # the load's offer
    d_firm: np.ndarray  # the firm level the operator may not curtail below
    c_sigma: np.ndarray  # the offer price c^σ
    y: np.ndarray  # (J,) capacity: nameplate in the short run, chosen in the long run
    curtailable: bool  # the load declared a firm level, so d may sit below d_bid
    status: str = ""


@dataclass(frozen=True)
class Market:
    """The environment: ``reserve`` is ``"pjm"`` (hard requirement: if unit j'
    trips, everyone else's reserve covers its output plus γ d_sys) or
    ``"ercot"`` (R_t ≥ γ d_sys, and reserve above that valued on the demand
    curve Π_t). ``C_inv`` is the annual cost of the investment layer from
    :func:`C_inv`; the short run needs it. Never the operator's choice."""

    reserve: str = "ercot"
    gamma: float = 0.03
    voll: float = 5000.0
    long_run: bool = False
    ordc: ORDC | None = None  # ercot; None -> fit from the window's forecast error
    C_inv: float | None = None
    solver: str = "GUROBI"
    solver_options: dict = field(default_factory=dict)

    def ordc_for(self, scenario: Scenario) -> ORDC:
        """The curve: ``ordc`` if given, else fit with R̲ at the largest unit's
        output (the contingency PJM's row protects against) and the data's ε."""
        if self.ordc is not None:
            return self.ordc
        return ORDC.from_lolp(
            self.voll,
            float((scenario.units @ scenario.nameplate).max()),
            scenario.epsilon_std,
        )

    # --- the objective and constraints, written once; used by clear, planner, S --
    def C_sys(self, scenario: Scenario, u, r, sigma, c_sigma, shed, y, Pi):
        """System cost: Σ_t [Σ_j (cᵘ u + cʳ r) + c^σ σ + cⱽᴼᴸᴸ s − Π_t] plus Σ_j cⁱⁿᵛ y
        in the long run. The dispatch objective is this plus the load's own
        curtailment at VOLL, which stands in for its value."""
        cost = cp.sum(cp.multiply(scenario.cost_gen[:, None], u)) + cp.sum(
            cp.multiply(scenario.cost_res[:, None], r)
        )
        cost = (
            cost
            + cp.sum(cp.multiply(c_sigma, sigma))
            + self.voll * cp.sum(shed)
            - cp.sum(Pi)
        )
        if self.long_run:
            cost = cost + (scenario.cost_inv * scenario.T / HOURS_PER_YEAR) @ y
        return cost

    def constraints(
        self, scenario: Scenario, sigma_bid, d_firm, u, r, sigma, d, y, z, shed
    ) -> dict:
        """Balance (λ), capacity (ν), reserve (μ), offer (η), as named cvxpy
        constraints. Reserve held is R_t = Σ_j r_jt + σ_t + (d_t − dᶠⁱʳᵐ_t)."""
        T, J = scenario.T, scenario.J
        d_sys = d + scenario.d_other
        cons = {"balance": cp.sum(u, axis=0) + shed == d_sys}
        if self.long_run:
            cons["capacity"] = u + r <= cp.multiply(
                scenario.availability,
                cp.reshape(y, (J, 1), order="C") @ np.ones((1, T)),
            )
        else:
            cons["capacity"] = u + r <= scenario.capacity
        X = cp.Variable(
            T
        )  # reserve above load-following, its own variable so the per-unit rows stay sparse
        cons["net_reserve"] = (
            X == cp.sum(r, axis=0) + sigma + (d - d_firm) - self.gamma * d_sys
        )
        M = scenario.units
        if self.reserve == "pjm":
            cons["reserve"] = (
                np.ones((M.shape[0], 1)) @ cp.reshape(X, (1, T), order="C")
                >= M @ u + M @ r
            )
        else:
            widths = self.ordc_for(scenario).widths
            cons["reserve"] = (
                cp.sum(z, axis=0) == X
            )  # dual: the height of the step in use, μ_t
            cons["steps"] = (
                z[np.isfinite(widths), :] <= widths[np.isfinite(widths), None]
            )
        if isinstance(sigma, cp.Variable):
            cons["offer"] = sigma <= sigma_bid
        return cons

    # --- dispatch ------------------------------------------------------------------
    def clear(
        self,
        scenario: Scenario,
        d_bid: np.ndarray,
        sigma_bid: np.ndarray,
        c_sigma: np.ndarray,
        d_firm: np.ndarray | None = None,
    ) -> Dispatch:
        """𝓜_ω(d, σ): dispatch against the load's bid (d_bid, sigma_bid) at offer
        price c^σ and its declared firm level, and read what cleared. ``d_firm``
        is the type's level for a curtailable load, ``None`` otherwise. A
        curtailable load does not offer reserve."""
        T, J = scenario.T, scenario.J
        d_bid = np.asarray(d_bid, float)
        sigma_bid = np.maximum(np.asarray(sigma_bid, float), 0.0)  # a solver's −1e-10 on σ ≥ 0 is no offer
        c_sigma = np.broadcast_to(np.asarray(c_sigma, float), (T,))
        curtailable = d_firm is not None
        d_firm = np.asarray(d_firm, float) if curtailable else d_bid
        if curtailable:
            sigma_bid = np.zeros(T)
        offers = bool(np.any(sigma_bid > 0.0))

        u = cp.Variable((J, T), nonneg=True)
        r = cp.Variable((J, T), nonneg=True)
        shed = cp.Variable(T, nonneg=True)
        sigma = cp.Variable(T, nonneg=True) if offers else np.zeros(T)
        d = cp.Variable(T) if curtailable else d_bid
        y = cp.Variable(J, nonneg=True) if self.long_run else scenario.nameplate
        if self.reserve == "ercot":
            z = cp.Variable((self.ordc_for(scenario).widths.size, T), nonneg=True)
            Pi = self.ordc_for(scenario).prices @ z
        else:
            z, Pi = None, np.zeros(T)

        cost = self.C_sys(scenario, u, r, sigma, c_sigma, shed, y, Pi)
        cons = self.constraints(scenario, sigma_bid, d_firm, u, r, sigma, d, y, z, shed)
        if curtailable:
            cost = cost + self.voll * cp.sum(d_bid - d)
            cons["curtail"] = d >= d_firm
            cons["serve"] = d <= d_bid
        problem = cp.Problem(cp.Minimize(cost), list(cons.values()))
        problem.solve(solver=self.solver, **self.solver_options)
        if problem.status not in ("optimal", "optimal_inaccurate"):
            raise RuntimeError(f"clearing failed: {problem.status}")

        # cvxpy reports an equality dual as −∂cost/∂rhs. Balance has load on the right, so λ = −dual.
        # The demand-curve row has reserve on the right and more reserve lowers cost, so μ = +dual.
        lam = -_dual(cons["balance"])
        mu = (
            np.asarray(cons["reserve"].dual_value).sum(axis=0)
            if self.reserve == "pjm"
            else _dual(cons["reserve"])
        )
        d, sigma, r_ = _value(d), _value(sigma), _value(r)
        if self.C_inv is None and not self.long_run:
            raise ValueError(
                "the short run needs Market.C_inv; see C_inv(market, windows(...))"
            )
        return Dispatch(
            d=d,
            sigma=sigma,
            u=_value(u),
            r=r_,
            shed=_value(shed),
            lam=lam,
            mu=np.asarray(mu),
            nu=np.asarray(cons["capacity"].dual_value),
            eta=_dual(cons["offer"]) if "offer" in cons else np.zeros(T),
            Pi=_value(Pi),
            C_energy=lam * (d + scenario.d_other),
            C_res=mu * (r_.sum(axis=0) + sigma),
            C_inv=0.0 if self.long_run else float(self.C_inv) * T / HOURS_PER_YEAR,
            d_bid=d_bid,
            sigma_bid=sigma_bid,
            d_firm=d_firm,
            c_sigma=np.asarray(c_sigma),
            y=_value(y),
            curtailable=curtailable,
            status=problem.status,
        )

    def marginal_cost(self, dispatch: Dispatch) -> dict[str, np.ndarray]:
        """∂C_sys/∂d_t split the way the bill is: energy λ, reserve γμ less μ on
        curtailable headroom, investment 0 in the short run. For alignment."""
        headroom = dispatch.d_firm < dispatch.d_bid - 1e-9
        return {
            "energy": dispatch.lam,
            "reserve": self.gamma * dispatch.mu - headroom * dispatch.mu,
            "investment": np.zeros(dispatch.lam.shape),
        }


def C_inv(market: Market, windows: list[Scenario], cache: bool = True) -> float:
    """The annual cost of the investment layer: max(0, Σ_j (cⁱⁿᵛ_j − Σ_t ν_jt) ū_j)
    on the B0 path (δ, 0) over the year, investment cost less the rents capacity
    earns in the market, in $. The floor at zero: a market whose prices overpay
    the fleet has nothing left to collect, so the layer bills zero rather than
    crediting the load. ``clear`` prorates it to the window by T/8760. Cached
    under ``~/.cache/flexload`` by market fields and the year's data; the cache
    keeps the signed value."""
    key = None
    if cache:
        h = hashlib.sha1(repr((market.reserve, market.gamma, market.voll)).encode())
        if market.ordc is not None:
            h.update(market.ordc.widths.tobytes() + market.ordc.prices.tobytes())
        for s in windows:
            for a in (
                s.d_sys,
                s.capacity,
                s.cost_inv,
                s.cost_gen,
                s.cost_res,
                np.array([s.epsilon_std]),
            ):
                h.update(np.ascontiguousarray(a).tobytes())
        key = Path.home() / ".cache" / "flexload" / "C_inv" / f"{h.hexdigest()}.json"
        if key.exists():
            return max(float(json.loads(key.read_text())["annual"]), 0.0)
    m = Market(
        market.reserve,
        market.gamma,
        market.voll,
        False,
        market.ordc,
        0.0,
        market.solver,
        market.solver_options,
    )
    by_window = []
    for s in windows:
        b0 = m.clear(s, s.delta, np.zeros(s.T), np.zeros(s.T))
        by_window.append(
            float(
                np.sum(
                    (s.cost_inv * s.T / HOURS_PER_YEAR - b0.nu.sum(axis=1))
                    * s.nameplate
                )
            )
        )
    annual = float(np.sum(by_window))
    if key is not None:
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text(
            json.dumps(
                {
                    "annual": annual,
                    "by_window": by_window,
                    "starts": [s.start for s in windows],
                }
            )
        )
    return max(annual, 0.0)


def _value(v) -> np.ndarray:
    """A number from a cvxpy expression or a number."""
    return np.asarray(v.value if isinstance(v, cp.Expression) else v, dtype=float)


def _dual(constraint) -> np.ndarray:
    return np.asarray(constraint.dual_value, dtype=float).reshape(-1)
