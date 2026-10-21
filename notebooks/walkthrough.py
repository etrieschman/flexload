# %% [markdown]
# # flexload walkthrough
#
# One window of the game, step by step (report §5, Table "code"). Run as a
# script, `uv run python notebooks/walkthrough.py`, or cell by cell in the
# `flexload (uv)` kernel. Every setting is in the next cell.

# %%
import time
from dataclasses import replace

import numpy as np
import polars as pl
import rts_gmlc as rts

import flexload as fl

pl.Config.set_tbl_rows(30)
pl.Config.set_tbl_width_chars(160)
np.set_printoptions(precision=1, suppress=True, linewidth=140)

# %% [markdown]
# ## Settings

# %%
T = 168  # hours per operating window: one week
WEEK = 31  # the window shown: early August, in the scarcity weeks 28-35
ALPHA = 0.05  # the load's size, its share of system load
RESERVE_MARGIN = 0.15  # spare capacity at the year's tightest hour (the default)
RESERVE = "ercot"  # "ercot" (demand curve) or "pjm" (hard requirement)
BUSINESS = "data_center"  # or "bitcoin_mine": sets (psi, beta, A) of the swept types
TYPE = "mover"  # inflexible, mover, controllable, emergency, curtailable
LEARN_WEEKS = slice(28, 36)  # windows the learner plays, in order
ETA = 0.5  # the learner's weight on the latest window
print(f"RTS-GMLC data: {rts.data_root()} at ref {rts.REF[:8]}")

# %% [markdown]
# ## 1. Fix the market and window; set the tariff
#
# `windows` cuts the year into windows under one tightness scale. `C_inv` is the
# annual cost of the investment layer, from a B0 run over the year (cached).

# %%
t0 = time.time()
weeks = fl.windows(T=T, alpha=ALPHA, reserve_margin=RESERVE_MARGIN)
scenario = weeks[WEEK]
market = fl.Market(reserve=RESERVE)
market = replace(market, C_inv=fl.C_inv(market, weeks))
tau = fl.named_tariffs(scenario)["tau_0"]
theta = fl.named_types(T, BUSINESS)[TYPE]
offer = fl.c_sigma(theta, scenario.delta)
d_firm = theta.d_firm(scenario.delta)
print(f"set up in {time.time() - t0:.0f}s")
print(f"T={scenario.T}, J={scenario.J} offer blocks, {scenario.units.shape[0]} units")
print(f"peak load {scenario.d_sys.max():,.0f} MW")
print(f"delta {scenario.delta.min():,.0f}-{scenario.delta.max():,.0f} MW")
print(f"window margin {fl.margin(scenario):.3f}; peak hour t* = {scenario.peak}")
print(f"annual C_inv {market.C_inv / 1e6:,.1f} M$")
print(f"window share of C_inv {market.C_inv * T / 8760 / 1e6:,.2f} M$")
ordc = market.ordc_for(scenario)
steps = list(zip(ordc.widths.round().tolist(), ordc.prices.round().tolist()))
print(f"sigma_eps {scenario.epsilon_std:,.0f} MW")
print(f"ORDC steps (MW, $/MWh): {steps[:4]} ...")

# %% [markdown]
# ## 2. Inputs for the load's belief: dispatch at the preferred profile (B0)

# %%
t0 = time.time()
b0 = market.clear(scenario, scenario.delta, np.zeros(T), offer, d_firm)
print(f"cleared in {time.time() - t0:.1f}s")
print(f"lambda mean {b0.lam.mean():.1f}, max {b0.lam.max():.1f}")
print(f"mu > 0 in {(b0.mu > 1e-6).sum()} hours")
print(f"energy cost {b0.C_energy.sum():,.0f} $")
print(f"reserve cost {b0.C_res.sum():,.0f} $")
print(f"investment cost {b0.C_inv:,.0f} $")

# %% [markdown]
# ## 3. The load bids (exogenous price-taker: posted rates at the B0 prices)

