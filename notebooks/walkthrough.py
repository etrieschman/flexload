# %% [markdown]
# # flexload walkthrough
#
# One operating window of the game, played the way the report's prototype table
# lays it out: fix the market, window and tariff; form the load's belief; the
# load bids; dispatch clears; the bill settles and the metrics are read. Then
# the two benchmarks (B0, B1), the consistent price-taker, the table over the
# load types, and one figure. The report's figures and tables are in
# `deliverableI.py`.
#
# Run it as a script, `uv run python notebooks/walkthrough.py`, or cell by cell
# in the `flexload (uv)` kernel. The first code cell holds every setting: the
# window, the load's size and type, the market, the reserve margin.
# Each later cell prints what it does. The RTS-GMLC data is fetched once into
# `~/.cache/rts_gmlc`; the first run downloads it. The report (§3) has the model;
# `docs/assumptions.md` has every choice the report does not make.


# %%
import time
from dataclasses import replace

import numpy as np
import polars as pl
import rts_gmlc as rts

import flexload as fl

pl.Config.set_tbl_rows(-1)  # every row
pl.Config.set_tbl_cols(-1)  # every column
pl.Config.set_tbl_width_chars(1000)
pl.Config.set_fmt_str_lengths(100)
np.set_printoptions(precision=1, suppress=True, linewidth=140)

# %%
# Settings. Every knob the walkthrough turns is here and nowhere else.
print("\nSettings")
T = 168  # hours per operating window: one week
WEEK = 31  # the window shown: early August, in the scarcity weeks 28-35
ALPHA = 0.05  # the load's size, its share of system load
RESERVE_MARGIN = 0.15  # spare capacity at the year's tightest hour (the default)
RESERVE = "ercot"  # "ercot" (demand curve) or "pjm" (hard requirement)
BUSINESS = "data_center_train"  # or "data_center_infer", "bitcoin_mine": sets (psi, beta, A) of the swept types
TYPE = "mover"  # inflexible, mover, controllable, emergency, curtailable
print(f"RTS-GMLC data folder:\t{rts.data_root()}")
print(f"RTS-GMLC git ref:\t{rts.REF[:8]}")

# %%
# Step 1. Build the environment and the operator's action. `windows` cuts the
# year into T-hour windows and scales load so the year's tightest hour has the
# reserve margin. `Market` is PJM or ERCOT; `C_inv` is the annual cost of the
# investment layer from a B0 run over the year (cached). `named_tariffs` gives
# today's tariff; `named_types` gives the load type; `c_sigma` its offer price;
# `d_firm` its firm level (None unless curtailable).
print("\n1. Fix the market and window; set the tariff")
t0 = time.time()
weeks = fl.windows(T=T, alpha=ALPHA, reserve_margin=RESERVE_MARGIN)
scenario = weeks[WEEK]
market = fl.Market(reserve=RESERVE)
market = replace(market, C_inv=fl.C_inv(market, weeks))
tau = fl.named_tariffs(scenario)["tau_0"]
theta = fl.named_types(T, BUSINESS)[TYPE]
offer = fl.c_sigma(theta, scenario.delta)
d_firm = theta.d_firm(scenario.delta)
ordc = market.ordc_for(scenario)
steps = list(zip(ordc.widths.round().tolist(), ordc.prices.round().tolist()))
print(f"setup time [s]:\t{time.time() - t0:.0f}")
print(f"hours in the window T:\t{scenario.T}")
print(f"generator offer blocks J:\t{scenario.J}")
print(f"physical units:\t{scenario.units.shape[0]}")
print(f"peak system load [MW]:\t{scenario.d_sys.max():,.0f}")
delta_range = f"{scenario.delta.min():,.0f}-{scenario.delta.max():,.0f}"
print(f"load's preferred profile delta, min-max [MW]:\t{delta_range}")
print(f"this window's tightest-hour margin [fraction]:\t{fl.margin(scenario):.3f}")
print(f"ex-ante peak hour t* [hour of window]:\t{scenario.peak}")
print(f"annual investment-layer cost C_inv [M$]:\t{market.C_inv / 1e6:,.1f}")
print(f"this window's share of C_inv [M$]:\t{market.C_inv * T / 8760 / 1e6:,.2f}")
print(f"forecast error std sigma_eps [MW]:\t{scenario.epsilon_std:,.0f}")
print(f"ORDC first steps (width [MW], price [$/MWh]):\t{steps[:4]} ...")

# %%
# Step 2. The load's belief for the exogenous price-taker: clear the market at
# the preferred profile with no reserve offered. This dispatch is also B0.
print("\n2. The load's belief: dispatch at the preferred profile (B0)")
t0 = time.time()
b0 = market.clear(scenario, scenario.delta, np.zeros(T), offer, d_firm)
print(f"clearing time [s]:\t{time.time() - t0:.1f}")
print(f"energy price lambda, mean [$/MWh]:\t{b0.lam.mean():.1f}")
print(f"energy price lambda, max [$/MWh]:\t{b0.lam.max():.1f}")
print(f"hours with a positive reserve price mu [count]:\t{(b0.mu > 1e-6).sum()}")
print(f"energy layer cost over the window [M$]:\t{b0.C_energy.sum() / 1e6:,.2f}")
print(f"reserve layer cost over the window [M$]:\t{b0.C_res.sum() / 1e6:,.2f}")
print(f"investment layer cost over the window [M$]:\t{b0.C_inv / 1e6:,.2f}")

