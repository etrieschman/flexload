# %% [markdown]
# # Results: the reserve constructs and a flexible load
#
# Run cell by cell, or as a script: `uv run python notebooks/results.py`.
# The settings cell says what is run. To drop a construct, a workload, a
# belief or a sensitivity, take it out of its list there; the rows cell then
# skips those runs.
#
# | table | question | rows |
# |---|---|---|
# | 0 | How do the constructs differ before any load responds? | construct, over the baseline year |
# | 1 | What is the load's flexibility worth, and where does the money go? | construct × workload × contract × belief |
# | 2 | Which construct sheds less, at what reserve cost, and does the response help? | the same |
# | 3 | Do the answers hold when one value moves? | sensitivity × construct × workload |
#
# Every construct runs with today's tariff, tau_0. Tables 1 to 3 sum the weeks
# in `WEEKS`. Rows are cached in `notebooks/tables/rows.parquet`: a row already
# there is read, not recomputed. Delete that file after the code changes.
# Tables go to `notebooks/tables` as .csv and as booktabs .tex for `\input`;
# with `FLEXLOAD_OUT` set (in the environment or in `.env` at the repo root)
# each .tex is also copied there.

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
TIGHT = (29, 34, 35, 28)  # the four tightest weeks; 29 holds the year's tightest hour
WEEKS = TIGHT  # the weeks run; tuple(range(52)) is the year, about two seconds per row and week
RESERVE_OFFER = 0.1
CONSTRUCTS = ("ercot", "pjm", "n-1")  # remove one to drop its runs
WORKLOADS = ("training", "inference")
CONTRACTS = {"firm": "mover"}  # the contract and the named type that carries it; add "curtailable": "curtailable" for the curtailable contract
BELIEFS = {"exogenous": False, "consistent": True}  # the belief and whether it is the consistent one; consistent is about a minute per row and week
# The base setting and the sensitivities (report Table 4): alpha is the load's
# size, margin the reserve margin at the year's tightest hour, scale multiplies
# the strike and the penalty, chi and psi set them outright, kappa is the
# load's variability. None keeps the workload's own value. Each sensitivity
# changes one value and repeats the run under the exogenous belief.
BASE = {"alpha": 0.1, "margin": 0.06, "scale": 1.0, "chi": None, "psi": None, "kappa": None}
SENSITIVITIES = {
    "margin": (0.04, 0.10),
    "alpha": (0.05, 0.20),
    "scale": (0.5, 2.0),
    "chi": (3000.0,),  # the spot value of compute, Billimoria and Byers 2026
    "psi": (2000.0,),  # the marginal loss at the band's edge, 2 psi beta, at that value
    "kappa": (0.0, 0.05, 0.10),
}
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
# The environment at a size and a margin: the year in weeks, and each construct
# as a market with its annual investment-layer cost (the fleet's cost less its
# rent on the baseline year, floored at zero; cached on disk).
environments = {}


def environment(alpha: float, margin: float) -> tuple[list, dict]:
    if (alpha, margin) not in environments:
        t0 = time.time()
        weeks = fl.windows(T=T, alpha=alpha, reserve_margin=margin, reserve_offer=RESERVE_OFFER)
        markets = {c: fl.Market(fl.named_ordcs(weeks[0])[c]) for c in CONSTRUCTS}
        markets = {c: replace(mk, C_inv_year=fl.C_inv(mk, weeks)) for c, mk in markets.items()}
        environments[(alpha, margin)] = (weeks, markets)
        print(f"environment alpha {alpha} margin {margin} [s]:\t{time.time() - t0:.0f}")
    return environments[(alpha, margin)]


weeks, markets = environment(BASE["alpha"], BASE["margin"])
fleet = float(np.sum(weeks[0].cost_inv * weeks[0].nameplate))  # the fleet's annual investment cost
largest = float((weeks[0].units @ (weeks[0].nameplate * ~weeks[0].renewable)).max())

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
        edges, prices = fl.steps(mk.ordc, mk.c_shed)
        level = max(mk.ordc.min_contingency, mk.ordc.multiple.max() * largest)
        b0s = fl.baseline(mk, weeks)
        rent = sum(fl.rent(w, b0) for w, b0 in zip(weeks, b0s)) * fl.HOURS_PER_YEAR / sum(w.T for w in weeks)
        held = np.mean([fl.reserve(b0.r, b0.sigma, b0.d, b0.d_firm).value.mean() for b0 in b0s])
        rows.append(
            {
                "construct": c,
                "top price [$/MWh]": float(prices[0]),
                "up to [MW]": level,
                "pays to [MW]": level + float(edges.max()),
                "rent [M$]": rent / M,
                "fleet cost [M$]": fleet / M,
                "left unpaid [M$]": max(fleet - rent, 0.0) / M,
                "hours above $100": int(sum((b0.mu > 100).sum() for b0 in b0s)),
                "hours above $1,000": int(sum((b0.mu > 1000).sum() for b0 in b0s)),
                "reserve held, mean [MW]": float(held),
                "reserve cost [M$]": sum(float(b0.C_res.sum()) for b0 in b0s) / M,
                "shed in dispatch [MWh]": sum(float(b0.s.sum()) for b0 in b0s),
            }
        )
    table_0 = pl.DataFrame(rows)
