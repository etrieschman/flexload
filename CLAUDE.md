# flexload — working notes for Claude

Tariff design for price-responsive loads in wholesale electricity markets: the
6.S974 wargame and Erich's flexible-loads research stream after it. **The memo is
the spec**: `~/dev/incubator/flexible_loads/overleaf/6_S974/wargame_master.tex`.
This repo transcribes it: one class per memo object, one function per memo
equation, nothing else. Private repo.

## Rules of engagement (Erich's, 2026-10-13)

- **No code, file edits, repos or commits without an explicit yes in chat** for that
  piece of work. "Feel free" in a planning conversation is not a yes. Propose, list the
  decisions needed, stop.
- Use the memo's terms. Do not invent abstractions (no "PriceView", "Belief class",
  "truth rule"). If a name needs explaining, it is wrong.
- Letters where the memo has a letter, words where it has a word (table below).
- An option exists only if a research question in the memo varies it; an option is an
  enum value or a vector, never a branch in a solver; the memo's base configuration is
  the default. Erich is "very bad at narrowing down" and asked to be held to this.
- No docs for their own sake. The walkthrough notebook is the documentation.

## Notation: memo → code

| memo | code | where |
|---|---|---|
| ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū), δ | `Scenario(delta, d_other, cost_gen, cost_res, cost_inv, capacity, nameplate, unit)` | `scenario.py` |
| α (flexible share), profile, tightness, outages | `build_scenario(week, alpha, profile, reserve_margin, outage_seed)` | `scenario.py` |
| PJM / ERCOT, γ, cⱽᴼᴸᴸ, short/long run | `Market(reserve, gamma, voll, long_run, ordc)` | `market.py` |
| 𝓜_ω(d, σ) | `market.clear(scenario, tariff, d, sigma, c_s) -> Dispatch` | `market.py` |
| (dᶜᵘʳᵗ, σᶜˡʳ, u, r, λ, μ, ν, η) | `Dispatch(d, sigma, u, r, lam, mu, nu, eta, ...)` | `market.py` |
| Cʳᵉˢₜ, Ĉⁱⁿᵛ (pools) | `market.pools(dispatch, scenario) -> (C_res, C_inv)` | `market.py` |
| C_sys | `market.C_sys(dispatch, scenario)`; same assembly as the LP objective (`system_cost`) | `market.py` |
| κₜ | `market.kappa(dispatch)` | `market.py` |
| θ = (ψ, β, A, p), sells reserve | `LoadType(psi, beta, A, p, sells_reserve)`; 𝒦ʳᵉˢᵖ deferred | `load.py` |
| cˢₜ = 2pψβδₜ | `c_s(theta, delta)` | `load.py` |
| V(d, σ) = −ψ‖d−δ‖² − cˢᵀσᶜˡʳ | `V(theta, delta, d, sigma)` | `load.py` |
| 𝒟_θ | `feasible(theta, delta, d, sigma)` | `load.py` |
| R, price-taker (QP) | `best_response(theta, tariff, delta, lam, mu, C_res, C_inv, d_other, d_hat, curtailed)` | `load.py` |
| consistent price-taker | `fixed_point(theta, tariff, market, scenario)` | `load.py` |
| B1 | `planner(theta, market, scenario) -> (d, sigma, S_star)` | `load.py` |
| B0 | `market.clear(scenario, tau, delta, zeros, c_s)`; no function | — |
| τ: three charge forms + curtailment | `Tariff(energy, reserve, investment, curtail)`; `marginal(w)`, `share(w, ex_ante)`, `two_part(w, ex_ante, phi, T)`, `firm(beta_firm, hours, exempt_reserve)` | `tariff.py` |
| window 𝒲 | a weight vector `w` over hours: `hourly(T)`, `all_hours(T)`, `peak_hour(d_sys)`; the load's belief about an uncertain peak is a probability vector in the same slot | `tariff.py` |
| B = Σₖ Φᵏ | `tariff.bill(d, sigma, lam, mu, C_res, C_inv, d_other, d_hat) -> {energy, reserve, investment, credit}` | `tariff.py` |
| ∂Φᵏ/∂dₜ | `tariff.marginal(...)` | `tariff.py` |
| τ₀…τ₆, menu | `named_tariffs(scenario)`; `Menu(options)` | `tariff.py` |
| S, ρᵏ, Δᵏₜ, fairness | `S`, `recovery`, `alignment`, `fairness`, `summary` | `metrics.py` |
| settlement (which dispatch feeds which pool) | `settle(tariff, market, scenario, realized, ex_ante)` | `metrics.py` |
| repeated weeks, learning | `simulate(theta, tariff, market, scenarios, learner)`; `Belief`, `Static`, `PriceAveraging`, `PeakCounts` | `simulate.py` |
| operator | `evaluate(tariffs, types, market, scenarios) -> table`; `choose(table, rule)` | `operator.py` |

