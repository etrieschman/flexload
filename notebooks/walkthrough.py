# %% [markdown]
# # flexload walkthrough
#
# The memo, one call at a time, on one week of RTS-GMLC. Run as a script
# (`uv run python notebooks/walkthrough.py`) or cell by cell in VS Code / Jupyter.

# %%
import time

import numpy as np
import polars as pl

import flexload as fl

pl.Config.set_tbl_rows(30)
pl.Config.set_tbl_width_chars(140)
np.set_printoptions(precision=1, suppress=True, linewidth=140)

# %% [markdown]
# ## ω and δ: a week of RTS-GMLC at one node
#
# Week 31 is early August, the annual peak. `alpha` is the flexible load's share of
# weekly energy, carved out of the RTS total. `reserve_margin` scales both loads so
# the tightest hour has 10% spare capacity; without it RTS-GMLC is slack (34%) and
# nothing ever binds.

# %%
scenario = fl.build_scenario(week=31, alpha=0.05, reserve_margin=0.10)
print(f"T={scenario.T} hours, J={scenario.J} offer blocks on {scenario.units.shape[0]} units")
print(f"peak system load {scenario.d_sys.max():,.0f} MW, flexible load delta {scenario.delta.min():,.0f}-{scenario.delta.max():,.0f} MW")
print(f"tightest-hour reserve margin {fl.reserve_margin(scenario):.3f}, ex-ante peak hour {scenario.peak}")

# %% [markdown]
# ## The environment, the operator's action, the load's type

# %%
market = fl.Market(reserve="ercot")  # or "pjm"; gamma, voll, long_run are fields
tariffs = fl.named_tariffs(scenario, gamma=market.gamma)
theta = fl.named_types(scenario.T)["mover"]
tau = tariffs["tau_0"]
offer = fl.c_s(theta, scenario.delta)  # the mover sells no reserve, so this is zero
print(tau)

# %% [markdown]
# ## B0: the inflexible path, and what it clears
#
# `clear` is 𝓜_ω(d, σ). The tariff enters only through dᶠⁱʳᵐ (none under τ₀).

# %%
t0 = time.time()
b0 = market.clear(scenario, tau, scenario.delta, np.zeros(scenario.T), offer)
print(f"cleared in {time.time() - t0:.1f}s: lambda mean {b0.lam.mean():.1f}, max {b0.lam.max():.1f}; mu > 0 in {(b0.mu > 1e-6).sum()} hours")
C_res, C_inv = market.pools(b0, scenario)
print(f"reserve pool over the week {C_res.sum():,.0f} $, missing money {C_inv:,.0f} $ (negative: scarcity rents exceed the weekly share of investment cost)")

# %% [markdown]
# ## R: the exogenous price-taker's best response
#
# A QP in (d, σ). Prices, pools and the average rate at δ are taken as given.

# %%
d, sigma = fl.best_response(theta, tau, scenario.delta, b0.lam, b0.mu, C_res, C_inv, scenario.d_other, d_hat=scenario.delta)
dispatch = market.clear(scenario, tau, d, sigma, offer)
print(f"energy shifted {np.abs(d - scenario.delta).sum():,.0f} MWh over the week; weekly energy conserved: {np.isclose(d.sum(), scenario.delta.sum())}")
print("hours the load moved most:", np.argsort(-np.abs(d - scenario.delta))[:8])

# %% [markdown]
# ## The bill, by layer, at settlement
#
# `settle` reads the pool of each cost-share layer from the dispatch its basis names
# (ex ante: the one at (δ, 0); realized: the one at the bid).

# %%
bill_b0 = fl.settle(tau, market, scenario, b0, b0)
bill_r = fl.settle(tau, market, scenario, dispatch, b0)
print(pl.DataFrame({"layer": list(bill_b0), "B0": [float(v) for v in bill_b0.values()], "R": [float(v) for v in bill_r.values()]}))

# %% [markdown]
# ## B1: the planner, and the four metrics

# %%
t0 = time.time()
d1, s1, S_star = fl.planner(theta, market, scenario)
b1 = market.clear(scenario, None, d1, s1, offer)
print(f"planner in {time.time() - t0:.1f}s")
row = fl.summary(theta, tau, market, scenario, dispatch, b1, S_star, b0)
print(row.select("S_star", "S_B0", "S_R", "regret", "value_of_flexibility", "bill_total", "recovery_reserve", "recovery_investment", "fairness_reserve"))

# %%
align = fl.alignment(tau, market, scenario, dispatch, b0)
print(align.filter(pl.col("layer") == "reserve").sort("wedge", descending=True).head(5))
print(align.group_by("layer").agg(pl.col("wedge").abs().mean().alias("mean_abs_wedge")))

# %% [markdown]
# ## The consistent price-taker: a fixed point
#
# Solve the QP, clear at the response, hand the new prices back, repeat. Under a
# step-function merit order the map can cycle at scarcity hours; the harmonic step
# averages it out and the history shows whether it settled.

# %%
t0 = time.time()
d_c, s_c, dispatch_c, history = fl.fixed_point(theta, tau, market, scenario, max_iter=20, damping=None)
print(f"{len(history)} iterations in {time.time() - t0:.0f}s, last change {history[-1]:.2f} MW")
print(f"S_R exogenous {fl.S(theta, market, scenario, dispatch):,.0f}  consistent {fl.S(theta, market, scenario, dispatch_c):,.0f}  S* {S_star:,.0f}")

# %% [markdown]
# ## The operator's table: tariffs x types, one week
#
# The operator's objective is a rule over this table.

# %%
t0 = time.time()
table = fl.evaluate(
    {k: tariffs[k] for k in ("tau_0", "tau_2", "tau_4", "tau_6")},
    {k: v for k, v in fl.named_types(scenario.T).items() if k in ("mover", "clr")},
    market,
    [scenario],
)
print(f"{table.shape[0]} rows in {time.time() - t0:.0f}s")
print(table.select("tariff", "elected", "type", "regret", "bill_total", "recovery_reserve", "recovery_investment", "fairness_reserve"))
print("min-max regret picks", fl.choose(table, "minmax_regret"), "; max welfare picks", fl.choose(table, "max_welfare"))

# %% [markdown]
# ## Learning across weeks: the peak-hour chase
#
# Settle the investment layer on the *realized* peak hour, reveal it after each
# week, and let the load count. Watch the believed and realized peaks.

# %%
weeks = [fl.build_scenario(week=w, alpha=0.05, reserve_margin=0.10) for w in (29, 30, 31, 32)]
learner = fl.Combined((fl.PriceAveraging(0.5), fl.PeakCounts(strength=1.0)))
trace, dispatches = fl.simulate(theta, tau, market, weeks, learner, ex_post_peak=True)
print(trace)

# %% [markdown]
# ## Figures

# %%
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path

    out = Path(__file__).parent / "figures" if "__file__" in globals() else Path("figures")
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
