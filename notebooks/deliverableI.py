# %% [markdown]
# # Deliverable I: the figures and tables of the Workshop I report (§4)
#
# Every exhibit sits at the base configuration and moves at most two dimensions.
# Base: ERCOT, week 31, α = 5%, training data center, exogenous price-taker, τ₀.
#
# | exhibit | moves | question |
# |---|---|---|
# | Figure 0 | week | the market: the supply stack and the pools by week under B0 |
# | Figure 1 | market, business | week 31: λ and consumption at B0, R and B1 |
# | Table 1 | market, type, business | RQ1a: value of flexibility, efficiency, bill change by layer |
# | Table 2 | market, type, business, layer | RQ1a, b: alignment, recovery at R and B1, fairness |
# | Figure 2 | α, market, business | RQ3a: price error, efficiency share, fairness against load size |
# | Table 3 | α, market | RQ3b: the consistent price-taker's fixed point, training data center |
#
# Beliefs move only in Table 3 (RQ4 is about beliefs). Run as a script,
# `uv run python notebooks/deliverableI.py`, or cell by cell. Figures go to
# `notebooks/figures`, tables to `notebooks/tables` as booktabs for `\input`.

# %%
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
WEEK = 31
ALPHA = 0.05
RESERVE_MARGIN = 0.15
TYPE = "mover"  # the type Figures 1 and 2 and Table 3 follow
BUSINESSES = {"data_center_train": "training DC", "bitcoin_mine": "bitcoin mine"}
MARKETS = ("ercot", "pjm")
ALPHAS = (0.01, 0.05, 0.10, 0.20)
SWEPT = ("mover", "controllable", "curtailable")  # the types whose (ψ, β, A) the business sets
LAYERS_BILLED = ("reserve", "investment")  # energy is at the margin: Δ = 0 by construction
K = 1e3  # dollars per k$
here = Path(__file__).parent if "__file__" in globals() else Path(".")
figures, tables = here / "figures", here / "tables"
figures.mkdir(exist_ok=True)
tables.mkdir(exist_ok=True)
percent = lambda col: (pl.col(col) * 100).round().cast(pl.Int64)  # noqa: E731
COLOR = {"ercot": "C3", "pjm": "C0", "data_center_train": "C1", "bitcoin_mine": "C2"}
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
# by week under B0 in each market, the window's share of the investment pool
# as a flat line, and the week's own missing money (cost share less rents),
# which is why the investment pool is annual.
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
        rents = float((b0_w.nu.sum(axis=1) * w.nameplate).sum())
        share = float((w.cost_inv * T / 8760 * w.nameplate).sum())
        rows.append(
            {
                "week": w.start // T,
                "energy": float(b0_w.C_energy.sum()),
                "reserve": float(b0_w.C_res.sum()),
                "investment": b0_w.C_inv,
                "missing_money": share - rents,
            }
        )
    pools[m] = pl.DataFrame(rows)
print(f"B0 over the year, both markets [s]:\t{time.time() - t0:.0f}")

