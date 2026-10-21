"""Settlement, welfare, the outcomes, and the loops that fill the operator's
table: one row per (tariff, type, market, window), the repeated game with a
learning load, and the operator's choice rule over the table.

Outcomes (report §1): welfare S at B0, B1 and R; efficiency S^B1 − S^R; and per
layer, alignment Δᵏ_t, recovery ρᵏ, fairness.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product

import numpy as np
import polars as pl

from .load import LoadType, V, best_response, c_sigma, elect, fixed_point, planner
from .system import Dispatch, Market, Scenario
from .tariff import Menu, Tariff, total


# ----------------------------------------------------------------------------
# settlement and welfare
# ----------------------------------------------------------------------------
def settle(tariff: Tariff, scenario: Scenario, realized: Dispatch, b0: Dispatch, own: bool = True) -> dict[str, float]:
    """The bill in dollars. ``own=False`` bills everyone else as one load."""
    if own:
        bill = tariff.bill(realized.d, realized.sigma, realized, scenario.d_other, b0)
    else:
        bill = tariff.bill(scenario.d_other, np.zeros(scenario.T), realized, realized.d, b0, own=False)
    return {k: float(v.value) for k, v in bill.items()}


def S(theta: LoadType, market: Market, scenario: Scenario, dispatch: Dispatch) -> float:
    """S = V − C_sys + c^σᵀσᶜˡʳ: the offer cost sits in V and in C_sys, so it is added back once."""
    dp = dispatch
    C_sys = market.C_sys(scenario, dp.u, dp.r, dp.sigma, dp.c_sigma, dp.shed, dp.y, dp.Pi)
    return float(V(theta, scenario.delta, dp.d, dp.sigma).value) - float(C_sys.value) + float(dp.c_sigma @ dp.sigma)


# ----------------------------------------------------------------------------
# outcomes per layer (welfare and efficiency are in ``summary``)
# ----------------------------------------------------------------------------
def recovery(tariff: Tariff, scenario: Scenario, realized: Dispatch, b0: Dispatch) -> dict[str, float]:
    """ρᵏ = Cᵏ − Bᵏ(dᶜᵘʳᵗ, σᶜˡʳ) − Bᵏ(d°, 0): the layer's realized cost less what the load and everyone else pay."""
    own, others = settle(tariff, scenario, realized, b0), settle(tariff, scenario, realized, b0, own=False)
    return {
        "reserve": float(realized.C_res.sum()) - own["reserve"] - others["reserve"],
        "investment": realized.C_inv - own["investment"] - others["investment"],
    }


def alignment(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, b0: Dispatch) -> pl.DataFrame:
    """Δᵏ_t = ∂Bᵏ/∂d_t − ∂Cᵏ_sys/∂d_t, one row per hour and layer."""
    charge, cost = tariff.marginal(realized.d, realized, scenario.d_other, b0), market.marginal_cost(realized)
    rows = [(t, k, float(charge[k][t]), float(cost[k][t])) for k in cost for t in range(scenario.T)]
    return pl.DataFrame(rows, schema=["t", "layer", "marginal_charge", "marginal_cost"], orient="row").with_columns((pl.col("marginal_charge") - pl.col("marginal_cost")).alias("wedge"))


def fairness(tariff: Tariff, scenario: Scenario, responding: Dispatch, planned: Dispatch, b0: Dispatch) -> dict[str, float]:
    """Bᵏ(d°)|R − Bᵏ(d°)|B1: how everyone else's bill moves when the load plays R instead of B1."""
    at_r, at_b1 = settle(tariff, scenario, responding, b0, own=False), settle(tariff, scenario, planned, b0, own=False)
    return {k: at_r[k] - at_b1[k] for k in ("energy", "reserve", "investment")}


# ----------------------------------------------------------------------------
# one row of the operator's table
# ----------------------------------------------------------------------------
def respond(theta: LoadType, tariff: Tariff | Menu, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False) -> tuple[Dispatch, Dispatch, Dispatch, Tariff]:
    """R: the load's response under its belief about prices, ``"exogenous"``
    (the clearing at (δ, 0)) or ``"consistent"`` (the fixed point). Returns the
    dispatch at the response, the ex-ante dispatch, the belief the bid answered
    to, and the elected tariff."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    b0 = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    curtailed = (b0.lam >= market.voll - 1e-6) if anticipate else None  # shortage hours: λ̃ at VOLL
    tau = elect(theta, tariff, scenario, b0, curtailed=curtailed) if isinstance(tariff, Menu) else tariff
    if belief == "exogenous":
        d, sigma = best_response(theta, tau, scenario, b0, curtailed=curtailed)
        dispatch, believed = market.clear(scenario, d, sigma, offer, d_firm), b0
    elif belief == "consistent":
        d, sigma, dispatch, believed, _ = fixed_point(theta, tau, market, scenario, anticipate)
    else:
        raise ValueError(belief)
    return dispatch, b0, believed, tau


def summary(theta: LoadType, tariff: Tariff | Menu, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False, b1: tuple | None = None) -> dict:
    """One row: welfare at B0, B1 and R, efficiency, the bill by layer, recovery,
    fairness, and the belief's price error. ``b1`` is ``(d, σ, S^B1)`` from
    ``planner`` if already solved."""
    dispatch, b0, believed, tau = respond(theta, tariff, market, scenario, belief, anticipate)
    d1, s1, S_B1 = planner(theta, market, scenario) if b1 is None else b1
    planned = market.clear(scenario, d1, s1, c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta))
    bill, rho, fair = settle(tau, scenario, dispatch, b0), recovery(tau, scenario, dispatch, b0), fairness(tau, scenario, dispatch, planned, b0)
    S_R, S_B0 = S(theta, market, scenario, dispatch), S(theta, market, scenario, b0)
    return {
        "tariff": tariff.name, "elected": tau.name, "type": theta.name, "market": market.reserve, "belief": belief, "start": scenario.start,
        "S_B0": S_B0, "S_B1": S_B1, "S_R": S_R, "efficiency": S_B1 - S_R, "value_of_flexibility": S_B1 - S_B0,
        **{f"bill_{k}": v for k, v in bill.items()}, "bill_total": sum(bill.values()),
        **{f"recovery_{k}": v for k, v in rho.items()}, **{f"fairness_{k}": v for k, v in fair.items()},
        "price_error": float(np.abs(believed.lam - dispatch.lam).mean()),
        "energy_shifted": float(np.abs(dispatch.d_bid - scenario.delta).sum()),
    }


def table(types: dict[str, LoadType], tariffs: dict[str, Tariff | Menu], markets: list[Market], scenarios: list[Scenario], belief: str = "exogenous", anticipate: bool = False) -> pl.DataFrame:
    """The operator's table: one row per (type, tariff, market, window). B1 is solved once per (type, market, window)."""
    rows = []
    for theta, market, scenario in product(types.values(), markets, scenarios):
        b1 = planner(theta, market, scenario)
        rows += [summary(theta, tariff, market, scenario, belief, anticipate, b1) for tariff in tariffs.values()]
    return pl.DataFrame(rows)


