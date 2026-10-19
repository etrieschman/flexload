"""Settlement, welfare, the four metrics, and the loops that fill the operator's
table: one row per (tariff, type, market, period), the repeated game with a
learning load, and the operator's choice rule over the table.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product

import numpy as np
import polars as pl

from .load import LoadType, V, best_response, c_s, elect, fixed_point, planner
from .system import Dispatch, Market, Scenario
from .tariff import Menu, Tariff, total


# ----------------------------------------------------------------------------
# settlement and welfare
# ----------------------------------------------------------------------------
def settle(tariff: Tariff, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch, own: bool = True) -> dict[str, float]:
    """The bill in dollars. ``own=False`` bills everyone else as one load."""
    if own:
        bill = tariff.bill(realized.d, realized.sigma, realized, scenario.d_other, ex_ante)
    else:
        bill = tariff.bill(scenario.d_other, np.zeros(scenario.T), realized, realized.d, ex_ante, own=False)
    return {k: float(v.value) for k, v in bill.items()}


def S(theta: LoadType, market: Market, scenario: Scenario, dispatch: Dispatch) -> float:
    """S = V − C_sys + cˢᵀσ: the offer cost sits in V and in C_sys, so it is counted once."""
    return float(V(theta, scenario.delta, dispatch.d, dispatch.sigma).value) - market.C_sys(dispatch, scenario) + float(dispatch.c_s @ dispatch.sigma)


# ----------------------------------------------------------------------------
# the four metrics (regret is S* − S_R, in ``summary``)
# ----------------------------------------------------------------------------
def recovery(tariff: Tariff, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch) -> dict[str, float]:
    """ρᵏ = Cᵏ − Φᵏ − Φᵏ_∘ on the cost-share layers, against the realized pools."""
    own, others = settle(tariff, scenario, realized, ex_ante), settle(tariff, scenario, realized, ex_ante, own=False)
    return {
        "reserve": float(realized.C_res.sum()) - own["reserve"] - others["reserve"],
        "investment": realized.C_inv - own["investment"] - others["investment"],
    }


def alignment(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch) -> pl.DataFrame:
    """Δᵏ_t = ∂Φᵏ/∂d_t − ∂Cᵏ_sys/∂d_t, one row per hour and layer."""
    charge, cost = tariff.marginal(realized.d, realized, scenario.d_other, ex_ante), market.marginal_cost(realized)
    rows = [(t, k, float(charge[k][t]), float(cost[k][t])) for k in cost for t in range(scenario.T)]
    return pl.DataFrame(rows, schema=["t", "layer", "marginal_charge", "marginal_cost"], orient="row").with_columns((pl.col("marginal_charge") - pl.col("marginal_cost")).alias("wedge"))


def fairness(tariff: Tariff, scenario: Scenario, responding: Dispatch, planned: Dispatch, ex_ante: Dispatch) -> dict[str, float]:
    """Φᵏ_∘|R − Φᵏ_∘|B1: how everyone else's bill moves when the load responds instead of doing what the planner would."""
    at_r, at_b1 = settle(tariff, scenario, responding, ex_ante, own=False), settle(tariff, scenario, planned, ex_ante, own=False)
    return {k: at_r[k] - at_b1[k] for k in ("energy", "reserve", "investment")}