fig, ax = plt.subplots(1, 3, figsize=(15, 4.5), gridspec_kw={"width_ratios": [1.3, 1, 1]})
colors = [FUEL_COLOR.get(f, "#999999") for f in fuel[order]]
ax[0].bar(left, scenario.cost_gen[order], width=avg_capacity[order], align="edge", color=colors, edgecolor="none")
free = scenario.cost_gen[order] <= 0.0  # zero-cost units: a strip below the axis, so they show
ax[0].bar(left[free], -4.0, width=avg_capacity[order][free], align="edge", color=np.array(colors)[free], edgecolor="none")
ax[0].axhline(0.0, color="k", lw=0.5)
ax[0].axvline(d_sys_year.mean(), color="k", lw=1, label=f"average load {d_sys_year.mean():,.0f} MW")
ax[0].axvline(d_sys_year.max(), color="k", lw=1, ls="--", label=f"peak load {d_sys_year.max():,.0f} MW")
ax[0].set_xlabel("cumulative capacity, average hour [MW]; zero-cost units drawn below the axis")
ax[0].set_ylabel("marginal cost [$/MWh]")
ax[0].set_title("supply stack")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for f, c in FUEL_COLOR.items() if f in set(fuel)]
handles += ax[0].get_legend_handles_labels()[0]
labels = [f for f in FUEL_COLOR if f in set(fuel)] + ax[0].get_legend_handles_labels()[1]
ax[0].legend(handles, labels, fontsize=8, ncol=2)
for a, m in zip(ax[1:], MARKETS):
    p = pools[m]
    a.bar(p["week"], p["energy"] / 1e6, label="energy pool", color="#bbbbbb")
    a.bar(p["week"], p["reserve"] / 1e6, bottom=p["energy"] / 1e6, label="reserve pool", color=COLOR[m])
    a.axhline(markets[m].C_inv * T / 8760 / 1e6, color="k", lw=1, label="investment pool, the window's share")
    a.plot(p["week"], p["missing_money"] / 1e6, color="k", lw=1, ls="--", label="week's own missing money")
    a.axvline(WEEK, color="k", lw=0.5, alpha=0.5)
    a.set_title(f"pools by week under B0, {m.upper()}")
    a.set_xlabel("week of the year")
    a.set_ylabel("M$ per week")