def choose(table: pl.DataFrame, rule: str = "maxmin_welfare", prior: dict[str, float] | None = None, g: str = "layer", epsilon: float | None = None) -> str:
    """The operator's objective as a rule over the table. ``maxmin_welfare``:
    the tariff with the largest worst-case mean welfare over types (Θ should
    exclude the inflexible load, whose welfare no tariff moves).
    ``expected_welfare``: the largest welfare averaged over types with ``prior``
    weights. The recovery constraint g(ρ) ≤ 0 drops a tariff when any type
    breaks it: ``g="layer"`` holds each layer within ``epsilon``, ``g="total"``
    holds the bill in total; ``epsilon=None`` imposes no constraint."""
    t = table
    if epsilon is not None:
        if g == "layer":
            broken = t.filter((pl.col("recovery_reserve").abs() > epsilon) | (pl.col("recovery_investment").abs() > epsilon))
        elif g == "total":
            broken = t.filter((pl.col("recovery_reserve") + pl.col("recovery_investment")).abs() > epsilon)
        else:
            raise ValueError(g)
        t = t.filter(~pl.col("tariff").is_in(broken["tariff"].unique()))
    by_type = t.group_by("tariff", "type").agg(pl.col("S_R").mean())
    if rule == "maxmin_welfare":
        score = by_type.group_by("tariff").agg(pl.col("S_R").min().alias("score"))
    elif rule == "expected_welfare":
        assert prior is not None, "expected_welfare needs a prior over types"
        w = pl.DataFrame({"type": list(prior), "w": list(prior.values())})
        score = by_type.join(w, on="type").group_by("tariff").agg((pl.col("S_R") * pl.col("w")).sum().alias("score"))
    else:
        raise ValueError(rule)
    return str(score.sort("score", descending=True)["tariff"][0])


# ----------------------------------------------------------------------------
# the repeated game: a price-taker that learns across windows
# ----------------------------------------------------------------------------
def learn(theta: LoadType, tariff: Tariff, market: Market, scenarios: list[Scenario], eta: float = 0.3) -> tuple[pl.DataFrame, list[Dispatch]]:
    """Window after window: respond to the belief, clear, observe, update. The
    belief is a dispatch whose prices, layer costs and consumption are
    exponential averages (weight ``eta`` on the latest) of what the load saw; it
    starts at the first window's clearing at (δ, 0). The learner is the fourth
    belief in the report's table. Returns one row per window."""
    rows, dispatches, belief = [], [], None
    for scenario in scenarios:
        offer, d_firm = c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta)
        b0 = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer, d_firm)
        belief = b0 if belief is None else belief
        d, sigma = best_response(theta, tariff, scenario, belief)
        dispatch = market.clear(scenario, d, sigma, offer, d_firm)
        bill = settle(tariff, scenario, dispatch, b0)
        rows.append({
            "start": scenario.start, "S": S(theta, market, scenario, dispatch), "bill_total": sum(bill.values()),
            "price_error": float(np.abs(dispatch.lam - belief.lam).mean()), "energy_shifted": float(np.abs(d - scenario.delta).sum()),
        })
        dispatches.append(dispatch)
        belief = replace(belief, lam=(1 - eta) * belief.lam + eta * dispatch.lam, mu=(1 - eta) * belief.mu + eta * dispatch.mu,
                         Pi=(1 - eta) * belief.Pi + eta * dispatch.Pi, C_energy=(1 - eta) * belief.C_energy + eta * dispatch.C_energy,
                         C_res=(1 - eta) * belief.C_res + eta * dispatch.C_res, C_inv=(1 - eta) * belief.C_inv + eta * dispatch.C_inv,
                         d=(1 - eta) * belief.d + eta * dispatch.d)
    return pl.DataFrame(rows), dispatches