# ----------------------------------------------------------------------------
# one row of the operator's table
# ----------------------------------------------------------------------------
def respond(theta: LoadType, tariff: Tariff | Menu, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False) -> tuple[Dispatch, Dispatch, Tariff]:
    """R: the load's response under its belief about prices, ``"exogenous"``
    (the clearing at (δ, 0)) or ``"consistent"`` (the fixed point). Returns the
    dispatch at the response, the ex-ante dispatch, and the elected tariff."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_s(theta, delta), theta.d_firm(delta)
    ex_ante = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    curtailed = (market.kappa(ex_ante) >= market.voll) if anticipate else None
    tau = elect(theta, tariff, scenario, ex_ante, curtailed=curtailed) if isinstance(tariff, Menu) else tariff
    if belief == "exogenous":
        d, sigma = best_response(theta, tau, scenario, ex_ante, curtailed=curtailed)
        dispatch = market.clear(scenario, d, sigma, offer, d_firm)
    elif belief == "consistent":
        d, sigma, dispatch, _ = fixed_point(theta, tau, market, scenario, anticipate)
    else:
        raise ValueError(belief)
    return dispatch, ex_ante, tau


def summary(theta: LoadType, tariff: Tariff | Menu, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False, b1: tuple | None = None) -> dict:
    """Welfare at B0, B1 and R, regret, the bill by layer, recovery, fairness.
    ``b1`` is ``(d, σ, S*)`` from ``planner`` if already solved."""
    dispatch, ex_ante, tau = respond(theta, tariff, market, scenario, belief, anticipate)
    d1, s1, S_star = planner(theta, market, scenario) if b1 is None else b1
    planned = market.clear(scenario, d1, s1, c_s(theta, scenario.delta), theta.d_firm(scenario.delta))
    bill, rho, fair = settle(tau, scenario, dispatch, ex_ante), recovery(tau, scenario, dispatch, ex_ante), fairness(tau, scenario, dispatch, planned, ex_ante)
    S_R, S_B0 = S(theta, market, scenario, dispatch), S(theta, market, scenario, ex_ante)
    return {
        "tariff": tariff.name, "elected": tau.name, "type": theta.name, "market": market.reserve, "start": scenario.start,
        "S_star": S_star, "S_B0": S_B0, "S_R": S_R, "regret": S_star - S_R, "value_of_flexibility": S_star - S_B0,
        **{f"bill_{k}": v for k, v in bill.items()}, "bill_total": sum(bill.values()),
        **{f"recovery_{k}": v for k, v in rho.items()}, **{f"fairness_{k}": v for k, v in fair.items()},
        "energy_shifted": float(np.abs(dispatch.d_bid - scenario.delta).sum()),
    }


def table(types: dict[str, LoadType], tariffs: dict[str, Tariff | Menu], markets: list[Market], scenarios: list[Scenario], belief: str = "exogenous", anticipate: bool = False) -> pl.DataFrame:
    """The operator's table: one row per (type, tariff, market, period). B1 is solved once per (type, market, period)."""
    rows = []
    for theta, market, scenario in product(types.values(), markets, scenarios):
        b1 = planner(theta, market, scenario)
        rows += [summary(theta, tariff, market, scenario, belief, anticipate, b1) for tariff in tariffs.values()]
    return pl.DataFrame(rows)


def choose(table: pl.DataFrame, rule: str = "minmax_regret") -> str:
    """The operator's objective as a rule over the table: ``minmax_regret`` picks
    the tariff with the smallest worst-case mean regret over types, ``max_welfare``
    the largest mean S_R."""
    by_type = table.group_by("tariff", "type").agg(pl.col("regret").mean(), pl.col("S_R").mean())
    if rule == "minmax_regret":
        score = by_type.group_by("tariff").agg(pl.col("regret").max().alias("score"))
    elif rule == "max_welfare":
        score = by_type.group_by("tariff").agg((-pl.col("S_R").mean()).alias("score"))
    else:
        raise ValueError(rule)
    return str(score.sort("score")["tariff"][0])


# ----------------------------------------------------------------------------
# the repeated game: a price-taker that learns across periods
# ----------------------------------------------------------------------------
def learn(theta: LoadType, tariff: Tariff, market: Market, scenarios: list[Scenario], eta: float = 0.3) -> tuple[pl.DataFrame, list[Dispatch]]:
    """Period after period: respond to the belief, clear, observe, update. The
    belief is a dispatch whose prices, pools and consumption are exponential
    averages (weight ``eta`` on the latest) of what the load saw; it starts at
    the first period's clearing at (δ, 0). The learned price-taker is the third
    belief beside the exogenous and consistent ones. Returns one row per period."""
    rows, dispatches, belief = [], [], None
    for scenario in scenarios:
        offer, d_firm = c_s(theta, scenario.delta), theta.d_firm(scenario.delta)
        ex_ante = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer, d_firm)
        belief = ex_ante if belief is None else belief
        d, sigma = best_response(theta, tariff, scenario, belief)
        dispatch = market.clear(scenario, d, sigma, offer, d_firm)
        bill = settle(tariff, scenario, dispatch, ex_ante)
        rows.append({
            "start": scenario.start, "S": S(theta, market, scenario, dispatch), "bill_total": sum(bill.values()),
            "price_error": float(np.abs(dispatch.lam - belief.lam).mean()), "energy_shifted": float(np.abs(d - scenario.delta).sum()),
        })
        dispatches.append(dispatch)
        belief = replace(belief, lam=(1 - eta) * belief.lam + eta * dispatch.lam, mu=(1 - eta) * belief.mu + eta * dispatch.mu,
                         C_res=(1 - eta) * belief.C_res + eta * dispatch.C_res, C_inv=(1 - eta) * belief.C_inv + eta * dispatch.C_inv,
                         d=(1 - eta) * belief.d + eta * dispatch.d)
    return pl.DataFrame(rows), dispatches