fig.legend(*ax[1].get_legend_handles_labels(), loc="lower center", ncol=4, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(figures / "figure_0_market.png", dpi=150)
print(f"saved:\t{figures / 'figure_0_market.png'}")

# %%
# Figure 1, week 31. Rows: the energy price λ and the load's consumption.
# Columns: the markets. Lines: B0 (dotted, black), R (solid) and B1 (dashed)
# for the mover run as a training data center and as a bitcoin mine.
print("\nFigure 1: week 31 at B0, R and B1 by market and business")
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

fig, ax = plt.subplots(2, 2, figsize=(13, 7), sharex=True, sharey="row")
for j, m in enumerate(MARKETS):
    ax[0, j].plot(paths[m, "B0"].lam, color="k", ls=STYLE["B0"])
    ax[1, j].plot(scenario.delta, color="k", ls=STYLE["B0"])
    for b in BUSINESSES:
        for path in ("R", "B1"):
            x = paths[m, path, b]
            ax[0, j].plot(x.lam, color=COLOR[b], ls=STYLE[path], alpha=0.85)
            ax[1, j].plot(x.d, color=COLOR[b], ls=STYLE[path], alpha=0.85)
    ax[0, j].set_title(m.upper())
    ax[1, j].set_xlabel("hour of week 31")
ax[0, 0].set_ylabel("energy price λ [$/MWh]")
ax[1, 0].set_ylabel("the load's consumption [MW]")
legend = [Line2D([], [], color="k", ls=STYLE["B0"], label="B0 (λ at B0; δ)")]
legend += [Line2D([], [], color=COLOR[b], label=name) for b, name in BUSINESSES.items()]
legend += [Line2D([], [], color="k", ls=STYLE[p], label=p) for p in ("R", "B1")]
ax[0, 1].legend(handles=legend, fontsize=8)
fig.tight_layout()
fig.savefig(figures / f"figure_1_week{WEEK}.png", dpi=150)
print(f"saved:\t{figures / f'figure_1_week{WEEK}.png'}")

# %%
# The operator's table at the base configuration: every type under each
# business in both markets, week 31, exogenous belief. Tables 1 and 2 read from
# it. Under ERCOT the investment pool is zero at this margin (rents pay the
# fleet), so its investment columns are zero; PJM carries the layer.
print("\nThe operator's table: market × type × business under tau_0, week 31")
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
# Table 1 (RQ1a). Rows: market × type × business. Columns: the value of
# flexibility S^B1 − S^B0, efficiency S^B1 − S^R, efficiency as a share of that
# value, and the bill change from B0 to R by layer.
print("\nTable 1: response to tau_0 by market, type and business (RQ1a)")
table_1 = label(rows.sort("market", "type", "business")).select(
    "market",
    "type",
    "business",
    (pl.col("value_of_flexibility") / K).alias(r"$S^{B1} - S^{B0}$ [k\$]"),
    (pl.col("efficiency") / K).alias(r"$S^{B1} - S^{R}$ [k\$]"),
    percent("efficiency_share").alias(r"share [\%]"),
    *[
        ((pl.col(f"bill_{k}") - pl.col(f"bill_b0_{k}")) / K).alias(rf"$\Delta B^{{\rm {s}}}$ [k\$]")
        for k, s in zip((*fl.LAYERS, "credit"), ("energy", "res", "inv", "credit"))
    ],
)
print(table_1)
fl.tex(
    table_1,
    tables / "table_1.tex",
    "Response to $\\tau_0$ by market, type and business, week 31, exogenous price-taker: the value of flexibility, efficiency, and the bill change from B0 to R by layer. ERCOT's investment pool is zero at this margin.",
    "tab:rq1a",
    digits=1,
)

# %%
# Table 2 (RQ1a, b). Rows: market × type × business × layer, reserve and
# investment (energy is at the margin, so its wedge is zero). Columns: the
# alignment wedge Δᵏ_t, its mean over the week's hours, the hours where it is
# nonzero, and its 1st and 99th percentiles over those hours; recovery ρᵏ at R
# and at B1; fairness.
print("\nTable 2: alignment, recovery and fairness by market, type, business and layer (RQ1a, b)")
table_2 = pl.concat(
    [
        label(rows.filter(pl.col("type") != "inflexible").sort("market", "type", "business")).select(
            "market",
            "type",
            "business",
            pl.lit(k).alias("layer"),
            pl.col(f"alignment_{k}").alias(r"mean $\Delta^k_t$ [\$/MWh]"),
            pl.col(f"alignment_hours_{k}").alias(r"hours $\Delta^k_t \neq 0$"),
            pl.col(f"alignment_p1_{k}").alias(r"p1 of those [\$/MWh]"),
            pl.col(f"alignment_p99_{k}").alias(r"p99 of those [\$/MWh]"),
            (pl.col(f"recovery_{k}") / K).alias(r"$\rho^k$ at R [k\$]"),
            (pl.col(f"recovery_b1_{k}") / K).alias(r"$\rho^k$ at B1 [k\$]"),
            (pl.col(f"fairness_{k}") / K).alias(r"fairness [k\$]"),
        )
        for k in LAYERS_BILLED
    ]
).sort("market", "type", "business", "layer")
print(table_2)
fl.tex(
    table_2,
    tables / "table_2.tex",
    "Alignment, recovery and fairness under $\\tau_0$ by market, type, business and layer, week 31, exogenous price-taker. The energy layer is at the margin and omitted; ERCOT's investment pool is zero at this margin.",
    "tab:rq1b",
    digits=1,
)

# %%
# Load size. The mover at four sizes α in both markets under each business,
# exogenous belief; and the consistent price-taker's fixed point for the
# training data center. Each α re-cuts the year so δ + d° stays the data.
print("\nLoad size: alpha × market × business (RQ3)")
t0 = time.time()
grid, cycle = [], []
for alpha in ALPHAS:
    window = fl.windows(T=T, alpha=alpha, reserve_margin=RESERVE_MARGIN)[WEEK]
    tau_alpha = fl.named_tariffs(window)["tau_0"]
    for m, mk in markets.items():
        for b in BUSINESSES:
            theta = types[b][TYPE]
            b1 = fl.planner(theta, mk, window)
            grid.append({"alpha": alpha, "business": b, **fl.summary(theta, tau_alpha, mk, window, "exogenous", b1)})
            if b == first:
                cycle.append({"alpha": alpha, **fl.summary(theta, tau_alpha, mk, window, "consistent", b1)})
grid = pl.DataFrame(grid).with_columns(pl.col("market").cast(pl.Enum(list(MARKETS))))
cycle = pl.DataFrame(cycle).with_columns(pl.col("market").cast(pl.Enum(list(MARKETS))))
print(f"time [s]:\t{time.time() - t0:.0f}")
grid.write_csv(tables / "rows_alpha.csv")
cycle.write_csv(tables / "rows_alpha_consistent.csv")

# %%
# Figure 2 (RQ3a). α against the belief's price error, efficiency S^B1 − S^R,
# and fairness summed over layers. Color: market. Line style: business.
# Efficiency is in k$, not as a share: under PJM the value of flexibility is
# near zero at every α, so the share is in the hundreds and says nothing.
print("\nFigure 2: load size against price error, efficiency share and fairness (RQ3a)")
BUSINESS_STYLE = dict(zip(BUSINESSES, ("-", "--")))
panels = (
    ("price_error", r"mean $|\tilde\lambda_t - \lambda_t|$ [\$/MWh]", 1.0),
    ("efficiency", r"efficiency $S^{B1} - S^R$ [k\$]", K),
    ("fairness_total", r"fairness, all layers [k\$]", K),
)
grid = grid.with_columns(pl.sum_horizontal([pl.col(f"fairness_{k}") for k in fl.LAYERS]).alias("fairness_total"))
fig, ax = plt.subplots(1, 3, figsize=(14, 4))
for a, (col, name, scale) in zip(ax, panels):
    for m in MARKETS:
        for b in BUSINESSES:
            g = grid.filter((pl.col("market") == m) & (pl.col("business") == b)).sort("alpha")
            a.plot(g["alpha"] * 100, g[col] / scale, color=COLOR[m], ls=BUSINESS_STYLE[b], marker="o", ms=3)
    a.set_xlabel(r"load size $\alpha$ [% of system load]")
    a.set_ylabel(name)
    a.set_xticks([x * 100 for x in ALPHAS])
legend = [Line2D([], [], color=COLOR[m], label=m.upper()) for m in MARKETS]
legend += [Line2D([], [], color="k", ls=BUSINESS_STYLE[b], label=n) for b, n in BUSINESSES.items()]
ax[0].legend(handles=legend, fontsize=8)
fig.tight_layout()
fig.savefig(figures / "figure_2_alpha.png", dpi=150)
print(f"saved:\t{figures / 'figure_2_alpha.png'}")

# %%
# Table 3 (RQ3b). Rows: α by market, the training data center. Columns: the
# fixed point's rounds and last change, S^R under each belief, each belief's
# price error. A last change above 1 MW is the cycle of finding 1.
print("\nTable 3: the consistent price-taker by load size and market (RQ3b)")
exogenous = grid.filter(pl.col("business") == first)
table_3 = (
    exogenous.join(cycle, on=["alpha", "market"], suffix="_c")
    .sort("alpha", "market")
    .select(
        percent("alpha").alias(r"$\alpha$ [\%]"),
        "market",
        pl.col("iterations_c").alias("rounds"),
        pl.col("last_change_c").alias("last change [MW]"),
        (pl.col("S_R") / K).alias(r"$S^R$ exogenous [k\$]"),
        (pl.col("S_R_c") / K).alias(r"$S^R$ consistent [k\$]"),
        pl.col("price_error").alias(r"price error, exogenous [\$/MWh]"),
        pl.col("price_error_c").alias(r"price error, consistent [\$/MWh]"),
    )
)
print(table_3)
fl.tex(
    table_3,
    tables / "table_3.tex",
    "Price-taking beliefs by load size and market under $\\tau_0$, training data center: convergence of the fixed point, welfare, and price error.",
    "tab:rq3b",
    digits=1,
)
print(f"figures saved to:\t{figures}")
print(f"tables saved to:\t{tables}")