print("\nTable 0: the constructs on the baseline year")
save(table_0, "table_0", digits=0)

# %%
# The rows: one per setting, construct, workload, contract, belief and week.
# Each is `fl.summary`: B0, the load's response R under its belief, the
# planner's B1, settlement, and realized dispatch over DRAWS draws. The base
# setting runs under every belief; each sensitivity under the exogenous one.
SETTINGS = [(BASE, belief) for belief in BELIEFS] + [({**BASE, k: v}, "exogenous") for k, vs in SENSITIVITIES.items() for v in vs]
KEY = ["construct", "workload", "contract", "belief", "start", "alpha", "margin", "scale", "chi", "psi", "kappa", "reserve_offer", "T", "draws"]
path = tables / "rows.parquet"  # parquet: each row keeps its draws as a list
cached = pl.read_parquet(path) if path.exists() and not REFRESH else None
if cached is not None:  # rows written before a setting existed carry it as null, and match nothing
    cached = cached.with_columns([pl.lit(None).alias(k) for k in KEY if k not in cached.columns])
done = set(cached.select(KEY).iter_rows()) if cached is not None else set()
new = []
t0 = time.time()
for (setting, belief), c, workload, (contract, kind), week in product(SETTINGS, CONSTRUCTS, WORKLOADS, CONTRACTS.items(), WEEKS):
    weeks_, markets_ = environment(setting["alpha"], setting["margin"])
    scenario = weeks_[week]
    tags = {"workload": workload, "contract": contract, "belief": belief, **setting, "reserve_offer": RESERVE_OFFER, "T": T, "draws": DRAWS}
    key = (c, workload, contract, belief, scenario.start, *(tags[k] for k in KEY[5:]))
    if key in done:
        continue
    theta = fl.named_types(T, workload)[kind]
    theta = replace(theta, chi=setting["scale"] * theta.chi, psi=setting["scale"] * theta.psi)
    theta = replace(theta, **{k: setting[k] for k in ("chi", "psi", "kappa") if setting[k] is not None})
    row = fl.summary(theta, fl.named_tariffs(scenario)["tau_0"], markets_[c], scenario, BELIEFS[belief], draws=DRAWS)
    new.append({**row, **tags})
    print(f"{time.time() - t0:5.0f} s\t{c}\t{workload}\t{belief}\t{setting}\tweek {week}", flush=True)
if new:
    cached = pl.concat([x for x in (cached, pl.DataFrame(new)) if x is not None], how="diagonal_relaxed")
    cached.write_parquet(path)
rows = cached.filter(
    pl.col("construct").is_in(CONSTRUCTS)
    & pl.col("workload").is_in(WORKLOADS)
    & pl.col("contract").is_in(list(CONTRACTS))
    & pl.col("belief").is_in(list(BELIEFS))
    & pl.col("start").is_in([weeks[w].start for w in WEEKS])
    & (pl.col("reserve_offer") == RESERVE_OFFER)
    & (pl.col("T") == T)
    & (pl.col("draws") == DRAWS)
)
print(f"rows: {rows.height} ({len(new)} computed, {rows.height - len(new)} read)")
GROUP = ["construct", "workload", "contract", "belief"]
others = pl.sum_horizontal("fairness_energy", "fairness_reserve", "fairness_investment")


def at(rows: pl.DataFrame, setting: dict) -> pl.DataFrame:
    """The rows of one setting; None matches a null, the workload's own value."""
    return rows.filter(pl.all_horizontal(pl.col(k).is_null() if v is None else pl.col(k) == v for k, v in setting.items()))


base = at(rows, BASE)

# %%
# The two tables, for a set of weeks.
def flexibility(rows: pl.DataFrame, group: list[str] = GROUP) -> pl.DataFrame:
    """Table 1. What the load's flexibility is worth and where the money goes,
    the weeks summed, in M$. Flexibility value is S^B1 − S^B0. The tariff loses
    S^B1 − S^R, also as a share of the value. The bill changes are R less B0:
    the load's, and everyone else's. The fleet's rent change is what generators
    earn above fuel and reserve offers at R, less at B0."""
    return rows.group_by(group, maintain_order=True).agg(
        (pl.col("value_of_flexibility").sum() / M).alias("flexibility value"),
        (pl.col("efficiency").sum() / M).alias("tariff loses"),
        pl.when(pl.col("value_of_flexibility").sum() > 0.005 * M)  # blank where the value rounds to zero
        .then(100 * pl.col("efficiency").sum() / pl.col("value_of_flexibility").sum())
        .alias("loses [%]"),
        ((pl.col("bill_total") - pl.col("bill_b0_total")).sum() / M).alias("load's bill"),
        (others.sum() / M).alias("others' bill"),
        (pl.col("rent_b0").sum() / M).alias("rent at B0"),
        ((pl.col("rent") - pl.col("rent_b0")).sum() / M).alias("rent change"),
        pl.col("last_change").max().alias("fixed point, last change [MW]"),
    )


