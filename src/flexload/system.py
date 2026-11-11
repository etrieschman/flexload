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
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

import cvxpy as cp
import numpy as np
import polars as pl
import rts_gmlc as rts

HOURS_PER_YEAR = 8760
VOLL = 5000.0  # c^VOLL, the value of lost load, $/MWh: c^shed, and c^pen where a construct prices at it
# PJM's curve (placeholders, 2026-11-11): $850/MWh up to the requirement, then $300/MWh for 190 MW more.
# The second step is kept as a share of the contingency, 190 MW over a largest contingency of about 1,600 MW.
PJM_PENALTY, PJM_SECOND_STEP, PJM_EXTENDED = 850.0, 300.0, 0.12
PJM_PRIMARY = 1.5  # PJM's 10-minute requirement, primary reserve, is 1.5 times the largest contingency

# Placeholder annualized capital cost by RTS-GMLC category, $/kW-year (RTS-GMLC
# has none). Round numbers that sum to 1,757 M$ a year for the fleet. At the
# 0.027 reserve margin ERCOT's rent pays 1,075 M$ of that and PJM's 795 M$
# (notebooks/tune_reserve_margin.py). Replace with a cited table before a
# result depends on the investment layer.
INVESTMENT_COST_PER_KW_YEAR = {
    "Nuclear": 400.0,
    "Coal": 250.0,
    "Gas CC": 80.0,
    "Gas CT": 60.0,
    "Oil CT": 60.0,
    "Oil ST": 200.0,
    "Hydro": 200.0,
    "Wind": 100.0,
    "Solar PV": 60.0,
    "Solar RTPV": 60.0,
    "CSP": 350.0,
}
EXCLUDED = ("Storage", "Sync_Cond", "CSP")  # no single-period dispatch model
RENEWABLE = ("pv", "rtpv", "wind", "hydro")  # availability from the time series


# ----------------------------------------------------------------------------
# ω and δ
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Normal:
    """An error model: error ~ N(m, v²), in MW."""

    m: float
    v: float


def fit(error: np.ndarray) -> Normal:
    """The normal fit to a sample of errors, as ERCOT fits its curve: their
    mean and standard deviation. An operator that learns calls this on the
    imbalance it has seen."""
    return Normal(float(np.mean(error)), float(np.std(error)))


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
    error_fit: Normal | None = None  # (m, v) of the normal fit to the year's net-load error, MW
    trip: np.ndarray | None = None  # (J,) hourly probability that the column's unit trips, 1/MTTF; zero for renewables
    error: np.ndarray | None = None  # (T, 12) the window's net-load error: each five-minute value less the hour's mean, MW

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
    def renewable(self) -> np.ndarray:
        """(J,) True for wind, solar and hydro columns, by name. They offer no
        reserve and are no contingency: their output is a forecast quantity,
        whose error is ε."""
        return np.array([any(tag in n.upper() for tag in ("WIND", "PV", "HYDRO")) for n in self.names], dtype=bool)

    @property
    def availability(self) -> np.ndarray:
        """(J, T) capacity as a fraction of nameplate; the long run's capacity shape."""
        return (
            self.capacity / np.where(self.nameplate > 0, self.nameplate, 1.0)[:, None]
        )


def _year(df: pl.DataFrame) -> pl.DataFrame:
    """The data's year without February 29: 8,760 hours, so a year is a year."""
    return df.filter(~((pl.col("month") == 2) & (pl.col("day") == 29)))