# %%
# Step 3. The load bids. The exogenous price-taker solves its QP taking the B0
# prices, layer costs and posted rates as given; the result is the bid.
print("\n3. The load bids (exogenous price-taker)")
d_bid, sigma_bid = fl.best_response(theta, tau, scenario, fl.Belief(b0, consistent=False), b0)
shift = np.abs(d_bid - scenario.delta)
print(f"energy moved away from delta over the window [MWh]:\t{shift.sum():,.0f}")
print(f"hours moved most [hour of window]:\t{np.argsort(-shift)[:8]}")

# %%
# Step 4. Dispatch clears at the bid: what the load consumed and what cleared,
# the prices, the cost of each layer. The gap between the believed and realized
# energy price is the belief's error.
print("\n4. Dispatch clears")
dispatch = market.clear(scenario, d_bid, sigma_bid, offer, d_firm)
print(f"energy bid [MWh]:\t{d_bid.sum():,.0f}")
print(f"energy served [MWh]:\t{dispatch.d.sum():,.0f}")
price_error = np.abs(b0.lam - dispatch.lam).mean()
print(f"mean |believed - realized lambda| [$/MWh]:\t{price_error:.1f}")

# %%
# Step 5. Settle the bill at the realized dispatch, for the load at B0 and at R,
# then the alignment wedge (marginal charge less marginal system cost) by layer.
print("\n5. The bill settles; the metrics are calculated")
bill_b0 = fl.settle(tau, scenario, b0, b0)
bill_r = fl.settle(tau, scenario, dispatch, b0)
bills = {"layer": list(bill_b0)}
bills["B0 [$]"], bills["R [$]"] = list(bill_b0.values()), list(bill_r.values())
print("bill by layer at B0 and at R:")
print(pl.DataFrame(bills))
align = fl.alignment(tau, market, scenario, dispatch, b0)
print("mean |alignment wedge| by layer [$/MWh]:")
print(align.group_by("layer").agg(pl.col("wedge").abs().mean().alias("mean_abs_wedge")))

# %%
# Benchmarks. B0 is the dispatch of step 2. B1 is the planner, which chooses the
# load's bid to maximize welfare. `summary` collects one row: welfare at B0, B1
# and R, efficiency (S_B1 - S_R), the value of flexibility (S_B1 - S_B0), the bill.
print("\nBenchmarks: B0 is step 2; B1 is the planner")
t0 = time.time()
d_b1, sigma_b1 = fl.planner(theta, market, scenario)
print(f"planner time [s]:\t{time.time() - t0:.1f}")
row = fl.summary(theta, tau, market, scenario, b1=(d_b1, sigma_b1))
for k in ("S_B0", "S_B1", "S_R", "efficiency", "value_of_flexibility", "bill_total"):
    print(f"{k} [$]:\t{row[k]:,.0f}")

# %%
# The consistent price-taker. Bid, clear at the bid, make that dispatch the
# belief, repeat until the bid stops moving; the load knows its own share.
# Harmonic damping averages out the cycle a step merit order can produce.
print("\nThe consistent price-taker: steps 2-4 iterated to a fixed point")
t0 = time.time()
fp = fl.fixed_point(theta, tau, market, scenario, b0, max_iter=20, damping=None)
d_c, s_c, dispatch_c, believed, history = fp
print(f"rounds [count]:\t{len(history)}")
print(f"fixed-point time [s]:\t{time.time() - t0:.0f}")
print(f"last change in the bid [MW]:\t{history[-1]:.2f}")
S_R = float(
    fl.S(
        theta,
        market,
        scenario,
        dispatch.d,
        dispatch.sigma,
        dispatch.u,
        dispatch.r,
        dispatch.shed,
        dispatch.y,
        dispatch.Pi,
    ).value
)
S_R_c = float(
    fl.S(
        theta,
        market,
        scenario,
        dispatch_c.d,
        dispatch_c.sigma,
        dispatch_c.u,
        dispatch_c.r,
        dispatch_c.shed,
        dispatch_c.y,
        dispatch_c.Pi,
    ).value
)
print(f"welfare at R, exogenous belief [$]:\t{S_R:,.0f}")
print(f"welfare at R, consistent belief [$]:\t{S_R_c:,.0f}")
print(f"welfare at B1 [$]:\t{row['S_B1']:,.0f}")

# %%
# The table for RQ1: steps 2 to 5 and both benchmarks for every load type under
# today's tariff, one row per type.
print("\nThe table: one row per type (RQ1)")
t0 = time.time()
types = fl.named_types(T, BUSINESS)
table = fl.table(types, fl.named_tariffs(scenario), [market], [scenario])
print(f"table time [s]:\t{time.time() - t0:.0f}")
print("welfare by type [$]:")
print(table.select("type", "S_B0", "S_B1", "S_R", "efficiency", "value_of_flexibility"))

# %%
# Figure. Top: the energy price at B0 and at R, by hour. Bottom: the preferred
# profile delta, the load's bid, and the planner's consumption. Saved to
# notebooks/figures.
print("\nFigure: prices and consumption on the window")
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
print(f"figure saved to:\t{out / f'walkthrough_week{WEEK}.png'}")
