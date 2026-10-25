"""Settlement, welfare, the outcomes, and the loop that fills the operator's
table, one row per (type, tariff, market, window). Report §1 "Outcomes" and
§3 "System operator". The operator's rule over the table is not built
(deleted 2026-10-23; git 22257a4 has the last version).

Outcomes: welfare S at B0, B1 and R; efficiency S^B1 − S^R; and per layer,
alignment Δᵏ_t, recovery ρᵏ, fairness.
"""

from __future__ import annotations

from dataclasses import replace
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
    else as one load: d and d° swapped, σ = 0 so the credit is zero, and the
    tariff without the curtailable exemption, which is the load's alone."""
    if own:
        bill = tariff.bill(realized.d, realized.sigma, realized, scenario.d_other, b0)
    else:
        others = replace(tariff, exempt_curtailable=False)
        bill = others.bill(scenario.d_other, np.zeros(scenario.T), realized, realized.d, b0)
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


def rent(scenario: Scenario, dispatch: Dispatch) -> float:
    """The fleet's capacity rent over the window, Σ_j Σ_t ν_jt ū_jt: what Cⁱⁿᵛ
    nets out of investment cost over the year. In $."""
    return float(np.sum(dispatch.nu * scenario.capacity))


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
    b0: Dispatch,
) -> dict[str, float]:
    """Bᵏ(d°)|R − Bᵏ(d°)|B0: how everyone else's bill moves when the load
    responds, against the bill before it did. Positive: others pay more.
    (Erich, 2026-10-23: against B0, not B1; the planner never holds the
    flexibility, and R against B1 is efficiency.)"""
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
        _, _, dispatch, believed, history = fixed_point(theta, tariff, market, scenario, b0)
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
    of flexibility, the bill by layer at B0, R and B1, Δᵏ_t at R, signed, over
    the hours where the layer's marginal charge or marginal cost is nonzero
    (Erich, 2026-10-24; with reserve offers that is every hour on reserve, and
    t* on investment): their count, mean, 1st and 99th percentiles, recovery at R and B1, fairness (others' bill, R − B0), the fleet's capacity rent at B0, R and B1, the
    belief's price error, and the fixed point's iterations and last change.
    ``b1`` is the bid ``(d_bid, σ_bid)`` from ``planner`` if already solved.
    S is read from a clearing at each of the three bids."""
    dispatch, b0, believed, history = respond(theta, tariff, market, scenario, belief)
    d1, s1 = planner(theta, market, scenario) if b1 is None else b1
    planned = market.clear(
        scenario, d1, s1, c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta)
    )
    bill, bill_b0, bill_b1 = (settle(tariff, scenario, x, b0) for x in (dispatch, b0, planned))
    rho, rho_b1 = (recovery(tariff, scenario, x, b0) for x in (dispatch, planned))
    fair = fairness(tariff, scenario, dispatch, b0)
    wedge = alignment(tariff, market, scenario, dispatch, b0)
    align = {}
    for k in LAYERS:
        layer = wedge.filter(pl.col("layer") == k)
        priced = (layer["marginal_charge"].abs() > 1e-6) | (layer["marginal_cost"].abs() > 1e-6)
        hours = layer.filter(priced)["wedge"].to_numpy()  # where the layer charges or costs anything
        align[f"alignment_hours_{k}"] = int(hours.size)
        align[f"alignment_{k}"] = float(hours.mean()) if hours.size else None
        align[f"alignment_p1_{k}"] = float(np.percentile(hours, 1)) if hours.size else None
        align[f"alignment_p99_{k}"] = float(np.percentile(hours, 99)) if hours.size else None
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
        **{f"bill_b1_{k}": v for k, v in bill_b1.items()},
        "bill_b1_total": sum(bill_b1.values()),
        **align,
        **{f"recovery_{k}": v for k, v in rho.items()},
        **{f"recovery_b1_{k}": v for k, v in rho_b1.items()},
        **{f"fairness_{k}": v for k, v in fair.items()},
        "rent_b0": rent(scenario, b0),
        "rent": rent(scenario, dispatch),
        "rent_b1": rent(scenario, planned),
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
