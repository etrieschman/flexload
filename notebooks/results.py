# %% [markdown]
# # Results: the reserve constructs and a flexible load
#
# Run cell by cell, or as a script: `uv run python notebooks/results.py`.
# The settings cell says what is run. To drop a construct, a workload or a
# belief, take it out of its list there; the rows cell then skips those runs.
#
# | table | question | rows |
# |---|---|---|
# | 0 | How do the constructs differ before any load responds? | construct, over the baseline year |
# | 1 | What is the load's flexibility worth, and where does the money go? | construct × workload × contract |
# | 2 | Which construct sheds less, at what reserve cost, and does the response help? | the same |
#
# Each construct runs with its market's form of today's tariff. Tables 1 and 2
# sum the weeks in `WEEKS`. Rows are cached in `notebooks/tables/rows.csv`: a
# row already there is read, not recomputed. Set `REFRESH = True` after the
# code changes. Tables go to `notebooks/tables` as .csv and as booktabs .tex
# for `\input`; with `FLEXLOAD_OUT` set (in the environment or in `.env` at
# the repo root) each .tex is also copied there.

# %%
import os
import shutil
import time
from dataclasses import replace
from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

import flexload as fl

pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_width_chars(1000)

# %%
# Settings.
T = 168
WEEKS = (29, 34, 35, 28)  # the four tightest weeks; 29 holds the year's tightest hour
ALPHA = 0.1  # the load's size, its share of system load
RESERVE_MARGIN = 0.06  # where ERCOT's rent pays the fleet (notebooks/tune_reserve_margin.py)
RESERVE_OFFER = 0.1
CONSTRUCTS = ("ercot", "pjm", "n-1")  # remove one to drop its runs
TARIFF = {"ercot": "tau_0_ercot", "pjm": "tau_0_pjm", "n-1": "tau_0_pjm"}  # each construct with its market's tariff
WORKLOADS = ("training", "inference")
CONTRACTS = {"firm": "mover", "curtailable": "curtailable"}  # the contract and the named type that carries it
BELIEFS = ("exogenous",)  # add "consistent": the fixed point, about a minute per row and week
DRAWS = 200  # draws of realized dispatch per window
REFRESH = False  # True recomputes every row and the baseline year
M = 1e6  # dollars per M$

here = Path(__file__).parent if "__file__" in globals() else Path(".")
tables = here / "tables"
tables.mkdir(exist_ok=True)
dotenv = here.parent / ".env"
if dotenv.exists():  # KEY=VALUE lines; the environment wins
    for line in dotenv.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
OUT = Path(os.environ["FLEXLOAD_OUT"]).expanduser() if os.environ.get("FLEXLOAD_OUT") else None


def save(table: pl.DataFrame, name: str, digits: int = 1) -> None:
    """Print a table and write it as .csv and .tex; copy the .tex to FLEXLOAD_OUT, if set."""
    print(table)
    table.write_csv(tables / f"{name}.csv")
    fl.tex(table, tables / f"{name}.tex", digits=digits)
    if OUT is not None:
        OUT.mkdir(parents=True, exist_ok=True)
        shutil.copy(tables / f"{name}.tex", OUT / f"{name}.tex")


# %%
# The environment: the year in weeks, and each construct as a market with its
# annual investment-layer cost (the fleet's cost less its rent on the baseline
# year, floored at zero; cached).
t0 = time.time()
weeks = fl.windows(T=T, alpha=ALPHA, reserve_margin=RESERVE_MARGIN, reserve_offer=RESERVE_OFFER)
markets = {c: fl.Market(fl.named_ordcs(weeks[0])[c]) for c in CONSTRUCTS}
markets = {c: replace(mk, C_inv=fl.C_inv(mk, weeks)) for c, mk in markets.items()}
fleet = float(np.sum(weeks[0].cost_inv * weeks[0].nameplate))  # the fleet's annual investment cost
largest = float((weeks[0].units @ (weeks[0].nameplate * ~weeks[0].renewable)).max())
print(f"setup time [s]:\t{time.time() - t0:.0f}")

# %%
# Table 0. The constructs on the baseline year, the load inflexible: the curve
# each one prices reserve on, the rent it pays the fleet and what that leaves,
# how often reserve is scarce, and what it holds.
path = tables / "table_0.csv"
if path.exists() and not REFRESH and set(pl.read_csv(path)["construct"]) == set(CONSTRUCTS):
    table_0 = pl.read_csv(path)
else:
    rows = []
    for c, mk in markets.items():
        edges, prices = mk.curve()
        level = max(mk.ordc.min_contingency, mk.ordc.units.max() * largest)
        rent = reserve_cost = shed = held = 0.0
        above = {100: 0, 1000: 0}
        for w in weeks:
            b0 = mk.clear(w, w.delta, np.zeros(T), np.zeros(T))
            rent += fl.rent(w, b0)
            reserve_cost += float(b0.C_res.sum())
            shed += float(b0.shed.sum())
            held += float(fl.reserve(b0).mean())
            for price in above:
                above[price] += int((b0.mu > price).sum())
        rent *= fl.HOURS_PER_YEAR / sum(w.T for w in weeks)
        rows.append(
            {
                "construct": c,
                "top price [$/MWh]": float(prices[0]),
                "up to [MW]": level,
                "pays to [MW]": level + float(edges.max()),
                "rent [M$]": rent / M,
                "fleet cost [M$]": fleet / M,
                "left unpaid [M$]": max(fleet - rent, 0.0) / M,
                "hours above $100": above[100],
                "hours above $1,000": above[1000],
                "reserve held, mean [MW]": held / len(weeks),
                "reserve cost [M$]": reserve_cost / M,
                "shed in dispatch [MWh]": shed,
            }
        )
    table_0 = pl.DataFrame(rows)
