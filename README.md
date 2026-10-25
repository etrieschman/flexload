# flexload

Tariff design for price-responsive loads in wholesale electricity markets, as a
two-player game: a system operator commits to a tariff, a flexible load
best-responds under beliefs about how the market clears, dispatch clears on a
single-node RTS-GMLC week, a bill settles, and four metrics are read:
efficiency, alignment, recovery, fairness.

The model is specified in the Workshop I report (`wargame_report.tex` in the
Overleaf project, §3); this package transcribes it. Symbols keep their letters, words keep
their words; `CLAUDE.md` holds the notation table and the design decisions. Four modules: `system` (ω, 𝓜), `tariff` (τ), `load` (θ, R, B1), `metrics`. Every formula is a cvxpy expression; read numbers with `.value`.

```python
from dataclasses import replace

import numpy as np
import flexload as fl

weeks = fl.windows(T=168, alpha=0.05, reserve_margin=0.11)  # ω and δ from RTS-GMLC: the year in operating windows
scenario = weeks[31]
market = fl.Market(reserve="ercot")                          # or "pjm"
market = replace(market, C_inv=fl.C_inv(market, weeks))      # annual investment pool, net of rents, cached
tau = fl.named_tariffs(scenario)["tau_0"]                    # today's tariff
theta = fl.named_types(scenario.T, "data_center_train")["mover"]  # θ₁ as a training data center

offer = fl.c_sigma(theta, scenario.delta)
b0 = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer)        # B0
d, sigma = fl.best_response(theta, tau, scenario, fl.Belief(b0, False), b0)  # R, exogenous price-taker
dispatch = market.clear(scenario, d, sigma, offer)
bill = fl.settle(tau, scenario, dispatch, b0)
```

Setup, tests, the walkthrough and the report's figures and tables:

```bash
uv sync
uv run pytest -q
uv run python notebooks/walkthrough.py     # one window end to end, with the benchmarks and the metrics
uv run python notebooks/deliverableI.py    # Figures 0-2 and Tables 1-3 of the Workshop I report (§4)
```

The first run fetches the data; the walkthrough takes about a minute, the
figures and tables about four. Both also run cell by cell in the `flexload (uv)` kernel.
Set `FLEXLOAD_OUT` in the environment or in `.env` at the repo root to a folder
and `deliverableI.py` also copies each .png and .tex there, flat, for the Overleaf project.

Data comes from [rts-gmlc](https://github.com/etrieschman/rts-gmlc), a git
dependency imported as `rts_gmlc` at the top of `system.py`, fetched once into
`~/.cache/rts_gmlc`. The LP and QP solver is Gurobi (academic license).
