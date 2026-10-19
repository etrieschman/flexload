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
| ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū), δ | `Scenario(delta, d_other, cost_gen, cost_res, cost_inv, capacity, nameplate, unit, names, start)` | `system.py` |
| one period 𝒯, the year, α, tightness | `scenario(start, T, alpha, reserve_margin)`; `periods(T, alpha, reserve_margin)` (one tightness scale for the year); `tighten`; `margin` | `system.py` |
| PJM / ERCOT, γ, cⱽᴼᴸᴸ, short/long run, Ĉⁱⁿᵛ | `Market(reserve, gamma, voll, long_run, ordc, missing_money, solver)` | `system.py` |
| 𝓜_ω(d, σ) | `market.clear(scenario, d, sigma, c_s, d_firm) -> Dispatch` | `system.py` |
| (dᶜᵘʳᵗ, σᶜˡʳ, u, r, λ, μ, ν, η), Cʳᵉˢₜ, Ĉⁱⁿᵛ | `Dispatch(d, sigma, u, r, shed, lam, mu, nu, eta, C_res, C_inv, ...)`; the pools ride on the dispatch | `system.py` |
| Ĉⁱⁿᵛ := Σⱼ(cⁱⁿᵛⱼ − Σₜνⱼₜ)ūⱼ over the year | `missing_money(market, periods)`, annual; `clear` prorates it by T/8760 | `system.py` |
| C_sys, κₜ | `market.C_sys(dispatch, scenario)`, `market.kappa(dispatch)`, `market.marginal_cost(dispatch)` | `system.py` |
| θ = (ψ, β, A, p), sells reserve, curtailable | `LoadType(psi, beta, A, p, sells_reserve, curtailable)`; `windows(T, hours)`; `named_types(T)`; 𝒦ʳᵉˢᵖ deferred | `load.py` |
| dᶠⁱʳᵐ = (1−β)δ for a curtailable type | `theta.d_firm(delta)` (None otherwise) | `load.py` |
| cˢₜ = 2pψβδₜ; V(d, σ); 𝒟_θ | `c_s`, `V`, `feasible` | `load.py` |
| the load's objective under a belief 𝓜̃ | `payoff(theta, tariff, scenario, belief, d, sigma, d_hat, curtailed)`; the belief is a `Dispatch` | `load.py` |
| R, price-taker (QP); menu election | `best_response(theta, tariff, scenario, belief, d_hat, curtailed)`; `elect(theta, menu, ...)` | `load.py` |
| consistent price-taker | `fixed_point(theta, tariff, market, scenario)` | `load.py` |
| B1 | `planner(theta, market, scenario) -> (d, sigma, S_star)` | `load.py` |
| B0 | `market.clear(scenario, delta, zeros, c_s, d_firm)`; no function | — |
| τ: share / two-part per cost-share layer, exemption | `Tariff(reserve, investment, exempt_curtailable)`; `share(w, ex_ante)`, `two_part(w, ex_ante, phi, T)`; energy is always λᵀd | `tariff.py` |
| window 𝒲 | a weight vector `w`: `all_hours(T)`, `peak_hour(d_sys)` | `tariff.py` |
| B = Σₖ Φᵏ, ∂Φᵏ/∂dₜ | `tariff.bill(d, sigma, realized, d_other, ex_ante, d_hat, own)`, `tariff.marginal(...)`; cvxpy expressions, `.value` for numbers | `tariff.py` |
| τ₀…τ₄, τ₆, menu | `named_tariffs(scenario)`; `Menu(options)`; τ₅ became the curtailable type | `tariff.py` |
| settlement, S, ρᵏ, Δᵏₜ, fairness | `settle`, `S`, `recovery`, `alignment`, `fairness` | `metrics.py` |
| R under a belief; one row; the operator's table; choice | `respond(theta, tariff, market, scenario, belief, anticipate)`; `summary`; `table(types, tariffs, markets, scenarios)`; `choose(table, rule)` | `metrics.py` |
| repeated periods, the learned price-taker | `learn(theta, tariff, market, scenarios, eta)` | `metrics.py` |

Conventions: capitalized = class holding data; lowercase = function; order is always
(d, σ). **One number system**: every formula is a cvxpy expression whether its
inputs are numbers or variables; read a number with `.value`. No wrapper layer.

## Locked design (settled 2026-10-13 over a long planning pass; do not relitigate)

