# %% [markdown]
# # flexload walkthrough
#
# The memo, one call at a time, on one week of RTS-GMLC. Run as a script
# (`uv run python notebooks/walkthrough.py`) or cell by cell in the `flexload (uv)` kernel.

import time
from dataclasses import replace

import numpy as np
import polars as pl

import flexload as fl

pl.Config.set_tbl_rows(30)
pl.Config.set_tbl_width_chars(160)
np.set_printoptions(precision=1, suppress=True, linewidth=140)

# %% [markdown]
# ## ω and δ: the year in operating windows of one week
#
# `alpha` sets the load's size: δ is that share of system load, hour by hour,
# carved out of the RTS total. `reserve_margin` scales both loads by one factor
# for the whole year so the annual tightest hour has 10% spare capacity; without
# it RTS-GMLC is slack (34%) and nothing ever binds. Week 31 is early August, in
# the run of scarcity weeks (28–35); the tightest hour is in week 32, the peak
# load in 34.

weeks = fl.windows(T=24 * 7, alpha=0.05, reserve_margin=0.10)
scenario = weeks[31]
print(
    f"T={scenario.T} hours, J={scenario.J} offer blocks on {scenario.units.shape[0]} units"
)
print(
    f"peak system load {scenario.d_sys.max():,.0f} MW, flexible load delta {scenario.delta.min():,.0f}-{scenario.delta.max():,.0f} MW"
)
print(
    f"this week's tightest-hour margin {fl.margin(scenario):.3f}, ex-ante peak hour {scenario.peak}"
)

# %% [markdown]
# ## The environment, the operator's action, the load's type
#
# The cost of the investment layer Cⁱⁿᵛ is annual: investment cost less the rents
# capacity earns on the B0 path over the year, prorated to the window. It takes
# 52 clearings and is cached. Under ERCOT the reserve demand curve is fit to the
# window's forecast error, with R̲ at the largest unit.

# %%
market = fl.Market(reserve="ercot")  # or "pjm"; gamma, voll, long_run are fields
market = replace(market, C_inv=fl.C_inv(market, weeks))
print(f"annual investment-layer cost {market.C_inv / 1e6:,.1f} M$; this window's share {market.C_inv * 168 / 8760 / 1e6:,.2f} M$")
curve = market.curve(scenario)
print(f"forecast error {scenario.forecast_error:,.0f} MW; ORDC steps (MW wide, $/MWh): {list(zip(np.round(curve.widths).tolist(), np.round(curve.prices).tolist()))[:4]} ...")
tau = fl.named_tariffs(scenario)["tau_0"]  # today's tariff
theta = fl.named_types(scenario.T, "data_center")["mover"]  # θ₁ as a data center
offer = fl.c_sigma(theta, scenario.delta)  # the mover sells no reserve, so this is zero
print(
    f"tau_0: reserve {type(tau.reserve).__name__} every hour, investment {type(tau.investment).__name__} on the peak hour t* = {scenario.peak}"
)

# %% [markdown]
# ## B0: the inflexible path, and what it clears
#
# `clear` is 𝓜_ω(d, σ). The dispatch carries λ, μ and the cost of each layer.

# %%
t0 = time.time()
b0 = market.clear(
    scenario, scenario.delta, np.zeros(scenario.T), offer, theta.d_firm(scenario.delta)
)
print(
    f"cleared in {time.time() - t0:.1f}s: lambda mean {b0.lam.mean():.1f}, max {b0.lam.max():.1f}; mu > 0 in {(b0.mu > 1e-6).sum()} hours"
)
print(
    f"cost of each layer over the week: energy {b0.C_energy.sum():,.0f} $, reserve {b0.C_res.sum():,.0f} $, investment {b0.C_inv:,.0f} $"
)

# %% [markdown]
# ## R: the exogenous price-taker's best response
#
# A QP in (d, σ). The belief is the B0 dispatch: prices, layer costs and the rate at δ are taken as given.

# %%
d, sigma = fl.best_response(theta, tau, scenario, belief=b0)
dispatch = market.clear(scenario, d, sigma, offer, theta.d_firm(scenario.delta))
print(
    f"energy shifted {np.abs(d - scenario.delta).sum():,.0f} MWh over the week; energy conserved: {np.isclose(d.sum(), scenario.delta.sum())}"
)
print("hours the load moved most:", np.argsort(-np.abs(d - scenario.delta))[:8])

# %% [markdown]
# ## The bill, by layer, at settlement
#
# Each cost-share layer's cost comes from the dispatch its `ex_ante` flag names.