# %%
d_bid, sigma_bid = fl.best_response(theta, tau, scenario, belief=b0, b0=b0)
print(f"energy shifted {np.abs(d_bid - scenario.delta).sum():,.0f} MWh")
print("hours moved most:", np.argsort(-np.abs(d_bid - scenario.delta))[:8])

# %% [markdown]
# ## 4. Dispatch clears

# %%
dispatch = market.clear(scenario, d_bid, sigma_bid, offer, d_firm)
print(f"served {dispatch.d.sum():,.0f} of {d_bid.sum():,.0f} MWh bid")
print(f"price error {np.abs(b0.lam - dispatch.lam).mean():.1f} $/MWh")

# %% [markdown]
# ## 5. The bill settles; the metrics are calculated

# %%
bill_b0 = fl.settle(tau, scenario, b0, b0)
bill_r = fl.settle(tau, scenario, dispatch, b0)
bills = {"layer": list(bill_b0)}
bills["B0"], bills["R"] = list(bill_b0.values()), list(bill_r.values())
print(pl.DataFrame(bills))
align = fl.alignment(tau, market, scenario, dispatch, b0)
print(align.group_by("layer").agg(pl.col("wedge").abs().mean().alias("mean_abs_wedge")))

# %% [markdown]
# ## Benchmarks: B0 is step 2; B1 is the planner

# %%
t0 = time.time()
d_b1, sigma_b1, S_B1 = fl.planner(theta, market, scenario)
print(f"planner in {time.time() - t0:.1f}s")
row = fl.summary(theta, tau, market, scenario, b1=(d_b1, sigma_b1, S_B1))
keys = ("S_B0", "S_B1", "S_R", "efficiency", "value_of_flexibility", "bill_total")
print({k: round(row[k], 1) for k in keys})

# %% [markdown]
# ## The consistent price-taker: steps 2-4 iterated to a fixed point
#
# Harmonic damping averages out the cycle a step merit order can produce.

# %%
t0 = time.time()
fp = fl.fixed_point(theta, tau, market, scenario, max_iter=20, damping=None)
d_c, s_c, dispatch_c, believed, history = fp
print(f"{len(history)} rounds in {time.time() - t0:.0f}s")
print(f"last change {history[-1]:.2f} MW")
print(f"S_R exogenous {fl.S(theta, market, scenario, dispatch):,.0f}")
print(f"S_R consistent {fl.S(theta, market, scenario, dispatch_c):,.0f}")
print(f"S_B1 {S_B1:,.0f}")

# %% [markdown]
# ## The table: one row per type (RQ1)

# %%
t0 = time.time()
types = fl.named_types(T, BUSINESS)
table = fl.table(types, fl.named_tariffs(scenario), [market], [scenario])
print(f"{table.shape[0]} rows in {time.time() - t0:.0f}s")
cols = ("type", "S_B0", "S_B1", "S_R", "efficiency", "value_of_flexibility")
print(table.select(*cols))

# %% [markdown]
# ## The learner across windows

# %%
trace, _ = fl.learn(theta, tau, market, weeks[LEARN_WEEKS], eta=ETA)
print(trace)

# %% [markdown]
# ## Figure: prices and consumption on the window

# %%
import matplotlib

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

here = Path(__file__).parent if "__file__" in globals() else Path(".")
out = here / "figures"
out.mkdir(exist_ok=True)
fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax[0].plot(b0.lam, label="lambda at B0")
ax[0].plot(dispatch.lam, label="lambda at R", alpha=0.7)
ax[0].set_ylabel("$/MWh")
ax[0].legend()
ax[1].plot(scenario.delta, label="delta")
ax[1].plot(d_bid, label="d_bid, exogenous price-taker")
ax[1].plot(d_b1, label="d, planner", alpha=0.7)
ax[1].set_ylabel("MW")
ax[1].set_xlabel("hour of window")
ax[1].legend()
fig.tight_layout()
fig.savefig(out / f"walkthrough_week{WEEK}.png", dpi=120)
print("saved", out / f"walkthrough_week{WEEK}.png")
