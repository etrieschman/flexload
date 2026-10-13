"""The exogenous state ω and the load's preferred profile δ for one week.

A :class:`Scenario` is numbers only: what the memo calls
ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū) plus δ. :func:`build_scenario` makes one from RTS-GMLC
through the ``rts_gmlc`` package, aggregated to a single node, with the four
knobs the memo's experiment section varies: the week, the flexible share α, the
capacity tightness, and the outage seed.

Generators are *offer blocks*: each column ``j`` is one step of a unit's
heat-rate curve (or one variable-output unit), so costs are linear and the
merit order is a step function, as the memo assumes. ``unit[j]`` says which
physical unit a column belongs to, which is what the largest-single-contingency
reserve constraint is written over.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HOURS_PER_WEEK = 168

# Placeholder annualized capital cost by RTS-GMLC category, $/kW-year. RTS-GMLC
# carries no capital costs; these are order-of-magnitude figures in the spirit of
# EIA AEO overnight costs annualized at ~8% over ~30 years. Replace with a cited
# table before any result depends on the investment layer (docs/assumptions.md).
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
EXCLUDED_CATEGORIES = ("Storage", "Sync_Cond", "CSP")  # no single-period dispatch model
RENEWABLE_SERIES = ("pv", "rtpv", "wind", "hydro")  # availability from the time series


@dataclass(frozen=True)
class Scenario:
    """One week. Shapes: T hours, J generator columns."""

    delta: np.ndarray  # (T,) the load's preferred consumption δ, MW
    d_other: np.ndarray  # (T,) all other load d°, MW
    cost_gen: np.ndarray  # (J,) energy cost cᵘ, $/MWh
    cost_res: np.ndarray  # (J,) reserve cost cʳ, $/MW-h
    cost_inv: np.ndarray  # (J,) investment cost cⁱⁿᵛ, $/MW per week
    capacity: np.ndarray  # (J, T) available capacity ū after outages and renewable availability, MW
    nameplate: np.ndarray  # (J,) installed capacity, MW; the long run chooses y against this shape
    unit: np.ndarray  # (J,) int, physical unit of each column
    names: tuple[str, ...] = ()
    week: int | None = None

    def __post_init__(self):
        T, J = self.delta.shape[0], self.cost_gen.shape[0]
        assert self.d_other.shape == (T,)
        assert self.cost_res.shape == self.cost_inv.shape == self.nameplate.shape == self.unit.shape == (J,)
        assert self.capacity.shape == (J, T), self.capacity.shape

    @property
    def T(self) -> int:
        return self.delta.shape[0]

    @property
    def J(self) -> int:
        return self.cost_gen.shape[0]

    @property
    def d_sys(self) -> np.ndarray:
        """System load when the flexible load consumes δ (the B0 path)."""
        return self.delta + self.d_other

    @property
    def availability(self) -> np.ndarray:
        """(J, T) capacity as a fraction of nameplate; the long-run capacity shape."""
        nz = self.nameplate > 0
        out = np.zeros_like(self.capacity)
        out[nz] = self.capacity[nz] / self.nameplate[nz, None]
        return out

    @property
    def units(self) -> np.ndarray:
        """(U, J) membership matrix: row u sums the columns of unit u."""
        ids = np.unique(self.unit)
        M = np.zeros((ids.size, self.J))
        for row, uid in enumerate(ids):
            M[row, self.unit == uid] = 1.0
        return M

    @property
    def peak(self) -> int:
        """Hour of the weekly peak on the B0 path; the ex-ante peak hour."""
        return int(np.argmax(self.d_sys))


# ----------------------------------------------------------------------------
# RTS-GMLC
# ----------------------------------------------------------------------------
def build_scenario(
    week: int,
    alpha: float = 0.05,
    profile: str = "system",
    reserve_margin: float | None = None,
    outage_seed: int | None = None,
    reserve_cost_fraction: float = 0.0,
) -> Scenario:
    """A week of RTS-GMLC at one node.

    ``week``: 0..51, hours ``[168 w, 168 (w + 1))`` of the day-ahead series.
    ``alpha``: the flexible load's share of weekly system energy; it is carved out
    of the RTS total, so ``delta + d_other`` is the data and tightness does not
    move with ``alpha``.
    ``profile``: the shape of δ, ``"system"`` (proportional to total load) or
    ``"area:1"``, ``"area:2"``, ``"area:3"`` (an area's profile, scaled to the
    same weekly energy).
    ``reserve_margin``: if given, scale both loads so that peak available
    capacity over peak system load, minus one, equals it. Scaling load rather
    than derating capacity keeps unit sizes, the largest contingency and the
    merit order intact.
    ``outage_seed``: seed for a two-state Markov chain per thermal unit driven by
    ``for``, ``mttf``, ``mttr``; ``None`` means no outages.
    ``reserve_cost_fraction``: cʳ as a fraction of cᵘ (RTS-GMLC has no reserve
    offer cost).
    """
    import polars as pl
    import rts_gmlc as rts

    T = HOURS_PER_WEEK
    lo, hi = T * week, T * (week + 1)
    load = rts.timeseries("load", "day_ahead")[lo:hi]
    if len(load) != T:
        raise ValueError(f"week {week} is not a full week of the day-ahead series")
    areas = {a: load[str(a)].to_numpy().astype(float) for a in (1, 2, 3)}
    total = sum(areas.values())

    # --- δ and d° -----------------------------------------------------------
    if profile == "system":
        shape = total
    elif profile.startswith("area:"):
        shape = areas[int(profile.split(":")[1])]
    else:
        raise ValueError(f"profile must be 'system' or 'area:k', got {profile!r}")
    delta = alpha * total.sum() * shape / shape.sum()
    d_other = total - delta

    # --- generator columns -----------------------------------------------------
    gen = rts.gen()
    blocks = rts.offer_blocks().filter(pl.col("mw") > 0.0)
    series = {k: rts.timeseries(k, "day_ahead")[lo:hi] for k in RENEWABLE_SERIES}
    renewable_cols = {c: k for k, s in series.items() for c in s.columns if c not in rts.TIME_COLS}

    cost_gen, cost_res, cost_inv, capacity, nameplate, unit, names = [], [], [], [], [], [], []
    rng = np.random.default_rng(outage_seed) if outage_seed is not None else None
    unit_index = 0
    for g in gen.iter_rows(named=True):
        uid, cat = g["gen_uid"], g["category"]
        if cat in EXCLUDED_CATEGORIES:
            continue
        inv = INVESTMENT_COST_PER_KW_YEAR[cat] * 1000.0 / 52.0  # $/MW per week
        if uid in renewable_cols:
            avail = series[renewable_cols[uid]][uid].to_numpy().astype(float)
            cost_gen.append(float(g["vom"] or 0.0))
            cost_res.append(0.0)
            cost_inv.append(inv)
            capacity.append(avail)
            nameplate.append(float(g["pmax_mw"]))
            unit.append(unit_index)
            names.append(uid)
        else:
            up = _availability(g, T, rng)
            for mw, cost in blocks.filter(pl.col("gen_uid") == uid).select("mw", "cost").iter_rows():
                cost_gen.append(float(cost))
                cost_res.append(reserve_cost_fraction * float(cost))
                cost_inv.append(inv)
                capacity.append(mw * up)
                nameplate.append(float(mw))
                unit.append(unit_index)
                names.append(uid)
        unit_index += 1

    scenario = Scenario(
        delta=delta,
        d_other=d_other,
        cost_gen=np.array(cost_gen),
        cost_res=np.array(cost_res),
        cost_inv=np.array(cost_inv),
        capacity=np.array(capacity),
        nameplate=np.array(nameplate),
        unit=np.array(unit),
        names=tuple(names),
        week=week,
    )
    if reserve_margin is not None:
        scenario = with_reserve_margin(scenario, reserve_margin)
    return scenario


def _availability(g: dict, T: int, rng: np.random.Generator | None) -> np.ndarray:
    """(T,) 0/1 availability of a thermal unit: a two-state Markov chain with
    hourly failure rate 1/mttf and repair rate 1/mttr, started from the
    stationary distribution implied by ``for``."""
    if rng is None:
        return np.ones(T)
    f, mttf, mttr = float(g["for"] or 0.0), float(g["mttf_hr"] or 0.0), float(g["mttr_hr"] or 0.0)
    if f <= 0.0 or mttf <= 0.0 or mttr <= 0.0:
        return np.ones(T)
    p_fail, p_repair = 1.0 / mttf, 1.0 / mttr
    up = np.ones(T)
    state = rng.random() >= f  # True = available
    for t in range(T):
        up[t] = 1.0 if state else 0.0
        state = (rng.random() >= p_fail) if state else (rng.random() < p_repair)
    return up


def with_reserve_margin(scenario: Scenario, reserve_margin: float) -> Scenario:
    """Scale δ and d° together so that the tightest hour's margin,
    ``min_t Σ_j capacity_jt / d_sys_t − 1``, equals ``reserve_margin``. α is
    unchanged because both loads scale. Clearing needs the margin to cover
    load-following γ plus, under PJM, the largest unit's share of load."""
    s = _margin_ratio(scenario).min() / (1.0 + reserve_margin)
    return Scenario(
        delta=scenario.delta * s,
        d_other=scenario.d_other * s,
        cost_gen=scenario.cost_gen,
        cost_res=scenario.cost_res,
        cost_inv=scenario.cost_inv,
        capacity=scenario.capacity,
        nameplate=scenario.nameplate,
        unit=scenario.unit,
        names=scenario.names,
        week=scenario.week,
    )


def _margin_ratio(scenario: Scenario) -> np.ndarray:
    return scenario.capacity.sum(axis=0) / scenario.d_sys


def reserve_margin(scenario: Scenario) -> float:
    """The tightness knob read back from a scenario: the tightest hour's
    available capacity over system load, minus one."""
    return float(_margin_ratio(scenario).min() - 1.0)
