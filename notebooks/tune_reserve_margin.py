# %% [markdown]
# # Tuning the reserve margin
#
# The reserve margin sets how tight the year is. `windows` scales every week's
# load by one factor so that at the year's tightest hour capacity over load is
# 1 + margin; the other weeks keep their seasonal slack. The margin is the
# model's one calibration (report §3, Assumptions): it is set where ERCOT's
# energy and reserve prices pay the fleet's annual investment cost through
# rents, so ERCOT's investment pool is zero and PJM's carries the shortfall.
#
# This notebook sweeps the margin and reports, for each market on the B0 path
# over the year, the fleet's rent (its profit, revenue above fuel and reserve
# offers, scaled to 8,760 hours), its investment cost Σ_j cⁱⁿᵛ_j ū_j on nameplate, the pool
# max(0, cost − rent), the scarcity hours in the year and in week 32, and the
# energy shed. Under ERCOT an hour is scarce when μ_t is on the demand curve,
# above every reserve offer; under PJM when load is shed.
#
# Set 2026-10-25 at 0.08, the tightest margin at which PJM's requirement is
# slack: at 0.07 PJM sheds load. ERCOT's rent there is 1,768 M$, and the
# investment-cost placeholders are round numbers that sum to 1,757 M$, so its
# pool is zero and PJM's is about 1,210 M$. With the costs as they were
# (2,500 M$) ERCOT's rent reached them only near 0.06, with PJM in shortage.
#
# Run as a script, `uv run python notebooks/tune_reserve_margin.py`, or cell by
# cell; about 70 s per market and margin. The table goes to `notebooks/tables`,
# the figure to `notebooks/figures`.

# %%
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

import flexload as fl
from flexload.metrics import rent as fleet_rent

pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_width_chars(200)

# %%
# Settings: the base configuration of the deliverable, and the margins to sweep.
T = 168
WEEK = 32  # the window with the year's tightest hour
ALPHA = 0.05
RESERVE_OFFER = 0.1
MARGINS = (0.12, 0.10, 0.08, 0.07)
MARKETS = ("ercot", "pjm")
M = 1e6  # dollars per M$
here = Path(__file__).parent if "__file__" in globals() else Path(".")
figures, tables = here / "figures", here / "tables"
figures.mkdir(exist_ok=True)
tables.mkdir(exist_ok=True)

# %%
# The sweep: the year at each margin, B0 in each market, one row per market and margin.
print("\nThe fleet's rent against its cost, by margin and market")
rows = []
for margin in MARGINS:
    weeks = fl.windows(T=T, alpha=ALPHA, reserve_margin=margin, reserve_offer=RESERVE_OFFER)
    fleet = float(np.sum(weeks[0].cost_inv * weeks[0].nameplate))
    hours = sum(w.T for w in weeks)
    for m in MARKETS:
        t0 = time.time()
        mk = fl.Market(reserve=m, C_inv=0.0)  # the pool is what this notebook computes
        rent = shed = 0.0
        scarce = {"year": 0, "week": 0}
        for i, w in enumerate(weeks):
            b0 = mk.clear(w, w.delta, np.zeros(T), np.zeros(T))
            rent += fleet_rent(w, b0)  # the fleet's profit: revenue above fuel and reserve offers
            shed += float(b0.shed.sum())
            hot = int(((b0.mu > w.cost_res.max() + 1e-6) if m == "ercot" else (b0.shed > 1e-6)).sum())
            scarce["year"] += hot
            scarce["week"] += hot if i == WEEK else 0
        rows.append(
            {
                "margin": margin,
                "market": m,
                "rent [M$]": rent * 8760 / hours / M,
                "fleet cost [M$]": fleet / M,
                "pool [M$]": max(fleet - rent * 8760 / hours, 0.0) / M,
                "scarcity hours": scarce["year"],
                f"scarcity hours, week {WEEK}": scarce["week"],
                "shed [MWh]": shed,
            }
        )
        print(f"margin {margin:.2f} {m}:\t{time.time() - t0:.0f} s", flush=True)
table = pl.DataFrame(rows)
print(table)
table.write_csv(tables / "tune_reserve_margin.csv")

# %%
# The figure: rent against margin in each market, with the fleet's cost. The
# margin is set where ERCOT's line crosses the cost.
fig, ax = plt.subplots(figsize=(6, 3.5))
for m, color in zip(MARKETS, ("#BF5700", "#1F4E79")):
    t = table.filter(pl.col("market") == m).sort("margin")
    ax.plot(t["margin"] * 100, t["rent [M$]"], marker="o", color=color, label=f"{m.upper()} rent")
ax.axhline(table["fleet cost [M$]"][0], color="k", lw=1, ls="--", label="fleet investment cost")
ax.set_xlabel("reserve margin at the year's tightest hour [%]")
ax.set_ylabel("the year under B0 [M$]")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(figures / "tune_reserve_margin.png", dpi=150)
print(f"saved:\t{figures / 'tune_reserve_margin.png'}")