def scenario(
    start: int = 29 * 168,
    T: int = 168,
    alpha: float = 0.05,
    reserve_margin: float | None = 0.027,
    reserve_offer: float = 0.1,
) -> Scenario:
    """Hours ``[start, start + T)`` of RTS-GMLC's real-time series at one node,
    each hour at the mean of its twelve five-minute values, February 29
    dropped. Dispatch stands for the real-time market, so it clears on what the
    hour was; what moves within the hour is the imbalance (``error``).
    ``alpha`` sets the load's size: δ is that share of system load, hour by
    hour, carved out of the RTS total so δ + d° is the data. ``reserve_margin``
    scales both loads so the tightest hour has that margin (``tighten``). The
    default 0.027 is held from 2026-11-11: the inflexible baseline then sheds
    502 MWh a year under ERCOT, 0.0011% of energy, near a common reliability
    standard, and ERCOT's rent pays 1,075 M$ of the fleet's 1,757 M$
    (notebooks/tune_reserve_margin.py). ERCOT's rent pays all of it only near
    0.010. Dispatch has no outages: every unit is available in every hour, so
    the margin is capacity that is spare at the tightest hour. ``reserve_offer`` sets the
    reserve offer cʳⱼ = reserve_offer × cᵘⱼ on thermal blocks (RTS-GMLC has
    none); renewables and hydro offer none."""
    lo, hi = start, start + T
    if hi > HOURS_PER_YEAR:
        raise ValueError(f"hours {lo}:{hi} are not in the year")
    total = _real_time("load")[1][lo:hi].mean(axis=1).sum(axis=1)  # the hour's mean, the three areas summed
    delta = alpha * total

    blocks = rts.offer_blocks().filter(pl.col("mw") > 0.0)
    renewable = {}  # unit -> (T,) available output, the hour's mean
    for kind in RENEWABLE:
        names, mw = _real_time(kind)
        renewable |= {uid: mw[lo:hi, :, i].mean(axis=1) for i, uid in enumerate(names)}
    cols = []  # (cost_gen, cost_res, cost_inv, capacity (T,), nameplate, unit, name, trip)
    for u, g in enumerate(rts.gen().iter_rows(named=True)):
        uid, cat = g["gen_uid"], g["category"]
        if cat in EXCLUDED:
            continue
        inv = INVESTMENT_COST_PER_KW_YEAR[cat] * 1000.0
        if uid in renewable:
            avail = renewable[uid]
            cols.append(
                (float(g["vom"] or 0.0), 0.0, inv, avail, float(g["pmax_mw"]), u, uid, 0.0)  # no offer: nothing idle to hold
            )
        else:
            trip = 1.0 / float(g["mttf_hr"])  # a failure every MTTF hours of running
            for mw, cost in (
                blocks.filter(pl.col("gen_uid") == uid).select("mw", "cost").iter_rows()
            ):
                cols.append(
                    (float(cost), reserve_offer * float(cost), inv, mw * np.ones(T), float(mw), u, uid, trip)
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
        error_fit=fit(_net_load_error()),
        trip=np.array([c[7] for c in cols]),
        error=_net_load_error()[lo:hi],
    )
    return tighten([s], reserve_margin)[0]


@lru_cache(maxsize=None)
def _real_time(kind: str) -> tuple[tuple[str, ...], np.ndarray]:
    """The year's real-time series of ``kind`` (load, wind, pv, rtpv, hydro):
    its column names and an (8760, 12, C) array, MW in each five-minute
    interval of each hour."""
    series = _year(rts.timeseries(kind, "real_time"))
    names = tuple(c for c in series.columns if c not in rts.TIME_COLS)
    return names, series.select(names).to_numpy().astype(float).reshape(-1, 12, len(names))


@lru_cache(maxsize=None)
def _net_load_error() -> np.ndarray:
    """(8760, 12) net-load error over the year, MW: net load in each
    five-minute interval less its mean over the hour. Dispatch clears on the
    hour's mean, so this is what it does not see. Net load is load less wind
    and solar."""
    net = sum(sign * _real_time(kind)[1].sum(axis=2) for kind, sign in (("load", 1.0), ("wind", -1.0), ("pv", -1.0), ("rtpv", -1.0)))
    return net - net.mean(axis=1, keepdims=True)


def windows(
    T: int = 168,
    alpha: float = 0.05,
    reserve_margin: float | None = 0.027,
    reserve_offer: float = 0.1,
) -> list[Scenario]:
    """The year cut into operating windows of T hours, under one tightness
    scale: the annual tightest hour has the margin and the other windows keep
    their seasonal slack. At the default 0.027, ERCOT's prices leave 683 M$
    of the fleet's investment cost to its pool and PJM's leave 963 M$
    (notebooks/tune_reserve_margin.py). Week 29 holds the year's tightest
    hour. The last 24 hours of the year fall outside the 52 windows."""
    hours = HOURS_PER_YEAR
    return tighten(
        [
            scenario(s, T, alpha, reserve_margin=None, reserve_offer=reserve_offer)
            for s in range(0, hours - hours % T, T)
        ],
        reserve_margin,
    )


