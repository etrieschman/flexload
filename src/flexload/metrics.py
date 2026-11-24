"""Settlement, welfare, the outcomes, and the loop that fills the operator's
table, one row per (type, tariff, construct, window).

Outcomes: welfare S at B0, B1 and R; efficiency S^B1 − S^R; the bills and
fairness; and, once the imbalance realizes, load shed and realized welfare
(``realized.outcomes``). Alignment Δᵏ_t and recovery ρᵏ are read off a
dispatch by ``alignment`` and ``recovery``; the tables do not carry them.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

from .load import Belief, LoadType, S, best_response, c_sigma, fixed_point, planner
from .realized import outcomes
from .system import Dispatch, Market, Scenario, marginal_cost, rent
from .tariff import LAYERS, Tariff


# ----------------------------------------------------------------------------
# settlement
# ----------------------------------------------------------------------------
def settle(
    tariff: Tariff,
    scenario: Scenario,
    dispatch: Dispatch,
    b0: Dispatch,
    own: bool = True,
) -> dict[str, float]:
    """The bill in dollars, by layer plus the credit. ``dispatch`` is the
    dispatch at the bid, ``b0`` the one at (δ, 0). ``own=False`` bills everyone
    else as one load: d and d° swapped, σ = 0 so the credit is zero, and the
    tariff without the curtailable exemption, which is the load's alone."""
    if own:
        bill = tariff.bill(dispatch.d, dispatch.sigma, dispatch, scenario.d_other, b0)
    else:
        others = replace(tariff, exempt_curtailable=False)
        bill = others.bill(scenario.d_other, np.zeros(scenario.T), dispatch, dispatch.d, b0)
    return {k: float(v.value) for k, v in bill.items()}


# ----------------------------------------------------------------------------
# outcomes at dispatch
# ----------------------------------------------------------------------------
def welfare(theta: LoadType, market: Market, scenario: Scenario, dispatch: Dispatch) -> float:
    """S read off a dispatch, in dollars."""
    return float(S(theta, market, scenario, dispatch.d, dispatch.sigma, dispatch.g, dispatch.r, dispatch.s, dispatch.C_ordc).value)


def recovery(
    tariff: Tariff, scenario: Scenario, dispatch: Dispatch, b0: Dispatch
) -> dict[str, float]:
    """ρᵏ = Cᵏ − Bᵏ(d, σ) − Bᵏ(d°, 0): the layer's cost at the bid less what the
    load and everyone else pay for it. Zero for energy at the margin."""
    own, others = (
        settle(tariff, scenario, dispatch, b0, own=True),
        settle(tariff, scenario, dispatch, b0, own=False),
    )
    cost = {
        "energy": float(dispatch.C_energy.sum()),
        "reserve": float(dispatch.C_res.sum()),
        "investment": dispatch.C_inv,
    }
    return {k: cost[k] - own[k] - others[k] for k in LAYERS}


