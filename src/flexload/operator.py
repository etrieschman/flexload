"""The operator's problem as a table and a rule.

For every (tariff, type, week): the load's response, the clearing, welfare at
B0, B1 and R, regret, recovery and fairness. The operator's objective, whether
max welfare, min-max regret or an expectation over a prior, is a selection over
that table, so it can change without recomputing anything.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from .load import LoadType, best_response, c_s, fixed_point, planner
from .market import Market
from .metrics import summary
from .scenario import Scenario
from .tariff import Menu, Tariff, total


def respond(theta: LoadType, tariff: Tariff | Menu, market: Market, scenario: Scenario, how: str = "exogenous", anticipate_curtailment: bool = False):
    """The load's response R and what it produced: (d, σ, dispatch, ex_ante
    dispatch, elected tariff). ``how`` is ``"exogenous"`` (one pass at the prices
    of the clearing at (δ, 0)) or ``"consistent"`` (the fixed point)."""
    offer = c_s(theta, scenario.delta)
    tau0 = tariff.options[0] if isinstance(tariff, Menu) else tariff
    ex_ante = market.clear(scenario, tau0, scenario.delta, np.zeros(scenario.T), offer)
    if how == "consistent":
        d, sigma, dispatch, _ = fixed_point(theta, tariff, market, scenario, anticipate_curtailment)
    elif how == "exogenous":
        C_res, C_inv = market.pools(ex_ante, scenario)
        curtailed = (market.kappa(ex_ante) >= market.voll) if anticipate_curtailment else None
        d, sigma = best_response(theta, tariff, scenario.delta, ex_ante.lam, ex_ante.mu, C_res, C_inv, scenario.d_other, scenario.delta, curtailed)
        dispatch = market.clear(scenario, _elected(theta, tariff, scenario, ex_ante, market, d, sigma), d, sigma, offer)
    else:
        raise ValueError(how)
    elected = _elected(theta, tariff, scenario, ex_ante, market, d, sigma)
    return d, sigma, dispatch, ex_ante, elected


def _elected(theta, tariff, scenario, ex_ante, market, d, sigma) -> Tariff:
    if not isinstance(tariff, Menu):
        return tariff
    from .load import V

    C_res, C_inv = market.pools(ex_ante, scenario)
    best, best_payoff = None, -np.inf
    for option in tariff.options:
        bill = option.bill(d, sigma, ex_ante.lam, ex_ante.mu, C_res, C_inv, scenario.d_other, d_hat=scenario.delta)
        payoff = float(V(theta, scenario.delta, d, sigma) - total(bill))
        if payoff > best_payoff:
            best, best_payoff = option, payoff
    return best


def evaluate(
    tariffs: dict[str, Tariff | Menu],
    types: dict[str, LoadType],
    market: Market,
    scenarios: list[Scenario],
    how: str = "exogenous",
    anticipate_curtailment: bool = False,
) -> pl.DataFrame:
    """One row per (tariff, type, week). B1 is solved once per (type, week)."""
    frames = []
    for scenario in scenarios:
        for tname, theta in types.items():
            d1, s1, S_star = planner(theta, market, scenario)
            b1 = market.clear(scenario, None, d1, s1, c_s(theta, scenario.delta))
            for name, tariff in tariffs.items():
                d, sigma, dispatch, ex_ante, elected = respond(theta, tariff, market, scenario, how, anticipate_curtailment)
                if elected.curtail is not None:  # B1 gets the same instrument
                    d1c, s1c, S_star_c = planner(theta, market, scenario, elected)
                    b1c = market.clear(scenario, elected, d1c, s1c, c_s(theta, scenario.delta))
                    frames.append(summary(theta, tariff, market, scenario, dispatch, b1c, S_star_c, ex_ante, elected))
                else:
                    frames.append(summary(theta, tariff, market, scenario, dispatch, b1, S_star, ex_ante, elected))
    return pl.concat(frames)


def choose(table: pl.DataFrame, rule: str = "minmax_regret", recovery_bound: float | None = None, prior: dict[str, float] | None = None) -> str:
    """The tariff the rule picks from an ``evaluate`` table.
    ``minmax_regret``: smallest worst-case mean regret over types.
    ``max_welfare``: largest mean S_R over types and weeks.
    ``expected_regret``: smallest regret averaged over types with ``prior`` weights.
    ``recovery_bound``: drop tariffs whose |ρᵏ| exceeds it for any type."""
    t = table
    if recovery_bound is not None:
        bad = (
            t.filter((pl.col("recovery_reserve").abs() > recovery_bound) | (pl.col("recovery_investment").abs() > recovery_bound))
            .select("tariff").unique()
        )
        t = t.filter(~pl.col("tariff").is_in(bad["tariff"]))
    by_type = t.group_by("tariff", "type").agg(pl.col("regret").mean(), pl.col("S_R").mean())
    if rule == "minmax_regret":
        score = by_type.group_by("tariff").agg(pl.col("regret").max().alias("score")).sort("score")
    elif rule == "max_welfare":
        score = by_type.group_by("tariff").agg((-pl.col("S_R").mean()).alias("score")).sort("score")
    elif rule == "expected_regret":
        assert prior is not None
        w = pl.DataFrame({"type": list(prior), "w": list(prior.values())})
        score = by_type.join(w, on="type").group_by("tariff").agg((pl.col("regret") * pl.col("w")).sum().alias("score")).sort("score")
    else:
        raise ValueError(rule)
    return str(score["tariff"][0])
