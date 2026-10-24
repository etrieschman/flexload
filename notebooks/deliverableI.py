# %% [markdown]
# # Deliverable I: the figures and tables of the Workshop I report (§4)
#
# Every exhibit sits at the base configuration and moves at most two dimensions.
# Base: ERCOT, week 32, α = 5%, training data center, exogenous price-taker, τ₀.
# Week 32 holds the year's tightest hour, where the reserve margin is set, and
# 12 of ERCOT's 56 scarcity hours (week 29 has 21; week 31 has one).
#
# | exhibit | moves | question |
# |---|---|---|
# | Figure 0 | week | the market: the supply stack (`genstack`) and the pools by week under B0 (`pools`) |
# | Figure 1 | market, business | the window: λ and consumption at B0, R and B1; system load against capacity and the market's scarcity line |
# | Table 1 | market, type, business | RQ1a: flexibility value, efficiency, bill change B0 → R by layer |
# | Table 2 | market, type, business | RQ1a, b: alignment, recovery and fairness by layer |
# | Table 3 | α, market, business | RQ3: flexibility value, efficiency and fairness by layer against load size |
#
# Beliefs do not move: every exhibit is the exogenous price-taker (RQ4 is about
# beliefs; the consistent price-taker's table was dropped 2026-10-23). Run as a script,
# `uv run python notebooks/deliverableI.py`, or cell by cell. Figures go to
# `notebooks/figures`, tables to `notebooks/tables` as booktabs for `\input`;
# with `FLEXLOAD_OUT` set (in the environment or in `.env` at the repo root)
# each .png and .tex is also copied there, flat, for the Overleaf project.

# %%
import os
import shutil
import time
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.lines import Line2D

import flexload as fl

pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_width_chars(1000)
pl.Config.set_fmt_str_lengths(100)
np.set_printoptions(precision=1, suppress=True, linewidth=140)

# %%
# Settings: the base configuration and the dimensions each exhibit moves.
T = 168
WEEK = 32  # the window: the year's tightest hour is in it
ALPHA = 0.05
RESERVE_MARGIN = 0.15
TYPE = "mover"  # the type Figure 1 and Table 3 follow
BUSINESSES = {"data_center_train": "training DC", "bitcoin_mine": "bitcoin mine"}
MARKETS = ("ercot", "pjm")
ALPHAS = (0.01, 0.05, 0.10, 0.20)
SWEPT = ("mover", "controllable", "curtailable")  # the types whose (ψ, β, A) the business sets
LAYERS_BILLED = fl.LAYERS  # energy too: its wedge is zero at the margin, but others' energy bill moves
K = 1e3  # dollars per k$
here = Path(__file__).parent if "__file__" in globals() else Path(".")
figures, tables = here / "figures", here / "tables"
figures.mkdir(exist_ok=True)
tables.mkdir(exist_ok=True)
dotenv = here.parent / ".env"
if dotenv.exists():  # KEY=VALUE lines; the environment wins
    for line in dotenv.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
OUT = Path(os.environ["FLEXLOAD_OUT"]).expanduser() if os.environ.get("FLEXLOAD_OUT") else None


def publish(path: Path) -> None:
    """Copy a saved figure or table to FLEXLOAD_OUT, if set."""
    if OUT is not None:
        OUT.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, OUT / path.name)
    print(f"saved:\t{path}" + (f"\t-> {OUT / path.name}" if OUT else ""))


percent = lambda col: (pl.col(col) * 100).round().cast(pl.Int64)  # noqa: E731
DAMBLUE, FTRORANGE, CAPPLUM = "#1F4E79", "#BF5700", "#703078"  # the report's colors
SLATELT, INK = "#96A0AA", "#262C34"
COLOR = {"data_center_train": DAMBLUE, "bitcoin_mine": FTRORANGE}  # business: one hue everywhere
POOL = {"energy": SLATELT, "reserve": CAPPLUM, "investment": INK}  # the pools, where no business applies


STYLE = {"B0": ":", "R": "-", "B1": "--"}

