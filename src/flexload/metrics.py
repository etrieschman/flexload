"""Settlement, welfare, the outcomes, and the loops that fill the operator's
table: one row per (type, tariff, market, window), the repeated game with a
learning load, and the operator's rule over the table. Report §1 "Outcomes"
and §3 "System operator".

Outcomes: welfare S at B0, B1 and R; efficiency S^B1 − S^R; and per layer,
alignment Δᵏ_t, recovery ρᵏ, fairness.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product

import numpy as np
import polars as pl

from .load import LoadType, V, best_response, c_sigma, fixed_point, planner
from .system import Dispatch, Market, Scenario
from .tariff import LAYERS, Tariff


# ----------------------------------------------------------------------------
# settlement and welfare
# ----------------------------------------------------------------------------
def settle(tariff: Tariff, scenario: Scenario, realized: Dispatch, b0: Dispatch, own: bool = True) -> dict[str, float]:
    """The bill in dollars, by layer plus the credit. ``realized`` is the
    dispatch at the bid, ``b0`` the one at (δ, 0). ``own=False`` bills everyone
    else as one load."""
    if own:
        bill = tariff.bill(realized.d, realized.sigma, realized, scenario.d_other, b0, own=True)
    else:
        bill = tariff.bill(scenario.d_other, np.zeros(scenario.T), realized, realized.d, b0, own=False)
    return {k: float(v.value) for k, v in bill.items()}


def S(theta: LoadType, market: Market, scenario: Scenario, dispatch: Dispatch) -> float:
    """S = V − C_sys + c^σᵀσ: the offer cost sits in V and in C_sys, so it is added back once."""
    C_sys = market.C_sys(scenario, dispatch.u, dispatch.r, dispatch.sigma, dispatch.c_sigma, dispatch.shed, dispatch.y, dispatch.Pi)
    return float(V(theta, scenario.delta, dispatch.d, dispatch.sigma).value) - float(C_sys.value) + float(dispatch.c_sigma @ dispatch.sigma)


# ----------------------------------------------------------------------------
# outcomes per layer (welfare and efficiency are in ``summary``)
# ----------------------------------------------------------------------------
def recovery(tariff: Tariff, scenario: Scenario, realized: Dispatch, b0: Dispatch) -> dict[str, float]:
    """ρᵏ = Cᵏ − Bᵏ(d, σ) − Bᵏ(d°, 0): the layer's realized cost less what the
    load and everyone else pay for it. Zero for energy at the margin."""
    own, others = settle(tariff, scenario, realized, b0, own=True), settle(tariff, scenario, realized, b0, own=False)
    cost = {"energy": float(realized.C_energy.sum()), "reserve": float(realized.C_res.sum()), "investment": realized.C_inv}
    return {k: cost[k] - own[k] - others[k] for k in LAYERS}


def alignment(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, b0: Dispatch) -> pl.DataFrame:
    """Δᵏ_t = ∂Bᵏ/∂d_t − ∂Cᵏ_sys/∂d_t, one row per hour and layer."""
    charge, cost = tariff.marginal(realized.d, realized, scenario.d_other, b0), market.marginal_cost(realized)
    rows = [(t, k, float(charge[k][t]), float(cost[k][t])) for k in LAYERS for t in range(scenario.T)]
    out = pl.DataFrame(rows, schema=["t", "layer", "marginal_charge", "marginal_cost"], orient="row")
    return out.with_columns((pl.col("marginal_charge") - pl.col("marginal_cost")).alias("wedge"))


def fairness(tariff: Tariff, scenario: Scenario, responding: Dispatch, planned: Dispatch, b0: Dispatch) -> dict[str, float]:
    """Bᵏ(d°)|R − Bᵏ(d°)|B1: how everyone else's bill moves when the load plays R instead of B1."""
    at_r = settle(tariff, scenario, responding, b0, own=False)
    at_b1 = settle(tariff, scenario, planned, b0, own=False)
    return {k: at_r[k] - at_b1[k] for k in LAYERS}


