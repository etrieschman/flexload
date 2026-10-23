"""Settlement, welfare, the outcomes, and the loop that fills the operator's
table, one row per (type, tariff, market, window). Report §1 "Outcomes" and
§3 "System operator". The operator's rule over the table is not built
(deleted 2026-10-23; git 22257a4 has the last version).

Outcomes: welfare S at B0, B1 and R; efficiency S^B1 − S^R; and per layer,
alignment Δᵏ_t, recovery ρᵏ, fairness.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

from .load import Belief, LoadType, S, best_response, c_sigma, fixed_point, planner
from .system import Dispatch, Market, Scenario
from .tariff import LAYERS, Tariff


# ----------------------------------------------------------------------------
# settlement
# ----------------------------------------------------------------------------
def settle(
    tariff: Tariff,
    scenario: Scenario,
    realized: Dispatch,
    b0: Dispatch,
    own: bool = True,
) -> dict[str, float]:
    """The bill in dollars, by layer plus the credit. ``realized`` is the
    dispatch at the bid, ``b0`` the one at (δ, 0). ``own=False`` bills everyone
    else as one load."""
    if own:
        bill = tariff.bill(
            realized.d, realized.sigma, realized, scenario.d_other, b0, own=True
        )
    else:
        bill = tariff.bill(
            scenario.d_other, np.zeros(scenario.T), realized, realized.d, b0, own=False
        )
    return {k: float(v.value) for k, v in bill.items()}


# ----------------------------------------------------------------------------
# outcomes per layer (welfare and efficiency are in ``summary``)
# ----------------------------------------------------------------------------
def recovery(
    tariff: Tariff, scenario: Scenario, realized: Dispatch, b0: Dispatch
) -> dict[str, float]:
    """ρᵏ = Cᵏ − Bᵏ(d, σ) − Bᵏ(d°, 0): the layer's realized cost less what the
    load and everyone else pay for it. Zero for energy at the margin."""
    own, others = (
        settle(tariff, scenario, realized, b0, own=True),
        settle(tariff, scenario, realized, b0, own=False),
    )
    cost = {
        "energy": float(realized.C_energy.sum()),
        "reserve": float(realized.C_res.sum()),
        "investment": realized.C_inv,
    }
    return {k: cost[k] - own[k] - others[k] for k in LAYERS}


def alignment(
    tariff: Tariff, market: Market, scenario: Scenario, realized: Dispatch, b0: Dispatch
) -> pl.DataFrame:
    """Δᵏ_t = ∂Bᵏ/∂d_t − ∂Cᵏ_sys/∂d_t, one row per hour and layer."""
    charge, cost = (
        tariff.marginal(realized.d, realized, scenario.d_other, b0),
        market.marginal_cost(realized),
    )
    rows = [
        (t, k, float(charge[k][t]), float(cost[k][t]))
        for k in LAYERS
        for t in range(scenario.T)
    ]
    out = pl.DataFrame(
        rows, schema=["t", "layer", "marginal_charge", "marginal_cost"], orient="row"
    )
    return out.with_columns(
        (pl.col("marginal_charge") - pl.col("marginal_cost")).alias("wedge")
    )


def fairness(
    tariff: Tariff,
    scenario: Scenario,
    responding: Dispatch,
    planned: Dispatch,
    b0: Dispatch,
) -> dict[str, float]:
    """Bᵏ(d°)|R − Bᵏ(d°)|B1: how everyone else's bill moves when the load plays R instead of B1."""
    at_r = settle(tariff, scenario, responding, b0, own=False)
    at_b1 = settle(tariff, scenario, planned, b0, own=False)
    return {k: at_r[k] - at_b1[k] for k in LAYERS}