| topic | decision |
|---|---|
| accounting | cˢᵀσ sits in V **and** in the LP objective (the load offers at cost). Welfare counts it once: `S = V − C_sys + cˢᵀσ`. The reserve payment μᵀσ is a **credit layer of the bill**; the load's payoff is V − bill. |
| the tariff is a function | two charge forms (`share`, `two_part`), one per cost-share layer, plus the reserve exemption flag. Energy is always λᵀd. No enums, no strings: windows are vectors, `ex_ante` is a bool, φ and T are computed from the pool unless `T` is given. |
| what the bill reads | a `Dispatch` (λ, μ and the pools ride on it) plus d°. Each layer's `ex_ante` flag picks the ex-ante or realized dispatch. Inside the load's objective the dispatch is its belief; a price-setter's belief would be a dispatch whose prices are expressions. Revised 2026-10-19 from "explicit arguments": the nine-argument signatures were the cost. |
| rate-taker | a price-taker takes each cost-share layer's **average rate** as given at `d_hat` (δ exogenous; previous iterate consistent). C·x/(x̂+x∘) is linear in x, so the best response is a QP. At settlement x̂ = x and the share form is exact. Needs one sentence in the memo. |
| beliefs | no belief class. A price-taker's belief is a `Dispatch`; the learner's state (`learn`) is a dispatch with averaged fields; a price-setter's belief is the market itself (bilevel, not built). |
| clearing | `clear` takes dᶠⁱʳᵐ as a vector from the type (`theta.d_firm`), not a tariff. Constraints and objective are assembled once (`constraints`, `system_cost`) and shared by `clear`, `C_sys` and `planner`. Net reserve X is its own variable so per-unit rows stay sparse. |
| curtailment | **a load type**, not a tariff (revised 2026-10-19 by Erich): `LoadType.curtailable` sets dᶠⁱʳᵐ = (1−β)δ in every hour; the LP curtails only where κ > VOLL; unpaid, in exchange for connection. The planner holds the headroom instrument but consumes what it bids. τ₆'s reserve exemption stays a tariff flag. |
| period | T hours from `start`; the week is the default instance, nothing is hard-coded to it. cⁱⁿᵛ is annual on the scenario and prorated by T/8760. |
| solver | Gurobi (academic license) for the LP and the QPs; 3× HiGHS on the clearing. `Market(solver="HIGHS")` and `best_response(..., solver=)` switch. |
| scenario knobs | carve-out α with the system's shape; **no flat or area profile** until an RQ needs it; tightness by `reserve_margin` at the tightest hour, scaling load not capacity; over a year one scale factor (`periods`), so only the annual peak period is at the margin. Outages and reserve offer costs were removed 2026-10-19; restore from git when an RQ needs them. |
| investment pool | annual missing money from the 52-week B0 run, spread evenly (Ĉⁱⁿᵛ/52 every week); decided 2026-10-19. Not weekly (negative in peak weeks), not allocated to scarcity weeks. |
| repos | data from `rts-gmlc` (github.com/etrieschman/rts-gmlc, public, data only); never re-add a fetcher here. Tariff catalog lives in `docs/catalog/`. |
| parameter objects | frozen dataclasses throughout for now (arrays inside parameter objects); pydantic when a YAML config layer arrives with the experiment grids. |

## Layout

```
src/flexload/
  system.py   Scenario; scenario, periods, tighten, margin; DemandCurve; Dispatch; Market (system_cost, constraints, clear, C_sys, kappa, marginal_cost); missing_money
  tariff.py   all_hours, peak_hour; Share, TwoPart (+ share, two_part); Tariff (bill, marginal); Menu; total; named_tariffs
  load.py     LoadType; windows; named_types; c_s; V; feasible; payoff; best_response; elect; fixed_point; planner
  metrics.py  settle; S; recovery; alignment; fairness; respond; summary; table; choose; learn
notebooks/walkthrough.py   jupytext cells; the documentation
tests/        conftest (3-generator, 4-hour scenario); test_system, test_tariff, test_load
docs/         assumptions.md (every non-memo choice, one line each), catalog/
```

Imports run one way: system ← tariff ← load ← metrics. 911 lines (2026-10-19), down from 1,742.

## Status (2026-10-19)

- 35 tests pass. Refactored 2026-10-19 at Erich's request (unreadable, overengineered):
  four files, one number system, the bill reads a dispatch, curtailment is a type,
  period not week, Gurobi. With Gurobi: clearing ≈ 1.3 s, planner ≈ 2–3 s.
