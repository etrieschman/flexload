# flexload

Tariff design for price-responsive loads in wholesale electricity markets, as a
two-player game: a system operator commits to a tariff, a flexible load
best-responds under beliefs about how the market clears, dispatch clears on a
single-node RTS-GMLC week, a bill settles, and four metrics are read:
efficiency, alignment, recovery, fairness.

The model is specified in the memo (`wargame_master.tex` in the Overleaf
project); this package transcribes it. Symbols keep their letters, words keep
their words; `CLAUDE.md` holds the notation table and the design decisions. Four modules: `system` (ω, 𝓜), `tariff` (τ), `load` (θ, R, B1), `metrics`. Every formula is a cvxpy expression; read numbers with `.value`.

```python
from dataclasses import replace

import numpy as np
import flexload as fl

weeks = fl.periods(T=168, alpha=0.05, reserve_margin=0.10)  # ω and δ, the year in weeks
scenario = weeks[31]
market = fl.Market(reserve="ercot")                          # or "pjm"
market = replace(market, missing_money=fl.missing_money(market, weeks))  # annual Ĉⁱⁿᵛ, cached
tau = fl.named_tariffs(scenario)["tau_0"]                    # today's tariff
theta = fl.named_types(scenario.T)["mover"]                  # a load type

offer = fl.c_s(theta, scenario.delta)
b0 = market.clear(scenario, scenario.delta, np.zeros(scenario.T), offer)   # B0
d, sigma = fl.best_response(theta, tau, scenario, belief=b0)              # R, exogenous price-taker
dispatch = market.clear(scenario, d, sigma, offer)
bill = fl.settle(tau, scenario, dispatch, b0)
```

`notebooks/walkthrough.py` runs this end to end with the planner benchmark and
the metrics. Setup:

```bash
uv sync
uv run pytest -q
```

Data comes from [rts-gmlc](https://github.com/etrieschman/rts-gmlc), a git
dependency imported as `rts_gmlc` at the top of `system.py`, fetched once into
`~/.cache/rts_gmlc`. The LP and QP solver is Gurobi (academic license).
