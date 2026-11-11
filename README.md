# flexload

A game between a system operator and one large flexible load in a wholesale
electricity market. The operator's reserve construct prices reserve. The load
bids against today's tariff. Dispatch clears on a single-node RTS-GMLC week,
the bill settles, and then the imbalance realizes: units trip, net load moves
within the hour, and reserve covers it or load is shed.

The model is specified in the Workshop I report (`wargame_workshopI.tex` in the
Overleaf project, §3), and this package transcribes it. Symbols keep their
letters and words keep their words. `CLAUDE.md` holds the notation table, the
design decisions and the to-do list. `docs/assumptions.md` lists each modeling
assumption and its gap with reality.

Five modules, each importing only the ones before it: `system` (the scenario,
the reserve construct, dispatch), `tariff`, `load` (the type, the best
response, the planner), `realized` (shed after dispatch), `metrics`. Every
formula is a cvxpy expression; read a number with `.value`.

```python
from dataclasses import replace

import numpy as np
import flexload as fl

weeks = fl.windows()                                         # the year in weeks: load at 10% of the system, a 6% margin
scenario = weeks[29]                                         # the week with the year's tightest hour
market = fl.Market(fl.named_ordcs(scenario)["ercot"])        # the reserve construct: "ercot", "pjm" or "n-1"
market = replace(market, C_inv=fl.C_inv(market, weeks))      # the fleet's cost less its rent over the year, cached
tau = fl.named_tariffs(scenario)["tau_0_ercot"]              # today's tariff in ERCOT's form
theta = fl.named_types(scenario.T, "training")["mover"]      # a firm data center running training

offer = fl.c_sigma(theta, scenario.delta)
b0 = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer)        # B0
d, sigma = fl.best_response(theta, tau, scenario, fl.Belief(b0, False), b0)  # R, exogenous price-taker
dispatch = market.clear(scenario, d, sigma, offer)
bill = fl.settle(tau, scenario, dispatch, b0)
mwh = fl.shed(scenario, dispatch, theta, np.random.default_rng(0), 200)      # (draws, T) load shed after dispatch
```

Setup, tests, the walkthrough and the results tables:

```bash
uv sync
uv run pytest -q
uv run python notebooks/walkthrough.py     # one window end to end, with the benchmarks and the metrics
uv run python notebooks/results.py      # the results tables; settings at the top, rows cached in notebooks/tables
```

The first run fetches the data; the walkthrough takes about a minute, the
tables about ten on a first run and seconds once their rows are cached. Both also run cell by cell in the `flexload (uv)` kernel.
Set `FLEXLOAD_OUT` in the environment or in `.env` at the repo root to a folder
and `results.py` also copies each .tex there, flat, for the Overleaf project.

Data comes from [rts-gmlc](https://github.com/etrieschman/rts-gmlc), a git
dependency imported as `rts_gmlc` at the top of `system.py`, fetched once into
`~/.cache/rts_gmlc`. The LP and QP solver is Gurobi (academic license).