# ----------------------------------------------------------------------------
# one row of the operator's table
# ----------------------------------------------------------------------------
def respond(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    belief: str = "exogenous",
) -> tuple[Dispatch, Dispatch, Dispatch, list[float]]:
    """R: the load's response under its belief about prices, ``"exogenous"``
    (the clearing at (δ, 0), the posted rate, consumption as bid) or
    ``"consistent"`` (the fixed point, knowing its share, cut to dᶠⁱʳᵐ where
    the last clearing cut it). Returns the dispatch at the response, b0, the
    belief the bid answered to, and the fixed point's bid changes (empty when
    exogenous)."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    b0 = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    history: list[float] = []
    if belief == "exogenous":
        d_bid, sigma_bid = best_response(
            theta, tariff, scenario, Belief(b0, consistent=False), b0
        )
        dispatch, believed = market.clear(scenario, d_bid, sigma_bid, offer, d_firm), b0
    elif belief == "consistent":
        _, _, dispatch, believed, history = fixed_point(theta, tariff, market, scenario)
    else:
        raise ValueError(belief)
    return dispatch, b0, believed, history


def summary(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    belief: str = "exogenous",
    b1: tuple | None = None,
) -> dict:
    """One row: welfare at B0, B1 and R, efficiency and its share of the value
    of flexibility, the bill by layer at B0 and at R, mean |Δᵏ_t|, recovery,
    fairness, the belief's price error, and the fixed point's iterations and
    last change. ``b1`` is the bid ``(d_bid, σ_bid)`` from ``planner`` if
    already solved. S is read from a clearing at each of the three bids."""
    dispatch, b0, believed, history = respond(theta, tariff, market, scenario, belief)
    d1, s1 = planner(theta, market, scenario) if b1 is None else b1
    planned = market.clear(
        scenario, d1, s1, c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta)
    )
    bill, bill_b0 = (
        settle(tariff, scenario, dispatch, b0),
        settle(tariff, scenario, b0, b0),
    )
    rho = recovery(tariff, scenario, dispatch, b0)
    fair = fairness(tariff, scenario, dispatch, planned, b0)
    wedge = dict(
        alignment(tariff, market, scenario, dispatch, b0)
        .group_by("layer")
        .agg(pl.col("wedge").abs().mean())
        .iter_rows()
    )
    S_B0, S_R, S_B1 = (
        float(
            S(theta, market, scenario, x.d, x.sigma, x.u, x.r, x.shed, x.y, x.Pi).value
        )
        for x in (b0, dispatch, planned)
    )
    value = S_B1 - S_B0
    return {
        "tariff": tariff.name,
        "type": theta.name,
        "market": market.reserve,
        "belief": belief,
        "start": scenario.start,
        "S_B0": S_B0,
        "S_B1": S_B1,
        "S_R": S_R,
        "efficiency": S_B1 - S_R,
        "value_of_flexibility": value,
        "efficiency_share": (S_B1 - S_R) / value if value > 1e-9 else None,
        **{f"bill_{k}": v for k, v in bill.items()},
        "bill_total": sum(bill.values()),
        **{f"bill_b0_{k}": v for k, v in bill_b0.items()},
        **{f"alignment_{k}": float(wedge[k]) for k in LAYERS},
        **{f"recovery_{k}": v for k, v in rho.items()},
        **{f"fairness_{k}": v for k, v in fair.items()},
        "price_error": float(np.abs(believed.lam - dispatch.lam).mean()),
        "iterations": len(history) or None,
        "last_change": history[-1] if history else None,
    }


def table(
    types: dict[str, LoadType],
    tariffs: dict[str, Tariff],
    markets: list[Market],
    scenarios: list[Scenario],
    belief: str = "exogenous",
) -> pl.DataFrame:
    """The operator's table: one row per (type, tariff, market, window). B1 is solved once per (type, market, window)."""
    rows = []
    for theta, market, scenario in product(types.values(), markets, scenarios):
        b1 = planner(theta, market, scenario)
        rows += [
            summary(theta, tariff, market, scenario, belief, b1)
            for tariff in tariffs.values()
        ]
    return pl.DataFrame(rows)


# ----------------------------------------------------------------------------
# a table for the report
# ----------------------------------------------------------------------------
def tex(
    table: pl.DataFrame, path: str | Path, caption: str, label: str, digits: int = 0
) -> None:
    """Write ``table`` as a booktabs table for ``\\input``. Column names are the
    headers, written as given; floats get ``digits`` decimals, integers none,
    both thousands separators; nulls print as --."""

    def cell(v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "--"
        if isinstance(v, float):
            return f"{round(v, digits) or 0.0:,.{digits}f}"  # no −0
        return f"{v:,d}" if isinstance(v, int) else str(v)

    align = "".join("r" if dt.is_numeric() else "l" for dt in table.dtypes)
    lines = [
        r"\begin{table}[h]\centering\small",
        rf"\begin{{tabular}}{{@{{}}{align}@{{}}}}",
        r"\toprule",
        " & ".join(table.columns) + r" \\",
        r"\midrule",
        *(" & ".join(cell(v) for v in row) + r" \\" for row in table.iter_rows()),
        r"\bottomrule",
        r"\end{tabular}",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\end{table}",
    ]
    Path(path).write_text("\n".join(lines) + "\n")
