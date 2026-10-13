"""Settlement and the four metrics: efficiency (regret), alignment, recovery,
fairness. The only module that labels rows and returns DataFrames.

Settlement reads two dispatches: the one at the bid (realized) and the one at
(δ, 0) (ex ante). Each cost-share layer's ``ex_ante`` flag says which supplies
its pool; energy and the reserve credit always settle at realized prices.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from .load import LoadType, V
from .market import Dispatch, Market
from .scenario import Scenario
from .tariff import Menu, Tariff, total


# ----------------------------------------------------------------------------
# settlement
# ----------------------------------------------------------------------------
def pools_for(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch):
    """(Cʳᵉˢ, Cⁱⁿᵛ) read from the dispatch each layer's basis names."""
    C_res_r, C_inv_r = market.pools(realized, scenario)
    C_res_e, C_inv_e = market.pools(ex_ante, scenario)
    C_res = C_res_e if tariff.reserve.ex_ante else C_res_r
    C_inv = C_inv_e if tariff.investment.ex_ante else C_inv_r
    return C_res, C_inv


def settle(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch, own: bool = True) -> dict:
    """The bill on realized consumption. ``own=False`` bills everyone else as one
    load: the same tariff with d and d° swapped, no credit, no exemption."""
    C_res, C_inv = pools_for(tariff, market, scenario, realized, ex_ante)
    if own:
        return tariff.bill(realized.d, realized.sigma, realized.lam, realized.mu, C_res, C_inv, scenario.d_other)
    return tariff.bill(scenario.d_other, np.zeros(scenario.T), realized.lam, realized.mu, C_res, C_inv, realized.d, own=False)


# ----------------------------------------------------------------------------
# welfare
# ----------------------------------------------------------------------------
def S(theta: LoadType, market: Market, scenario: Scenario, dispatch: Dispatch) -> float:
    """S = V(d, σ) − C_sys, counting the load's offer cost once: it sits in V and,
    because the load offers at cost, in the LP objective too."""
    return float(
        V(theta, scenario.delta, dispatch.d, dispatch.sigma)
        - market.C_sys(dispatch, scenario)
        + float(dispatch.c_s @ dispatch.sigma)
    )


# ----------------------------------------------------------------------------
# the four metrics
# ----------------------------------------------------------------------------
def recovery(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch) -> dict[str, float]:
    """ρᵏ = Cᵏ − Φᵏ − Φᵏ_∘ on the cost-share layers, against the *realized* cost."""
    C_res, C_inv = market.pools(realized, scenario)
    own = settle(tariff, market, scenario, realized, ex_ante, own=True)
    others = settle(tariff, market, scenario, realized, ex_ante, own=False)
    return {
        "reserve": float(np.sum(C_res)) - float(own["reserve"]) - float(others["reserve"]),
        "investment": float(C_inv) - float(own["investment"]) - float(others["investment"]),
    }


def alignment(tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, ex_ante: Dispatch) -> pl.DataFrame:
    """Δᵏ_t = ∂Φᵏ/∂d_t − ∂Cᵏ_sys/∂d_t per hour and layer."""
    C_res, C_inv = pools_for(tariff, market, scenario, realized, ex_ante)
    charge = tariff.marginal(realized.d, realized.sigma, realized.lam, realized.mu, C_res, C_inv, scenario.d_other)
    cost = market.marginal_cost_by_layer(realized)
    rows = []
    for layer in ("energy", "reserve", "investment"):
        for t in range(scenario.T):
            rows.append((t, layer, float(charge[layer][t]), float(cost[layer][t]), float(charge[layer][t] - cost[layer][t])))
    return pl.DataFrame(rows, schema=["t", "layer", "marginal_charge", "marginal_cost", "wedge"], orient="row")


def fairness(tariff: Tariff, market: Market, scenario: Scenario, responding: Dispatch, planner: Dispatch, ex_ante: Dispatch) -> dict[str, float]:
    """Φᵏ_∘|R − Φᵏ_∘|B1: how everyone else's bill moves when the load responds
    instead of doing what the planner would."""
    at_r = settle(tariff, market, scenario, responding, ex_ante, own=False)
    at_b1 = settle(tariff, market, scenario, planner, ex_ante, own=False)
    return {k: float(at_r[k]) - float(at_b1[k]) for k in ("energy", "reserve", "investment")}


def summary(
    theta: LoadType,
    tariff: Tariff | Menu,
    market: Market,
    scenario: Scenario,
    responding: Dispatch,
    planner: Dispatch,
    S_star: float,
    ex_ante: Dispatch,
    elected: Tariff | None = None,
) -> pl.DataFrame:
    """One row: welfare at B0, B1 and R, regret, recovery, fairness, the bill.
    Under a menu pass the ``elected`` option the load chose."""
    tau = elected if elected is not None else tariff
    assert isinstance(tau, Tariff), "summary needs the elected Tariff under a Menu"
    S_R, S_B0 = S(theta, market, scenario, responding), S(theta, market, scenario, ex_ante)
    bill = settle(tau, market, scenario, responding, ex_ante)
    rho = recovery(tau, market, scenario, responding, ex_ante)
    fair = fairness(tau, market, scenario, responding, planner, ex_ante)
    row = {
        "tariff": tariff.name,
        "elected": tau.name,
        "type": theta.name,
        "week": scenario.week,
        "S_star": S_star,
        "S_B0": S_B0,
        "S_R": S_R,
        "regret": S_star - S_R,
        "value_of_flexibility": S_star - S_B0,
        "bill_energy": float(bill["energy"]),
        "bill_reserve": float(bill["reserve"]),
        "bill_investment": float(bill["investment"]),
        "bill_credit": float(bill["credit"]),
        "bill_total": float(total(bill)),
        "recovery_reserve": rho["reserve"],
        "recovery_investment": rho["investment"],
        "fairness_energy": fair["energy"],
        "fairness_reserve": fair["reserve"],
        "fairness_investment": fair["investment"],
    }
    return pl.DataFrame([row])