# ----------------------------------------------------------------------------
# one row of the operator's table
# ----------------------------------------------------------------------------
def respond(theta: LoadType, tariff: Tariff, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False) -> tuple[Dispatch, Dispatch, Dispatch]:
    """R: the load's response under its belief about prices, ``"exogenous"``
    (the clearing at (δ, 0), posted rates) or ``"consistent"`` (the fixed point,
    knowing its share). ``anticipate``: a curtailable load expects to be cut in
    the hours where its believed price is at VOLL. Returns the dispatch at the
    response, b0, and the belief the bid answered to."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    b0 = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    if belief == "exogenous":
        curtailed = (b0.lam >= market.voll - 1e-6) if anticipate else None
        d_bid, sigma_bid = best_response(theta, tariff, scenario, b0, d_hat=delta, curtailed=curtailed, knows_share=False)
        dispatch, believed = market.clear(scenario, d_bid, sigma_bid, offer, d_firm), b0
    elif belief == "consistent":
        _, _, dispatch, believed, _ = fixed_point(theta, tariff, market, scenario, anticipate)
    else:
        raise ValueError(belief)
    return dispatch, b0, believed


def summary(theta: LoadType, tariff: Tariff, market: Market, scenario: Scenario, belief: str = "exogenous", anticipate: bool = False, b1: tuple | None = None) -> dict:
    """One row: welfare at B0, B1 and R, efficiency, the bill by layer, recovery,
    fairness, and the belief's price error. ``b1`` is ``(d, σ, S^B1)`` from
    ``planner`` if already solved."""
    dispatch, b0, believed = respond(theta, tariff, market, scenario, belief, anticipate)
    d1, s1, S_B1 = planner(theta, market, scenario) if b1 is None else b1
    planned = market.clear(scenario, d1, s1, c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta))
    bill = settle(tariff, scenario, dispatch, b0, own=True)
    rho = recovery(tariff, scenario, dispatch, b0)
    fair = fairness(tariff, scenario, dispatch, planned, b0)
    S_R, S_B0 = S(theta, market, scenario, dispatch), S(theta, market, scenario, b0)
    return {
        "tariff": tariff.name, "type": theta.name, "market": market.reserve, "belief": belief, "start": scenario.start,
        "S_B0": S_B0, "S_B1": S_B1, "S_R": S_R, "efficiency": S_B1 - S_R, "value_of_flexibility": S_B1 - S_B0,
        **{f"bill_{k}": v for k, v in bill.items()}, "bill_total": sum(bill.values()),
        **{f"recovery_{k}": v for k, v in rho.items()}, **{f"fairness_{k}": v for k, v in fair.items()},
        "price_error": float(np.abs(believed.lam - dispatch.lam).mean()),
    }


def table(types: dict[str, LoadType], tariffs: dict[str, Tariff], markets: list[Market], scenarios: list[Scenario], belief: str = "exogenous", anticipate: bool = False) -> pl.DataFrame:
    """The operator's table: one row per (type, tariff, market, window). B1 is solved once per (type, market, window)."""
    rows = []
    for theta, market, scenario in product(types.values(), markets, scenarios):
        b1 = planner(theta, market, scenario)
        rows += [summary(theta, tariff, market, scenario, belief, anticipate, b1) for tariff in tariffs.values()]
    return pl.DataFrame(rows)


def choose(table: pl.DataFrame, rule: str = "maxmin_welfare", prior: dict[str, float] | None = None, g: str = "layer", epsilon: float | None = None) -> str:
    """The operator's objective as a rule over the table. ``maxmin_welfare``:
    the tariff with the largest worst-case mean welfare over types. The
    inflexible load's welfare is the same under every tariff, so leave it out
    of ``table``. ``expected_welfare``: the largest welfare averaged over types
    with ``prior`` weights. The recovery constraint g(ρ) ≤ 0 drops a tariff
    when any type breaks it: ``g="layer"`` holds each layer within ``epsilon``,
    ``g="total"`` holds the bill in total; ``epsilon=None`` skips it."""
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
        weights = pl.DataFrame({"type": list(prior), "w": list(prior.values())})
        score = by_type.join(weights, on="type").group_by("tariff").agg((pl.col("S_R") * pl.col("w")).sum().alias("score"))
    else:
        raise ValueError(rule)
    return str(score.sort("score", descending=True)["tariff"][0])


# ----------------------------------------------------------------------------
# the repeated game: a price-taker that learns across windows
# ----------------------------------------------------------------------------
def learn(theta: LoadType, tariff: Tariff, market: Market, scenarios: list[Scenario], eta: float = 0.3) -> tuple[pl.DataFrame, list[Dispatch]]:
    """Window after window: respond to the belief, clear, observe, update. The
    belief is a dispatch whose prices, layer costs and consumption are
    exponential averages, weight ``eta`` on the latest, of what the load saw.
    It starts at the first window's clearing at (δ, 0) and takes the posted
    rate. Returns one row per window and the dispatches."""
    rows, dispatches, belief = [], [], None
    for scenario in scenarios:
        offer, d_firm = c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta)
        b0 = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer, d_firm)
        belief = b0 if belief is None else belief
        d_bid, sigma_bid = best_response(theta, tariff, scenario, belief, d_hat=belief.d, curtailed=None, knows_share=False)
        dispatch = market.clear(scenario, d_bid, sigma_bid, offer, d_firm)
        bill = settle(tariff, scenario, dispatch, b0, own=True)
        rows.append({
            "start": scenario.start, "S": S(theta, market, scenario, dispatch), "bill_total": sum(bill.values()),
            "price_error": float(np.abs(dispatch.lam - belief.lam).mean()),
        })
        dispatches.append(dispatch)
        belief = replace(
            belief,
            lam=(1 - eta) * belief.lam + eta * dispatch.lam,
            mu=(1 - eta) * belief.mu + eta * dispatch.mu,
            Pi=(1 - eta) * belief.Pi + eta * dispatch.Pi,
            C_energy=(1 - eta) * belief.C_energy + eta * dispatch.C_energy,
            C_res=(1 - eta) * belief.C_res + eta * dispatch.C_res,
            C_inv=(1 - eta) * belief.C_inv + eta * dispatch.C_inv,
            d=(1 - eta) * belief.d + eta * dispatch.d,
        )
    return pl.DataFrame(rows), dispatches