def after_dispatch(rows: pl.DataFrame, group: list[str] = GROUP) -> pl.DataFrame:
    """Table 2. The test after dispatch, at B0 and at R, the weeks summed.
    Reserve cost is the pool μ × reserve bought [M$]. Lowest reserve is the
    tightest hour's [MW]. Shed is over DRAWS draws of trips and the load's own
    variability [MWh]. A simulated run of the weeks is one draw of each week:
    shed is summed over the weeks within a draw, then reported as its mean over
    draws, the mean of the worst 5% of draws, and the worst draw. With every
    week of the year a draw is a simulated year. Realized welfare is S with the
    ORDC's cost replaced by the mean shed at c^shed, which compares constructs
    [M$]. Two trips is the shed if the two thermal units with the most output
    and reserve trip together, in the worst hour [MW]."""
    by_draw = (
        rows.select(*group, "shed_draws_b0", "shed_draws")
        .with_columns(pl.int_ranges(pl.col("shed_draws").list.len()).alias("draw"))
        .explode("shed_draws_b0", "shed_draws", "draw")
        .group_by(*group, "draw", maintain_order=True)
        .agg(pl.col("shed_draws_b0").sum(), pl.col("shed_draws").sum())
    )
    tail = max(DRAWS // 20, 1)
    shed = by_draw.group_by(group, maintain_order=True).agg(
        pl.col("shed_draws_b0").mean().alias("shed, B0"),
        pl.col("shed_draws").mean().alias("shed, R"),
        pl.col("shed_draws_b0").top_k(tail).mean().alias("worst 5%, B0"),
        pl.col("shed_draws").top_k(tail).mean().alias("worst 5%, R"),
        pl.col("shed_draws_b0").max().alias("worst draw, B0"),
        pl.col("shed_draws").max().alias("worst draw, R"),
    )
    held = rows.group_by(group, maintain_order=True).agg(
        (pl.col("reserve_cost_b0").sum() / M).alias("reserve cost, B0"),
        (pl.col("reserve_cost").sum() / M).alias("reserve cost, R"),
        pl.col("reserve_min_b0").min().alias("lowest reserve, B0"),
        pl.col("reserve_min").min().alias("lowest reserve, R"),
        (pl.col("S_realized_b0").sum() / M).alias("realized welfare, B0"),
        (pl.col("S_realized").sum() / M).alias("realized welfare, R"),
        pl.col("worst_2_b0").max().alias("two trips, B0"),
        pl.col("worst_2").max().alias("two trips, R"),
    )
    first = [*group, "reserve cost, B0", "reserve cost, R", "lowest reserve, B0", "lowest reserve, R"]
    return held.join(shed, on=group, how="left").select(*first, *shed.columns[len(group):], pl.exclude(*first, *shed.columns))


# %%
# The tables for the weeks run, and for the four tightest weeks when more were run.
for suffix, some in {"": WEEKS, **({} if set(WEEKS) == set(TIGHT) else {"_tight": TIGHT})}.items():
    part = base.filter(pl.col("start").is_in([weeks[w].start for w in some]))
    span = "the year" if len(some) == len(weeks) else f"weeks {some}"
    print(f"\nTable 1: flexibility and who gets it, {span} [M$]")
    save(flexibility(part), f"table_1{suffix}", digits=2)
    print(f"\nTable 2: the test after dispatch, {span}")
    save(after_dispatch(part), f"table_2{suffix}", digits=1)

# %%
# Table 3. The sensitivities, the base first: one row per value, construct and
# workload, under the exogenous belief; the columns that Tables 1 and 2 turn
# on. Flexibility value, what the tariff loses of it and the rent change are
# Table 1's; reserve cost, shed and realized welfare at R are Table 2's.
parts = []
for k, vs in (("base", (None,)), *SENSITIVITIES.items()):
    for v in vs:
        setting = BASE if v is None else {**BASE, k: v}
        part = at(rows, setting).filter(pl.col("belief") == "exogenous")
        if part.height == 0:
            continue
        group = ["construct", "workload"]
        one = flexibility(part, group).join(after_dispatch(part, group), on=group).select(
            pl.lit(k).alias("varied"),
            pl.lit("" if v is None else f"{v:g}").alias("value"),
            *group,
            "flexibility value",
            "loses [%]",
            "rent change",
            "reserve cost, R",
            "shed, R",
            "worst 5%, R",
            "realized welfare, R",
        )
        parts.append(one)
if parts:
    print(f"\nTable 3: sensitivities, weeks {WEEKS}")
    save(pl.concat(parts), "table_3", digits=2)