def alignment(tariff: Tariff, scenario: Scenario, dispatch: Dispatch, b0: Dispatch) -> pl.DataFrame:
    """Δᵏ_t = ∂Bᵏ/∂d_t − ∂Cᵏ_sys/∂d_t, one row per hour and layer."""
    charge, cost = (
        tariff.marginal(dispatch.d, dispatch, scenario.d_other, b0),
        marginal_cost(dispatch),
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


def alignment_summary(wedge: pl.DataFrame) -> dict:
    """Δᵏ_t by layer, signed, over the hours where the layer's marginal charge
    or marginal cost is nonzero: their count, mean, 1st and 99th percentiles.
    None when no hour has a wedge."""
    out = {}
    for k in LAYERS:
        layer = wedge.filter(pl.col("layer") == k)
        priced = (layer["marginal_charge"].abs() > 1e-6) | (layer["marginal_cost"].abs() > 1e-6)
        hours = layer.filter(priced)["wedge"].to_numpy()  # where the layer charges or costs anything
        out[f"alignment_hours_{k}"] = int(hours.size)
        out[f"alignment_{k}"] = float(hours.mean()) if hours.size else None
        out[f"alignment_p1_{k}"] = float(np.percentile(hours, 1)) if hours.size else None
        out[f"alignment_p99_{k}"] = float(np.percentile(hours, 99)) if hours.size else None
    return out


def fairness(
    tariff: Tariff,
    scenario: Scenario,
    responding: Dispatch,
    b0: Dispatch,
) -> dict[str, float]:
    """Bᵏ(d°)|R − Bᵏ(d°)|B0: how everyone else's bill moves when the load
    responds, against the bill before it did. Positive: others pay more."""
    at_r = settle(tariff, scenario, responding, b0, own=False)
    at_b0 = settle(tariff, scenario, b0, b0, own=False)
    return {k: at_r[k] - at_b0[k] for k in LAYERS}


# ----------------------------------------------------------------------------
# one row of the operator's table
# ----------------------------------------------------------------------------
def respond(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    consistent: bool = False,
) -> tuple[Dispatch, Dispatch, Dispatch, list[float]]:
    """R: the load's response as an exogenous price-taker (the clearing at
    (δ, 0), the posted rate, consumption as bid) or, if ``consistent``, as the
    consistent one (the fixed point, knowing its share, cut to dᶠⁱʳᵐ where the
    last clearing cut it). Returns the dispatch at the response, b0, the
    dispatch the bid answered to, and the fixed point's bid changes (empty when
    exogenous)."""
    delta, T = scenario.delta, scenario.T
    offer, d_firm = c_sigma(theta, delta), theta.d_firm(delta)
    b0 = market.clear(scenario, delta, np.zeros(T), offer, d_firm)
    if consistent:
        dispatch, believed, history = fixed_point(theta, tariff, market, scenario, b0)
        return dispatch, b0, believed, history
    d_bid, sigma_bid = best_response(theta, tariff, scenario, Belief(b0, consistent=False), b0, solver=market.solver)
    return market.clear(scenario, d_bid, sigma_bid, offer, d_firm), b0, b0, []


def summary(
    theta: LoadType,
    tariff: Tariff,
    market: Market,
    scenario: Scenario,
    consistent: bool = False,
    bid_b1: tuple | None = None,
    draws: int = 200,
) -> dict:
    """One row. At dispatch: welfare at B0, B1 and R, the value of flexibility
    S^B1 − S^B0 and what the tariff loses of it, S^B1 − S^R; the load's bill at
    B0 and R; everyone else's bill change by layer (fairness); the fleet's rent
    at B0 and R; and the fixed point's iterations and last change (None when
    exogenous). After the imbalance realizes, at B0 and at R:
    ``realized.outcomes`` and realized welfare ``S_realized``, which is S with
    the ORDC's cost replaced by the mean shed at c^shed, so it compares
    constructs. ``bid_b1`` is the bid ``(d_bid, σ_bid)`` from ``planner`` if
    already solved. Alignment and recovery are not in the row: ``alignment``
    and ``recovery`` read them off a dispatch."""
    dispatch, b0, believed, history = respond(theta, tariff, market, scenario, consistent)
    d1, s1 = planner(theta, market, scenario) if bid_b1 is None else bid_b1
    planned = market.clear(scenario, d1, s1, c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta))
    bill, bill_b0 = (settle(tariff, scenario, x, b0) for x in (dispatch, b0))
    S_B0, S_R, S_B1 = (welfare(theta, market, scenario, x) for x in (b0, dispatch, planned))
    after = {}
    for at, x, S_hat in (("_b0", b0, S_B0), ("", dispatch, S_R)):
        out = outcomes(scenario, x, theta, draws)
        out["S_realized"] = S_hat + out.pop("C_ordc") - market.c_shed * float(np.mean(out["shed_draws"]))
        after |= {f"{k}{at}": v for k, v in out.items()}
    return {
        "tariff": tariff.name,
        "type": theta.name,
        "construct": market.ordc.name,
        "consistent": consistent,
        "start": scenario.start,
        "S_B0": S_B0,
        "S_B1": S_B1,
        "S_R": S_R,
        "value_of_flexibility": S_B1 - S_B0,
        "efficiency": S_B1 - S_R,
        "bill_total": sum(bill.values()),
        "bill_b0_total": sum(bill_b0.values()),
        **{f"fairness_{k}": v for k, v in fairness(tariff, scenario, dispatch, b0).items()},
        "rent_b0": rent(scenario, b0),
        "rent": rent(scenario, dispatch),
        **after,
        "iterations": len(history) or None,
        "last_change": history[-1] if history else None,
    }


def table(
    types: dict[str, LoadType],
    tariffs: dict[str, Tariff],
    markets: list[Market],
    scenarios: list[Scenario],
    consistent: bool = False,
) -> pl.DataFrame:
    """The operator's table: one row per (type, tariff, construct, window). B1 is solved once per (type, construct, window)."""
    rows = []
    for theta, market, scenario in product(types.values(), markets, scenarios):
        bid_b1 = planner(theta, market, scenario)
        rows += [
            summary(theta, tariff, market, scenario, consistent, bid_b1)
            for tariff in tariffs.values()
        ]
    return pl.DataFrame(rows)


# ----------------------------------------------------------------------------
# a table for the report
# ----------------------------------------------------------------------------
def tex(
    table: pl.DataFrame,
    path: str | Path,
    digits: int = 0,
    groups: dict[str, list[str]] | None = None,
) -> None:
    """Write ``table`` as a booktabs ``tabular`` for ``\\input`` inside a table
    environment the document controls. Column names are the headers, written as
    given; floats get ``digits`` decimals, integers none, both thousands
    separators; nulls print as --. ``groups`` maps a header that spans several
    adjacent columns to their names; it adds a first header row with the spans."""

    def cell(v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "--"
        if isinstance(v, float):
            return f"{round(v, digits) or 0.0:,.{digits}f}"  # no −0
        return f"{v:,d}" if isinstance(v, int) else str(v)

    align = "".join("r" if dt.is_numeric() else "l" for dt in table.dtypes)
    header = [" & ".join(table.columns) + r" \\"]
    if groups:
        cols, cells, rules = list(table.columns), [""] * table.width, []
        for name, members in groups.items():
            idx = [cols.index(c) for c in members]
            a, b = min(idx), max(idx)
            if idx != list(range(a, b + 1)):
                raise ValueError(f"group {name!r} must span adjacent columns")
            cells[a] = rf"\multicolumn{{{b - a + 1}}}{{c}}{{{name}}}"
            cells[a + 1 : b + 1] = [None] * (b - a)
            rules.append(rf"\cmidrule(lr){{{a + 1}-{b + 1}}}")
        header = [" & ".join(c for c in cells if c is not None) + r" \\", " ".join(rules), *header]
    lines = [
        rf"\begin{{tabular}}{{@{{}}{align}@{{}}}}",
        r"\toprule",
        *header,
        r"\midrule",
        *(" & ".join(cell(v) for v in row) + r" \\" for row in table.iter_rows()),
        r"\bottomrule",
        r"\end{tabular}",
    ]
    Path(path).write_text("\n".join(lines) + "\n")