Conventions: capitalized = class holding data; lowercase = function; order is always
(d, σ); tildes and hats live on the container, not the field (`dispatch.lam` is λ,
the belief's constants are the arguments of `best_response`).

## Locked design (settled 2026-10-13 over a long planning pass; do not relitigate)

| topic | decision |
|---|---|
| accounting | cˢᵀσ sits in V **and** in the LP objective (the load offers at cost). Welfare counts it once: `S = V − C_sys + cˢᵀσ`. The reserve payment μᵀσ is a **credit layer of the bill**; the load's payoff is V − bill. |
| the tariff is a function | three charge forms (`marginal`, `share`, `two_part`), one per layer, plus a curtailment rule. Energy is a full member (`marginal`). No enums, no strings: windows are vectors, `ex_ante` is a bool, φ and T are computed from the pool unless `T` is given. |
| what the bill reads | explicit arguments (λ, μ, Cʳᵉˢ, Cⁱⁿᵛ, d°), never dispatches. The caller computes pools with `market.pools` from the dispatch each layer's `ex_ante` names (`metrics.settle` does this). Inside the load's objective the same arguments are its belief. The bill is plain arithmetic over numpy or cvxpy (`_expr.py`), which is the setup for the price-setter. |
| rate-taker | a price-taker takes each cost-share layer's **average rate** as given at `d_hat` (δ exogenous; previous iterate consistent). C·x/(x̂+x∘) is linear in x, so the best response is a QP. At settlement x̂ = x and the share form is exact. Needs one sentence in the memo. |
| beliefs | no belief class in the core. A price-taker's belief is the constants passed to `best_response`; a price-setter's belief is the market itself (bilevel, not built). `simulate.Belief` exists only as the learner's state. |
| clearing | `clear` takes the tariff (dᶠⁱʳᵐ is a tariff slot). Constraints and objective are assembled once (`constraints`, `system_cost`) and shared by `clear`, `C_sys` and `planner`. Net reserve X is its own variable so per-unit rows stay sparse. |
| scenario knobs | carve-out α; δ profile system (default) or area; **no flat option** until an RQ needs it; tightness by `reserve_margin` at the tightest hour, scaling load not capacity. |
| repos | data from `rts-gmlc` (github.com/etrieschman/rts-gmlc, public, data only); never re-add a fetcher here. Tariff catalog lives in `docs/catalog/`. |
| parameter objects | frozen dataclasses throughout for now (arrays inside parameter objects); pydantic when a YAML config layer arrives with the experiment grids. |

## Layout

```
src/flexload/
  _expr.py      numpy-or-cvxpy arithmetic (sum_, mul, dot, sum_squares, where)
  scenario.py   Scenario; build_scenario from rts_gmlc; with_reserve_margin; reserve_margin
  market.py     DemandCurve, Dispatch, Market (system_cost, constraints, clear, C_sys, pools, kappa, marginal_cost_by_layer)
  tariff.py     windows; Marginal/Share/TwoPart (+ lowercase constructors); Firm; Tariff; Menu; total; named_tariffs
  load.py       LoadType; windows_*; named_types; c_s; V; feasible; best_response; fixed_point; planner
  metrics.py    pools_for; settle; S; recovery; alignment; fairness; summary
  simulate.py   Belief; Observation; learners; simulate
  operator.py   respond; evaluate; choose
notebooks/walkthrough.py   jupytext cells; the documentation
tests/          conftest (3-generator, 4-hour scenario); test_market, test_tariff, test_load
docs/           assumptions.md (every non-memo choice), plan.md (the planning record), catalog/
```

## Status (2026-10-13)

- 31 tests pass. On RTS-GMLC week 31 at `reserve_margin=0.10`: scenario 0.7 s, clearing
  3–4 s per market, planner 4–8 s, best response 0.02 s, fixed point ≈ 3.5 s per iteration.
- Built: both reserve constructs, short and long run, curtailment (τ₅) and the exempt
  menu (τ₆), all three charge forms, ex-ante and realized bases, the price-taker QP,
  the consistent fixed point, the planner, the four metrics, the weekly loop with two
  learners, the operator table and three choice rules.
- Not built: the price-setter (bilevel); 𝒦ʳᵉˢᵖ (a filter over bill layers); experiment
  grids over 52 weeks and seeds; figures beyond the walkthrough's one.

### Findings from the first run (worth the memo's attention)

1. **ERCOT fixed point cycles** at scarcity hours: the load leaves them, scarcity
   vanishes, the load returns. Harmonic damping averages it; `history[-1]` reports
   whether it settled. This is RQ3(b) showing up on day one.
2. **Weekly missing money is negative in a peak week** (rents in 32 scarcity hours
   exceed the weekly share of annual investment cost). The pool, and so the investment
   layer, needs the memo's proration decision.
3. **PJM's margin band is narrow**: with the largest unit at ~4% of load and γ = 3%,
   the requirement is slack above ~7% margin and clearing is infeasible below it
   (other load cannot be shed). The tightness sweep under PJM needs either load
   shedding at VOLL for all load or unit derating.
4. Under ERCOT, `C_sys` includes −Σ∫π, which is large and negative when reserve is
   free; regret is a difference, so it cancels there, but absolute welfare numbers
   under ERCOT are not comparable to PJM's.
5. **Regret can be negative under τ₅/τ₆.** Curtailable headroom counts toward the
   reserve requirement unpaid, and the planner is "evaluated with dᶠⁱʳᵐ = d", so a
   curtailable load has a reserve resource the planner does not. Either give the
   planner the headroom instrument or read regret under τ₅/τ₆ against that caveat.
6. The fixed point under scarcity: `damping=0.5` (default) converges in ~17 steps on
   PJM but cycles on ERCOT; `damping=None` (harmonic) settles ERCOT to ~1 MW in 20
   steps at 3.5 s each.

## Next steps, in order

1. Decisions from Erich (below), then the memo sentences they imply.
2. `experiments/`: config grids for RQ1–RQ3 over 52 weeks and outage seeds; cache by
   config hash; the figure list. pydantic configs arrive here.
3. Price-setter: embed `market.constraints` as KKT conditions in the load's problem
   (regime enumeration first, hour-wise under linear costs, coupled through A).
4. 𝒦ʳᵉˢᵖ as a filter over the bill's layers in `best_response`.
5. Replace placeholders: investment costs (#1), ORDC from LOLP (#3), named-type values (#16).
6. Operator learning slot (`Operator.update`) only when a study needs it.

## Decisions needed from Erich

1. Missing-money proration: weekly (current, negative in peak weeks), annual spread
   evenly, or annual allocated to scarcity weeks.
2. PJM tightness: allow shedding of other load at VOLL (one more LP term) or sweep by
   derating capacity instead of scaling load.
3. ORDC: keep the placeholder shape until an LOLP curve is built, or build it now.
4. Named-type parameter values (ψ, β, p) and β_firm.
5. The rate-taker sentence and the V(d, σ) argument in the memo.
6. Whether the planner (B1) gets the curtailment headroom instrument (finding 5).