- Built: both reserve constructs, short and long run, curtailment (τ₅) and the exempt
  menu (τ₆), all three charge forms, ex-ante and realized bases, the price-taker QP,
  the consistent fixed point, the planner, the four metrics, the weekly loop with two
  learners, the operator table and three choice rules.
- Not built: the price-setter (bilevel); 𝒦ʳᵉˢᵖ (a filter over bill layers); experiment
  grids over 52 weeks and seeds; figures beyond the walkthrough's one.

### Findings from the first run (worth the memo's attention)

1. **The consistent price-taker cycles under ERCOT.** The load leaves the 32 scarcity
   hours, scarcity vanishes, prices fall, the load returns. The map from prices to
   response to prices has no fixed point in pure strategies when the load's tolerance
   band straddles a merit-order step at the peak, which is the memo's own condition
   for price-taking to stop being exact (Section "Load's beliefs"): the load is large
   enough to change the marginal unit. `fixed_point(damping=None)` averages the
   iteration and `history` shows whether it settled. Erich (2026-10-13): nothing wrong
   with the cycle; it is the point of RQ3(b).
2. **Resolved 2026-10-19: the investment pool is annual.** Weekly missing money went
   negative in the peak week (rents ≈$195M against a ≈$16M weekly cost share, pool
   −$178M), so under every tariff with an investment layer, τ₀ included, the layer
   paid the load to consume at the peak. Now Ĉⁱⁿᵛ comes from a 52-week B0 run under
   one tightness scale and is spread evenly. Allocation to scarcity weeks stays an
   option for a later RQ.
3. **Resolved: other load now sheds at VOLL** (`Dispatch.shed`, in `C_sys`). Before
   this, PJM's hard requirement was slack above ~7% margin and infeasible below, so
   the tightness sweep had no room. Now λ and μ reach VOLL in shortage hours in both
   markets.
4. Under ERCOT, `C_sys` includes −Σ∫π, which is large and negative when reserve is
   free; regret is a difference, so it cancels there, but absolute welfare numbers
   under ERCOT are not comparable to PJM's.
5. **Resolved: B1 holds the tariff's curtailment instrument.** `planner(theta, market,
   scenario, tariff)` may serve dᶜᵘʳᵗ between the firm level and the bid in the
   curtailable hours with the headroom counting toward reserve, so regret under τ₅/τ₆
   is against a planner with the same constraints (Erich's reading of B1: "under a
   given tariff"). `evaluate` does this per elected tariff.
6. The fixed point: `damping=0.5` (default) converges in ~17 steps on PJM; under
   scarcity use `damping=None` (harmonic), ~1 MW in 20 steps at 3.5 s each.
7. Week 31, ERCOT, exogenous price-taker: τ₄ (two-part investment) wins both choice
   rules for the mover; the menu τ₆ wins for the mover and loses for the CLR, which
   must give up reserve sales to elect the curtailable option.

## Next steps, in order

1. Decisions from Erich (below), then the memo sentences they imply (now also: Ĉⁱⁿᵛ is
   annual on the B0 path, prorated 1/52; tightness is set at the annual peak).
2. `experiments/`: config grids for RQ1–RQ3 over 52 weeks and outage seeds; cache by
   config hash; the figure list. pydantic configs arrive here.
3. Price-setter: embed `market.constraints` as KKT conditions in the load's problem
   (regime enumeration first, hour-wise under linear costs, coupled through A).
4. 𝒦ʳᵉˢᵖ as a filter over the bill's layers in `best_response`.
5. Replace placeholders: investment costs (#1), ORDC from LOLP (#3), named-type values (#16).
6. Operator learning slot (`Operator.update`) only when a study needs it.
7. Rewrite finding 1 as a proposition in the memo: the fixed point exists iff the tolerance band lies within one merit-order step at every hour it binds.

## Decisions needed from Erich

1. **Investment pool proration** (finding 2): weekly, annual spread evenly, or annual
   allocated to scarcity weeks. Recommendation: annual from a 52-week B0 run, spread evenly.
2. Placeholders to replace before the paper: investment costs by category, the ORDC
   shape (from LOLP), named-type values (ψ, β, p), β_firm. Fine for Workshop 1.
3. Two memo sentences: the rate-taker reading of the price-taker, and V(d, σ) with the
   reserve payment as a bill credit.