# %%
bill_b0, bill_r = (
    fl.settle(tau, scenario, b0, b0),
    fl.settle(tau, scenario, dispatch, b0),
)
print(
    pl.DataFrame(
        {
            "layer": list(bill_b0),
            "B0": list(bill_b0.values()),
            "R": list(bill_r.values()),
        }
    )
)

# %% [markdown]
# ## B1: the planner, and the outcomes

# %%
t0 = time.time()
d1, s1, S_B1 = fl.planner(theta, market, scenario)
b1 = market.clear(scenario, d1, s1, offer, theta.d_firm(scenario.delta))
print(f"planner in {time.time() - t0:.1f}s")
row = fl.summary(theta, tau, market, scenario)
print(
    {
        k: round(v, 1) if isinstance(v, float) else v
        for k, v in row.items()
        if k
        in (
            "S_B0",
            "S_B1",
            "S_R",
            "efficiency",
            "value_of_flexibility",
            "bill_total",
            "recovery_reserve",
            "fairness_reserve",
            "price_error",
        )
    }
)

# %%
align = fl.alignment(tau, market, scenario, dispatch, b0)
print(align.filter(pl.col("layer") == "reserve").sort("wedge", descending=True).head(5))
print(align.group_by("layer").agg(pl.col("wedge").abs().mean().alias("mean_abs_wedge")))

# %% [markdown]
# ## The consistent price-taker: a fixed point
#
# Respond, clear at the response, make that the belief, repeat. Under a step
# merit order the map can cycle at scarcity hours; the harmonic step averages it
# out and `history` shows whether it settled.

# %%
t0 = time.time()
d_c, s_c, dispatch_c, believed, history = fl.fixed_point(
    theta, tau, market, scenario, max_iter=20, damping=None
)
print(
    f"{len(history)} iterations in {time.time() - t0:.0f}s, last change {history[-1]:.2f} MW, price error {np.abs(believed.lam - dispatch_c.lam).mean():.1f} $/MWh"
)
print(
    f"S_R exogenous {fl.S(theta, market, scenario, dispatch):,.0f}  consistent {fl.S(theta, market, scenario, dispatch_c):,.0f}  S_B1 {S_B1:,.0f}"
)

# %% [markdown]
# ## The operator's table: types x tariffs, one week
#
# The operator's objective is a rule over this table: max-min welfare over the
# types, with the inflexible load left out, subject to recovery.

# %%
t0 = time.time()
tariffs = fl.named_tariffs(scenario)
types = fl.named_types(scenario.T, "data_center")
table = fl.table(
    {k: types[k] for k in ("mover", "controllable", "curtailable")},
    {k: tariffs[k] for k in ("tau_0", "tau_2", "tau_4", "tau_5")},
    [market],
    [scenario],
)
print(f"{table.shape[0]} rows in {time.time() - t0:.0f}s")
print(
    table.select(
        "tariff",
        "elected",
        "type",
        "efficiency",
        "value_of_flexibility",
        "bill_total",
        "recovery_reserve",
        "fairness_reserve",
    )
)
print(
    "max-min welfare picks",
    fl.choose(table),
    "; with a uniform prior",
    fl.choose(
        table,
        "expected_welfare",
        prior={"mover": 1 / 3, "controllable": 1 / 3, "curtailable": 1 / 3},
    ),
)

# %% [markdown]
# ## Learning across weeks: the fourth price belief
#
# The load averages the prices it saw. `price_error` is how far its belief sat
# from what cleared.

# %%
trace, _ = fl.learn(theta, tau, market, weeks[28:36], eta=0.5)
print(trace)

# %% [markdown]
# ## Figure

# %%
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path

    out = (
        Path(__file__).parent / "figures"
        if "__file__" in globals()
        else Path("figures")
    )
    out.mkdir(exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(b0.lam, label="lambda at B0")
    ax[0].plot(dispatch.lam, label="lambda at R", alpha=0.7)
    ax[0].set_ylabel("$/MWh")
    ax[0].legend()
    ax[1].plot(scenario.delta, label="delta")
    ax[1].plot(d, label="d (exogenous price-taker)")
    ax[1].plot(d1, label="d (planner)", alpha=0.7)
    ax[1].set_ylabel("MW")
    ax[1].set_xlabel("hour of week")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(out / "walkthrough_week31.png", dpi=120)
    print("saved", out / "walkthrough_week31.png")
except ImportError:
    pass