print("\nTable 0: the constructs on the baseline year")
save(table_0, "table_0", digits=0)

# %%
# The rows: one per construct, workload, contract, belief and week. Each is
# `fl.summary`: B0, the load's response R under its belief, the planner's B1,
# settlement, and realized dispatch over DRAWS draws.
KEY = ["market", "workload", "contract", "belief", "start", "alpha", "margin", "draws"]
path = tables / "rows.csv"
cached = pl.read_csv(path) if path.exists() and not REFRESH else None
done = set(cached.select(KEY).iter_rows()) if cached is not None else set()
new = []
t0 = time.time()
for c, workload, (contract, kind), belief, week in product(CONSTRUCTS, WORKLOADS, CONTRACTS.items(), BELIEFS, WEEKS):
    scenario = weeks[week]
    key = (c, workload, contract, belief, scenario.start, ALPHA, RESERVE_MARGIN, DRAWS)
    if key in done:
        continue
    theta = fl.named_types(T, workload)[kind]
    row = fl.summary(theta, fl.named_tariffs(scenario)[TARIFF[c]], markets[c], scenario, belief, draws=DRAWS)
    new.append({**row, "workload": workload, "contract": contract, "alpha": ALPHA, "margin": RESERVE_MARGIN, "draws": DRAWS})
    print(f"{time.time() - t0:5.0f} s\t{c}\t{workload}\t{contract}\t{belief}\tweek {week}", flush=True)
if new:
    cached = pl.concat([x for x in (cached, pl.DataFrame(new)) if x is not None], how="diagonal_relaxed")
    cached.write_csv(path)
rows = cached.filter(
    pl.col("market").is_in(CONSTRUCTS)
    & pl.col("workload").is_in(WORKLOADS)
    & pl.col("belief").is_in(BELIEFS)
    & pl.col("start").is_in([weeks[w].start for w in WEEKS])
    & (pl.col("alpha") == ALPHA)
    & (pl.col("margin") == RESERVE_MARGIN)
    & (pl.col("draws") == DRAWS)
)
print(f"rows: {rows.height} ({len(new)} computed, {rows.height - len(new)} read)")
GROUP = ["market", "workload", "contract", "belief"]
bill_b0 = pl.sum_horizontal("bill_b0_energy", "bill_b0_reserve", "bill_b0_investment", "bill_b0_credit")
others = pl.sum_horizontal("fairness_energy", "fairness_reserve", "fairness_investment")

# %%
# Table 1. What the load's flexibility is worth and where the money goes, the
# weeks summed, in M$. Flexibility value is S^B1 − S^B0. The tariff loses
# S^B1 − S^R, also as a share of the value. The bill changes are R less B0:
# the load's, and everyone else's. The fleet's rent change is what generators
# earn above fuel and reserve offers at R, less at B0.
table_1 = rows.group_by(GROUP, maintain_order=True).agg(
    (pl.col("value_of_flexibility").sum() / M).alias("flexibility value"),
    (pl.col("efficiency").sum() / M).alias("tariff loses"),
    pl.when(pl.col("value_of_flexibility").sum() > 0.005 * M)  # blank where the value rounds to zero
    .then(100 * pl.col("efficiency").sum() / pl.col("value_of_flexibility").sum())
    .alias("loses [%]"),
    ((pl.col("bill_total") - bill_b0).sum() / M).alias("load's bill"),
    (others.sum() / M).alias("others' bill"),
    (pl.col("rent_b0").sum() / M).alias("rent at B0"),
    ((pl.col("rent") - pl.col("rent_b0")).sum() / M).alias("rent change"),
)
print(f"\nTable 1: flexibility and who gets it, weeks {WEEKS} [M$]")
save(table_1, "table_1", digits=2)

# %%
# Table 2. The test after dispatch, at B0 and at R, the weeks summed. Reserve
# cost is the pool μ × reserve bought [M$]. Lowest reserve is the tightest
# hour's [MW]. Shed is over DRAWS draws of trips, the net-load error and the
# load's own variability [MWh]: its mean, and the mean of the worst 5% of
# draws in the worst week. Two trips is the shed if the two thermal units with
# the most output and reserve trip together, in the worst hour [MW].
table_2 = rows.group_by(GROUP, maintain_order=True).agg(
    (pl.col("reserve_cost_b0").sum() / M).alias("reserve cost, B0"),
    (pl.col("reserve_cost").sum() / M).alias("reserve cost, R"),
    pl.col("reserve_min_b0").min().alias("lowest reserve, B0"),
    pl.col("reserve_min").min().alias("lowest reserve, R"),
    pl.col("shed_b0").sum().alias("shed, B0"),
    pl.col("shed").sum().alias("shed, R"),
    pl.col("shed_tail_b0").max().alias("worst 5%, B0"),
    pl.col("shed_tail").max().alias("worst 5%, R"),
    pl.col("worst_2_b0").max().alias("two trips, B0"),
    pl.col("worst_2").max().alias("two trips, R"),
)
print(f"\nTable 2: the test after dispatch, weeks {WEEKS}")
save(table_2, "table_2", digits=1)
