# flexload

Tariff design for price-responsive loads in wholesale electricity markets, as a
two-player game: a system operator commits to a tariff, a flexible load
best-responds under beliefs about how the market clears, dispatch clears on a
single-node RTS-GMLC week, a bill settles, and four metrics are read:
efficiency, alignment, recovery, fairness.

The model is specified in the memo (`wargame_master.tex` in the Overleaf
project); this package transcribes it. Symbols keep their letters, words keep
their words; `CLAUDE.md` holds the notation table and the design decisions.

```python
import flexload as fl

scenario = fl.build_scenario(week=31, alpha=0.05)          # ω and δ from RTS-GMLC
market = fl.Market(reserve="ercot")                         # or "pjm"
tariffs = fl.named_tariffs(scenario)                        # tau_0 ... tau_6
theta = fl.named_types(scenario.T)["mover"]
tau = tariffs["tau_0"]

c_s = fl.c_s(theta, scenario.delta)
base = market.clear(scenario, tau, scenario.delta, np.zeros(scenario.T), c_s)   # B0
C_res, C_inv = market.pools(base, scenario)
d, sigma = fl.best_response(theta, tau, scenario.delta, base.lam, base.mu,
                            C_res, C_inv, scenario.d_other, d_hat=scenario.delta)
dispatch = market.clear(scenario, tau, d, sigma, c_s)
bill = tau.bill(dispatch.d, dispatch.sigma, dispatch.lam, dispatch.mu, C_res, C_inv, scenario.d_other)
```

`notebooks/walkthrough.py` runs this end to end with the planner benchmark and
the metrics. Setup:

```bash
uv sync
uv run pytest -q
```

Data comes from [rts-gmlc](https://github.com/etrieschman/rts-gmlc), fetched
once into `~/.cache/rts_gmlc`.