# %%
# The environment: the year in weeks under one tightness scale, the two markets
# with their annual investment-layer cost, week 31, and τ₀.
print("\nEnvironment")
t0 = time.time()
weeks = fl.windows(T=T, alpha=ALPHA, reserve_margin=RESERVE_MARGIN)
scenario = weeks[WEEK]
markets = {m: fl.Market(reserve=m) for m in MARKETS}
markets = {m: replace(mk, C_inv=fl.C_inv(mk, weeks)) for m, mk in markets.items()}
tau = fl.named_tariffs(scenario)["tau_0"]
types = {b: fl.named_types(T, b) for b in BUSINESSES}
print(f"setup time [s]:\t{time.time() - t0:.0f}")
for m, mk in markets.items():  # the pool: the fleet's investment cost net of its rents, floored at zero
    print(f"annual investment pool C_inv, net of rents, {m} [M$]:\t{mk.C_inv / 1e6:,.1f}")


def label(df: pl.DataFrame) -> pl.DataFrame:
    """Business names for the tables; one row each for the types the business does not move."""
    return df.with_columns(pl.col("business").replace_strict(BUSINESSES, default="--"))


# %%
# Figure 0, the market. Left: the supply stack, cumulative capacity against
# marginal cost, one bar per offer block, colored by fuel; renewables at their
# average hour over the year, thermal units at nameplate; the year's average
# and peak system load as vertical lines. Right: the energy and reserve pools
# and the window's share of the annual investment pool, Cⁱⁿᵛ T/8760, stacked by
# week under B0 in each market. ERCOT's investment pool is zero at this margin:
# the scarcity weeks' energy and reserve prices pay the fleet. PJM's hard
# requirement never binds at this margin, so its reserve pool is zero and the
# investment pool carries the fleet's cost.
print("\nFigure 0: the supply stack and the pools by week under B0")
t0 = time.time()
avg_capacity = np.mean([w.capacity.mean(axis=1) for w in weeks], axis=0)
fuel = np.array([n.split("_")[1] for n in scenario.names])
FUEL_COLOR = {
    "NUCLEAR": "#6a3d9a", "STEAM": "#4d4d4d", "CC": "#1f78b4", "CT": "#a6cee3",
    "HYDRO": "#33a02c", "WIND": "#b2df8a", "PV": "#ff7f00", "RTPV": "#fdbf6f", "CSP": "#e31a1c",
}
order = np.argsort(scenario.cost_gen, kind="stable")
left = np.concatenate([[0.0], np.cumsum(avg_capacity[order])[:-1]])
d_sys_year = np.concatenate([w.d_sys for w in weeks])

pools = {}
for m, mk in markets.items():
    rows = []
    for w in weeks:
        b0_w = mk.clear(w, w.delta, np.zeros(T), np.zeros(T))
        rows.append(
            {
                "week": w.start // T,
                "energy": float(b0_w.C_energy.sum()),
                "reserve": float(b0_w.C_res.sum()),
                "investment": b0_w.C_inv,
            }
        )
    pools[m] = pl.DataFrame(rows)
print(f"B0 over the year, both markets [s]:\t{time.time() - t0:.0f}")

fig, a0 = plt.subplots(figsize=(7, 4.5))
colors = [FUEL_COLOR.get(f, "#999999") for f in fuel[order]]
a0.bar(left, scenario.cost_gen[order], width=avg_capacity[order], align="edge", color=colors, edgecolor="none")
free = scenario.cost_gen[order] <= 0.0  # zero-cost units: a strip below the axis, so they show
a0.bar(left[free], -4.0, width=avg_capacity[order][free], align="edge", color=np.array(colors)[free], edgecolor="none")
a0.axhline(0.0, color="k", lw=0.5)
a0.axvline(d_sys_year.mean(), color="k", lw=1, label=f"average load {d_sys_year.mean():,.0f} MW")
a0.axvline(d_sys_year.max(), color="k", lw=1, ls="--", label=f"peak load {d_sys_year.max():,.0f} MW")
a0.set_xlabel("cumulative capacity, average hour [MW]; zero-cost units drawn below the axis")
a0.set_ylabel("marginal cost [$/MWh]")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for f, c in FUEL_COLOR.items() if f in set(fuel)]
handles += a0.get_legend_handles_labels()[0]
labels = [f for f in FUEL_COLOR if f in set(fuel)] + a0.get_legend_handles_labels()[1]
a0.legend(handles, labels, fontsize=8, ncol=2)
fig.tight_layout()
fig.savefig(figures / "figure_0_genstack.png", dpi=150)
publish(figures / "figure_0_genstack.png")

fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))  # own scales: ERCOT's scarcity weeks are ten times PJM's
for a, m in zip(ax, MARKETS):
    p = pools[m]
    a.bar(p["week"], p["energy"] / 1e6, label="energy pool", color=POOL["energy"])
    a.bar(p["week"], p["reserve"] / 1e6, bottom=p["energy"] / 1e6, label="reserve pool", color=POOL["reserve"])
    a.bar(p["week"], p["investment"] / 1e6, bottom=(p["energy"] + p["reserve"]) / 1e6,
          label=r"investment pool $C^{inv}\,T/8760$", color=POOL["investment"])
    a.axvline(WEEK, color="k", lw=0.5, alpha=0.5)
    pool_week = markets[m].C_inv * T / 8760 / 1e6
    a.set_title(m.upper())
    a.set_xlabel("week of the year")
    a.set_ylim(0, 1.08 * float((p["energy"] + p["reserve"] + p["investment"]).max()) / 1e6)
ax[0].set_ylabel("pools by week under B0 [M$ per week]")
fig.legend(*ax[1].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(figures / "figure_0_pools.png", dpi=150)
publish(figures / "figure_0_pools.png")

# %%
# Figure 1, the window. Rows: the energy price λ, the load's consumption, and
# the system load at B0 against capacity and the market's scarcity line,
# capacity less the reserve the market pays for: under ERCOT load-following
# γ d_sys plus the width of the demand curve, under PJM the largest unit plus
# load-following. Load above the line and the market prices scarcity. The
# response moves system load by at most βα, invisible at this scale, so the
# row shows B0 only. Columns: the markets. Lines: B0 (dotted, black), R (solid)
# and B1 (dashed) for the mover run as a training data center and as a bitcoin
# mine. λ is shown from 20 to 40 $/MWh (ERCOT's scarcity hours reach the
# thousands). The grey line marks t*, the ex-ante peak hour where τ₀ bills the
# investment pool.
print(f"\nFigure 1: week {WEEK} at B0, R and B1 by market and business")
t0 = time.time()
paths = {}
for m, mk in markets.items():
    b0 = mk.clear(scenario, scenario.delta, np.zeros(T), np.zeros(T))
    paths[m, "B0"] = b0
    for b in BUSINESSES:
        theta = types[b][TYPE]
        offer, d_firm = fl.c_sigma(theta, scenario.delta), theta.d_firm(scenario.delta)
        dispatch, _, _, _ = fl.respond(theta, tau, mk, scenario, "exogenous")
        d1, s1 = fl.planner(theta, mk, scenario)
        paths[m, "R", b] = dispatch
        paths[m, "B1", b] = mk.clear(scenario, d1, s1, offer, d_firm)
print(f"time [s]:\t{time.time() - t0:.0f}")

capacity = scenario.capacity.sum(axis=0)
ordc = markets["ercot"].ordc_for(scenario)
reserve_priced = {  # the reserve the market pays for; load above capacity less this and it prices scarcity
    "ercot": markets["ercot"].gamma * scenario.d_sys + ordc.widths[ordc.prices > 0].sum(),
    "pjm": scenario.capacity.max(axis=0) + markets["pjm"].gamma * scenario.d_sys,
}
fig, ax = plt.subplots(3, 2, figsize=(13, 10), sharex=True, sharey="row")
for j, m in enumerate(MARKETS):
    ax[0, j].plot(paths[m, "B0"].lam, color="k", ls=STYLE["B0"], lw=2.2)
    ax[1, j].plot(scenario.delta, color="k", ls=STYLE["B0"], lw=2.2)
    ax[2, j].plot(scenario.d_sys, color="k", ls=STYLE["B0"], lw=2.2)
    ax[2, j].plot(capacity, color="grey", lw=1.2)
    ax[2, j].plot(capacity - reserve_priced[m], color="grey", ls="--", lw=1.2)
    for b in BUSINESSES:
        for path in ("R", "B1"):
            x = paths[m, path, b]
            ax[0, j].plot(x.lam, color=COLOR[b], ls=STYLE[path], lw=0.9, alpha=0.6)
            ax[1, j].plot(x.d, color=COLOR[b], ls=STYLE[path], lw=0.9, alpha=0.6)
    for a in ax[:, j]:
        a.axvline(scenario.peak, color="grey", lw=0.8)
    ax[0, j].set_title(m.upper())
    ax[2, j].set_xlabel(f"hour of week {WEEK}")
ax[0, 0].set_ylim(20, 40)
ax[0, 0].set_ylabel("energy price λ [$/MWh], 20 to 40 shown")
ax[1, 0].set_ylabel("the load's consumption [MW]")
ax[2, 0].set_ylabel("system load at B0 [MW]")
legend = [Line2D([], [], color="k", ls=STYLE["B0"], label="B0 (λ at B0; δ; system load)")]
legend += [Line2D([], [], color=COLOR[b], label=name) for b, name in BUSINESSES.items()]
legend += [Line2D([], [], color="k", ls=STYLE[p], label=p) for p in ("R", "B1")]
legend += [Line2D([], [], color="grey", lw=0.8, label=f"t* = {scenario.peak}, the ex-ante peak hour")]
legend += [Line2D([], [], color="grey", lw=1.2, label="capacity")]
legend += [Line2D([], [], color="grey", ls="--", lw=1.2, label="scarcity line: capacity $-$ the reserve the market pays for (ERCOT: γ d_sys + the curve's width; PJM: the largest unit + γ d_sys)")]
fig.legend(handles=legend, loc="lower center", ncol=3, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(figures / f"figure_1_week{WEEK}.png", dpi=150)
publish(figures / f"figure_1_week{WEEK}.png")

# %%
# The operator's table at the base configuration: every type under each
# business in both markets, the window, exogenous belief. Tables 1 and 2 read from
# it. Under ERCOT the investment pool is zero at this margin (rents pay the
# fleet), so its investment columns are zero; PJM carries the layer.
print(f"\nThe operator's table: market × type × business under tau_0, week {WEEK}")
t0 = time.time()
rows = pl.concat(
    [
        fl.table(types[b], {"tau_0": tau}, list(markets.values()), [scenario]).with_columns(
            pl.lit(b).alias("business")
        )
        for b in BUSINESSES
    ],
    how="vertical_relaxed",
)
first = next(iter(BUSINESSES))
rows = rows.filter(  # the inflexible and emergency rows do not move with the business
    pl.col("type").is_in(SWEPT) | (pl.col("business") == first)
).with_columns(
    pl.when(pl.col("type").is_in(SWEPT)).then(pl.col("business")).otherwise(pl.lit("--")).alias("business"),
    pl.col("type").cast(pl.Enum(["inflexible", *SWEPT, "emergency"])),
    pl.col("market").cast(pl.Enum(list(MARKETS))),
)
print(f"time [s]:\t{time.time() - t0:.0f}")
rows.write_csv(tables / "rows_type_business.csv")

# %%
# Table 1 (RQ1a). Rows: market × type × business, the inflexible left out (its
# row is zero). Columns: the flexibility
# value S^B1 − S^B0, with its share of the load's bill at B0 in parentheses (S^B0
# is negative under PJM, so it is no base); efficiency S^B1 − S^R with its share
# of that value; the load's bill change from B0 to R by layer. The bill change is
# not the welfare change: the price falls on everything the load still buys,
# a transfer from generators, and the bill is priced at B0's λ while the
# system saves the area under a falling marginal cost.
print("\nTable 1: response to tau_0 by market, type and business (RQ1a)")
BILL_CHANGE = {k: k for k in (*fl.LAYERS, "credit")}  # the bill change from B0 to R, by layer
bill_b0_total = pl.sum_horizontal([pl.col(f"bill_b0_{k}") for k in (*fl.LAYERS, "credit")])  # the share's base
FLEXIBILITY = (
    pl.struct(v=pl.col("value_of_flexibility") / K, s=pl.col("value_of_flexibility") / bill_b0_total * 100)
    .map_elements(lambda r: f"{r['v']:,.1f} ({r['s']:.1f}\\%)", return_dtype=pl.String)
    .alias(r"flexibility value [k\$ (\%)]")
)
EFFICIENCY = (
    pl.struct(v=pl.col("efficiency") / K, s=percent("efficiency_share").fill_null(0))
    .map_elements(lambda r: f"{r['v']:,.1f} ({r['s']}\\%)", return_dtype=pl.String)
    .alias(r"efficiency [k\$ (\%)]")
)
table_1 = label(rows.filter(pl.col("type") != "inflexible").sort("market", "type", "business")).select(
    "market",
    "type",
    "business",
    FLEXIBILITY,
    EFFICIENCY,
    *[((pl.col(f"bill_{k}") - pl.col(f"bill_b0_{k}")) / K).alias(name) for k, name in BILL_CHANGE.items()],
)
print(table_1)
fl.tex(table_1, tables / "table_1.tex", digits=1, groups={r"bill change [k\$]": list(BILL_CHANGE.values())})
publish(tables / "table_1.tex")

# %%
# Table 2 (RQ1a, b). Rows: market × type × business, the inflexible left out.
# Column groups: the layers. On reserve and investment: the alignment wedge
# Δᵏ_t = ∂Bᵏ/∂d_t − ∂Cᵏ/∂d_t, charge less cost, over the hours where it is
# nonzero, their count and its mean Δ̄ (positive: the load pays more at the margin
# than it costs); recovery ρᵏ at R; fairness, everyone else's bill at R less at
# B0 (positive: others pay more once the load responds). On energy the wedge and
# the recovery are zero under τ₀ (a marginal charge), so only fairness is shown.
# The headers repeat across the groups; polars wants them unique, so a trailing
# {} tells them apart, and LaTeX prints nothing for it.
print("\nTable 2: alignment, recovery and fairness by market, type, business and layer (RQ1a, b)")
HOURS, MEAN, RHO, FAIRNESS = r"$\#\Delta \neq 0$", r"$\bar\Delta$ [\$/MWh]", r"$\rho$ [k\$]", r"fairness [k\$]"
columns, groups = [], {}
for i, k in enumerate(LAYERS_BILLED):
    tag = "{}" * i
    named = [] if k == "energy" else [
        pl.col(f"alignment_hours_{k}").alias(HOURS + tag),
        pl.col(f"alignment_{k}").cast(pl.Float64).alias(MEAN + tag),
        (pl.col(f"recovery_{k}") / K).alias(RHO + tag),
    ]
    named.append((pl.col(f"fairness_{k}") / K).alias(FAIRNESS + tag))
    columns += named
    groups[k] = [c.meta.output_name() for c in named]
table_2 = label(rows.filter(pl.col("type") != "inflexible").sort("market", "type", "business")).select(
    "market", "type", "business", *columns
)
print(table_2)
fl.tex(table_2, tables / "table_2.tex", digits=1, groups=groups)
publish(tables / "table_2.tex")

# %%
# Load size. The mover at four sizes α in both markets under each business,
# exogenous belief. Each α re-cuts the year so δ + d° stays the data.
print("\nLoad size: alpha × market × business (RQ3)")
t0 = time.time()
grid = []
for alpha in ALPHAS:
    window = fl.windows(T=T, alpha=alpha, reserve_margin=RESERVE_MARGIN)[WEEK]
    tau_alpha = fl.named_tariffs(window)["tau_0"]
    for m, mk in markets.items():
        for b in BUSINESSES:
            theta = types[b][TYPE]
            b1 = fl.planner(theta, mk, window)
            grid.append({"alpha": alpha, "business": b, **fl.summary(theta, tau_alpha, mk, window, "exogenous", b1)})
grid = pl.DataFrame(grid).with_columns(pl.col("market").cast(pl.Enum(list(MARKETS))))
print(f"time [s]:\t{time.time() - t0:.0f}")
grid.write_csv(tables / "rows_alpha.csv")

# %%
# Table 3 (RQ3). Rows: market × α × business, the mover. Columns: the
# flexibility value and efficiency with their shares, as in Table 1; fairness
# by layer. Under ERCOT the response removes the scarcity prices and everyone
# else's energy bill falls by tens of M$, a hundred times the other layers;
# under PJM the investment layer carries the change.
print("\nTable 3: load size against flexibility value, efficiency and fairness (RQ3)")
table_3 = label(grid.sort("market", "alpha", "business")).select(
    "market",
    (pl.col("alpha") * 100).cast(pl.Int64).alias(r"$\alpha$ [\%]"),
    "business",
    FLEXIBILITY,
    EFFICIENCY,
    *[(pl.col(f"fairness_{k}") / K).alias(k) for k in fl.LAYERS],
)
print(table_3)
fl.tex(table_3, tables / "table_3.tex", digits=1, groups={r"fairness [k\$]": list(fl.LAYERS)})
publish(tables / "table_3.tex")