def tighten(scenarios: list[Scenario], reserve_margin: float | None) -> list[Scenario]:
    """Scale δ and d° in every scenario by one factor so that the tightest hour
    across them has ``margin == reserve_margin``, and the forecast error ε with
    them, since it is an error on load. Scaling load, not capacity, keeps unit
    sizes and the merit order intact; α is unchanged."""
    if reserve_margin is None:
        return scenarios
    s = (min(margin(sc) for sc in scenarios) + 1.0) / (1.0 + reserve_margin)
    return [
        replace(
            sc,
            delta=sc.delta * s,
            d_other=sc.d_other * s,
            error_fit=None if sc.error_fit is None else Normal(sc.error_fit.m * s, sc.error_fit.v * s),
            error=None if sc.error is None else sc.error * s,
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
class Points:
    """An error model: the error is ``mw[i]`` with ``probability[i]``. One
    point at zero is no error."""

    mw: np.ndarray
    probability: np.ndarray


@dataclass(frozen=True)
class Expectation:
    """A statistic: the expectation, priced at c^pen. The curve is
    π(z) = c^pen · Pr[error > z]."""

    c_pen: float


@dataclass(frozen=True)
class Maximum:
    """A statistic: the maximum. Reserve must cover the largest error; a
    requirement, priced at c^shed because shedding load is what relieves it."""


@dataclass(frozen=True)
class ORDC:
    """A reserve construct: the operator's model of the imbalance,
    ε_t = contingency_t + error, and the statistic that prices it.
    The contingency is the larger of the level R̲ (``min_contingency``) and the
    largest online unit's output and reserve, each unit weighted by ``units``:
    0 leaves a unit out, 1 covers it, 1.5 covers it one and a half times.
    ERCOT sets the level; a requirement on the largest unit sets the vector."""

    min_contingency: float  # R̲, MW
    units: np.ndarray  # (U,) the multiple of each unit's output and reserve the requirement covers
    error: Normal | Points
    statistic: Expectation | Maximum
    name: str = ""


def steps(ordc: ORDC, c_shed: float, n: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """The curve π as steps. ``edges`` e_1 < … < e_S are MW of reserve above
    the contingency and ``prices`` are π_1, …, π_S: π_s prices reserve between
    e_{s−1} and e_s, the first step starts at zero reserve, and reserve above
    e_S is priced at zero. So the first step's width is contingency_t + e_1 and
    the others' are w_s = e_s − e_{s−1}.
    Reserve below the contingency is priced at the top price, as ERCOT sets its
    probability to one below the minimum contingency level and PJM prices its
    requirement at the penalty factor: e_1 = 0. Above it each step is priced at
    the curve's height at its left edge. A normal error is cut into ``n`` steps
    evenly spaced in price, so its tail below 1/n of c^pen is priced at zero."""
    error, statistic = ordc.error, ordc.statistic
    if isinstance(error, Normal):
        from scipy.stats import norm

        exceed = np.arange(n - 1, 0, -1) / n  # Pr[error > e_s]
        edges = error.m + error.v * norm.ppf(1.0 - exceed)
    else:
        order = np.argsort(error.mw)
        edges = np.asarray(error.mw, float)[order]
        exceed = np.maximum(1.0 - np.cumsum(np.asarray(error.probability, float)[order]), 0.0)
    edges = np.maximum(edges, 0.0)  # the top price up to the contingency
    if isinstance(statistic, Maximum):
        if isinstance(error, Normal):
            raise ValueError("the maximum of a normal error is unbounded")
        return edges[-1:], np.array([c_shed])
    prices = statistic.c_pen * np.concatenate([[1.0], exceed[:-1]])
    keep = np.concatenate([[True], np.diff(edges) > 0.0])  # steps of zero width say nothing
    return edges[keep], prices[keep]


def named_ordcs(scenario: Scenario) -> dict[str, ORDC]:
    """The constructs, on the scenario's fleet and forecast error. A
    contingency is a thermal unit: a wind farm's output is a forecast quantity,
    and its error is in ε.
    ``ercot``: R̲ at the largest thermal unit's nameplate, a normal error, the
    expectation at VOLL.
    ``pjm``: 1.5 times the largest online thermal unit (PJM's primary reserve,
    its 10-minute requirement), then PJM's second step read as an error (zero,
    or the extended requirement with probability 300/850), the expectation at
    the $850 penalty factor.
    ``n-1``: the largest online thermal unit, no error, the maximum: a hard
    requirement."""
    thermal = (scenario.units @ ~scenario.renewable > 0).astype(float)
    largest = float((scenario.units @ (scenario.nameplate * ~scenario.renewable)).max())
    second = PJM_SECOND_STEP / PJM_PENALTY
    extended = Points(np.array([0.0, PJM_EXTENDED * largest]), np.array([1.0 - second, second]))
    return {
        "ercot": ORDC(largest, np.zeros(thermal.size), scenario.error_fit, Expectation(VOLL), "ercot"),
        "pjm": ORDC(0.0, PJM_PRIMARY * thermal, extended, Expectation(PJM_PENALTY), "pjm"),
        "n-1": ORDC(0.0, thermal, Points(np.zeros(1), np.ones(1)), Maximum(), "n-1"),
    }


@dataclass(frozen=True)
class Dispatch:
    """What 𝓜_ω(d, σ) determined: the load's consumption d (the report's dᶜᵘʳᵗ)
    and cleared reserve σ (σᶜˡʳ), generation, prices (λ, μ, ν), the ORDC's
    cost C^ORDC_t, and the cost of each layer Cᵏ. The bid it answered is kept
    as ``d_bid``, ``sigma_bid``. Shapes (T,) unless noted."""

    d: np.ndarray  # consumption served
    sigma: np.ndarray  # reserve cleared from the load's offer
    u: np.ndarray  # (J, T) generation
    r: np.ndarray  # (J, T) generator reserve
    shed: np.ndarray  # other load not served, at VOLL
    lam: np.ndarray  # energy price λ
    mu: np.ndarray  # reserve price μ
    nu: np.ndarray  # (J, T) capacity rent ν
    C_ordc: np.ndarray  # the ORDC's cost C^ORDC_t = Σ_s π_s (w_st − z_st): expected imbalance reserve does not cover
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
    """The environment: the reserve construct ``ordc`` and the price c^shed on
    load shed. ``C_inv`` is the annual cost of the investment layer from
    :func:`C_inv`; the short run needs it."""

    ordc: ORDC
    c_shed: float = VOLL
    long_run: bool = False
    C_inv: float | None = None
    solver: str = "GUROBI"
    solver_options: dict = field(default_factory=dict)

    def curve(self) -> tuple[np.ndarray, np.ndarray]:
        """The ORDC as steps, (edges, prices); see :func:`steps`."""
        return steps(self.ordc, self.c_shed)

    # --- the objective and constraints, written once; used by clear, planner, S --
    def C_ordc(self, scenario: Scenario, u, r, z):
        """C^ORDC_t = Σ_s π_s (w_st − z_st), the expected cost of the imbalance
        that reserve does not cover; z_st is how much of step s reserve fills.
        The first step's width is the contingency plus e_1. Where the
        contingency is the largest online unit that width moves with dispatch,
        so the first step's unfilled part is written max(0, w − z): one row
        per unit, as a requirement on the largest unit is."""
        edges, prices = self.curve()
        M = (scenario.units * self.ordc.units[:, None])[self.ordc.units > 0]
        contingency = self.ordc.min_contingency
        if M.shape[0] > 0:
            contingency = cp.maximum(contingency, cp.max(M @ (u + r), axis=0))
        cost = prices[0] * cp.pos(contingency + edges[0] - z[0])
        if edges.size > 1:
            cost = cost + prices[1:] @ (np.diff(edges)[:, None] - z[1:])
        return cost

    def C_sys(self, scenario: Scenario, u, r, sigma, c_sigma, shed, y, C_ordc):
        """System cost: Σ_t [Σ_j (cᵘ u + cʳ r) + c^σ σ + c^shed s + C^ORDC_t] plus
        Σ_j cⁱⁿᵛ y in the long run. The dispatch objective is this plus the
        load's own curtailment at c^shed, which stands in for its value."""
        cost = cp.sum(cp.multiply(scenario.cost_gen[:, None], u)) + cp.sum(
            cp.multiply(scenario.cost_res[:, None], r)
        )
        cost = (
            cost
            + cp.sum(cp.multiply(c_sigma, sigma))
            + self.c_shed * cp.sum(shed)
            + cp.sum(C_ordc)
        )
        if self.long_run:
            cost = cost + (scenario.cost_inv * scenario.T / HOURS_PER_YEAR) @ y
        return cost

    def constraints(
        self, scenario: Scenario, sigma_bid, d_firm, u, r, sigma, d, y, z, shed
    ) -> dict:
        """Balance (λ), capacity (ν), reserve (μ) and the load's offer, as
        named cvxpy constraints. Reserve held is
        R_t = Σ_j r_jt + σ_t + (d_t − dᶠⁱʳᵐ_t), and it fills the ORDC's steps:
        R_t = Σ_s z_st."""
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
        if scenario.renewable.any():  # wind, solar and hydro offer no reserve
            cons["renewable_reserve"] = r[np.flatnonzero(scenario.renewable), :] == 0
        cons["reserve"] = (  # dual: the height of the step in use, μ_t
            cp.sum(z, axis=0) == cp.sum(r, axis=0) + sigma + (d - d_firm)
        )
        edges = self.curve()[0]
        if edges.size > 1:  # the first step's width is in C_ordc
            cons["steps"] = z[1:] <= np.diff(edges)[:, None]
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
        z = cp.Variable((self.curve()[1].size, T), nonneg=True)
        C_ordc = self.C_ordc(scenario, u, r, z)

        cost = self.C_sys(scenario, u, r, sigma, c_sigma, shed, y, C_ordc)
        cons = self.constraints(scenario, sigma_bid, d_firm, u, r, sigma, d, y, z, shed)
        if curtailable:
            cost = cost + self.c_shed * cp.sum(d_bid - d)
            cons["curtail"] = d >= d_firm
            cons["serve"] = d <= d_bid
        problem = cp.Problem(cp.Minimize(cost), list(cons.values()))
        problem.solve(solver=self.solver, **self.solver_options)
        if problem.status not in ("optimal", "optimal_inaccurate"):
            raise RuntimeError(f"clearing failed: {problem.status}")

        # cvxpy reports an equality dual as −∂cost/∂rhs. Balance has load on the right, so λ = −dual.
        # The reserve row has reserve on the right and more reserve lowers cost, so μ = +dual.
        lam = -_dual(cons["balance"])
        mu = _dual(cons["reserve"])
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
            C_ordc=_value(C_ordc),
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
        """∂C_sys/∂d_t split the way the bill is: energy λ, reserve −μ on
        curtailable headroom and zero otherwise, investment 0 in the short run.
        For alignment."""
        headroom = dispatch.d_firm < dispatch.d_bid - 1e-9
        return {
            "energy": dispatch.lam,
            "reserve": -(headroom * dispatch.mu),
            "investment": np.zeros(dispatch.lam.shape),
        }


def C_inv(market: Market, windows: list[Scenario], cache: bool = True) -> float:
    """The annual cost of the investment layer: max(0, Σ_j cⁱⁿᵛ_j ū_j − rent),
    the fleet's investment cost on nameplate less the rent it earns on the B0
    path (δ, 0), in $. The rent is the fleet's profit, revenue above fuel and
    reserve offers (:func:`flexload.metrics.rent`), summed over the windows and
    scaled to 8760 hours. (Until 2026-10-25 the rent was Σ ν ū on nameplate,
    which overstated renewables' rent and missed the reserve row's dual on the
    binding unit under PJM.) The floor at zero: a market whose prices overpay
    the fleet has nothing left to collect, so the layer bills zero rather than
    crediting the load. ``clear`` prorates it to the window by T/8760. Cached
    under ``~/.cache/flexload`` by market fields and the year's data; the cache
    keeps the signed value."""
    key = None
    if cache:
        h = hashlib.sha1(repr((market.ordc.min_contingency, market.c_shed, "rent as profit, 8760 h")).encode())
        for a in (*market.curve(), market.ordc.units):
            h.update(np.ascontiguousarray(a, dtype=float).tobytes())
        for s in windows:
            for a in (
                s.d_sys,
                s.capacity,
                s.cost_inv,
                s.cost_gen,
                s.cost_res,
                np.array([s.error_fit.m, s.error_fit.v]),
            ):
                h.update(np.ascontiguousarray(a).tobytes())
        key = Path.home() / ".cache" / "flexload" / "C_inv" / f"{h.hexdigest()}.json"
        if key.exists():
            return max(float(json.loads(key.read_text())["annual"]), 0.0)
    m = replace(market, long_run=False, C_inv=0.0)
    by_window = []  # the fleet's rent in each window
    for s in windows:
        b0 = m.clear(s, s.delta, np.zeros(s.T), np.zeros(s.T))
        by_window.append(
            float(np.sum((b0.lam - s.cost_gen[:, None]) * b0.u + (b0.mu - s.cost_res[:, None]) * b0.r))
        )
    cost = float(np.sum(windows[0].cost_inv * windows[0].nameplate))
    annual = cost - float(np.sum(by_window)) * HOURS_PER_YEAR / sum(s.T for s in windows)
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
